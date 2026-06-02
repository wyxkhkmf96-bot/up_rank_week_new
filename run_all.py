"""
UP主充电榜单全流程查询脚本
执行顺序：
  阶段1 (并行): 代码1 (新星UP榜单主表) + 代码6 (黑马UP榜单主表) → 各产出 up_id 列表
  阶段2 (并行): 代码2~5
    代码2/4 依赖代码1的 up_id（仅服务新星）
    代码3 依赖 代码1 ∪ 代码6 的 up_id 并集（稿件明细同时供新星+黑马用）
    代码5 不依赖

用法:
  全流程:        PYTHONIOENCODING=utf-8 python run_all.py
  仅阶段1:       PYTHONIOENCODING=utf-8 python run_all.py --phase 1
  仅阶段2:       PYTHONIOENCODING=utf-8 python run_all.py --phase 2
"""
import json
import time
import urllib.request
import urllib.error
import sys
import threading
import os
import argparse

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

BASE_DIR = 'C:/Users/dengyuting02/WorkBuddy/20260514140206'

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
# 代码1: 新星UP主榜单主表
# ============================================================
def run_code1():
    sql_path = f'{BASE_DIR}/code1_up_rank.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return submit_and_wait('代码1-新星UP榜', sql, f'{BASE_DIR}/result_code1_up_rank.json')

# ============================================================
# 代码6: 黑马UP主榜单主表（与代码1并行，互不依赖）
# ============================================================
def run_code6():
    sql_path = f'{BASE_DIR}/code6_darkhorse.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return submit_and_wait('代码6-黑马UP榜', sql, f'{BASE_DIR}/result_code6_darkhorse.json')

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

# ============================================================
# 中间结果文件（阶段1→阶段2 的 up_id 传递）
# ============================================================
PHASE1_META = f'{BASE_DIR}/.phase1_meta.json'

def save_phase1_meta(up_ids_new, up_ids_dark):
    meta = {'up_ids_new': up_ids_new, 'up_ids_dark': up_ids_dark}
    with open(PHASE1_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f'阶段1元数据已保存 -> {PHASE1_META}', file=sys.stderr)

def load_phase1_meta():
    if not os.path.exists(PHASE1_META):
        print(f'错误：找不到阶段1元数据文件 {PHASE1_META}，请先运行 --phase 1', file=sys.stderr)
        sys.exit(1)
    with open(PHASE1_META, 'r', encoding='utf-8') as f:
        return json.load(f)

# ============================================================
# 阶段1: 并行执行代码1(新星UP榜) + 代码6(黑马UP榜)
# ============================================================
def run_phase1():
    print('=' * 60, file=sys.stderr)
    print('阶段1: 并行执行代码1(新星UP榜) + 代码6(黑马UP榜)', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

    results = {}
    def _run_and_store(key, fn):
        results[key] = fn()

    s1_threads = [
        threading.Thread(target=_run_and_store, args=('code1', run_code1)),
        threading.Thread(target=_run_and_store, args=('code6', run_code6)),
    ]
    for t in s1_threads:
        t.start()
    for t in s1_threads:
        t.join()

    result1 = results.get('code1')
    result6 = results.get('code6')
    if not result1:
        print('代码1失败，终止执行', file=sys.stderr)
        sys.exit(1)

    up_ids_new = [str(r['up_id']) for r in result1['data']['result']]
    print(f'\n代码1完成，获得 {len(up_ids_new)} 个新星 up_id', file=sys.stderr)

    if result6:
        up_ids_dark = [str(r['up_id']) for r in result6['data']['result']]
        print(f'代码6完成，获得 {len(up_ids_dark)} 个黑马 up_id', file=sys.stderr)
    else:
        up_ids_dark = []
        print('代码6失败/无结果，黑马 up_id 为空（不影响后续）', file=sys.stderr)

    save_phase1_meta(up_ids_new, up_ids_dark)
    print('\n' + '=' * 60, file=sys.stderr)
    print('阶段1完成!', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

# ============================================================
# 阶段2: 并行执行代码2~5
# ============================================================
def run_phase2():
    meta = load_phase1_meta()
    up_ids_new = meta['up_ids_new']
    up_ids_dark = meta.get('up_ids_dark', [])
    in_clause_new = ', '.join(up_ids_new)
    print(f'从元数据加载：新星 {len(up_ids_new)} 个，黑马 {len(up_ids_dark)} 个', file=sys.stderr)

    # 代码3 稿件明细用 新星 ∪ 黑马 的并集
    up_ids_all = list(dict.fromkeys(up_ids_new + up_ids_dark))
    in_clause_all = ', '.join(up_ids_all)
    print(f'代码3 稿件明细将覆盖并集 {len(up_ids_all)} 个 up_id', file=sys.stderr)

    print('\n' + '=' * 60, file=sys.stderr)
    print('阶段2: 并行执行代码2~5', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

    tasks = [
        ('代码2-日维度GMV_VV', build_code2_sql(in_clause_new), f'{BASE_DIR}/result_code2_daily_gmv_vv.json'),
        ('代码3-稿件充电明细', build_code3_sql(in_clause_all), f'{BASE_DIR}/result_code3_arch_charge.json'),
        ('代码4-Top3共粉UP', build_code4_sql(in_clause_new), f'{BASE_DIR}/result_code4_top3_fans.json'),
        ('代码5-分区渗透率', build_code5_sql(), f'{BASE_DIR}/result_code5_penetration.json'),
    ]

    threads = []
    for label, sql, output_path in tasks:
        t = threading.Thread(target=submit_and_wait, args=(label, sql, output_path))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print('\n' + '=' * 60, file=sys.stderr)
    print('阶段2完成!', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='UP主充电榜单全流程查询')
    parser.add_argument('--phase', type=int, choices=[1, 2], default=None,
                        help='仅运行指定阶段: 1=取主表, 2=取明细(依赖阶段1结果)')
    args = parser.parse_args()

    if args.phase == 1:
        run_phase1()
    elif args.phase == 2:
        run_phase2()
    else:
        # 默认：两阶段顺序执行（全流程）
        run_phase1()
        run_phase2()
        print('\n' + '=' * 60, file=sys.stderr)
        print('全部完成!', file=sys.stderr)
        print('=' * 60, file=sys.stderr)

if __name__ == '__main__':
    main()
