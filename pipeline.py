#!/usr/bin/env python3
"""
B站充电新星UP主周榜 & 充电稿件Top100 — 完整自动化工作流

用法:
    python pipeline.py --up-excel "C:/.../表汇总5.25.xlsx" --video-excel "C:/.../稿件榜5.26.xlsx"
    python pipeline.py --up-excel "C:/.../表汇总5.25.xlsx"           # 只更新UP榜
    python pipeline.py --video-excel "C:/.../稿件榜5.26.xlsx"        # 只更新稿件榜
    python pipeline.py --up-excel "..." --video-excel "..." --skip-api  # 跳过API，使用现有JSON
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# ========== API配置 ==========
API_URL = 'http://bxk.bilibili.co/api/bxk/private_chat'
API_KID = '1081'


def main():
    parser = argparse.ArgumentParser(description='充电榜单完整工作流')
    parser.add_argument('--up-excel', help='UP主数据Excel路径（表汇总MM.DD.xlsx）')
    parser.add_argument('--video-excel', help='稿件数据Excel路径（稿件榜MM.DD.xlsx）')
    parser.add_argument('--skip-api', action='store_true', help='跳过所有API调用，使用现有JSON缓存')
    args = parser.parse_args()

    if not args.up_excel and not args.video_excel:
        print('错误: 请至少提供 --up-excel 或 --video-excel')
        print('示例: python pipeline.py --up-excel "C:/Users/.../表汇总5.25.xlsx" --video-excel "C:/Users/.../稿件榜5.26.xlsx"')
        sys.exit(1)

    updated = []

    # ===== 步骤1: UP主榜单 =====
    if args.up_excel:
        print('\n' + '=' * 60)
        print('步骤1/3: UP主榜单')
        print('=' * 60)
        process_up_pipeline(args.up_excel, skip_api=args.skip_api)
        updated.append('新星榜')

    # ===== 步骤2: 稿件榜单 =====
    if args.video_excel:
        print('\n' + '=' * 60)
        print('步骤2/3: 稿件榜单')
        print('=' * 60)
        process_video_pipeline(args.video_excel, skip_api=args.skip_api)
        updated.append('稿件榜')

    # ===== 步骤3: 组装融合版 =====
    print('\n' + '=' * 60)
    print('步骤3/3: 组装融合版 merged.html')
    print('=' * 60)
    assemble_merged()

    # ===== 完成 =====
    print('\n' + '=' * 60)
    print('全部完成!')
    print('=' * 60)
    print('产出文件:')
    if '新星榜' in updated:
        print('  - charging_up_leaderboard.html       (新星榜独立版)')
    if '稿件榜' in updated:
        print('  - charging_up_videos.html             (稿件榜独立版)')
    print('  - charging_up_leaderboard_merged.html (三Tab融合版)')
    print('\nGit提交命令:')
    print('  git add -A')
    print('  git commit -m "update: YYYY-MM-DD 榜单更新"')
    print('  git push')


# ==================== 子流程 ====================

def process_up_pipeline(excel_path, skip_api=False):
    """UP主榜单完整流程: Excel → API → JSON → HTML"""
    print(f'[1/3] UP数据: {excel_path}')

    if not skip_api:
        print('[2/3] 增量生成UP内容总结 (~10分钟)...')
        run_script_with_excel('run_api.py', excel_path)

        print('[3/3] 生成热点主题 (~1分钟)...')
        run_script_with_excel('gen_hot_topics.py', excel_path)
    else:
        print('[2/3] 跳过UP API (使用现有 up_summaries.json)')
        print('[3/3] 跳过热点主题API (使用现有 hot_topics.json)')

    print('[4/4] 生成新星榜独立版HTML (~10秒)...')
    run_script_with_excel('build_leaderboard.py', excel_path)
    print('新星榜独立版: charging_up_leaderboard.html')


def process_video_pipeline(excel_path, skip_api=False):
    """稿件榜单完整流程: Excel → JSON → API → HTML"""
    print(f'[1/3] 稿件数据: {excel_path}')

    print('[2/3] 导出 video_top100.json...')
    export_video_json(excel_path)

    if not skip_api:
        print('[3/3] 生成稿件热点主题 (~1分钟)...')
        generate_video_hot_topics()
    else:
        print('[3/3] 跳过稿件API (使用现有 video_hot_topics.json)')

    print('[4/4] 生成稿件榜独立版HTML (~10秒)...')
    run_script('build_video_leaderboard.py')
    print('稿件榜独立版: charging_up_videos.html')


# ==================== 脚本执行工具 ====================

def run_script_with_excel(script_path, excel_path):
    """运行Python脚本，临时替换其中所有.xlsx路径为指定路径"""
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换所有Excel路径为新的路径
    # 匹配 r'...xxx.xlsx' 或 '...xxx.xlsx' 或 "...xxx.xlsx"
    original = content
    content = re.sub(r"([rR]?['\"])[^'\"]*\.xlsx\1", f"r'{excel_path}'", content)

    if content == original:
        print(f'  警告: {script_path} 中未找到.xlsx路径，使用原脚本')
        run_script(script_path)
        return

    tmp_path = script_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(content)

    try:
        result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True)
        # 打印输出（限制长度避免刷屏）
        out = result.stdout
        if len(out) > 3000:
            print(out[:1500])
            print('  ... (中间省略) ...')
            print(out[-1500:])
        else:
            print(out)
        if result.returncode != 0:
            err = result.stderr
            print(f'  错误: {err[:500]}')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def run_script(script_path):
    """直接运行Python脚本"""
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    out = result.stdout
    if len(out) > 3000:
        print(out[:1500])
        print('  ... (中间省略) ...')
        print(out[-1500:])
    else:
        print(out)
    if result.returncode != 0:
        print(f'  错误: {result.stderr[:500]}')


# ==================== 稿件数据处理 ====================

def export_video_json(excel_path):
    """读取稿件Excel，导出 video_top100.json"""
    import pandas as pd

    df = pd.read_excel(excel_path)

    # 日期列转字符串
    for col in df.columns:
        if '时间' in col or '日期' in col:
            df[col] = df[col].astype(str)

    # 数值列转换
    numeric_cols = ['稿件近30日GMV', '稿件近30日播放量', '稿件近30日ECPVV',
                    '稿件近30日充电人数', '稿件近30日转化率']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    records = df.to_dict('records')
    with open('video_top100.json', 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    tids = sorted({v['一级分区'] for v in records if v.get('一级分区')})
    print(f'  导出 {len(records)} 条稿件, {len(tids)} 个分区: {tids}')


def generate_video_hot_topics():
    """调用B站API生成稿件热点主题 → video_hot_topics.json"""
    try:
        import requests
    except ImportError:
        print('  错误: 缺少requests库，请安装: pip install requests')
        return

    with open('video_top100.json', 'r', encoding='utf-8') as f:
        videos = json.load(f)

    # 构建输入文本
    lines = []
    for i, v in enumerate(videos):
        title = v.get('稿件标题', '')
        up = v.get('UP主昵称', '')
        tid = v.get('一级分区', '')
        sub = v.get('二级分区', '')
        tag = v.get('tag', '')
        gmv = v.get('稿件近30日GMV', 0)
        asr = str(v.get('asr_data', ''))
        asr_short = asr[:150] + '...' if len(asr) > 150 else asr
        lines.append(f'{i+1}. 【{up}】{title} | {tid}/{sub} | tag:{tag} | GMV:{gmv} | {asr_short}')

    video_text = '\n'.join(lines)

    prompt = f'''你是B站内容分析师。以下是本周充电稿件Top100的详细信息（UP昵称、标题、一二级分区、tag、GMV、asr摘要）：

{video_text}

请根据这些信息，识别本周充电内容的热门主题聚集现象。

## 输出要求
1. 输出5个热门主题（根据聚集程度判断，不要凑数）
2. 每个主题需要有多个稿件作为支撑
3. 主题之间不能重叠，要有明显差异
4. 语气像运营周报，简洁有力
5. 不要出现"根据数据""通过分析"等生硬表述
6. 每个主题必须给出5个代表性稿件案例（格式：UP昵称《稿件标题》）

## 输出格式（严格遵守，每个主题一段，用---分隔）
🔥 热门top1主题-xxx（5字以内）
趋势描述：一段话详细说明这个主题的内容特征和为什么是热点（50字以内）
代表稿件：
1. UP昵称《稿件标题》
2. UP昵称《稿件标题》
3. UP昵称《稿件标题》
4. UP昵称《稿件标题》
5. UP昵称《稿件标题》
---
🔥 热门top2主题-xxx
...（同上格式）'''

    print(f'  调用API生成稿件热点总结，共{len(videos)}条稿件...')
    try:
        resp = requests.post(API_URL,
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            json={'kid': API_KID, 'query': prompt, 'chat_mod': 'bot'},
            timeout=180)
        obj = resp.json()
        if obj.get('code') == 0:
            data = obj.get('data', {})
            answer = data.get('answer', '').strip() if isinstance(data, dict) else ''
            if answer:
                with open('video_hot_topics.json', 'w', encoding='utf-8') as f:
                    json.dump({'hot_topics': answer, 'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')},
                              f, ensure_ascii=False, indent=2)
                print(f'  热点总结已保存，共5个主题')
                # 预览前200字
                preview = answer.replace('\n', ' ')[:200]
                print(f'  预览: {preview}...')
            else:
                print('  错误: API返回answer为空')
        else:
            print(f'  API错误: code={obj.get("code")} msg={obj.get("msg")}')
    except Exception as e:
        print(f'  API调用异常: {e}')


# ==================== 融合版组装 ====================

def extract_main_div(html):
    """用栈匹配提取 <div class="main"> 到对应的 </div>（包含div标签本身）"""
    start = html.find('<div class="main">')
    if start == -1:
        print('    警告: 未找到 <div class="main">')
        return ''
    pos = html.find('>', start) + 1
    stack = 1
    while pos < len(html) and stack > 0:
        open_pos = html.find('<div', pos)
        close_pos = html.find('</div>', pos)
        if open_pos == -1 and close_pos == -1:
            break
        if open_pos != -1 and (close_pos == -1 or open_pos < close_pos):
            stack += 1
            pos = open_pos + 4
        else:
            stack -= 1
            pos = close_pos + 6
            if stack == 0:
                return html[start:pos]
    print('    警告: main div栈匹配未完成')
    return ''


def extract_script(html):
    """提取 <script> 和 </script> 之间的内容（不包括script标签）"""
    m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    return m.group(1) if m else ''


def replace_between(html, start_marker, end_marker, new_content):
    """替换html中start_marker和end_marker之间的内容（不包括标记本身）"""
    start = html.find(start_marker)
    if start == -1:
        print(f'    警告: 未找到开始标记: {start_marker[:60]}')
        return html
    content_start = start + len(start_marker)
    end = html.find(end_marker, content_start)
    if end == -1:
        print(f'    警告: 未找到结束标记: {end_marker[:60]}')
        return html
    return html[:content_start] + '\n' + new_content + '\n' + html[end:]


def replace_main_in_tab(merged_html, tab_id, new_main_div):
    """在merged_html中，找到指定tab-id的div，替换其内部的<div class="main">...</div>"""
    tab_start = merged_html.find(f'<div id="{tab_id}"')
    if tab_start == -1:
        print(f'    警告: 未找到 tab {tab_id}')
        return merged_html

    # 栈匹配找到tab div的结束
    pos = merged_html.find('>', tab_start) + 1
    stack = 1
    tab_end = None
    while pos < len(merged_html) and stack > 0:
        open_pos = merged_html.find('<div', pos)
        close_pos = merged_html.find('</div>', pos)
        if open_pos == -1 and close_pos == -1:
            break
        if open_pos != -1 and (close_pos == -1 or open_pos < close_pos):
            stack += 1
            pos = open_pos + 4
        else:
            stack -= 1
            pos = close_pos + 6
            if stack == 0:
                tab_end = pos
                break

    if tab_end is None:
        print(f'    警告: 未找到 tab {tab_id} 的结束标签')
        return merged_html

    tab_full = merged_html[tab_start:tab_end]
    old_main = extract_main_div(tab_full)

    if not old_main:
        print(f'    警告: 未找到 tab {tab_id} 内的 main div')
        return merged_html

    new_tab_full = tab_full.replace(old_main, new_main_div, 1)
    return merged_html.replace(tab_full, new_tab_full, 1)


def assemble_merged():
    """基于现有 merged.html，精确替换新星榜和稿件榜的内容与JS"""
    print('读取源文件...')
    with open('charging_up_leaderboard.html', 'r', encoding='utf-8') as f:
        weekly = f.read()
    with open('charging_up_videos.html', 'r', encoding='utf-8') as f:
        videos = f.read()
    with open('charging_up_leaderboard_merged.html', 'r', encoding='utf-8') as f:
        merged = f.read()

    original = merged

    # ---- 1. 替换Tab内容（main div） ----
    print('[1/3] 替换新星榜Tab内容...')
    weekly_main = extract_main_div(weekly)
    print(f'    新星榜main div: {len(weekly_main)} chars')
    merged = replace_main_in_tab(merged, 'tab-weekly', weekly_main)

    print('[2/3] 替换稿件榜Tab内容...')
    videos_main = extract_main_div(videos)
    print(f'    稿件榜main div: {len(videos_main)} chars')
    merged = replace_main_in_tab(merged, 'tab-videos', videos_main)

    # ---- 2. 替换Script段 ----
    print('[3/3] 替换Script数据与逻辑...')
    weekly_script = extract_script(weekly)
    videos_script = extract_script(videos)
    print(f'    新星榜script: {len(weekly_script)} chars')
    print(f'    稿件榜script: {len(videos_script)} chars')

    # 替换新星榜JS: <script> 之后到 "// === 页面Tab切换" 之前
    merged = replace_between(
        merged,
        '<script>',
        '// ============================================================\n// 页面Tab切换',
        weekly_script
    )

    # 替换稿件榜JS: "// === 充电稿件Top100" 之后到 "// === 商业&充电潜力UP主榜" 之前
    merged = replace_between(
        merged,
        '// ============================================================\n// 充电稿件Top100\n// ============================================================',
        '// ============================================================\n// 商业&充电潜力UP主榜',
        videos_script
    )

    # ---- 3. 保存并验证 ----
    if merged == original:
        print('警告: merged.html 未发生任何变化')
    else:
        with open('charging_up_leaderboard_merged.html', 'w', encoding='utf-8') as f:
            f.write(merged)

    div_opens = merged.count('<div')
    div_closes = merged.count('</div>')
    tabs = re.findall(r'<div[^>]*id="tab-([^"]+)"', merged)
    print(f'\n验证结果:')
    print(f'  div标签: {div_opens}开/{div_closes}闭 {"OK" if div_opens == div_closes else "MISMATCH"}')
    print(f'  Tab内容区: {tabs}')
    print(f'  文件大小: {len(merged):,} bytes')
    print('融合版组装完成!')


if __name__ == '__main__':
    main()
