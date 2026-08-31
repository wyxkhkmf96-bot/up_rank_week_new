"""
UP主充电榜单全流程查询脚本（全自动版）

执行顺序：
  阶段1 (并行): 代码1 (新星UP榜单主表) + 代码6 (黑马UP榜单主表)
  阶段2 (并行): 代码2~5
  阶段3: 更新上榜次数
  阶段4: LLM内容总结
  阶段5: 热点主题
  阶段6: HTML生成

用法:
  全流程（默认）:  PYTHONIOENCODING=utf-8 python run_all.py --full
  仅Adhoc查询:     PYTHONIOENCODING=utf-8 python run_all.py --phase 1
  仅阶段2:         PYTHONIOENCODING=utf-8 python run_all.py --phase 2
  仅后续处理:      PYTHONIOENCODING=utf-8 python run_all.py --post
"""
import json
import time
import urllib.request
import urllib.error
import sys
import threading
import os
import argparse
import subprocess
import hashlib
from datetime import datetime

CONFIG = {
    'username': os.environ.get('ADHOC_USERNAME', 'dengyuting02'),
    'token': os.environ.get('ADHOC_TOKEN', ''),
    'baseUrl': 'https://berserker.bilibili.co'
}

if not CONFIG['token']:
    print('错误：未设置环境变量 ADHOC_TOKEN（adhoc 平台 token）', file=sys.stderr)
    print('Windows PowerShell 临时设置：$env:ADHOC_TOKEN="your_token"', file=sys.stderr)
    sys.exit(1)

BASE_DIR = 'C:/Users/dengyuting02/WorkBuddy/20260514140206'
PROGRESS_FILE = f'{BASE_DIR}/.progress.json'

# ============================================================
# 进度文件写入
# ============================================================
def write_progress(phase, phase_name, status='running', progress=None, message=None, extra=None):
    """写入进度文件，供外部随时查询当前状态"""
    data = {
        'status': status,
        'phase': phase,
        'phase_name': phase_name,
        'progress': progress,
        'message': message or f'{phase_name} 进行中',
        'started_at': datetime.now().isoformat(timespec='seconds'),
        'last_update': datetime.now().isoformat(timespec='seconds'),
    }
    if extra:
        data.update(extra)
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def clear_progress():
    """清理进度文件"""
    try:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
    except Exception:
        pass

# ============================================================
# 通用工具
# ============================================================
def api_request(url, method='GET', data=None, retries=None):
    """调用 Adhoc API。

    GET（状态/结果轮询）是幂等的，默认重试4次，避免偶发网络抖动打断已跑几十分钟的查询；
    POST（提交查询）不重试，防止同一条SQL被重复提交。
    """
    if retries is None:
        retries = 4 if method == 'GET' else 1
    headers = {
        'Adhoc-Username': CONFIG['username'],
        'Adhoc-Token': CONFIG['token'],
        'Content-Type': 'application/json; charset=utf-8',
    }
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f'  ! API请求失败({attempt}/{retries})，{5 * attempt}s后重试: {e}', file=sys.stderr)
                time.sleep(5 * attempt)
    raise last_err

def milestone(msg):
    """打印大阶段里程碑"""
    print('\n' + '=' * 60, file=sys.stderr)
    print(f'  {msg}', file=sys.stderr)
    print('=' * 60, file=sys.stderr)

def step(msg):
    """打印步骤信息"""
    print(f'  → {msg}', file=sys.stderr)

def submit_and_wait(label, sql, output_path, timeout=1800, phase_info=None):
    print(f'  → [{label}] 提交查询 ({len(sql)} chars)...', file=sys.stderr)
    resp = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/execute",
                       method='POST', data={'sqlCommand': sql, 'engineType': 19})
    if resp.get('code') != 200:
        print(f'  ✗ [{label}] 提交失败: {json.dumps(resp, ensure_ascii=False)}', file=sys.stderr)
        return None
    query_id = resp['data']['queryId']
    print(f'  → [{label}] Query ID: {query_id}', file=sys.stderr)
    elapsed = 0
    last_status = None
    names = {1: 'SUCCESS', 2: 'FAILED', 3: 'RUNNING', 4: 'QUEUED', 5: 'STOPPED'}
    while elapsed < timeout:
        status_resp = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/status/{query_id}")
        status = status_resp.get('data')
        # 平台异常时 data 可能是 dict/None（2026-W36 遇到 HTTP 500 重试后返回错误信封），
        # 直接丢给 names.get() 会因 dict 不可哈希抛 TypeError 把整个线程打死。当成一次抖动继续轮询。
        if not isinstance(status, int):
            print(f'  ! [{label}] 状态返回异常，继续轮询: '
                  f'{json.dumps(status_resp, ensure_ascii=False)[:200]}', file=sys.stderr)
            time.sleep(10)
            elapsed += 10
            continue
        status_name = names.get(status, f'UNKNOWN({status})')
        if status != last_status:
            print(f'  → [{label}] [{elapsed}s] {status_name}', file=sys.stderr)
            last_status = status
        else:
            if elapsed > 0 and elapsed % 60 == 0:
                print(f'  → [{label}] 仍在查询中... 已等待 {elapsed//60} 分钟', file=sys.stderr)
                # 每60秒更新进度
                if phase_info:
                    write_progress(
                        phase_info.get('phase', 1),
                        phase_info.get('phase_name', 'Adhoc查询'),
                        progress=phase_info.get('progress'),
                        message=f"{label} {status_name} 中，已等待 {elapsed//60} 分钟，Query ID: {query_id}",
                        extra=phase_info.get('extra', {})
                    )
        if status == 1:
            result = api_request(f"{CONFIG['baseUrl']}/api/adhoc/outer/v2/sql/result/{query_id}")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            rows = len(result.get('data', {}).get('result', []))
            print(f'  ✓ [{label}] 完成 - {rows} 行 -> {output_path}', file=sys.stderr)
            return result
        if status == 2:
            print(f'  ✗ [{label}] 查询失败', file=sys.stderr)
            return None
        if status == 5:
            print(f'  ✗ [{label}] 平台终止', file=sys.stderr)
            return None
        time.sleep(10)
        elapsed += 10
    print(f'  ✗ [{label}] 超时 ({timeout}s)', file=sys.stderr)
    return None

# ============================================================
# 代码1~6 SQL 构建与执行
# ============================================================
def run_code1():
    with open(f'{BASE_DIR}/code1_up_rank.sql', 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return submit_and_wait('代码1-新星UP榜', sql, f'{BASE_DIR}/result_code1_up_rank.json', timeout=3600)

def run_code6():
    with open(f'{BASE_DIR}/code6_darkhorse.sql', 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return submit_and_wait('代码6-黑马UP榜', sql, f'{BASE_DIR}/result_code6_darkhorse.json', timeout=3600)

def build_code2_sql(in_clause):
    with open(f'{BASE_DIR}/code2_daily_gmv_vv.sql', 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

def build_code3_sql(in_clause):
    with open(f'{BASE_DIR}/code3_arch_charge.sql', 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

def build_code4_sql(in_clause):
    with open(f'{BASE_DIR}/code4_top3_fans.sql', 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    return sql.replace('{IN_CLAUSE}', in_clause)

def build_code5_sql():
    with open(f'{BASE_DIR}/code5_penetration.sql', 'r', encoding='utf-8') as f:
        return f.read().strip()

# ============================================================
# 阶段1: 并行执行代码1 + 代码6
# ============================================================
PHASE1_META = f'{BASE_DIR}/.phase1_meta.json'

def save_phase1_meta(up_ids_new, up_ids_dark):
    meta = {'up_ids_new': up_ids_new, 'up_ids_dark': up_ids_dark}
    with open(PHASE1_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f'  → 阶段1元数据已保存', file=sys.stderr)

def load_phase1_meta():
    if not os.path.exists(PHASE1_META):
        print(f'  ✗ 找不到阶段1元数据文件', file=sys.stderr)
        sys.exit(1)
    with open(PHASE1_META, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_phase1():
    milestone('阶段1: 并行查询新星榜 + 黑马榜')
    write_progress(1, '阶段1 Adhoc查询', progress='0/2', message='并行查询code1(新星榜)+code6(黑马榜)')

    results = {}
    def _run_and_store(key, fn):
        try:
            results[key] = fn()
        except Exception:
            # 线程里的异常不会传播到主线程，必须自己打出来，否则只剩一句"失败"无从排查
            import traceback
            print(f'  ✗ [{key}] 线程异常:\n{traceback.format_exc()}', file=sys.stderr)
            results[key] = None

    threads = [
        threading.Thread(target=_run_and_store, args=('code1', run_code1)),
        threading.Thread(target=_run_and_store, args=('code6', run_code6)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result1 = results.get('code1')
    result6 = results.get('code6')

    if not result1:
        print('  ✗ 代码1失败，终止执行', file=sys.stderr)
        write_progress(1, '阶段1 Adhoc查询', status='error', message='代码1(新星榜)查询失败，终止执行')
        sys.exit(1)

    up_ids_new = [str(r['up_id']) for r in result1['data']['result']]
    print(f'  ✓ 新星榜: {len(up_ids_new)} 个UP', file=sys.stderr)

    up_ids_dark = []
    if result6:
        up_ids_dark = [str(r['up_id']) for r in result6['data']['result']]
        print(f'  ✓ 黑马榜: {len(up_ids_dark)} 个UP', file=sys.stderr)
    else:
        print('  ⚠ 黑马榜无结果', file=sys.stderr)

    save_phase1_meta(up_ids_new, up_ids_dark)
    write_progress(1, '阶段1 Adhoc查询', progress='2/2', message=f'code1({len(up_ids_new)}个UP)+code6({len(up_ids_dark)}个UP)完成')
    return up_ids_new, up_ids_dark

# ============================================================
# 阶段2: 并行执行代码2~5
# ============================================================
def run_phase2(up_ids_new, up_ids_dark):
    milestone('阶段2: 并行查询明细数据 (code2~5)')
    write_progress(2, '阶段2 Adhoc查询', progress='0/4', message='并行查询code2~5(日维度GMV/VV/稿件/共粉/渗透率)')

    in_clause_new = ', '.join(up_ids_new)
    up_ids_all = list(dict.fromkeys(up_ids_new + up_ids_dark))
    in_clause_all = ', '.join(up_ids_all)
    print(f'  → 新星UP: {len(up_ids_new)} 个, 并集UP: {len(up_ids_all)} 个', file=sys.stderr)

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

    # 数据校验
    print('  → 阶段2数据校验:', file=sys.stderr)
    completed = 0
    for code, path, desc in [
        ('code2', f'{BASE_DIR}/result_code2_daily_gmv_vv.json', '日维度GMV_VV'),
        ('code3', f'{BASE_DIR}/result_code3_arch_charge.json', '稿件充电明细'),
        ('code4', f'{BASE_DIR}/result_code4_top3_fans.json', 'Top3共粉UP'),
        ('code5', f'{BASE_DIR}/result_code5_penetration.json', '分区渗透率'),
    ]:
        if not os.path.exists(path):
            print(f'    ✗ {desc}: 文件不存在', file=sys.stderr)
            continue
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        rows = d.get('data', {}).get('result', [])
        print(f'    ✓ {desc}: {len(rows)} 行', file=sys.stderr)
        completed += 1
    
    write_progress(2, '阶段2 Adhoc查询', progress=f'{completed}/4', message=f'code2~5完成{completed}/4个查询')

# ============================================================
# 阶段3: 更新上榜次数
# ============================================================
def run_phase3():
    milestone('阶段3: 更新上榜次数')
    write_progress(3, '阶段3 更新上榜次数', progress='0/1', message='运行update_board_count.py')
    result = subprocess.run(
        [sys.executable, f'{BASE_DIR}/update_board_count.py'],
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f'  {line}', file=sys.stderr)
    if result.returncode != 0:
        print(f'  ✗ 上榜次数更新失败', file=sys.stderr)
        if result.stderr:
            print(f'  {result.stderr}', file=sys.stderr)
    else:
        print('  ✓ 上榜次数更新完成', file=sys.stderr)
    write_progress(3, '阶段3 更新上榜次数', progress='1/1', message='上榜次数更新完成')

# ============================================================
# 阶段4: LLM内容总结（带进度监控）
# ============================================================
import re

def parse_llm_progress(lines):
    """从 api_run.log 中解析 LLM 进度"""
    # 查找 "[N/M]" 格式的进度
    for line in reversed(lines):
        m = re.search(r'\[(\d+)/(\d+)\]', line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return 0, 0

def run_phase4():
    milestone('阶段4: LLM内容总结（增量更新）')
    write_progress(4, '阶段4 LLM内容总结', progress='0/0', message='启动run_api.py，分析待重跑UP数量')

    # 启动子进程运行 run_api.py
    proc = subprocess.Popen(
        [sys.executable, f'{BASE_DIR}/run_api.py'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', bufsize=1
    )

    # 同时监控 api_run.log 的进度
    log_path = f'{BASE_DIR}/api_run.log'
    last_line_count = 0
    last_progress_print = 0
    start_time = time.time()

    # 等待子进程完成，同时定期打印进度
    while proc.poll() is None:
        # 每5秒检查一次日志
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                current_count = len(lines)
                if current_count != last_line_count:
                    # 打印新增加的日志行
                    for line in lines[last_line_count:current_count]:
                        line = line.rstrip()
                        if line.strip():
                            print(f'  {line}', file=sys.stderr)
                    last_line_count = current_count
                    
                    # 解析进度并更新 .progress.json
                    current, total = parse_llm_progress(lines)
                    if total > 0:
                        write_progress(
                            4, '阶段4 LLM内容总结',
                            progress=f'{current}/{total}',
                            message=f'LLM处理中 {current}/{total} ({current*100//total}%)'
                        )
            except Exception:
                pass

        # 每30秒打印一次心跳
        elapsed = time.time() - start_time
        if elapsed - last_progress_print >= 30:
            print(f'  → LLM仍在运行中... 已等待 {int(elapsed)} 秒', file=sys.stderr)
            last_progress_print = elapsed

        time.sleep(2)

    # 子进程结束，打印剩余日志
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines[last_line_count:]:
                line = line.rstrip()
                if line.strip():
                    print(f'  {line}', file=sys.stderr)
        except Exception:
            pass

    # 打印子进程最终输出
    stdout, stderr = proc.communicate()
    if stdout:
        for line in stdout.strip().split('\n'):
            if line.strip():
                print(f'  {line}', file=sys.stderr)

    if proc.returncode != 0:
        print(f'  ✗ LLM内容总结失败', file=sys.stderr)
        if stderr:
            print(f'  {stderr}', file=sys.stderr)
        write_progress(4, '阶段4 LLM内容总结', status='error', message='LLM内容总结失败')
    else:
        print('  ✓ LLM内容总结完成', file=sys.stderr)
        # 解析最终完成数量
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            current, total = parse_llm_progress(lines)
            if total > 0:
                write_progress(4, '阶段4 LLM内容总结', progress=f'{total}/{total}', message=f'LLM完成 {total}/{total}')
            else:
                write_progress(4, '阶段4 LLM内容总结', progress='1/1', message='LLM完成（无需重跑）')
        except Exception:
            write_progress(4, '阶段4 LLM内容总结', progress='1/1', message='LLM完成')

# ============================================================
# 阶段5: 热点主题
# ============================================================
def run_phase5():
    milestone('阶段5: 生成热点主题')
    write_progress(5, '阶段5 生成热点主题', progress='0/1', message='运行gen_hot_topics.py')
    result = subprocess.run(
        [sys.executable, f'{BASE_DIR}/gen_hot_topics.py'],
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f'  {line}', file=sys.stderr)
    if result.returncode != 0:
        print(f'  ✗ 热点主题生成失败', file=sys.stderr)
        if result.stderr:
            print(f'  {stderr}', file=sys.stderr)
    else:
        print('  ✓ 热点主题生成完成', file=sys.stderr)
    write_progress(5, '阶段5 生成热点主题', progress='1/1', message='热点主题生成完成')

# ============================================================
# 阶段6: HTML生成
# ============================================================
def run_phase6():
    milestone('阶段6: 生成HTML看板')
    write_progress(6, '阶段6 生成HTML看板', progress='0/1', message='运行build_dashboard.py')
    result = subprocess.run(
        [sys.executable, f'{BASE_DIR}/build_dashboard.py'],
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f'  {line}', file=sys.stderr)
    if result.returncode != 0:
        print(f'  ✗ HTML生成失败', file=sys.stderr)
        if result.stderr:
            print(f'  {stderr}', file=sys.stderr)
    else:
        print('  ✓ HTML看板生成完成', file=sys.stderr)
    write_progress(6, '阶段6 生成HTML看板', progress='1/1', message='HTML看板生成完成')

# ============================================================
# 阶段7: Git推送
# ============================================================
def run_phase7():
    milestone('阶段7: Git推送')
    write_progress(7, '阶段7 Git推送', progress='0/1', message='执行git add/commit/push')
    
    # 获取当前ISO周编号
    today = datetime.now()
    iso_year, iso_week, _ = today.isocalendar()
    week_str = f'{iso_year}-W{iso_week:02d}'
    
    # git add
    result_add = subprocess.run(
        ['git', 'add', '-A'],
        cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8'
    )
    if result_add.returncode != 0:
        print(f'  ✗ git add 失败', file=sys.stderr)
        write_progress(7, '阶段7 Git推送', status='error', message='git add 失败')
        return
    
    # 检查是否有变更需要提交
    result_status = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8'
    )
    if not result_status.stdout.strip():
        print(f'  → 无文件变更，跳过Git推送', file=sys.stderr)
        write_progress(7, '阶段7 Git推送', progress='1/1', message='无文件变更，跳过Git推送')
        return
    
    # git commit
    commit_msg = f'feat: 更新{week_str}周榜数据'
    result_commit = subprocess.run(
        ['git', 'commit', '-m', commit_msg],
        cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8'
    )
    if result_commit.returncode != 0:
        print(f'  ✗ git commit 失败', file=sys.stderr)
        if result_commit.stderr:
            print(f'  {result_commit.stderr}', file=sys.stderr)
        write_progress(7, '阶段7 Git推送', status='error', message='git commit 失败')
        return
    
    # git push
    result_push = subprocess.run(
        ['git', 'push', 'origin', 'main'],
        cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8'
    )
    if result_push.returncode != 0:
        print(f'  ✗ git push 失败', file=sys.stderr)
        if result_push.stderr:
            print(f'  {result_push.stderr}', file=sys.stderr)
        write_progress(7, '阶段7 Git推送', status='error', message='git push 失败')
        return
    
    print(f'  ✓ Git推送完成: {commit_msg}', file=sys.stderr)
    write_progress(7, '阶段7 Git推送', progress='1/1', message=f'Git推送完成: {commit_msg}')

# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='UP主充电榜单全自动流水线')
    parser.add_argument('--phase', type=int, choices=[1, 2], default=None,
                        help='仅运行指定Adhoc阶段')
    parser.add_argument('--full', action='store_true',
                        help='全流程模式：Adhoc查询 + 后续处理（上榜次数/LLM/热点/HTML）')
    parser.add_argument('--post', action='store_true',
                        help='仅运行后续处理（上榜次数/LLM/热点/HTML），跳过Adhoc查询')
    args = parser.parse_args()

    if args.phase == 1:
        run_phase1()
    elif args.phase == 2:
        meta = load_phase1_meta()
        run_phase2(meta['up_ids_new'], meta.get('up_ids_dark', []))
    elif args.post:
        # 仅后续处理
        meta = load_phase1_meta()
        run_phase3()
        run_phase4()
        run_phase5()
        run_phase6()
    elif args.full:
        # 全流程模式
        clear_progress()  # 清理旧进度
        milestone('开始执行充电UP主榜单全流程')
        print(f'  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', file=sys.stderr)
        print(f'  目录: {BASE_DIR}', file=sys.stderr)
        print('', file=sys.stderr)

        # 阶段1: Adhoc主表查询
        up_ids_new, up_ids_dark = run_phase1()

        # 阶段2: Adhoc明细查询
        run_phase2(up_ids_new, up_ids_dark)

        # 阶段3: 更新上榜次数
        run_phase3()

        # 阶段4: LLM内容总结
        run_phase4()

        # 阶段5: 热点主题
        run_phase5()

        # 阶段6: HTML生成
        run_phase6()

        # 阶段7: Git推送
        run_phase7()

        milestone('全部完成!')
        write_progress(8, '全部完成', status='completed', message='周榜更新全部完成，Git推送成功')
        print(f'  HTML文件: {BASE_DIR}/charging_up_dashboard.html', file=sys.stderr)
        print(f'  完成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', file=sys.stderr)
    else:
        # 默认：仅Adhoc查询（兼容旧模式）
        up_ids_new, up_ids_dark = run_phase1()
        run_phase2(up_ids_new, up_ids_dark)
        milestone('Adhoc查询全部完成!')

if __name__ == '__main__':
    main()
