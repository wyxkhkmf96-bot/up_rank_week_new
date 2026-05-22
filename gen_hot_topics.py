"""单独生成热点主题总结，读取 up_summaries.json 调一次API输出 hot_topics.json"""
import json, requests, pandas as pd

EXCEL_PATH = r'C:/Users/dengyuting02/Desktop/需求：充电新星up/表汇总5.21.xlsx'
JSON_IN    = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\up_summaries.json'
JSON_OUT   = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\hot_topics.json'

xl = pd.ExcelFile(EXCEL_PATH)
df_up = pd.read_excel(EXCEL_PATH, sheet_name=xl.sheet_names[0])

with open(JSON_IN, 'r', encoding='utf-8') as f:
    summaries = json.load(f)

# 拼接 UP名 + summary，过滤无效条目
valid = []
for uid, summary in summaries.items():
    if not summary or summary.startswith('[') or summary == '暂无稿件内容信息':
        continue
    uid_int = int(uid)
    row = df_up[df_up['up_id'] == uid_int]
    up_name = str(row['up名'].iloc[0]) if len(row) > 0 and pd.notna(row['up名'].iloc[0]) else uid
    valid.append(f'【{up_name}】{summary}')

all_text = '\n'.join(valid)
total = len(valid)
print(f'有效UP数: {total}')

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
                json.dump({'hot_topics': answer, 'generated_at': str(pd.Timestamp.now())}, f, ensure_ascii=False, indent=2)
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
