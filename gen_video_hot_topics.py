import json, requests

JSON_IN = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\video_top100.json'
JSON_OUT = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\video_hot_topics.json'

with open(JSON_IN, 'r', encoding='utf-8') as f:
    videos = json.load(f)

# 构建输入文本（截断asr_data）
lines = []
for i, v in enumerate(videos):
    title = v.get('稿件标题', '')
    tid = v.get('一级分区', '')
    sub = v.get('二级分区', '')
    tag = v.get('tag', '')
    asr = str(v.get('asr_data', ''))
    asr_short = asr[:200] + '...' if len(asr) > 200 else asr
    lines.append(f'{i+1}. {title} | {tid}/{sub} | tag:{tag} | {asr_short}')

video_text = '\n'.join(lines)

HOT_PROMPT = f'''你是B站内容分析师。以下是本周充电稿件Top100的详细信息（标题、一二级分区、tag、asr摘要）：

{video_text}

请根据这些信息，识别本周充电内容的热门主题聚集现象。

## 输出要求
1. 输出5个热门主题（根据聚集程度判断，不要凑数）
2. 每个主题需要有多个稿件作为支撑
3. 主题之间不能重叠，要有明显差异
4. 语气像运营周报，简洁有力
5. 不要出现"根据数据""通过分析"等生硬表述

## 输出格式（严格遵守，每个主题一段，用---分隔）
🔥 主题名称（5字以内）
代表UP：UP昵称1、UP昵称2、UP昵称3
趋势描述：一句话说明这个主题的内容特征和为什么是热点（30字以内）
---
🔥 ...（后续主题同格式）'''

print(f'调用API生成稿件热点总结，共{len(videos)}条稿件...')
try:
    resp = requests.post('http://bxk.bilibili.co/api/bxk/private_chat',
        headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
        json={'kid': '1081', 'query': HOT_PROMPT, 'chat_mod': 'bot'},
        timeout=120)
    obj = resp.json()
    if obj.get('code') == 0:
        data = obj.get('data', {})
        answer = data.get('answer', '').strip() if isinstance(data, dict) else ''
        if answer:
            with open(JSON_OUT, 'w', encoding='utf-8') as f:
                json.dump({'hot_topics': answer, 'generated_at': str(__import__('datetime').datetime.now())}, f, ensure_ascii=False, indent=2)
            print(f'\n✓ 热点总结已保存: {JSON_OUT}')
            print('\n--- 预览 ---')
            print(answer)
        else:
            print(f'[错误] answer为空, obj={obj}')
    else:
        print(f'[API错误] code={obj.get("code")} msg={obj.get("msg")}')
except Exception as e:
    print(f'[异常] {e}')
    import traceback; traceback.print_exc()
