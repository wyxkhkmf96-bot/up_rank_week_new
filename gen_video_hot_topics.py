"""
Step 4: 稿件热点主题（增量版）
读取 result_code6_top100.json (Top100稿件)
拼接稿件信息一次API调用，输出 video_hot_topics.json

判断重跑条件：
1. video_hot_topics.json 不存在
2. Top100 稿件输入指纹与上次不同
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
JSON_IN = os.path.join(BASE, 'result_code6_top100.json')
JSON_OUT = os.path.join(BASE, 'video_hot_topics.json')

PROMPT_VERSION = 'v1'
FORCE = '--force' in sys.argv


def main():
    with open(JSON_IN, 'r', encoding='utf-8') as f:
        rows = json.load(f)['data']['result']
    print(f'稿件总数: {len(rows)}')

    lines = []
    for i, r in enumerate(rows, 1):
        up = str(r.get('UP主昵称') or '')
        title = str(r.get('稿件标题') or '')
        tid = str(r.get('一级分区') or '')
        sub = str(r.get('二级分区') or '')
        tag = str(r.get('tag') or '')
        gmv = str(r.get('稿件近30日GMV') or '0')
        asr = str(r.get('asr_data') or '')
        asr_short = asr[:200] + '...' if len(asr) > 200 else asr
        lines.append(f'{i}. 【{up}】《{title}》| {tid}/{sub} | tag:{tag} | GMV:{gmv} | asr:{asr_short}')
    all_text = '\n'.join(lines)
    input_hash = hashlib.sha1(all_text.encode('utf-8')).hexdigest()[:16]
    print(f'input_hash={input_hash}')

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

    HOT_PROMPT = f'''你是B站内容分析师。以下是本周充电稿件Top100榜单（按GMV排序）：

{all_text}

请识别其中的热点内容聚集现象，找出本周最显著的热点主题。
判断标准：有多个稿件呈现同类内容特征，说明这是当前的内容风口。

## 输出要求
1. 输出5个热点主题（按热度从高到低排序）
2. 每个主题需要选出5个最具代表性的稿件案例
3. 主题之间不能重叠，要有明显差异
4. 语气像运营周报，简洁有力
5. 不要出现"根据数据""通过分析"等生硬表述

## 输出格式（严格遵守，每个主题一段，用---分隔）
🔥 热门topN主题-主题名称（5字以内）

趋势描述：一句话说明这个主题的内容特征和热度原因（50字以内）

代表稿件：
1. UP名《稿件标题》
2. UP名《稿件标题》
3. UP名《稿件标题》
4. UP名《稿件标题》
5. UP名《稿件标题》
---
🔥 ...（后续主题同格式）'''

    print('调用API生成稿件热点总结...')
    try:
        resp = requests.post(
            'http://bxk.bilibili.co/api/bxk/private_chat',
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            json={'kid': '1081', 'query': HOT_PROMPT, 'chat_mod': 'bot'},
            timeout=180,
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
                        'total_videos': len(rows),
                        'updated_at': datetime.now().isoformat(timespec='seconds'),
                    },
                    'hot_topics': answer,
                    'generated_at': datetime.now().isoformat(timespec='seconds'),
                }
                with open(JSON_OUT, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
                print(f'\n✓ 稿件热点已保存: {JSON_OUT}')
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
