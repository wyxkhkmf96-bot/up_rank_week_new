#!/usr/bin/env python3
"""
充电UP主分析看板 - 数据更新构建脚本

用法：
  python3 build_leaderboard.py

功能：
  1. 扫描 charging_data/ 文件夹，找到最新日期的 CSV 文件
  2. 读取 *_weekly.csv 和 *_potential.csv
  3. 将数据嵌入 HTML 模板，生成 charging_up_leaderboard.html

文件命名规范：
  - charging_data/YYYYMMDD_weekly.csv    （充电新星UP主周榜）
  - charging_data/YYYYMMDD_potential.csv  （商业&充电潜力UP主榜）

定时任务只需将新 CSV 放入 charging_data/ 文件夹，然后运行本脚本即可更新页面。
"""

import os
import re
import csv
import json
import glob
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'charging_data'
OUTPUT_HTML = BASE_DIR / 'charging_up_leaderboard.html'
TEMPLATE_HTML = BASE_DIR / 'charging_up_leaderboard.html'

def find_latest_date():
    """扫描 charging_data/ 找到最新的日期前缀"""
    files = glob.glob(str(DATA_DIR / '*_weekly.csv')) + glob.glob(str(DATA_DIR / '*_potential.csv'))
    dates = set()
    for f in files:
        basename = os.path.basename(f)
        match = re.match(r'(\d{8})_', basename)
        if match:
            dates.add(match.group(1))
    if not dates:
        print('ERROR: charging_data/ 中未找到有效的数据文件')
        print('文件命名格式: YYYYMMDD_weekly.csv / YYYYMMDD_potential.csv')
        return None
    latest = sorted(dates)[-1]
    return latest

def read_weekly_csv(date_str):
    """读取周榜 CSV 并转为 JSON 兼容的 list"""
    filepath = DATA_DIR / f'{date_str}_weekly.csv'
    if not filepath.exists():
        print(f'WARNING: {filepath} 不存在，周榜数据将为空')
        return []

    data = []
    int_fields = {'fans', 'days_since', 'charge_video_cnt', 'vv', 'charge_users', 'on_board'}
    float_fields = {'gmv', 'avg_daily_gmv', 'ecpvv', 'cvr'}

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in int_fields:
                if k in row and row[k]:
                    try:
                        row[k] = int(float(row[k]))
                    except (ValueError, TypeError):
                        row[k] = 0
            for k in float_fields:
                if k in row and row[k]:
                    try:
                        row[k] = round(float(row[k]), 2)
                    except (ValueError, TypeError):
                        row[k] = 0
            data.append(row)
    return data

def read_potential_csv(date_str):
    """读取潜力榜 CSV 并转为 JSON 兼容的 list"""
    filepath = DATA_DIR / f'{date_str}_potential.csv'
    if not filepath.exists():
        print(f'WARNING: {filepath} 不存在，潜力榜数据将为空')
        return []

    data = []
    int_fields = {'fans', 'biz_scale_rank', 'biz_active_rank', 'biz_trend_rank', 'charge_users'}
    float_fields = {'biz_score', 'gmv_30d', 'avg_daily_gmv', 'ecpvv', 'cvr'}

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in int_fields:
                if k in row and row[k]:
                    try:
                        row[k] = int(float(row[k]))
                    except (ValueError, TypeError):
                        row[k] = 0
            for k in float_fields:
                if k in row and row[k]:
                    try:
                        row[k] = round(float(row[k]), 2)
                    except (ValueError, TypeError):
                        row[k] = 0
            if 'up_id' in row:
                try:
                    row['up_id'] = int(row['up_id'])
                except (ValueError, TypeError):
                    pass
            data.append(row)
    return data

def build_html(weekly_data, potential_data, date_str):
    """将数据注入 HTML 模板"""
    with open(TEMPLATE_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    # 替换周榜数据
    weekly_json = json.dumps(weekly_data, ensure_ascii=False, separators=(',', ':'))
    html = re.sub(
        r'const UPS = \[.*?\];',
        f'const UPS = {weekly_json};',
        html,
        count=1,
        flags=re.DOTALL
    )

    # 替换潜力榜数据
    potential_json = json.dumps(potential_data, ensure_ascii=False, separators=(',', ':'))
    html = re.sub(
        r'const POT_DATA = \[.*?\];',
        f'const POT_DATA = {potential_json};',
        html,
        count=1,
        flags=re.DOTALL
    )

    # 更新分区列表
    zones = sorted(set(d.get('tid_gen', '') for d in potential_data if d.get('tid_gen')))
    zones_json = json.dumps(zones, ensure_ascii=False)
    html = re.sub(
        r'const POT_ZONES = \[.*?\];',
        f'const POT_ZONES = {zones_json};',
        html,
        count=1,
        flags=re.DOTALL
    )

    # 更新结论列表
    conclusions = sorted(set(d.get('conclusion', '') for d in potential_data if d.get('conclusion')))
    conclusions_json = json.dumps(conclusions, ensure_ascii=False)
    html = re.sub(
        r'const POT_CONCLUSIONS = \[.*?\];',
        f'const POT_CONCLUSIONS = {conclusions_json};',
        html,
        count=1,
        flags=re.DOTALL
    )

    # 更新日期显示
    display_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}'
    html = re.sub(
        r'充电新星周榜 & 商业充电潜力UP主分析',
        f'充电新星周榜 & 商业充电潜力UP主分析 · 数据更新: {display_date}',
        html,
        count=1
    )

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'构建完成！')
    print(f'  数据日期: {display_date}')
    print(f'  周榜UP主: {len(weekly_data)} 位')
    print(f'  潜力榜UP主: {len(potential_data)} 位')
    print(f'  输出文件: {OUTPUT_HTML}')

def main():
    print('=== 充电UP主分析看板 - 构建 ===')
    print(f'数据目录: {DATA_DIR}')

    latest = find_latest_date()
    if not latest:
        return

    print(f'最新数据日期: {latest}')

    weekly = read_weekly_csv(latest)
    potential = read_potential_csv(latest)

    if not weekly and not potential:
        print('ERROR: 两个数据源都为空，终止构建')
        return

    build_html(weekly, potential, latest)

if __name__ == '__main__':
    main()
