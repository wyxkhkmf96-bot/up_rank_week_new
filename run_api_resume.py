"""
LLM补跑脚本 - 只跑up_summaries.json中缺失的UP
超时15秒，避免卡住
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
JSON_OUT = os.path.join(BASE, 'up_summaries.json')
UP_RANK = os.path.join(BASE, 'result_code1_up_rank.json')
ARCH = os.path.join(BASE, 'result_code3_arch_charge.json')

PROMPT_VERSION = 'v1'

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
            timeout=15,  # 缩短超时，避免卡住
        )
        obj = resp.json()
        if obj.get('code') == 0:
            data = obj.get('data', {})
            answer = data.get('answer', '') if isinstance(data, dict) else ''
            if answer:
                return answer.strip()
        return f'[API错误] code={obj.get("code")} msg={obj.get("msg")}'
    except requests.exceptions.Timeout:
        return '[超时跳过] API请求超过15秒'
    except Exception as e:
        return f'[异常] {e}'


def main():
    with open(UP_RANK, 'r', encoding='utf-8') as f:
        up_rows = json.load(f)['data']['result']
    with open(ARCH, 'r', encoding='utf-8') as f:
        arch_rows = json.load(f)['data']['result']

    up_name_map = {str(r['up_id']): r['up名'] for r in up_rows}
    up_ids = [str(r['up_id']) for r in up_rows]
    up_id_set = set(up_ids)

    # 加载现有summaries
    with open(JSON_OUT, 'r', encoding='utf-8') as f:
        d = json.load(f)
    summaries = d['summaries']

    # 只保留新星UP的稿件
    videos_by_up = defaultdict(list)
    for r in arch_rows:
        uid = str(r['UP主ID'])
        if uid in up_id_set:
            videos_by_up[uid].append(r)

    # 找出缺失的UP
    todo = [uid for uid in up_ids if uid not in summaries]
    print(f'新星榜UP: {len(up_ids)}, 当前总结: {len(summaries)}, 待补跑: {len(todo)}')

    if not todo:
        print('无需补跑')
        return

    error_count = 0
    for i, uid in enumerate(todo):
        up_name = up_name_map.get(uid, uid)
        videos = videos_by_up.get(uid, [])
        new_hash = compute_up_hash(up_name, videos) if videos else 'no_videos'

        if not videos:
            summaries[uid] = {'summary': '暂无稿件内容信息', 'input_hash': new_hash}
            print(f'  [{i+1}/{len(todo)}] UP{uid} {up_name}: 无稿件')
        else:
            result = call_api(up_name, videos)
            summaries[uid] = {'summary': result, 'input_hash': new_hash}
            has_err = result.startswith('[API') or result.startswith('[异常') or result.startswith('[超时')
            if has_err:
                error_count += 1
            status = '✗' if has_err else '✓'
            print(f'  [{i+1}/{len(todo)}] {status} UP{uid} {up_name}: {result[:80]}')

        # 每5个保存一次
        if (i + 1) % 5 == 0 or i + 1 == len(todo):
            d['_meta']['updated_at'] = datetime.now().isoformat(timespec='seconds')
            d['_meta']['count'] = len(summaries)
            with open(JSON_OUT, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

        time.sleep(0.3)

    print(f'\n完成！补跑{len(todo)}个UP，错误/超时{error_count}个，总计{len(summaries)}个')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'脚本异常: {e}')
        import traceback
        traceback.print_exc()
