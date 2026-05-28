"""
Step 3: UP 热点主题（增量版）
读取 up_summaries.json + result_code1_up_rank.json
拼接所有有效总结后调一次 API，输出 hot_topics.json

判断重跑条件：
1. hot_topics.json 不存在
2. 所有 UP summary 拼接后的 hash 与上次不同
3. prompt_version 变了
4. 命令行带 --force
"""
import json
import requests
import os
import sys
import hashlib
from datetime import datetime

BASE = r'C:\Users\dengyuting02\claude output\charging_up_newstar'
JSON_IN = os.path.join(BASE, 'up_summaries.json')
UP_RANK = os.path.join(BASE, 'result_code1_up_rank.json')
JSON_OUT = os.path.join(BASE, 'hot_topics.json')

PROMPT_VERSION = 'v1'
FORCE = '--force' in sys.argv


def load_summaries():
    """加载 up_summaries.json，兼容旧版（裸 dict）和新版（{summaries: {...}}）"""
    with open(JSON_IN, 'r', encoding='utf-8') as f:
        d = json.load(f)
    if isinstance(d, dict) and 'summaries' in d:
        return {uid: v.get('summary', '') for uid, v in d['summaries'].items()}
    return d  # 旧版


def main():
    with open(UP_RANK, 'r', encoding='utf-8') as f:
        up_rows = json.load(f)['data']['result']
    up_name_map = {str(r['up_id']): r['up名'] for r in up_rows}

    summaries = load_summaries()

    valid = []
    for uid, summary in summaries.items():
        if not summary or summary.startswith('[') or summary == '暂无稿件内容信息':
            continue
        up_name = up_name_map.get(uid, uid)
        valid.append(f'【{up_name}】{summary}')
    valid.sort()  # 排序保证 hash 稳定
    all_text = '\n'.join(valid)
    total = len(valid)
    input_hash = hashlib.sha1(all_text.encode('utf-8')).hexdigest()[:16]
    print(f'有效UP数: {total}, input_hash={input_hash}')

    # 检查是否需要重跑
    if not FORCE and os.path.exists(JSON_OUT):
        try:
            with open(JSON_OUT, 'r', encoding='utf-8') as f:
                old = json.load(f)
            old_meta = old.get('_meta', {})
            old_hash = old_meta.get('input_hash', '')
            old_ver = old_meta.get('prompt_version', '')
            if old_hash == input_hash and old_ver == PROMPT_VERSION:
                print(f'输入未变（hash 一致），跳过 API 调用')
                return
            print(f'输入变了：old_hash={old_hash[:10]}..., new_hash={input_hash[:10]}...')
        except Exception:
            pass

    HOT_PROMPT = f'''你是B站内容分析师。以下是本周{total}位充电新星UP主的内容总结：

{all_text}

请识别其中的热点内容聚集现象，找出本周明显涌现的热点主题。
判断标准：有多个不同UP都在做同一类型内容，说明这是当前的内容风口。

## 输出要求
1. 输出3-5个热点主题（根据聚集程度动态决定数量，不要凑数）
2. 每个主题需要有至少2个UP作为支撑
3. 主题之间不能重叠，要有明显差异
4. 语气像运营周报，简洁有力
5. 不要出现"根据数据""通过分析"等生硬表述

## 输出格式（严格遵守，每个主题一段，用---分隔）
🔥 主题名称（5字以内）
代表UP：UP名1、UP名2、UP名3
趋势描述：一句话说明这个主题的内容特征和为什么是热点（30字以内）
---
🔥 ...（后续主题同格式）'''

    print('调用API生成热点总结...')
    try:
        resp = requests.post(
            'http://bxk.bilibili.co/api/bxk/private_chat',
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            json={'kid': '1081', 'query': HOT_PROMPT, 'chat_mod': 'bot'},
            timeout=120,
        )
        obj = resp.json()
        if obj.get('code') == 0:
            data = obj.get('data', {})
            answer = data.get('answer', '').strip() if isinstance(data, dict) else ''
            if answer:
                out = {
                    '_meta': {
                        'prompt_version': PROMPT_VERSION,
                        'input_hash': input_hash,
                        'total_ups': total,
                        'updated_at': datetime.now().isoformat(timespec='seconds'),
                    },
                    'hot_topics': answer,
                    # 兼容字段：旧 build_dashboard.py 直接读 generated_at
                    'generated_at': datetime.now().isoformat(timespec='seconds'),
                }
                with open(JSON_OUT, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
                print(f'\n✓ 热点总结已保存: {JSON_OUT}')
                print('\n--- 预览 ---')
                print(answer)
            else:
                print(f'[错误] answer为空, obj={obj}')
        else:
            print(f'[API错误] code={obj.get("code")} msg={obj.get("msg")}')
    except Exception as e:
        print(f'[异常] {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
