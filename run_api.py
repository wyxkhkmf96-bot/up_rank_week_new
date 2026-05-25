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
    path = r'C:/Users/dengyuting02/Desktop/需求：充电新星up/表汇总5.25.xlsx'
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
    # 断点续跑：加载已有结果
    if os.path.exists(JSON_OUT):
        try:
            with open(JSON_OUT, 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f'加载已有结果: {len(results)}个UP，跳过已完成的')
        except:
            results = {}
    else:
        results = {}
    todo_ids = [uid for uid in up_ids if str(uid) not in results]
    print(f'开始调用API，共{len(todo_ids)}个UP待处理（总共{len(up_ids)}个）...')
    error_count = 0
    for i, uid in enumerate(todo_ids):
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
        # 边跑边写，防止超时丢失进度
        if (i+1) % 10 == 0 or i+1 == len(up_ids):
            with open(JSON_OUT, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        time.sleep(0.4)

    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n完成！共{len(results)}个UP，错误{error_count}个，JSON已保存: {JSON_OUT}')

except Exception as e:
    print(f'脚本异常: {e}')
    import traceback
    traceback.print_exc()
