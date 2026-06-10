"""维护 UP 主"上榜次数"（按周计数，以周一为周期起点）。

使用方式：
  python update_board_count.py            # 正常跑：累加本周计数（新星+黑马）
  python update_board_count.py --reset    # 重置：当前榜单UP计数设为1，下周起重新累加

放在 run_all.py 之后、build_dashboard.py 之前。
读 result_code1_up_rank.json 和 result_code6_darkhorse.json 的本期 UP 列表，
分别更新 board_count.json / board_count_dark.json 累加状态，
再把"上榜次数"字段写入对应 JSON 让 dashboard 直接展示。

规则（周粒度，周一为周期起点）：
- 周期为 ISO 周（YYYY-Www），周一至周日同一周期
- 同一周期内重复跑不重复加（幂等：以 _meta.last_update_period 锁定）
- 周二~周日取数不影响该周期已累加的值
- 当前榜单的 UP：
    上次记录是"上一周期" → count + 1（连续在榜）
    没记录或记录更早 → count = 1（新上榜，因脱榜会被清理，重新出现就当新 UP）
- 当前榜单未出现的 UP：直接从 board_count.json 中删掉（脱榜清理）
- --reset 行为：不清零，而是把当前榜单所有UP的计数设为1（本周为起始），下周起在此基础上继续累加
"""
import json
import os
import sys
from datetime import date, timedelta

BASE = r'C:\Users\dengyuting02\WorkBuddy\20260514140206'

GRANULARITY = 'week'   # 'day' | 'week'  ← 按周累计，以周一为周期起点
RESET = '--reset' in sys.argv


def period_str(d: date) -> str:
    if GRANULARITY == 'week':
        y, w, _ = d.isocalendar()
        return f'{y}-W{w:02d}'
    return d.isoformat()  # 'YYYY-MM-DD'


def prev_period(p: str) -> str:
    if GRANULARITY == 'week':
        y, w = p.split('-W')
        monday = date.fromisocalendar(int(y), int(w), 1)
        return period_str(monday - timedelta(days=7))
    d = date.fromisoformat(p)
    return period_str(d - timedelta(days=1))


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_state(count_path):
    if not os.path.exists(count_path):
        return {'_meta': {}, 'counts': {}}
    with open(count_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_state(count_path, state):
    with open(count_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def process_board(up_rank_path, count_path, board_name):
    """处理单个榜单的上榜次数计数与回填。"""
    if not os.path.exists(up_rank_path):
        print(f'⚠ {board_name} 数据文件不存在，跳过: {up_rank_path}')
        return

    up_rank = load_json(up_rank_path)
    rows = up_rank['data']['result']

    if RESET:
        this_period = period_str(date.today())
        new_counts = {}
        for r in rows:
            uid = str(r['up_id'])
            new_counts[uid] = {'count': 1, 'last_period': this_period}
            r['上榜次数'] = 1

        state = {
            'counts': new_counts,
            '_meta': {
                'granularity': GRANULARITY,
                'last_update_period': this_period,
                'updated_at': date.today().isoformat(),
            }
        }
        save_state(count_path, state)
        print(f'✓ [{board_name}] 累加状态已重置: 当前 {len(rows)} 个UP，计数全部设为1（{this_period}）')
        save_json(up_rank_path, up_rank)
        print(f'✓ [{board_name}] 已写入"上榜次数"到: {up_rank_path}')
        return

    state = load_state(count_path)
    this_period = period_str(date.today())
    last_period = prev_period(this_period)
    last_update_period = state['_meta'].get('last_update_period', '')
    prev_granularity = state['_meta'].get('granularity', GRANULARITY)

    if prev_granularity != GRANULARITY:
        print(f'⚠ [{board_name}] 检测到粒度切换 ({prev_granularity} → {GRANULARITY})')
        print(f'  请先执行 python update_board_count.py --reset 再继续。')
        return

    print(f'\n=== {board_name} ===')
    print(f'本期 UP 数:  {len(rows)}')
    print(f'当前周期:    {this_period}')
    print(f'上次更新到:  {last_update_period or "(首次运行)"}')

    old_counts = state.get('counts', {})
    this_uids = {str(r['up_id']) for r in rows}

    if last_update_period == this_period:
        # 同周期重跑：状态不动，只回填字段
        print(f'⚠ 本周期 ({this_period}) 已经累加过，本次只回填字段，不重复加。')
        for r in rows:
            uid = str(r['up_id'])
            entry = old_counts.get(uid)
            r['上榜次数'] = entry['count'] if entry else 1
    else:
        # 新周期：累加 + 清理脱榜
        new_counts = {}
        new_up = 0
        continued = 0

        for r in rows:
            uid = str(r['up_id'])
            prev_entry = old_counts.get(uid)
            if prev_entry and prev_entry.get('last_period') == last_period:
                count = prev_entry['count'] + 1
                continued += 1
            else:
                count = 1
                new_up += 1
            new_counts[uid] = {'count': count, 'last_period': this_period}
            r['上榜次数'] = count

        dropped = len(set(old_counts) - this_uids)

        state['counts'] = new_counts
        state['_meta'] = {
            'granularity': GRANULARITY,
            'last_update_period': this_period,
            'updated_at': date.today().isoformat(),
        }
        save_state(count_path, state)
        print(f'✓ 累加状态已更新: {count_path}')
        print(f'  新上榜（含脱榜重新入榜）: {new_up} 位')
        print(f'  连续在榜（计数+1）:        {continued} 位')
        print(f'  本期脱榜清理:              {dropped} 位')
        print(f'  当前榜单累计跟踪:          {len(new_counts)} 位')

    save_json(up_rank_path, up_rank)
    print(f'✓ 已写入"上榜次数"到: {up_rank_path}')


# ---------- 主流程：新星榜 + 黑马榜 ----------
print(f'计数粒度: {GRANULARITY}')

process_board(
    os.path.join(BASE, 'result_code1_up_rank.json'),
    os.path.join(BASE, 'board_count.json'),
    '新星榜'
)

process_board(
    os.path.join(BASE, 'result_code6_darkhorse.json'),
    os.path.join(BASE, 'board_count_dark.json'),
    '黑马榜'
)
