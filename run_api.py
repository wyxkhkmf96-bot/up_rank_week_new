import pandas as pd, requests, json, time, os, sys

# 重定向stdout到文件
LOG_FILE = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\api_run.log'
JSON_OUT = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\up_summaries.json'

class Tee:
    def __init__(self, file):
        self.file = open(file, 'w', encoding='utf-8')
        self.stdout = sys.stdout
        sys.stdout = self
    def write(self, s):
        self.file.write(s)
        self.stdout.write(s)
        self.file.flush()
    def flush(self):
        self.file.flush()

Tee(LOG_FILE)

try:
    path = r'C:/Users/dengyuting02/Desktop/需求：充电新星up/表汇总5.21.xlsx'
    xl = pd.ExcelFile(path)
    df_up = pd.read_excel(path, sheet_name=xl.sheet_names[0])
    df_video = pd.read_excel(path, sheet_name=xl.sheet_names[2])

    print(f'UP总数: {len(df_up)}, 稿件表记录: {len(df_video)}')

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

    def call_api(up_id, up_name, vids, vid_cnt):
        video_list = []
        for _, v in vids.iterrows():
            title = str(v['稿件标题']) if pd.notna(v['稿件标题']) else '无标题'
            tag = str(v['tag']) if pd.notna(v['tag']) else ''
            asr = str(v['asr_data']) if pd.notna(v['asr_data']) else ''
            tid = str(v['一级分区']) if pd.notna(v['一级分区']) else ''
            sub = str(v['二级分区']) if pd.notna(v['二级分区']) else ''
            asr_short = asr[:300] + '...' if len(asr) > 300 else asr
            video_list.append(f'{title} | {tid}/{sub} | {tag} | {asr_short}')
        video_str = '\n'.join(video_list)
        prompt = PROMPT_BASE.format(up_name=up_name, vid_cnt=vid_cnt, video_list=video_str)
        try:
            resp = requests.post('http://bxk.bilibili.co/api/bxk/private_chat',
                headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
                json={'kid': '1081', 'query': prompt, 'chat_mod': 'bot'},
                timeout=60)
            obj = resp.json()
            if obj.get('code') == 0:
                data = obj.get('data', {})
                answer = data.get('answer', '') if isinstance(data, dict) else ''
                if answer:
                    return answer.strip()
            return f'[API错误] code={obj.get("code")} msg={obj.get("msg")}'
        except Exception as e:
            return f'[异常] {e}'

    up_ids = df_up['up_id'].tolist()
    print(f'开始调用API，共{len(up_ids)}个UP...')
    results = {}
    error_count = 0
    for i, uid in enumerate(up_ids):
        uid_int = int(uid)
        row = df_up[df_up['up_id'] == uid_int]
        up_name = str(row['up名'].iloc[0]) if len(row) > 0 and pd.notna(row['up名'].iloc[0]) else str(uid)
        vids = df_video[df_video['UP主ID'] == uid_int]
        if len(vids) == 0:
            results[str(uid)] = '暂无稿件内容信息'
            print(f'  [{i+1}/{len(up_ids)}] UP{uid} {up_name}: 无稿件')
        else:
            vid_cnt = len(vids)
            result = call_api(uid, up_name, vids, vid_cnt)
            results[str(uid)] = result
            has_err = result.startswith('[API') or result.startswith('[异常')
            if has_err:
                error_count += 1
            status = '✗' if has_err else '✓'
            print(f'  [{i+1}/{len(up_ids)}] {status} UP{uid} {up_name}: {result[:80]}')
        time.sleep(0.4)

    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n完成！共{len(results)}个UP，错误{error_count}个，JSON已保存: {JSON_OUT}')

    # ---------- 热点主题总结（二次调用） ----------
    print('\n开始生成热点主题总结...')
    HOT_TOPICS_OUT = r'c:\Users\dengyuting02\WorkBuddy\20260514140206\hot_topics.json'

    # 拼接所有UP的名字 + summary（过滤掉无效条目）
    valid_summaries = []
    for uid, summary in results.items():
        if summary and not summary.startswith('[') and summary != '暂无稿件内容信息':
            # 取UP名
            uid_int = int(uid)
            row = df_up[df_up['up_id'] == uid_int]
            up_name = str(row['up名'].iloc[0]) if len(row) > 0 and pd.notna(row['up名'].iloc[0]) else uid
            valid_summaries.append(f'【{up_name}】{summary}')

    all_summary_text = '\n'.join(valid_summaries)
    total_up_count = len(valid_summaries)

    HOT_PROMPT = f'''你是B站内容分析师。以下是本周{total_up_count}位充电新星UP主的内容总结：

{all_summary_text}

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

    try:
        resp = requests.post('http://bxk.bilibili.co/api/bxk/private_chat',
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            json={'kid': '1081', 'query': HOT_PROMPT, 'chat_mod': 'bot'},
            timeout=120)
        obj = resp.json()
        hot_result = None
        if obj.get('code') == 0:
            data = obj.get('data', {})
            hot_result = data.get('answer', '').strip() if isinstance(data, dict) else ''
        if hot_result:
            with open(HOT_TOPICS_OUT, 'w', encoding='utf-8') as f:
                json.dump({'hot_topics': hot_result, 'generated_at': str(pd.Timestamp.now())}, f, ensure_ascii=False, indent=2)
            print(f'热点主题总结已生成: {HOT_TOPICS_OUT}')
            print('--- 热点主题预览 ---')
            print(hot_result[:500])
        else:
            print(f'[热点总结API错误] code={obj.get("code")} msg={obj.get("msg")}')
    except Exception as e:
        print(f'[热点总结异常] {e}')

except Exception as e:
    print(f'脚本异常: {e}')
    import traceback
    traceback.print_exc()
