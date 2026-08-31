"""充电UP周榜 · 无人值守全流程驱动

由 Windows 计划任务调用，不依赖 Claude 会话。串行执行 6 个阶段后提交并推送。

内置三类故障自愈（都是 2026-W31~W34 实际踩过的坑）：
  1. 阶段1 code6 线程被网络异常打断，但服务端查询仍在跑
     → 从日志提取 Query ID 直接拉结果，并回填 .phase1_meta.json 的 up_ids_dark
  2. run_api.py 整体挂起（挂起连接绕过 timeout，日志停滞但不报错）
     → 监控 api_run.log mtime，停滞超阈值就按 PID 杀掉重启，靠 checkpoint 续跑
  3. Adhoc 集群慢 / 偶发抖动
     → run_all.py 内部已有 3600s 等待上限与 GET 重试，这里只做整体重试

用法:
  python auto_weekly_update.py              # 正常全流程
  python auto_weekly_update.py --dry-run    # 只校验环境，不跑查询、不提交
  python auto_weekly_update.py --no-push    # 跑完只本地 commit，不 push
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, date, timedelta

BASE = r'C:\Users\dengyuting02\WorkBuddy\20260514140206'
PYTHON = sys.executable
TOKEN_FILE = os.path.join(BASE, '学claude', '.adhoc_token')
PHASE1_META = os.path.join(BASE, '.phase1_meta.json')
API_LOG = os.path.join(BASE, 'api_run.log')
LOG_DIR = os.path.join(BASE, 'log')

ADHOC_BASE = 'https://berserker.bilibili.co'
ADHOC_USER = 'dengyuting02'

# run_api.py 日志停滞多久算挂起（秒），以及最多重启几次
API_STALL_SEC = 240
API_MAX_RESTART = 8
# 阶段1/2 整体最多尝试几次
PHASE_MAX_ATTEMPT = 2

DATA_FILES = [
    'board_count.json',
    'board_count_dark.json',
    'charging_up_dashboard.html',
    'hot_topics.json',
    'result_code1_up_rank.json',
    'result_code2_daily_gmv_vv.json',
    'result_code3_arch_charge.json',
    'result_code4_top3_fans.json',
    'result_code5_penetration.json',
    'result_code6_darkhorse.json',
    'up_summaries.json',
]

_log_fh = None


def log(msg):
    line = f'[{datetime.now().strftime("%H:%M:%S")}] {msg}'
    print(line, flush=True)
    if _log_fh:
        _log_fh.write(line + '\n')
        _log_fh.flush()


def open_log():
    global _log_fh
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f'auto_weekly_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    _log_fh = open(path, 'w', encoding='utf-8')
    return path


def expected_period():
    """周编号按运行当天所属 ISO 周算（与 update_board_count.py 一致，W32/33/34 已验证）"""
    y, w, _ = date.today().isocalendar()
    return f'{y}-W{w:02d}'


def child_env():
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
        env['ADHOC_TOKEN'] = f.read().strip()
    return env


def run_step(args, label, timeout=7200):
    """跑一个子进程，输出实时转存到日志。返回 (returncode, 完整输出)"""
    log(f'▶ {label}: {" ".join(args)}')
    proc = subprocess.Popen(
        [PYTHON] + args, cwd=BASE, env=child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', bufsize=1,
    )
    chunks = []
    deadline = time.time() + timeout
    for line in proc.stdout:
        chunks.append(line)
        s = line.rstrip()
        # 只把关键行写进汇总日志，避免几千行噪音
        if any(k in s for k in ('✓', '✗', '⚠', 'Query ID', 'SUCCESS', 'FAILED', '完成', '错误', 'Error', 'Traceback')):
            log(f'   {s}')
        if time.time() > deadline:
            proc.kill()
            log(f'✗ {label} 超过 {timeout}s，已终止')
            break
    proc.wait()
    out = ''.join(chunks)
    log(f'{"✓" if proc.returncode == 0 else "✗"} {label} 结束 (exit={proc.returncode})')
    return proc.returncode, out


# ============================================================
# 阶段1 及其自愈
# ============================================================
def adhoc_get(path, retries=5):
    token = child_env()['ADHOC_TOKEN']
    headers = {
        'Adhoc-Username': ADHOC_USER,
        'Adhoc-Token': token,
        'Content-Type': 'application/json; charset=utf-8',
    }
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(f'{ADHOC_BASE}{path}', headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            last = e
            log(f'   ! Adhoc 请求失败({i + 1}/{retries}): {e}')
            time.sleep(5 * (i + 1))
    raise last


def load_meta():
    with open(PHASE1_META, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_meta(meta):
    with open(PHASE1_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def recover_query(qid, label, out_name):
    """线程崩了但服务端查询可能已完成：用 Query ID 直接捞结果，返回 up_id 列表"""
    log(f'→ 尝试用 Query ID {qid} 直接拉取 {label} 结果（不重跑）')
    names = {1: 'SUCCESS', 2: 'FAILED', 3: 'RUNNING', 4: 'QUEUED', 5: 'STOPPED'}
    waited = 0
    while waited < 3600:
        status = adhoc_get(f'/api/adhoc/outer/v2/sql/status/{qid}').get('data')
        if not isinstance(status, int):
            log(f'   [{waited}s] 状态返回异常，继续等')
        else:
            log(f'   [{waited}s] {names.get(status, status)}')
            if status == 1:
                result = adhoc_get(f'/api/adhoc/outer/v2/sql/result/{qid}')
                with open(os.path.join(BASE, out_name), 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                ids = [str(r['up_id']) for r in result.get('data', {}).get('result', [])]
                log(f'✓ {label} 补救成功 {len(ids)} 个UP')
                return ids
            if status in (2, 5):
                log(f'✗ {label} 查询状态 {names.get(status)}，无法补救')
                return None
        time.sleep(15)
        waited += 15
    log(f'✗ 等待 {label} 结果超时')
    return None


def phase1():
    boards = (
        ('up_ids_new', '代码1-新星UP榜', 'result_code1_up_rank.json'),
        ('up_ids_dark', '代码6-黑马UP榜', 'result_code6_darkhorse.json'),
    )
    for attempt in range(1, PHASE_MAX_ATTEMPT + 1):
        t0 = time.time()
        rc, out = run_step(['run_all.py', '--phase', '1'], f'阶段1 取数(第{attempt}次)')

        # 关键校验：meta 必须是本次运行写的。run_all.py 失败时不会重写它，
        # 沿用上一周的 UP 列表会产出"榜单数据没变、上榜次数照样+1"的错榜（2026-W36 踩过）。
        fresh = os.path.exists(PHASE1_META) and os.path.getmtime(PHASE1_META) >= t0
        if fresh:
            meta = load_meta()
        else:
            meta = {}
            log('⚠ .phase1_meta.json 未被本次运行重写，判定阶段1未成功（绝不沿用旧UP列表）')

        # 任一榜为空：服务端查询可能其实成功了，只是客户端线程崩了，用 Query ID 直接捞
        for key, label, fname in boards:
            if meta.get(key):
                continue
            m = re.search(rf'\[{re.escape(label)}\] Query ID: (\d+)', out)
            if not m:
                log(f'✗ 日志里找不到 {label} 的 Query ID，无法补救')
                continue
            ids = recover_query(m.group(1), label, fname)
            if ids:
                meta[key] = ids
                save_meta(meta)
                log(f'   已回填 .phase1_meta.json[{key}]')

        new_ids = meta.get('up_ids_new') or []
        dark_ids = meta.get('up_ids_dark') or []
        if new_ids and dark_ids:
            log(f'✓ 阶段1 完成：新星 {len(new_ids)}，黑马 {len(dark_ids)}')
            return True
        log(f'⚠ 阶段1 第{attempt}次未拿到完整结果'
            f'（新星 {len(new_ids)}，黑马 {len(dark_ids)}）')
    return False


# ============================================================
# 阶段4 run_api.py 挂起看门狗
# ============================================================
def api_summaries_ok():
    """检查 up_summaries.json 是否已无错误条目"""
    path = os.path.join(BASE, 'up_summaries.json')
    if not os.path.exists(path):
        return False, -1
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    summaries = d.get('summaries', d)
    bad = [uid for uid, v in summaries.items()
           if str((v or {}).get('summary', '')).startswith(('[API', '[异常', '[超时'))]
    return len(bad) == 0, len(bad)


def kill_pid(pid):
    subprocess.run(
        ['powershell', '-NoProfile', '-Command', f'Stop-Process -Id {pid} -Force'],
        capture_output=True, text=True,
    )


def run_api_with_watchdog():
    """跑 run_api.py，日志停滞就按 PID 杀掉重启（每10个UP有checkpoint，可续跑）"""
    for restart in range(1, API_MAX_RESTART + 1):
        log(f'▶ 阶段4 LLM总结(第{restart}次启动)')
        proc = subprocess.Popen(
            [PYTHON, 'run_api.py'], cwd=BASE, env=child_env(),
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        stalled = False
        while proc.poll() is None:
            time.sleep(20)
            if not os.path.exists(API_LOG):
                continue
            idle = time.time() - os.path.getmtime(API_LOG)
            if idle > API_STALL_SEC:
                log(f'⚠ api_run.log 停滞 {int(idle)}s，判定挂起，终止 PID {proc.pid} 后续跑')
                kill_pid(proc.pid)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    pass
                stalled = True
                break
        if stalled:
            continue
        ok, bad = api_summaries_ok()
        log(f'   run_api.py 退出 (exit={proc.returncode})，剩余错误条目: {bad}')
        if ok:
            log('✓ 阶段4 完成，无错误条目')
            return True
        log('⚠ 仍有错误条目，重跑一轮（增量逻辑只会补跑出错的UP）')
    log('✗ 阶段4 达到最大重启次数仍未干净收尾')
    return False


# ============================================================
# 校验与提交
# ============================================================
def validate():
    period = expected_period()
    problems = []
    for f, key in (('board_count.json', '新星'), ('board_count_dark.json', '黑马')):
        p = os.path.join(BASE, f)
        if not os.path.exists(p):
            problems.append(f'{f} 不存在')
            continue
        d = json.load(open(p, encoding='utf-8'))
        got = d.get('_meta', {}).get('last_update_period')
        cnt = len(d.get('counts', d))
        log(f'   {key}榜 {f}: period={got}, {cnt} 个UP')
        if got != period:
            problems.append(f'{f} 周期 {got} != 预期 {period}')
    html = os.path.join(BASE, 'charging_up_dashboard.html')
    if not os.path.exists(html):
        problems.append('charging_up_dashboard.html 不存在')
    else:
        age_min = (time.time() - os.path.getmtime(html)) / 60
        size_kb = os.path.getsize(html) // 1024
        log(f'   看板: {size_kb} KB, {age_min:.0f} 分钟前生成')
        if age_min > 180:
            problems.append(f'看板 HTML 太旧({age_min:.0f} 分钟前)，可能未重新生成')
    return problems


def git(*args, check=False):
    r = subprocess.run(['git'] + list(args), cwd=BASE,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} 失败: {r.stderr.strip()}')
    return r


def commit_and_push(do_push=True):
    period = expected_period()
    progress = os.path.join(BASE, '.progress.json')
    if os.path.exists(progress):
        os.remove(progress)

    existing = [f for f in DATA_FILES if os.path.exists(os.path.join(BASE, f))]
    missing = set(DATA_FILES) - set(existing)
    if missing:
        log(f'⚠ 缺少数据文件，跳过提交: {sorted(missing)}')
        return False
    # 只 add 这 11 个文件：仓库里有大量无关未跟踪文件，绝不能 git add -A
    git('add', *existing, check=True)
    if not git('diff', '--cached', '--quiet').returncode:
        log('→ 数据无变化，无需提交')
        return True
    r = git('commit', '-m', f'feat: 更新{period}周榜数据')
    if r.returncode != 0:
        log(f'✗ commit 失败: {r.stdout.strip()} {r.stderr.strip()}')
        return False
    head = git('rev-parse', '--short', 'HEAD').stdout.strip()
    log(f'✓ 已提交 {head}: feat: 更新{period}周榜数据')

    if not do_push:
        log('→ --no-push，已保留本地提交')
        return True
    r = git('push', 'origin', 'main')
    combined = (r.stdout + r.stderr)
    if r.returncode == 0 or 'main -> main' in combined:
        log(f'✓ 已推送到 origin/main（credential-manager-core 警告可忽略）')
        return True
    log(f'✗ push 失败，提交已保留在本地，下次登录后可手动 git push origin main')
    log(f'   {combined.strip()[:500]}')
    return False


def preflight():
    problems = []
    if not os.path.exists(TOKEN_FILE):
        problems.append(f'缺少 token 文件 {TOKEN_FILE}')
    elif not open(TOKEN_FILE, encoding='utf-8').read().strip():
        problems.append('token 文件为空')
    for f in ('run_all.py', 'update_board_count.py', 'run_api.py',
              'gen_hot_topics.py', 'build_dashboard.py'):
        if not os.path.exists(os.path.join(BASE, f)):
            problems.append(f'缺少脚本 {f}')
    if git('rev-parse', '--git-dir').returncode != 0:
        problems.append('不是 git 仓库')
    branch = git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    if branch != 'main':
        problems.append(f'当前分支是 {branch}，不是 main')
    return problems


def main():
    dry = '--dry-run' in sys.argv
    do_push = '--no-push' not in sys.argv
    path = open_log()
    started = datetime.now()
    log('=' * 60)
    log(f'充电UP周榜无人值守更新 · 目标周期 {expected_period()}')
    log(f'日志: {path}')
    log(f'Python: {PYTHON}')
    log('=' * 60)

    problems = preflight()
    if problems:
        for p in problems:
            log(f'✗ 环境检查: {p}')
        sys.exit(1)
    log('✓ 环境检查通过（token / 脚本 / git 分支）')

    if dry:
        log('→ --dry-run：跳过取数、LLM、提交')
        log(f'   数据文件齐全: {all(os.path.exists(os.path.join(BASE, f)) for f in DATA_FILES)}')
        log(f'   git 用户: {git("config", "user.name").stdout.strip()}')
        log('✓ dry-run 结束')
        return

    if not phase1():
        log('✗ 阶段1 失败，终止（黑马榜或新星榜缺数据，继续跑会产出错误看板）')
        sys.exit(1)

    ok2 = False
    for attempt in range(1, PHASE_MAX_ATTEMPT + 1):
        rc, _ = run_step(['run_all.py', '--phase', '2'], f'阶段2 明细取数(第{attempt}次)')
        if rc == 0:
            ok2 = True
            break
    if not ok2:
        log('✗ 阶段2 失败，终止')
        sys.exit(1)

    rc, _ = run_step(['update_board_count.py'], '阶段3 上榜次数')
    if rc != 0:
        log('✗ 阶段3 失败，终止')
        sys.exit(1)

    if not run_api_with_watchdog():
        log('⚠ 阶段4 未完全干净，仍继续生成看板（错误条目会显示为占位文本）')

    rc, _ = run_step(['gen_hot_topics.py'], '阶段5 热点主题')
    if rc != 0:
        log('⚠ 阶段5 失败，沿用上周 hot_topics.json 继续')

    rc, _ = run_step(['build_dashboard.py'], '阶段6 看板生成')
    if rc != 0:
        log('✗ 阶段6 失败，终止（无新看板可提交）')
        sys.exit(1)

    log('▶ 校验产出')
    problems = validate()
    if problems:
        for p in problems:
            log(f'✗ 校验: {p}')
        log('✗ 校验未通过，不提交。请人工检查后再决定是否 push')
        sys.exit(1)
    log('✓ 校验通过')

    log('▶ 提交并推送')
    pushed = commit_and_push(do_push)

    mins = (datetime.now() - started).total_seconds() / 60
    log('=' * 60)
    log(f'{"✓ 全流程完成" if pushed else "⚠ 流程结束但推送未成功"} · 耗时 {mins:.0f} 分钟')
    log('=' * 60)
    sys.exit(0 if pushed else 2)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        log('✗ 未捕获异常:')
        for line in traceback.format_exc().splitlines():
            log(f'   {line}')
        sys.exit(1)
