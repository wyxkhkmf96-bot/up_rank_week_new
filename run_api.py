"""
Step 2: UP内容总结（增量版）

判断重跑条件（满足任一即重跑）：
1. 该 UP 在旧 up_summaries.json 中不存在（新UP）
2. 本周新上榜（上榜次数 == 1）且稿件输入指纹（标题+分区+tag+asr_data）与上次不同
3. 本周新上榜（上榜次数 == 1）且上次结果是错误状态（[API错误] / [异常]）
4. 命令行带 --force 参数：全量重跑

连续在榜的UP（上榜次数 > 1），即使稿件变动也不跑LLM，直接复用旧结果。

JSON 格式：
{
  "_meta": {"prompt_version": "v1", "updated_at": "..."},
  "summaries": {
    "up_id": {"summary": "...", "input_hash": "abc..."},
    ...
  }
}
"""
import json
import requests
import time
import os
import sys
import hashlib
from collections import defaultdict
from datetime import datetime

BASE = r'C:\Users\dengyuting02\WorkBuddy\20260514140206'
LOG_FILE = os.path.join(BASE, 'api_run.log')
JSON_OUT = os.path.join(BASE, 'up_summaries.json')
UP_RANK = os.path.join(BASE, 'result_code1_up_rank.json')
ARCH = os.path.join(BASE, 'result_code3_arch_charge.json')

PROMPT_VERSION = 'v1'
FORCE = '--force' in sys.argv

class Tee:
    def __init__(self, path):
        self.file = open(path, 'w', encoding='utf-8')
        self.stdout = sys.stdout
        sys.stdout = self
    def write(self, s):
        self.file.write(s)
        self.stdout.write(s)
        self.file.flush()
    def flush(self):
        self.file.flush()

Tee(LOG_FILE)

PROMPT_BASE = '''你是B站内容分析师。请根据以下该UP主的视频数据，写一段120字以内的内容总结。

## 输入数据
- UP主昵称：{up_name}
- 近30日发布充电视频数量：{vid_cnt}部
- 视频列表（标题、类型、Tag标签、asr_data）：

{video_list}

## 输出要求
1. 总结视频主题分类（归纳共同主题，不要罗列标签）
2. 突出内容特色或风格
3. 如有多个主题，分点说明。突出核心主题，尽量精简，删掉重复或高度相似的描述，总数不超过3个主题。
4. 语气自然，像运营人员在描述该UP的内容定位
5. 不要出现"根据数据""通过分析"等生硬表述

## 输出格式
直接输出总结文案，不要加标题或前缀。

## 示例输出
①古装家庭伦理剧情向剪辑，聚焦传统家族中长辈对晚辈的教育训诫场景；②着重呈现父子（舅甥）之间因违规行为引发的严厉管教过程'''


def compute_up_hash(up_name, videos):
    """对 UP 的输入数据计算指纹（稿件按 avid 排序后拼接关键字段）"""
    sig_parts = [up_name, str(len(videos))]
    sorted_videos = sorted(videos, key=lambda v: str(v.get('稿件ID', '')))
    for v in sorted_videos:
        title = str(v.get('稿件标题') or '')
        tag = str(v.get('tag') or '')
        asr = str(v.get('asr_data') or '')[:300]
        tid = str(v.get('一级分区') or '')
        sub = str(v.get('二级分区') or '')
        sig_parts.append(f'{title}|{tid}/{sub}|{tag}|{asr}')
    sig = '\n'.join(sig_parts)
    return hashlib.sha1(sig.encode('utf-8')).hexdigest()[:16]


def call_api(up_name, videos):
    video_list = []
    for v in videos:
        title = str(v.get('稿件标题') or '无标题')
        tag = str(v.get('tag') or '')
        asr = str(v.get('asr_data') or '')
        tid = str(v.get('一级分区') or '')
        sub = str(v.get('二级分区') or '')
        asr_short = asr[:300] + '...' if len(asr) > 300 else asr
        video_list.append(f'{title} | {tid}/{sub} | {tag} | {asr_short}')
    video_str = '\n'.join(video_list)
    prompt = PROMPT_BASE.format(up_name=up_name, vid_cnt=len(videos), video_list=video_str)
    try:
        resp = requests.post(
            'http://bxk.bilibili.co/api/bxk/private_chat',
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            json={'kid': '1081', 'query': prompt, 'chat_mod': 'bot'},
            timeout=60,
        )
        obj = resp.json()
        if obj.get('code') == 0:
            data = obj.get('data', {})
            answer = data.get('answer', '') if isinstance(data, dict) else ''
            if answer:
                return answer.strip()
        return f'[API错误] code={obj.get("code")} msg={obj.get("msg")}'
    except Exception as e:
        return f'[异常] {e}'


def load_old():
    """加载旧的 up_summaries.json，兼容旧版（裸 dict）和新版（{summaries: {...}}）"""
    if not os.path.exists(JSON_OUT):
        return {}, {}
    try:
        with open(JSON_OUT, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return {}, {}
    if isinstance(d, dict) and 'summaries' in d:
        meta = d.get('_meta', {})
        return d['summaries'], meta
    # 旧版：直接是 {up_id: text}
    return {uid: {'summary': v, 'input_hash': ''} for uid, v in d.items()}, {}


def save(summaries):
    out = {
        '_meta': {
            'prompt_version': PROMPT_VERSION,
            'updated_at': datetime.now().isoformat(timespec='seconds'),
            'count': len(summaries),
        },
        'summaries': summaries,
    }
    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def main():
    with open(UP_RANK, 'r', encoding='utf-8') as f:
        up_rows = json.load(f)['data']['result']
    with open(ARCH, 'r', encoding='utf-8') as f:
        arch_rows = json.load(f)['data']['result']

    up_name_map = {str(r['up_id']): r['up名'] for r in up_rows}
    up_ids = [str(r['up_id']) for r in up_rows]
    up_id_set = set(up_ids)
    print(f'新星UP数: {len(up_ids)}, 稿件表总记录: {len(arch_rows)}')

    # 只保留新星UP的稿件，黑马UP不需要内容总结
    videos_by_up = defaultdict(list)
    for r in arch_rows:
        uid = str(r['UP主ID'])
        if uid in up_id_set:
            videos_by_up[uid].append(r)
    skipped = len(arch_rows) - sum(len(v) for v in videos_by_up.values())
    if skipped:
        print(f'过滤黑马UP稿件: {skipped} 条（仅新星UP参与hash计算和API调用）')

    old_summaries, old_meta = load_old()
    old_prompt_ver = old_meta.get('prompt_version', '')

    if FORCE:
        print('--force 模式：强制全量重跑')
        old_summaries = {}
    elif old_prompt_ver and old_prompt_ver != PROMPT_VERSION:
        print(f'prompt_version 升级 ({old_prompt_ver} → {PROMPT_VERSION})，全量重跑')
        old_summaries = {}
    else:
        print(f'增量模式：旧结果 {len(old_summaries)} 条')

    # 移除已不在最新榜单中的 UP（避免无效残留）
    new_summaries = {uid: old_summaries[uid] for uid in up_ids if uid in old_summaries}
    removed = len(old_summaries) - len(new_summaries)
    if removed > 0:
        print(f'清理旧 UP（已不在最新榜单）: {removed} 条')

    # 构建 {up_id: 上榜次数} 映射，用于判断本周是否新上榜
    board_count_map = {str(r['up_id']): r.get('上榜次数', 1) for r in up_rows}

    # 判断每个 UP 是否需要重跑
    # 策略：只有「旧结果完全不存在」的全新UP才跑LLM；
    #       其余一切情况（连续在榜、新上榜但已有旧结果、稿件变动、上次错误）全部复用。
    todo = []
    reuse = 0
    for uid in up_ids:
        up_name = up_name_map.get(uid, uid)
        videos = videos_by_up.get(uid, [])
        new_hash = compute_up_hash(up_name, videos) if videos else 'no_videos'

        old = new_summaries.get(uid)
        if old is None:
            todo.append((uid, '新UP'))
            continue

        # 旧结果存在，无论什么状态都直接复用（不再因稿件变动/错误/上榜次数而重跑）
        reuse += 1

    print(f'\n复用 {reuse} 条（含连续在榜跳过），待重跑 {len(todo)} 条')
    if not todo:
        save(new_summaries)
        print(f'\n无需调用API，已保存: {JSON_OUT}')
        return

    # 按原因分类显示
    by_reason = defaultdict(int)
    for _, reason in todo:
        by_reason[reason] += 1
    for reason, n in by_reason.items():
        print(f'  · {reason}: {n} 条')
    print()

    error_count = 0
    for i, (uid, reason) in enumerate(todo):
        up_name = up_name_map.get(uid, uid)
        videos = videos_by_up.get(uid, [])
        new_hash = compute_up_hash(up_name, videos) if videos else 'no_videos'
        if not videos:
            new_summaries[uid] = {'summary': '暂无稿件内容信息', 'input_hash': new_hash}
            print(f'  [{i+1}/{len(todo)}] UP{uid} {up_name} ({reason}): 无稿件')
        else:
            result = call_api(up_name, videos)
            new_summaries[uid] = {'summary': result, 'input_hash': new_hash}
            has_err = result.startswith('[API') or result.startswith('[异常')
            if has_err:
                error_count += 1
            status = '✗' if has_err else '✓'
            print(f'  [{i+1}/{len(todo)}] {status} UP{uid} {up_name} ({reason}): {result[:80]}')

        if (i + 1) % 10 == 0 or i + 1 == len(todo):
            save(new_summaries)
        time.sleep(0.4)

    save(new_summaries)
    print(f'\n完成！共{len(new_summaries)}个UP（重跑{len(todo)}，错误{error_count}），JSON已保存: {JSON_OUT}')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'脚本异常: {e}')
        import traceback
        traceback.print_exc()
