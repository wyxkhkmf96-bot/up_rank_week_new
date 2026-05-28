"""
UP主充电榜单全流程查询脚本
执行顺序：
  代码1 (UP主榜单主表) → 产出 up_id 列表
  代码2~6 并行执行（其中2/3/4依赖代码1的up_id列表，5/6不依赖）

用法: PYTHONIOENCODING=utf-8 python run_all.py
"""
import json
import time
import urllib.request
import urllib.error
import sys
import threading
import os

CONFIG = {
    'username': os.environ.get('ADHOC_USERNAME', 'dengyuting02'),
    'token': os.environ.get('ADHOC_TOKEN', ''),
    'baseUrl': 'https://berserker.bilibili.co'
}

if not CONFIG['token']:
    print('错误：未设置环境变量 ADHOC_TOKEN（adhoc 平台 token）', file=sys.stderr)
    print('Windows PowerShell 临时设置：$env:ADHOC_TOKEN="your_token"', file=sys.stderr)
    print('Windows cmd 临时设置：       set ADHOC_TOKEN=your_token', file=sys.stderr)
    sys.exit(1)

BASE_DIR = 'C:/Users/dengyuting02/claude output/charging_up_newstar'

def api_request(url, method='GET', data=None):
    headers = {
        'Adhoc-Username': CONFIG['username'],
        'Adhoc-Token': CONFIG['token'],
        'Content-Type': 'application/json; charset=utf-8',
    }
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))

def submit_and_wait(label, sql, output_path, timeout=1800):
    print(f'[{label}] Submitting ({len(sql)} chars)...', file=sys.stderr)
    resp = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/execute",
                       method='POST', data={'sqlCommand': sql, 'engineType': 19})
    if resp.get('code') != 200:
        print(f'[{label}] Submit FAILED: {json.dumps(resp, ensure_ascii=False)}', file=sys.stderr)
        return None
    query_id = resp['data']['queryId']
    print(f'[{label}] Query ID: {query_id}', file=sys.stderr)
    elapsed = 0
    names = {1: 'SUCCESS', 2: 'FAILED', 3: 'RUNNING', 4: 'QUEUED', 5: 'STOPPED'}
    while elapsed < timeout:
        status_resp = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/status/{query_id}")
        status = status_resp.get('data')
        print(f'[{label}] [{elapsed}s] {names.get(status, f"UNKNOWN({status})")}', file=sys.stderr)
        if status == 1:
            result = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/result/{query_id}")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            rows = len(result.get('data', {}).get('result', []))
            print(f'[{label}] DONE - {rows} rows -> {output_path}', file=sys.stderr)
            return result
        if status == 2:
            print(f'[{label}] FAILED', file=sys.stderr)
            return None
        if status == 5:
            print(f'[{label}] STOPPED (平台终止)', file=sys.stderr)
            return None
        time.sleep(10)
        elapsed += 10
    print(f'[{label}] TIMEOUT after {timeout}s', file=sys.stderr)
    return None

# ============================================================
# 代码1: UP主榜单主表
# ============================================================
def run_code1():
    sql_path = f'{BASE_DIR}/code1_up_rank.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return submit_and_wait('代码1-UP榜单', sql, f'{BASE_DIR}/result_code1_up_rank.json')

# ============================================================
# 代码2: 近30天UP主日维度充电GMV + VV (依赖代码1 up_id)
# ============================================================
def build_code2_sql(in_clause):
    sql_path = f'{BASE_DIR}/code2_daily_gmv_vv.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

# ============================================================
# 代码3: 稿件充电明细 (依赖代码1 up_id)
# ============================================================
def build_code3_sql(in_clause):
    sql_path = f'{BASE_DIR}/code3_arch_charge.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

# 代码4: Top3共粉UP (依赖代码1 up_id)
def build_code4_sql(in_clause):
    sql_path = f'{BASE_DIR}/code4_top3_fans.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

# 代码5: 分区充电渗透率 (不依赖up_id)
def build_code5_sql():
    sql_path = f'{BASE_DIR}/code5_penetration.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# 代码6: 全量稿件充电Top100 (不依赖up_id)
def build_code6_sql():
    sql_path = f'{BASE_DIR}/code6_top100.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# ============================================================
# 主流程
# ============================================================
def main():
    print('=' * 60, file=sys.stderr)
    print('阶段1: 执行代码1 (UP主榜单主表)', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

    result1 = run_code1()
    if not result1:
        print('代码1失败，终止执行', file=sys.stderr)
        sys.exit(1)

    up_ids = [r['up_id'] for r in result1['data']['result']]
    in_clause = ', '.join(up_ids)
    print(f'\n代码1完成，获得 {len(up_ids)} 个 up_id', file=sys.stderr)

    print('\n' + '=' * 60, file=sys.stderr)
    print('阶段2: 并行执行代码2~6', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

    tasks = [
        ('代码2-日维度GMV_VV', build_code2_sql(in_clause), f'{BASE_DIR}/result_code2_daily_gmv_vv.json'),
        ('代码3-稿件充电明细', build_code3_sql(in_clause), f'{BASE_DIR}/result_code3_arch_charge.json'),
        ('代码4-Top3共粉UP', build_code4_sql(in_clause), f'{BASE_DIR}/result_code4_top3_fans.json'),
        ('代码5-分区渗透率', build_code5_sql(), f'{BASE_DIR}/result_code5_penetration.json'),
        ('代码6-全量Top100', build_code6_sql(), f'{BASE_DIR}/result_code6_top100.json'),
    ]

    threads = []
    for label, sql, output_path in tasks:
        t = threading.Thread(target=submit_and_wait, args=(label, sql, output_path))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print('\n' + '=' * 60, file=sys.stderr)
    print('全部完成!', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

if __name__ == '__main__':
    main()
