"""
充电UP主分析看板 — 完整流水线
============================
一键跑完全流程：取数 → 累计 → LLM → 热点 → HTML → Git推送

用法:
  python run_pipeline.py           # 标准全流程
  python run_pipeline.py --skip-api  # 跳过LLM API调用（快速测试）
  python run_pipeline.py --force    # LLM强制全量重跑

前置条件:
  1. 环境变量 ADHOC_TOKEN 已设置（或 ~/.workbuddy/adhoc-config.json 存在）
  2. 当前目录是项目根目录（包含所有 SQL/py 文件）
  3. git remote 已配置

流水线步骤:
  ① run_all.py --phase 1    → 取主表（code1新星 + code6黑马）
  ② run_all.py --phase 2    → 取明细（code2~5）
  ③ update_board_count.py   → 周累计上榜次数
  ④ run_api.py              → LLM内容总结（仅新星UP，增量）
  ⑤ gen_hot_topics.py       → UP热点主题
  ⑥ build_dashboard.py      → 生成双Tab HTML
  ⑦ git add + commit + push → 推送到GitHub
"""
import subprocess
import sys
import os
import json
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = r'C:\Users\dengyuting02\.workbuddy\binaries\python\versions\3.13.12\python.exe'
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
LOG_FILE = os.path.join(BASE_DIR, 'pipeline.log')

SKIP_API = '--skip-api' in sys.argv
FORCE = '--force' in sys.argv


def log(msg, level='INFO'):
    """打印并写入日志"""
    ts = datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] [{level}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def run(cmd, desc, timeout=1800, check=True):
    """执行shell命令，带超时和错误处理"""
    log(f'▶ {desc}')
    log(f'  命令: {cmd[:120]}...' if len(cmd) > 120 else f'  命令: {cmd}')
    
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=BASE_DIR, env=ENV,
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8'
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        
        # 输出关键日志
        for line in (stdout + '\n' + stderr).split('\n')[-30:]:
            if line.strip():
                log(f'  {line.strip()}', 'OUTPUT')
        
        if check and result.returncode != 0:
            log(f'✗ {desc} 失败 (exit={result.returncode})', 'ERROR')
            if stderr:
                log(f'  stderr: {stderr[:500]}', 'ERROR')
            return False
            
        log(f'✓ {desc} 完成')
        return True
        
    except subprocess.TimeoutExpired:
        log(f'✗ {desc} 超时 ({timeout}s)', 'ERROR')
        return False
    except Exception as e:
        log(f'✗ {desc} 异常: {e}', 'ERROR')
        return False


def read_adhoc_token():
    """从配置文件读取token并设置环境变量"""
    token_path = os.path.expanduser('~/.workbuddy/adhoc-config.json')
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            token = cfg.get('token', '')
            if token:
                ENV['ADHOC_TOKEN'] = token
                log('✓ 从 ~/.workbuddy/adhoc-config.json 读取 ADHOC_TOKEN')
                return True
        except Exception as e:
            log(f'读取token失败: {e}', 'WARN')
    
    if os.environ.get('ADHOC_TOKEN'):
        log('✓ 从环境变量读取 ADHOC_TOKEN')
        return True
    
    log('✗ 未找到 ADHOC_TOKEN', 'ERROR')
    log('  请确保 ~/.workbuddy/adhoc-config.json 存在或设置环境变量', 'ERROR')
    return False


def check_data_integrity():
    """检查关键产出文件的数据完整性"""
    log('▶ 数据完整性检查')
    
    checks = {
        '新星UP主表': 'result_code1_up_rank.json',
        '黑马UP主表': 'result_code6_darkhorse.json',
        '日维度GMV_VV': 'result_code2_daily_gmv_vv.json',
        '稿件充电明细': 'result_code3_arch_charge.json',
        'Top3共粉UP': 'result_code4_top3_fans.json',
        '分区渗透率': 'result_code5_penetration.json',
    }
    
    all_ok = True
    for name, filename in checks.items():
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            log(f'  ✗ {name}: 文件不存在 ({filename})', 'ERROR')
            all_ok = False
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rows = data.get('data', {}).get('result', [])
            row_count = len(rows)
            if row_count == 0:
                log(f'  ✗ {name}: 0行', 'ERROR')
                all_ok = False
            else:
                log(f'  ✓ {name}: {row_count} 行')
        except Exception as e:
            log(f'  ✗ {name}: 解析失败 {e}', 'ERROR')
            all_ok = False
    
    # 检查黑马稿件覆盖率
    try:
        with open(os.path.join(BASE_DIR, 'result_code6_darkhorse.json'), 'r', encoding='utf-8') as f:
            dark_data = json.load(f)
        dark_ups = set(str(r['up_id']) for r in dark_data.get('data', {}).get('result', []))
        
        with open(os.path.join(BASE_DIR, 'result_code3_arch_charge.json'), 'r', encoding='utf-8') as f:
            arch_data = json.load(f)
        arch_rows = arch_data.get('data', {}).get('result', [])
        arch_ups = set(str(r['UP主ID']) for r in arch_rows)
        
        if dark_ups:
            coverage = len(dark_ups & arch_ups) / len(dark_ups) * 100
            log(f'  黑马稿件覆盖率: {coverage:.0f}% ({len(dark_ups & arch_ups)}/{len(dark_ups)})')
            if coverage < 100:
                log(f'  ⚠ 黑马UP有 {len(dark_ups - arch_ups)} 个缺少稿件数据', 'WARN')
    except Exception as e:
        log(f'  黑马覆盖率检查失败: {e}', 'WARN')
    
    return all_ok


def step1_fetch_main():
    """步骤1: 取主表（code1 + code6）"""
    return run(
        f'"{PYTHON}" run_all.py --phase 1',
        '步骤1/7: 取主表（code1新星 + code6黑马）',
        timeout=1800
    )


def step2_fetch_detail():
    """步骤2: 取明细（code2~5）"""
    return run(
        f'"{PYTHON}" run_all.py --phase 2',
        '步骤2/7: 取明细（code2~5）',
        timeout=1200
    )


def step3_board_count():
    """步骤3: 周累计上榜次数"""
    return run(
        f'"{PYTHON}" update_board_count.py',
        '步骤3/7: 周累计上榜次数',
        timeout=60
    )


def step4_llm_summary():
    """步骤4: LLM内容总结"""
    if SKIP_API:
        log('⏭ 跳过LLM API调用 (--skip-api)')
        return True
    
    cmd = f'"{PYTHON}" run_api.py'
    if FORCE:
        cmd += ' --force'
        log('⚡ LLM强制全量重跑 (--force)')
    
    return run(cmd, '步骤4/7: LLM内容总结（仅新星UP，增量）', timeout=600)


def step5_hot_topics():
    """步骤5: UP热点主题"""
    if SKIP_API:
        log('⏭ 跳过热点主题 (--skip-api)')
        return True
    
    return run(
        f'"{PYTHON}" gen_hot_topics.py',
        '步骤5/7: UP热点主题',
        timeout=120
    )


def step6_build_dashboard():
    """步骤6: 生成双Tab HTML"""
    return run(
        f'"{PYTHON}" build_dashboard.py',
        '步骤6/7: 生成双Tab HTML',
        timeout=120
    )


def step7_git_push():
    """步骤7: Git提交并推送"""
    log('▶ 步骤7/7: Git提交并推送')
    
    # 检查是否有变更
    result = subprocess.run(
        'git status --short', shell=True, cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8'
    )
    if not result.stdout.strip():
        log('  ⏭ 无文件变更，跳过git提交')
        return True
    
    # 添加所有变更
    if not run('git add -A', 'Git add', timeout=30):
        return False
    
    # 提交（使用当前日期作为message）
    today = datetime.now().strftime('%Y-%m-%d')
    commit_msg = f'chore: {today} 周榜更新'
    if not run(f'git commit -m "{commit_msg}"', 'Git commit', timeout=30):
        return False
    
    # 推送
    return run('git push origin main', 'Git push', timeout=60)


def main():
    """主流程"""
    start_time = time.time()
    
    # 清屏并打印标题
    print('\n' + '=' * 70)
    print(' 充电UP主分析看板 — 完整流水线')
    print(f' 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70 + '\n')
    
    # 清空日志
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f'Pipeline started at {datetime.now().isoformat()}\n')
    
    # 前置检查
    log('▶ 前置检查')
    if not read_adhoc_token():
        sys.exit(1)
    
    # 检查关键文件是否存在
    required_files = [
        'run_all.py', 'update_board_count.py', 'run_api.py',
        'gen_hot_topics.py', 'build_dashboard.py',
        'code1_up_rank.sql', 'code6_darkhorse.sql'
    ]
    for f in required_files:
        path = os.path.join(BASE_DIR, f)
        if not os.path.exists(path):
            log(f'✗ 缺少必要文件: {f}', 'ERROR')
            sys.exit(1)
    log('✓ 所有必要文件存在')
    
    # 执行7步流水线
    steps = [
        (1, step1_fetch_main),
        (2, step2_fetch_detail),
        (3, step3_board_count),
        (4, step4_llm_summary),
        (5, step5_hot_topics),
        (6, step6_build_dashboard),
        (7, step7_git_push),
    ]
    
    for step_num, step_fn in steps:
        success = step_fn()
        if not success:
            elapsed = time.time() - start_time
            log(f'\n✗ 流水线在步骤{step_num}失败，总耗时 {elapsed:.0f}s', 'ERROR')
            log(f'  详细日志: {LOG_FILE}', 'ERROR')
            sys.exit(1)
        
        # 步骤2后做数据完整性检查
        if step_num == 2:
            if not check_data_integrity():
                log('⚠ 数据完整性检查发现问题，继续执行...', 'WARN')
    
    # 完成
    elapsed = time.time() - start_time
    log('\n' + '=' * 70)
    log(f'✓ 流水线全部完成！总耗时 {elapsed:.0f}s')
    log(f'  日志文件: {LOG_FILE}')
    log('=' * 70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('\n✗ 用户中断', 'ERROR')
        sys.exit(1)
    except Exception as e:
        log(f'\n✗ 流水线异常: {e}', 'ERROR')
        import traceback
        traceback.print_exc()
        sys.exit(1)
