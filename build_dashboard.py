"""一次性生成双Tab充电看板HTML（不依赖中间文件）

输入：
  result_code1_up_rank.json (UP 榜)
  result_code2_daily_gmv_vv.json (趋势)
  result_code3_arch_charge.json (UP 稿件明细)
  result_code4_top3_fans.json (共粉)
  result_code5_penetration.json (渗透率)
  result_code6_top100.json (Top100 稿件)
  up_summaries.json (UP 内容总结)
  hot_topics.json (UP 热点主题)
  video_hot_topics.json (稿件热点主题)

输出：
  charging_up_dashboard.html （Tab1=新星榜，Tab2=稿件榜）

变量命名约定（避免冲突）：
  Tab1：UPS / TRENDS / VIDEOS / PENE_L1 / UP_TIDS / weeklyXxx() / fmtNum/fmtMoney/fmtPct/fmtDt
  Tab2：VIDEO_DATA / VIDEO_TIDS / videoSelTids / videoXxx() / fn/fm/fr/fd
共享 CSS 变量（仅长名）：--pink/--border/--card/--shadow/...
"""
import pandas as pd
import json
import re
from datetime import datetime

BASE = r'C:\Users\dengyuting02\claude output\charging_up_newstar'
P_UP_RANK = BASE + r'\result_code1_up_rank.json'
P_DAILY = BASE + r'\result_code2_daily_gmv_vv.json'
P_ARCH = BASE + r'\result_code3_arch_charge.json'
P_TOP3 = BASE + r'\result_code4_top3_fans.json'
P_PENE = BASE + r'\result_code5_penetration.json'
P_TOP100 = BASE + r'\result_code6_top100.json'
SUMMARY_PATH = BASE + r'\up_summaries.json'
HOT_TOPICS_PATH = BASE + r'\hot_topics.json'
VIDEO_HOT_PATH = BASE + r'\video_hot_topics.json'
OUT_PATH = BASE + r'\charging_up_dashboard.html'

# __DATA_PREP__

def load_rows(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)['data']['result']

def fmt_date_py(v):
    if pd.isna(v) or v is None:
        return ''
    try:
        return pd.to_datetime(v).strftime('%Y-%m-%d')
    except Exception:
        return str(v)

# ========== Tab1：UP 榜数据 ==========
df_up = pd.DataFrame(load_rows(P_UP_RANK))
df_trend = pd.DataFrame(load_rows(P_DAILY))
df_video = pd.DataFrame(load_rows(P_ARCH))
df_pene = pd.DataFrame(load_rows(P_PENE))
df_sim = pd.DataFrame(load_rows(P_TOP3))

NUM_UP = ['粉丝数', '首充距今天数', '近30日充电稿件数', '近30天gmv', '首充距今日均gmv',
          '近30日日均gmv', '近30日vv', '近30日ecpvv', '近30日充电人数', '近30日cvr', '上榜次数']
for c in NUM_UP:
    if c in df_up.columns:
        df_up[c] = pd.to_numeric(df_up[c], errors='coerce')
for c in ('gmv', 'vv'):
    if c in df_trend.columns:
        df_trend[c] = pd.to_numeric(df_trend[c], errors='coerce')
NUM_VIDEO = ['稿件近30日GMV', '稿件近30日播放量', '稿件近30日ECPVV', '稿件近30日充电人数', '稿件近30日转化率']
for c in NUM_VIDEO:
    if c in df_video.columns:
        df_video[c] = pd.to_numeric(df_video[c], errors='coerce')
NUM_PENE = ['充电渗透率', '近30日总稿件数', '近30日充电稿件数', '近30日总UP主数', '近30日有充电的UP主数']
for c in NUM_PENE:
    if c in df_pene.columns:
        df_pene[c] = pd.to_numeric(df_pene[c], errors='coerce')

sim_map = {}
for _, r in df_sim.iterrows():
    uid = str(r['UP主ID'])
    sim_map[uid] = str(r['Top3共粉UP昵称']) if pd.notna(r['Top3共粉UP昵称']) else ''

df_trend = df_trend.rename(columns={'日期': 'dt'})
df_trend['dt'] = df_trend['dt'].astype(str)

with open(SUMMARY_PATH, 'r', encoding='utf-8') as f:
    _summary_raw = json.load(f)
# 兼容旧格式（裸 dict）和新格式（{summaries: {uid: {summary, input_hash}}}）
if isinstance(_summary_raw, dict) and 'summaries' in _summary_raw:
    up_summaries = {uid: v.get('summary', '') for uid, v in _summary_raw['summaries'].items()}
else:
    up_summaries = _summary_raw

ups_data = []
for _, row in df_up.iterrows():
    up_id = str(row['up_id'])
    ups_data.append({
        'up_id': up_id,
        'uname': str(row['up名']),
        'fans': int(row['粉丝数']) if pd.notna(row['粉丝数']) else 0,
        'tid_gen': str(row['一级分区']) if pd.notna(row['一级分区']) else '',
        'tid_sub': str(row['二级分区']) if pd.notna(row['二级分区']) else '',
        'space_url': str(row['空间链接']) if pd.notna(row['空间链接']) else '',
        'first_charge_date': fmt_date_py(row['首充发布时间']),
        'days_since': int(row['首充距今天数']) if pd.notna(row['首充距今天数']) else 0,
        'charge_video_cnt': int(row['近30日充电稿件数']) if pd.notna(row['近30日充电稿件数']) else 0,
        'gmv': round(float(row['近30天gmv']), 0) if pd.notna(row['近30天gmv']) else 0,
        'avg_daily_gmv': round(float(row['近30日日均gmv']), 2) if pd.notna(row['近30日日均gmv']) else 0,
        'vv': int(row['近30日vv']) if pd.notna(row['近30日vv']) else 0,
        'ecpvv': round(float(row['近30日ecpvv']), 2) if pd.notna(row['近30日ecpvv']) else 0,
        'charge_users': int(row['近30日充电人数']) if pd.notna(row['近30日充电人数']) else 0,
        'cvr': round(float(row['近30日cvr']) * 100, 2) if pd.notna(row['近30日cvr']) else 0,
        'on_board': int(row['上榜次数']) if '上榜次数' in row and pd.notna(row['上榜次数']) and str(row['上榜次数']).strip() not in ('', 'nan') else 1,
        'summary': up_summaries.get(up_id, ''),
        'sim_ups': sim_map.get(up_id, ''),
    })

trend_by_up = {}
for up_id, grp in df_trend.groupby('up_id'):
    g = grp.sort_values('dt')
    trend_by_up[str(up_id)] = {
        'dates': g['dt'].tolist(),
        'gmv': [round(float(v), 0) if pd.notna(v) else 0 for v in g['gmv']],
        'vv': [int(v) if pd.notna(v) else 0 for v in g['vv']],
    }

videos_by_up = {}
for up_id, grp in df_video.groupby('UP主ID'):
    g = grp.sort_values('稿件近30日GMV', ascending=False)
    arr = []
    for _, r in g.iterrows():
        arr.append({
            'avid': str(r['稿件ID']),
            'title': str(r['稿件标题']) if pd.notna(r['稿件标题']) else '',
            'type': str(r['稿件类型']) if pd.notna(r['稿件类型']) else '',
            'play_url': str(r['播放页']) if pd.notna(r['播放页']) else '',
            'pubtime': fmt_date_py(r['发布时间']),
            'tag': str(r['tag']) if pd.notna(r['tag']) else '',
            'gmv': round(float(r['稿件近30日GMV']), 0) if pd.notna(r['稿件近30日GMV']) else 0,
            'vv': int(r['稿件近30日播放量']) if pd.notna(r['稿件近30日播放量']) else 0,
            'ecpvv': round(float(r['稿件近30日ECPVV']), 2) if pd.notna(r['稿件近30日ECPVV']) else 0,
            'charge_users': int(r['稿件近30日充电人数']) if pd.notna(r['稿件近30日充电人数']) else 0,
            'cvr': round(float(r['稿件近30日转化率']) * 100, 3) if pd.notna(r['稿件近30日转化率']) else 0,
        })
    videos_by_up[str(up_id)] = arr

pene_l1 = {}
for _, r in df_pene.iterrows():
    l1, l2 = str(r['一级分区']), str(r['二级分区'])
    if l1 == 'all':
        continue
    rate = round(float(r['充电渗透率']) * 100, 3) if pd.notna(r['充电渗透率']) else 0
    cc = int(r['近30日充电稿件数']) if pd.notna(r['近30日充电稿件数']) else 0
    tc = int(r['近30日总稿件数']) if pd.notna(r['近30日总稿件数']) else 0
    uc = int(r['近30日有充电的UP主数']) if pd.notna(r['近30日有充电的UP主数']) else 0
    tuc = int(r['近30日总UP主数']) if pd.notna(r['近30日总UP主数']) else 0
    if l1 == l2 or l2 == 'all' or l2 == 'nan':
        pene_l1[l1] = {'rate': rate, 'charge_cnt': cc, 'total_cnt': tc, 'up_cnt': uc, 'total_up_cnt': tuc}

# 二级聚合补一级缺失
pene_l2_tmp = {}
for _, r in df_pene.iterrows():
    l1, l2 = str(r['一级分区']), str(r['二级分区'])
    if l1 == 'all' or l1 == l2 or l2 == 'all' or l2 == 'nan':
        continue
    cc = int(r['近30日充电稿件数']) if pd.notna(r['近30日充电稿件数']) else 0
    tc = int(r['近30日总稿件数']) if pd.notna(r['近30日总稿件数']) else 0
    uc = int(r['近30日有充电的UP主数']) if pd.notna(r['近30日有充电的UP主数']) else 0
    tuc = int(r['近30日总UP主数']) if pd.notna(r['近30日总UP主数']) else 0
    pene_l2_tmp.setdefault(l1, []).append({'charge_cnt': cc, 'total_cnt': tc, 'up_cnt': uc, 'total_up_cnt': tuc})
for l1, kids in pene_l2_tmp.items():
    if l1 not in pene_l1:
        ttc = sum(c['charge_cnt'] for c in kids)
        ttt = sum(c['total_cnt'] for c in kids)
        pene_l1[l1] = {
            'rate': round(ttc / ttt * 100, 3) if ttt > 0 else 0,
            'charge_cnt': ttc, 'total_cnt': ttt, 'up_cnt': 0, 'total_up_cnt': 0,
        }

up_tids = sorted(df_up['一级分区'].dropna().unique().tolist())

# ---------- Tab1 热点主题 HTML ----------
def parse_up_hot_topics(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            ht = json.load(f)
    except Exception:
        return ''
    raw = ht.get('hot_topics', '')
    cards = []
    for block in raw.split('---'):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0].replace('🔥', '').strip()
        ups_line, desc_line = '', ''
        for l in lines[1:]:
            if l.startswith('代表UP：') or l.startswith('代表UP:'):
                ups_line = l.replace('代表UP：', '').replace('代表UP:', '').strip()
            elif l.startswith('趋势描述：') or l.startswith('趋势描述:'):
                desc_line = l.replace('趋势描述：', '').replace('趋势描述:', '').strip()
        ups_list = [u.strip() for u in ups_line.split('、') if u.strip()][:5]
        ups_tags = ''.join(f'<span class="hot-up-tag">{u}</span>' for u in ups_list)
        cards.append(
            f'<div class="hot-topic-card">\n'
            f'  <div class="hot-topic-title">🔥 {title}</div>\n'
            f'  <div class="hot-topic-ups">{ups_tags}</div>\n'
            f'  <div class="hot-topic-desc">{desc_line}</div>\n'
            f'</div>'
        )
    return '\n'.join(cards)

up_hot_html = parse_up_hot_topics(HOT_TOPICS_PATH)

# ========== Tab2：稿件 Top100 + 稿件热点主题 ==========
videos_top100 = load_rows(P_TOP100)
NUM_INT_VID = ['粉丝数', '稿件近30日播放量', '稿件近30日充电人数']
NUM_FLOAT_VID = ['稿件近30日GMV', '稿件近30日ECPVV', '稿件近30日转化率']
for v in videos_top100:
    for k in NUM_INT_VID:
        if k in v and v[k] not in (None, '', 'nan'):
            try: v[k] = int(float(v[k]))
            except (ValueError, TypeError): v[k] = None
    for k in NUM_FLOAT_VID:
        if k in v and v[k] not in (None, '', 'nan'):
            try: v[k] = float(v[k])
            except (ValueError, TypeError): v[k] = None

video_tids = sorted({v['一级分区'] for v in videos_top100 if v.get('一级分区')})

def parse_video_hot_topics(path, videos):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return ''
    raw = data.get('hot_topics', '')
    blocks = []
    for block in raw.split('---'):
        block = block.strip()
        if not block:
            continue
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        topic = {'name': '', 'trend': '', 'cases': []}
        in_cases = False
        for line in lines:
            if line.startswith('🔥'):
                topic['name'] = line.replace('🔥', '').strip()
            elif line.startswith('趋势描述：'):
                topic['trend'] = line.replace('趋势描述：', '').strip()
            elif line.startswith('代表'):
                in_cases = True
            elif in_cases and re.match(r'^\d+\.', line):
                topic['cases'].append(line)
        if topic['name']:
            blocks.append(topic)
    out = ''
    for topic in blocks:
        cases = ''
        for case in topic['cases'][:5]:
            m = re.search(r'(.+?)《(.+?)》', case)
            if m:
                up_name, vid_title = m.group(1).strip(), m.group(2).strip()
                play_url = next(
                    (v.get('播放页', '') for v in videos
                     if v.get('UP主昵称') == up_name and v.get('稿件标题') == vid_title),
                    '',
                )
                if play_url:
                    cases += f'<a href="{play_url}" target="_blank" class="case-link">{up_name}《{vid_title}》</a>'
                else:
                    cases += f'<span class="case-link no-link">{up_name}《{vid_title}》</span>'
            else:
                cases += f'<span class="case-link no-link">{case}</span>'
        out += (
            f'<div class="ht-v">\n'
            f'  <div class="ht-h">\n'
            f'    <div class="ht-name">🔥 {topic["name"]}</div>\n'
            f'    <div class="ht-trend">{topic["trend"]}</div>\n'
            f'  </div>\n'
            f'  <div class="ht-cases">\n'
            f'    <div class="cases-label">代表稿件：</div>\n'
            f'    {cases}\n'
            f'  </div>\n'
            f'</div>\n'
        )
    return out

video_hot_html = parse_video_hot_topics(VIDEO_HOT_PATH, videos_top100)

# 稿件榜初始卡片（Python 端先渲染一次，避免空白）
def fmt_num_py(n):
    if n is None: return '-'
    if n >= 10000: return f'{n/10000:.1f}w'
    return f'{int(n):,}'
def fmt_money_py(n):
    if n is None: return '-'
    return f'¥{n:,.0f}'
def fmt_rate_py(n):
    if n is None: return '-'
    return f'{n*100:.2f}%'
def fmt_date_str(s):
    if not s or s == 'nan': return '-'
    return str(s).split()[0]

video_init_cards = ''
for rank, v in enumerate(videos_top100, 1):
    url = v.get('播放页', '')
    title = v.get('稿件标题', '')
    tl = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    rc = f'r{rank}' if rank <= 3 else 'rank-n'
    video_init_cards += (
        f'<div class="vc" data-tid="{v.get("一级分区","")}">\n'
        f'  <div class="vch">\n'
        f'    <div class="vr {rc}">{rank}</div>\n'
        f'    <div class="vi">\n'
        f'      <div class="vt">{tl}</div>\n'
        f'      <div class="vmr"><span class="vn">{v.get("UP主昵称","")}</span><span class="vf">粉丝 {fmt_num_py(v.get("粉丝数"))}</span></div>\n'
        f'      <div class="vtags"><span class="tc tt">{v.get("一级分区","")}</span><span class="tc ts">{v.get("二级分区","")}</span><span class="tc" style="background:#f5f5f5;color:#666">{v.get("稿件类型","")}</span><span class="tc td">{fmt_date_str(v.get("发布时间",""))}</span></div>\n'
        f'      <div class="vtagl">{v.get("tag","")}</div>\n'
        f'    </div>\n'
        f'    <a class="vsl" href="https://space.bilibili.com/{v.get("UP主ID","")}" target="_blank">空间主页 →</a>\n'
        f'  </div>\n'
        f'  <div class="vm">\n'
        f'    <div class="mi"><div class="mv pink">{fmt_money_py(v.get("稿件近30日GMV"))}</div><div class="ml">近30日GMV</div></div>\n'
        f'    <div class="mi"><div class="mv">{fmt_num_py(v.get("稿件近30日播放量"))}</div><div class="ml">播放量</div></div>\n'
        f'    <div class="mi"><div class="mv">{v.get("稿件近30日ECPVV") or "-"}</div><div class="ml">ECPVV</div></div>\n'
        f'    <div class="mi"><div class="mv">{fmt_num_py(v.get("稿件近30日充电人数"))}</div><div class="ml">充电人数</div></div>\n'
        f'    <div class="mi"><div class="mv">{fmt_rate_py(v.get("稿件近30日转化率"))}</div><div class="ml">转化率</div></div>\n'
        f'    <div class="mi"><div class="mv">{fmt_num_py(v.get("粉丝数"))}</div><div class="ml">粉丝数</div></div>\n'
        f'  </div>\n'
        f'</div>\n'
    )

video_tid_tags = ''.join(
    f'<span class="ft" data-tid="{t}" onclick="videoFilterByTid(this, \'{t}\')">{t}</span>'
    for t in video_tids
)

print(f'数据加载完成: UP={len(ups_data)}, 趋势={len(trend_by_up)}, UP稿件={len(videos_by_up)}, '
      f'渗透分区={len(pene_l1)}, Top100={len(videos_top100)}')

# JSON 序列化（嵌入到 JS 中）
ups_json = json.dumps(ups_data, ensure_ascii=False)
trend_json = json.dumps(trend_by_up, ensure_ascii=False)
videos_json = json.dumps(videos_by_up, ensure_ascii=False)
pene_l1_json = json.dumps(pene_l1, ensure_ascii=False)
up_tids_json = json.dumps(up_tids, ensure_ascii=False)
video_data_json = json.dumps(videos_top100, ensure_ascii=False)
video_tids_json = json.dumps(video_tids, ensure_ascii=False)

gen_time = datetime.now().strftime('%Y-%m-%d %H:%M')

# __HTML_TEMPLATE_PLACEHOLDER__

html_head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>充电up主&稿件分析看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --pink: #FB7299;
    --pink-light: #fff0f5;
    --pink-dark: #e05a7a;
    --blue: #4A90E2;
    --green: #52c41a;
    --bg: #f7f8fc;
    --card: #ffffff;
    --border: #eef0f5;
    --text: #1a1a2e;
    --text-sub: #6b7280;
    --text-light: #9ca3af;
    --shadow: 0 2px 12px rgba(0,0,0,0.06);
    --shadow-hover: 0 6px 24px rgba(251,114,153,0.15);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: var(--bg); color: var(--text); font-size: 13px; }}

  /* ===== Header ===== */
  .header {{
    background: linear-gradient(135deg, #FC3D7E 0%, #FB7299 50%, #ff9bb5 100%);
    padding: 20px 32px 16px;
    color: white;
    box-shadow: 0 2px 12px rgba(251,114,153,0.3);
  }}
  .header-top {{ display: flex; align-items: center; justify-content: space-between; }}
  .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
  .header-meta {{ font-size: 12px; opacity: 0.8; margin-top: 6px; }}

  /* ===== 页面级 Tab ===== */
  .page-tabs {{
    max-width: 1280px;
    margin: 16px auto 0;
    padding: 0 24px;
    display: flex;
    gap: 8px;
    border-bottom: 2px solid var(--border);
  }}
  .page-tab-btn {{
    padding: 10px 20px;
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    color: var(--text-sub);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: -2px;
  }}
  .page-tab-btn:hover {{ color: var(--pink); }}
  .page-tab-btn.active {{ color: var(--pink); border-bottom-color: var(--pink); }}
  .page-content {{ display: none; }}
  .page-content.active {{ display: block; }}

  .main {{ max-width: 1280px; margin: 0 auto; padding: 20px 24px; }}

  /* ===== Tab1：筛选+渗透率融合模块 ===== */
  .filter-panel {{ background: var(--card); border-radius: 12px; padding: 14px 20px 12px; margin-bottom: 16px; box-shadow: var(--shadow); border: 2px solid var(--pink); }}
  .filter-row {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }}
  .filter-label {{ font-size: 12px; color: var(--pink); font-weight: 700; margin-right: 4px; white-space: nowrap; }}
  .filter-tag {{ padding: 5px 14px; border-radius: 20px; border: 1.5px solid var(--border); background: white; color: var(--text-sub); cursor: pointer; font-size: 12px; font-weight: 500; transition: all 0.2s; user-select: none; }}
  .filter-tag:hover {{ border-color: var(--pink); color: var(--pink); }}
  .filter-tag.active {{ background: var(--pink); border-color: var(--pink); color: white; font-weight: 600; }}
  .filter-divider {{ border-top: 1px dashed var(--border); margin: 10px 0; }}
  .pene-info-bar {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border); display: flex; flex-direction: column; gap: 8px; min-height: 0; }}
  .pene-info-bar.empty {{ align-items: center; color: var(--text-light); font-size: 12px; }}
  .pene-row {{ display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 6px 10px; background: #faf8ff; border-radius: 8px; }}
  .pene-row-all {{ background: linear-gradient(135deg, #f3f0ff, #f8f5ff); border: 1px solid #e8e0f8; }}
  .pene-info-tag {{ font-size: 12px; font-weight: 700; color: #764ba2; background: #ece7ff; padding: 3px 10px; border-radius: 6px; white-space: nowrap; min-width: 130px; }}
  .pene-info-item {{ font-size: 11px; color: var(--text-sub); white-space: nowrap; }}
  .pene-info-item strong {{ color: #764ba2; font-weight: 700; }}

  /* ===== Tab1：UP热点主题模块 ===== */
  .hot-topics-panel {{ background: var(--card); border-radius: 12px; box-shadow: var(--shadow); overflow: hidden; margin-bottom: 16px; }}
  .hot-topics-header {{ background: linear-gradient(135deg, #f093fb, #f5576c); color: white; padding: 12px 20px; font-size: 13px; font-weight: 700; display: flex; align-items: center; justify-content: space-between; }}
  .hot-topics-header small {{ font-size: 11px; font-weight: 400; opacity: 0.85; }}
  .hot-topics-body {{ padding: 16px 16px; display: flex; flex-wrap: wrap; gap: 12px; }}
  .hot-topic-card {{ flex: 1 1 220px; min-width: 200px; border: 1.5px solid #fbd0e0; border-radius: 10px; padding: 12px 14px; background: linear-gradient(135deg, #fff8fa, #fff0f5); transition: box-shadow 0.2s; }}
  .hot-topic-card:hover {{ box-shadow: 0 4px 16px rgba(245,87,108,0.15); border-color: var(--pink); }}
  .hot-topic-title {{ font-size: 13px; font-weight: 800; color: #f5576c; margin-bottom: 8px; }}
  .hot-topic-ups {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }}
  .hot-up-tag {{ font-size: 11px; background: #fde8ed; color: #c0284a; border-radius: 20px; padding: 2px 8px; font-weight: 600; }}
  .hot-topic-desc {{ font-size: 12px; color: var(--text-light); line-height: 1.5; }}
  .hot-topics-placeholder {{ padding: 28px; display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--text-light); width: 100%; }}
"""

html_css_2 = """
  /* ===== Tab1：UP榜单卡片 ===== */
  .board-panel { min-width: 0; }
  .board-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .board-title { font-size: 20px; font-weight: 800; color: var(--text); letter-spacing: 0.5px; }
  .board-right { display: flex; align-items: center; gap: 10px; }
  .board-count { font-size: 12px; color: var(--text-sub); }
  .download-btn { display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px; border-radius: 8px; border: 1.5px solid var(--pink); background: white; color: var(--pink); font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.2s; user-select: none; text-decoration: none; }
  .download-btn:hover { background: var(--pink); color: white; }
  .download-btn svg { width: 14px; height: 14px; }

  .up-card { background: var(--card); border-radius: 12px; box-shadow: var(--shadow); margin-bottom: 14px; overflow: hidden; transition: box-shadow 0.2s; border: 1px solid transparent; }
  .up-card:hover { box-shadow: var(--shadow-hover); border-color: rgba(251,114,153,0.2); }
  .up-card-head { padding: 14px 18px; display: flex; align-items: flex-start; gap: 14px; border-bottom: 1px solid var(--border); }
  .up-rank { min-width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800; flex-shrink: 0; background: var(--pink-light); color: var(--pink); }
  .rank-1, .rank-2, .rank-3 { background: linear-gradient(135deg, #FB7299, #FF9BB5); color: white; }
  .rank-n { background: var(--pink-light); color: var(--pink); }
  .up-info { flex: 1; min-width: 0; }
  .up-name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
  .up-name { font-size: 15px; font-weight: 700; color: var(--text); }
  .up-id { font-size: 11px; color: var(--text-light); }
  .up-fans { font-size: 11px; color: var(--text-sub); background: #f5f5f5; border-radius: 10px; padding: 2px 8px; }
  .up-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 6px; }
  .tag-chip { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
  .tag-tid { background: #e8f4ff; color: #1890ff; }
  .tag-sub { background: #f0fff4; color: #52c41a; }
  .tag-new { background: var(--pink-light); color: var(--pink); font-weight: 700; }
  .tag-days { background: #fff7e6; color: #fa8c16; }
  .up-space-link { color: var(--pink); text-decoration: none; font-size: 11px; border: 1px solid var(--pink); border-radius: 12px; padding: 3px 10px; transition: all 0.2s; flex-shrink: 0; align-self: flex-start; white-space: nowrap; }
  .up-space-link:hover { background: var(--pink); color: white; }
  .up-metrics { display: grid; grid-template-columns: repeat(6, 1fr); border-bottom: 1px solid var(--border); }
  .metric-item { padding: 10px 8px; text-align: center; border-right: 1px solid var(--border); }
  .metric-item:last-child { border-right: none; }
  .metric-val { font-size: 15px; font-weight: 700; color: var(--text); line-height: 1.2; }
  .metric-val.pink { color: var(--pink); }
  .metric-label { font-size: 10px; color: var(--text-light); margin-top: 2px; }

  .up-body { display: flex; flex-direction: column; gap: 0; }
  .up-chart-wrap { padding: 14px 18px; }
  .up-chart-title { font-size: 11px; color: var(--text-sub); font-weight: 600; margin-bottom: 8px; }
  .up-chart-canvas { display: block; width: 100% !important; height: 120px !important; }
  .up-summary-wrap { padding: 14px 18px; background: #fafbff; border-top: 1px solid var(--border); }
  .up-summary-title { font-size: 11px; color: var(--text-sub); font-weight: 600; margin-bottom: 6px; }
  .up-summary-text { font-size: 12px; color: var(--text); line-height: 1.7; }

  .expand-btn { padding: 9px 18px; display: flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; background: #f9f9fb; border-top: 1px solid var(--border); color: var(--text-sub); font-size: 12px; transition: all 0.2s; user-select: none; }
  .expand-btn:hover { background: var(--pink-light); color: var(--pink); }
  .expand-btn .arrow { font-size: 10px; transition: transform 0.2s; }
  .expand-btn.open .arrow { transform: rotate(180deg); }

  .video-list { display: none; border-top: 1px solid var(--border); }
  .video-list.open { display: block; }
  .video-list-header { display: grid; grid-template-columns: 50px 1fr 80px 90px 70px 70px 70px 80px; padding: 6px 18px; background: #f5f6fa; border-bottom: 1px solid var(--border); font-size: 11px; font-weight: 600; color: var(--text-sub); }
  .video-row { display: grid; grid-template-columns: 50px 1fr 80px 90px 70px 70px 70px 80px; padding: 8px 18px; border-bottom: 1px solid #f5f5f5; align-items: center; font-size: 11px; transition: background 0.15s; }
  .video-row:hover { background: #fafbff; }
  .video-row:last-child { border-bottom: none; }
  .video-rank { font-size: 12px; font-weight: 700; color: var(--text-sub); }
  .video-title { font-size: 12px; color: var(--text); line-height: 1.4; padding-right: 8px; }
  .video-title a { color: var(--text); text-decoration: none; }
  .video-title a:hover { color: var(--pink); }
  .video-title-sub { font-size: 10px; color: var(--text-light); margin-top: 2px; }
  .video-type { font-size: 10px; }
  .type-live { color: var(--pink); background: var(--pink-light); border-radius: 4px; padding: 2px 5px; }
  .type-free { color: #52c41a; background: #f0fff4; border-radius: 4px; padding: 2px 5px; }
  .video-val { font-size: 12px; color: var(--text); font-weight: 500; }
  .video-val.pink { color: var(--pink); font-weight: 700; }

  .no-results { text-align: center; padding: 60px 20px; color: var(--text-light); font-size: 14px; }
  .no-results .icon { font-size: 40px; margin-bottom: 12px; }

  @media (max-width: 900px) {
    .up-metrics { grid-template-columns: repeat(3, 1fr); }
    .video-list-header, .video-row { grid-template-columns: 40px 1fr 70px 70px 60px 60px; }
  }
"""

html_css_3 = """
  /* ===== Tab2：稿件榜样式 ===== */
  .fp { background: var(--card); border-radius: 12px; padding: 14px 20px 12px; margin-bottom: 16px; box-shadow: var(--shadow); border: 2px solid var(--pink); }
  .fr { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  .fl { font-size: 12px; color: var(--pink); font-weight: 700; margin-right: 4px; white-space: nowrap; }
  .ft { padding: 5px 14px; border-radius: 20px; border: 1.5px solid var(--border); background: #fff; color: var(--text-sub); cursor: pointer; font-size: 12px; font-weight: 500; transition: all .2s; user-select: none; }
  .ft:hover { border-color: var(--pink); color: var(--pink); }
  .ft.active { background: var(--pink); border-color: var(--pink); color: #fff; font-weight: 600; }

  .htp { background: var(--card); border-radius: 12px; box-shadow: var(--shadow); overflow: hidden; margin-bottom: 16px; }
  .hth { background: linear-gradient(135deg, #f093fb, #f5576c); color: #fff; padding: 12px 20px; font-size: 13px; font-weight: 700; display: flex; align-items: center; justify-content: space-between; }
  .hth small { font-size: 11px; font-weight: 400; opacity: .85; }
  .htb { padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
  .ht-v { background: linear-gradient(135deg, #fff8fa, #fff0f5); border: 1.5px solid #fbd0e0; border-radius: 10px; padding: 14px 18px; transition: box-shadow .2s; }
  .ht-v:hover { box-shadow: 0 4px 16px rgba(245,87,108,.15); border-color: var(--pink); }
  .ht-name { font-size: 15px; font-weight: 800; color: #f5576c; margin-bottom: 6px; }
  .ht-trend { font-size: 13px; color: var(--text-sub); line-height: 1.6; }
  .ht-cases { display: flex; flex-direction: column; gap: 5px; padding-top: 10px; border-top: 1px dashed #fbd0e0; margin-top: 10px; }
  .cases-label { font-size: 12px; font-weight: 600; color: var(--pink); margin-bottom: 2px; }
  .case-link { font-size: 12px; color: var(--text); text-decoration: none; padding: 4px 10px; background: #fff; border-radius: 6px; border: 1px solid var(--border); display: block; transition: all .15s; line-height: 1.4; }
  .case-link:hover { color: var(--pink); border-color: var(--pink); background: var(--pink-light); }
  .case-link.no-link { color: var(--text-sub); cursor: default; }
  .case-link.no-link:hover { color: var(--text-sub); border-color: var(--border); background: #fff; }

  .bp { min-width: 0; }
  .bh { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .bt { font-size: 20px; font-weight: 800; color: var(--text); letter-spacing: .5px; }
  .br { display: flex; align-items: center; gap: 10px; }
  .bc { font-size: 12px; color: var(--text-sub); }
  .db { display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px; border-radius: 8px; border: 1.5px solid var(--pink); background: #fff; color: var(--pink); font-size: 12px; font-weight: 600; cursor: pointer; transition: all .2s; user-select: none; text-decoration: none; }
  .db:hover { background: var(--pink); color: #fff; }
  .db svg { width: 14px; height: 14px; }

  /* 稿件卡片：默认浅边框 + hover 加深 */
  .vc { background: var(--card); border-radius: 12px; box-shadow: var(--shadow); margin-bottom: 14px; overflow: hidden; border: 1px solid var(--border); transition: all .2s; }
  .vc:hover { box-shadow: var(--shadow-hover); border-color: var(--pink); }
  .vch { padding: 14px 18px; display: flex; align-items: flex-start; gap: 14px; border-bottom: 1px solid var(--border); }
  .vr { min-width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800; flex-shrink: 0; background: var(--pink-light); color: var(--pink); }
  .r1, .r2, .r3 { background: linear-gradient(135deg, #FB7299, #FF9BB5); color: #fff; }
  .vi { flex: 1; min-width: 0; }
  .vt { font-size: 16px; font-weight: 700; color: var(--text); line-height: 1.5; margin-bottom: 6px; }
  .vt a { color: var(--blue); text-decoration: none; }
  .vt a:hover { color: var(--pink); text-decoration: underline; }
  .vmr { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
  .vn { font-size: 13px; font-weight: 600; color: var(--text-sub); }
  .vf { font-size: 11px; color: var(--text-light); background: #f5f5f5; border-radius: 10px; padding: 2px 8px; }
  .vtags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 4px; }
  .tc { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
  .tt { background: #e8f4ff; color: #1890ff; }
  .ts { background: #f0fff4; color: #52c41a; }
  .td { background: #fff7e6; color: #fa8c16; }
  .vtagl { font-size: 11px; color: var(--text-light); line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .vsl { color: var(--pink); text-decoration: none; font-size: 11px; border: 1px solid var(--pink); border-radius: 12px; padding: 3px 10px; transition: all .2s; flex-shrink: 0; align-self: flex-start; white-space: nowrap; }
  .vsl:hover { background: var(--pink); color: #fff; }
  .vm { display: grid; grid-template-columns: repeat(6, 1fr); border-bottom: 1px solid var(--border); }
  .mi { padding: 10px 8px; text-align: center; border-right: 1px solid var(--border); }
  .mi:last-child { border-right: none; }
  .mv { font-size: 15px; font-weight: 700; color: var(--text); line-height: 1.2; }
  .mv.pink { color: var(--pink); }
  .ml { font-size: 10px; color: var(--text-light); margin-top: 2px; }
  .nr { text-align: center; padding: 60px 20px; color: var(--text-light); font-size: 14px; }
  .nr .i { font-size: 40px; margin-bottom: 12px; }
  @media (max-width: 900px) { .vm { grid-template-columns: repeat(3, 1fr); } .vt { font-size: 14px; } }
</style>
</head>
<body>
"""

html_body = f"""
<div class="header">
  <div class="header-top">
    <div>
      <h1>📊 充电up主&稿件分析看板</h1>
      <div class="header-meta">充电新星（近30日，百万粉以下）&商业潜力up主分析 · 生成时间 {gen_time}</div>
    </div>
  </div>
</div>

<div class="page-tabs">
  <button class="page-tab-btn active" onclick="switchTab('weekly')">⚡ 充电新星UP主</button>
  <button class="page-tab-btn" onclick="switchTab('videos')">🎬 新充电稿件Top100</button>
</div>

<!-- ============ Tab1: 充电新星UP主 ============ -->
<div id="tab-weekly" class="page-content active">
<div class="main">

  <div class="hot-topics-panel">
    <div class="hot-topics-header">
      <span>🔥 热点主题总结</span>
      <small>本期新星UP主内容趋势</small>
    </div>
    <div class="hot-topics-body">
      {up_hot_html}
    </div>
  </div>

  <div class="filter-panel">
    <div class="filter-row">
      <span class="filter-label">🏷️ 上榜类型：</span>
      <span class="filter-tag active" data-board="all" onclick="weeklyFilterByBoardType(this, 'all')">全部</span>
      <span class="filter-tag" data-board="new" onclick="weeklyFilterByBoardType(this, 'new')">🆕 本期新上榜</span>
      <span class="filter-tag" data-board="continuous" onclick="weeklyFilterByBoardType(this, 'continuous')">🔥 连续上榜</span>
    </div>
    <div class="filter-divider"></div>
    <div class="filter-row">
      <span class="filter-label">📂 分区筛选：</span>
      <span class="filter-tag active" data-tid="all" onclick="weeklyFilterByTid(this, 'all')">全部</span>
      <span id="filter-tags"></span>
    </div>
    <div class="pene-info-bar" id="pene-info"></div>
  </div>

  <div class="board-panel">
    <div class="board-header">
      <div class="board-title">🏆 新星UP榜单</div>
      <div class="board-right">
        <div class="board-count" id="board-count"></div>
        <a class="download-btn" onclick="weeklyDownloadCSV()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载全量
        </a>
      </div>
    </div>
    <div id="up-board"></div>
  </div>

</div>
</div>

<!-- ============ Tab2: 充电稿件Top100 ============ -->
<div id="tab-videos" class="page-content">
<div class="main">

  <div class="htp">
    <div class="hth"><span>🔥 热门主题总结</span><small>本周充电稿件内容趋势</small></div>
    <div class="htb">{video_hot_html}</div>
  </div>

  <div class="fp">
    <div class="fr">
      <span class="fl">📂 分区筛选：</span>
      <span class="ft active" data-tid="all" onclick="videoFilterByTid(this, 'all')">全部</span>
      {video_tid_tags}
    </div>
  </div>

  <div class="bp">
    <div class="bh">
      <div class="bt">🏆 稿件榜单</div>
      <div class="br">
        <div class="bc" id="bc">共 {len(videos_top100)} 部稿件</div>
        <a class="db" onclick="videoDownloadCSV()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载全量
        </a>
      </div>
    </div>
    <div id="vb">{video_init_cards}</div>
  </div>

</div>
</div>

<script>
const UPS = {ups_json};
const TRENDS = {trend_json};
const VIDEOS = {videos_json};
const PENE_L1 = {pene_l1_json};
const UP_TIDS = {up_tids_json};
const VIDEO_DATA = {video_data_json};
const VIDEO_TIDS = {video_tids_json};
</script>
"""

html_js = r"""
<script>
// ============================================================
// 页面 Tab 切换
// ============================================================
function switchTab(name) {
  document.querySelectorAll('.page-content').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.page-tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector(`.page-tab-btn[onclick*="'${name}'"]`).classList.add('active');
}

// ============================================================
// Tab1：新星UP榜
// ============================================================
let weeklySelTids = [];
let weeklyBoardType = 'all';
const weeklyChartInstances = {};

function fmtNum(n) {
  if (n === null || n === undefined) return '-';
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n.toLocaleString();
}
function fmtMoney(n) {
  if (!n) return '-';
  return '¥' + n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
function fmtPct(n) {
  if (!n) return '-';
  return n.toFixed(2) + '%';
}
function fmtDt(s) {
  if (!s) return s;
  s = String(s);
  if (s.length === 8) return s.slice(4,6) + '/' + s.slice(6,8);
  return s.slice(5, 10).replace('-', '/');
}

function weeklyInitFilterTags() {
  const wrap = document.getElementById('filter-tags');
  UP_TIDS.forEach(tid => {
    const span = document.createElement('span');
    span.className = 'filter-tag';
    span.dataset.tid = tid;
    span.textContent = tid;
    span.onclick = function() { weeklyFilterByTid(this, tid); };
    wrap.appendChild(span);
  });
}

function weeklyFilterByTid(el, tid) {
  if (tid === 'all') {
    weeklySelTids = [];
    document.querySelectorAll('#tab-weekly .filter-tag[data-tid]').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
  } else {
    document.querySelector('#tab-weekly .filter-tag[data-tid="all"]').classList.remove('active');
    if (el.classList.contains('active')) {
      el.classList.remove('active');
      weeklySelTids = weeklySelTids.filter(t => t !== tid);
    } else {
      el.classList.add('active');
      weeklySelTids.push(tid);
    }
    if (weeklySelTids.length === 0) {
      document.querySelector('#tab-weekly .filter-tag[data-tid="all"]').classList.add('active');
    }
  }
  weeklyRenderBoard();
  weeklyRenderPene();
}

function weeklyFilterByBoardType(el, type) {
  weeklyBoardType = type;
  document.querySelectorAll('.filter-tag[data-board]').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  weeklyRenderBoard();
}

function weeklyRenderPene() {
  const wrap = document.getElementById('pene-info');
  wrap.innerHTML = '';
  wrap.classList.remove('empty');
  if (weeklySelTids.length === 0) {
    const all = Object.entries(PENE_L1);
    const tCharge = all.reduce((s, [, v]) => s + v.charge_cnt, 0);
    const tAll = all.reduce((s, [, v]) => s + v.total_cnt, 0);
    const tUpC = all.reduce((s, [, v]) => s + v.up_cnt, 0);
    const tUpA = all.reduce((s, [, v]) => s + v.total_up_cnt, 0);
    const rate = tAll > 0 ? (tCharge / tAll * 100) : 0;
    wrap.innerHTML = `
      <div class="pene-row pene-row-all">
        <span class="pene-info-tag">📊 全分区综合 ${rate.toFixed(2)}%</span>
        <span class="pene-info-item">总稿件 <strong>${fmtNum(tAll)}</strong></span>
        <span class="pene-info-item">充电稿件 <strong>${fmtNum(tCharge)}</strong></span>
        <span class="pene-info-item">发稿UP <strong>${fmtNum(tUpA)}</strong></span>
        <span class="pene-info-item">充电UP <strong>${fmtNum(tUpC)}</strong></span>
      </div>`;
  } else {
    weeklySelTids.forEach(tid => {
      const info = PENE_L1[tid];
      if (!info) return;
      const row = document.createElement('div');
      row.className = 'pene-row';
      row.innerHTML = `
        <span class="pene-info-tag">📊 ${tid} ${info.rate.toFixed(2)}%</span>
        <span class="pene-info-item">总稿件 <strong>${fmtNum(info.total_cnt)}</strong></span>
        <span class="pene-info-item">充电稿件 <strong>${fmtNum(info.charge_cnt)}</strong></span>
        <span class="pene-info-item">发稿UP <strong>${fmtNum(info.total_up_cnt)}</strong></span>
        <span class="pene-info-item">充电UP <strong>${fmtNum(info.up_cnt)}</strong></span>
      `;
      wrap.appendChild(row);
    });
    if (!wrap.children.length) {
      wrap.classList.add('empty');
      wrap.textContent = '所选分区暂无渗透率数据';
    }
  }
}

function weeklyGetFilteredUPS() {
  let r = UPS;
  if (weeklySelTids.length > 0) r = r.filter(u => weeklySelTids.includes(u.tid_gen));
  if (weeklyBoardType === 'new') r = r.filter(u => u.on_board === 1);
  else if (weeklyBoardType === 'continuous') r = r.filter(u => u.on_board > 1);
  return r;
}

function weeklyRenderBoard() {
  const board = document.getElementById('up-board');
  board.innerHTML = '';
  Object.keys(weeklyChartInstances).forEach(id => {
    if (weeklyChartInstances[id]) { weeklyChartInstances[id].destroy(); delete weeklyChartInstances[id]; }
  });
  const filtered = weeklyGetFilteredUPS();
  const top20 = filtered.slice(0, 20);
  const lt = weeklySelTids.length === 0 ? '全部分区' : weeklySelTids.join('、');
  const lbMap = { 'all': '', 'new': ' · 本期新上榜', 'continuous': ' · 连续上榜' };
  document.getElementById('board-count').textContent = `${lt}${lbMap[weeklyBoardType]} · 共 ${filtered.length} 位UP主，展示前 ${top20.length} 名`;
  if (top20.length === 0) {
    board.innerHTML = '<div class="no-results"><div class="icon">🔍</div>所选分区暂无上榜UP主</div>';
    return;
  }
  top20.forEach((up, idx) => board.appendChild(weeklyBuildUpCard(up, idx + 1)));
  setTimeout(() => top20.forEach(up => weeklyRenderChart(up.up_id)), 50);
}

function weeklyDownloadCSV() {
  const filtered = weeklyGetFilteredUPS();
  if (!filtered.length) { alert('当前无数据可下载'); return; }
  const BOM = '﻿';
  const header = '排名,UP名,UID,粉丝数,一级分区,二级分区,近30日GMV,近30日VV,ECPVV,充电人次,充电转化率,日均GMV,充电稿件数,首充发布时间,首充距今天数,上榜次数,空间链接,共粉UP,内容总结';
  const rows = filtered.map((up, i) => [
    i + 1,
    '"' + up.uname.replace(/"/g, '""') + '"',
    up.up_id, up.fans, up.tid_gen, up.tid_sub, up.gmv, up.vv, up.ecpvv || '', up.charge_users, up.cvr + '%',
    up.avg_daily_gmv, up.charge_video_cnt, up.first_charge_date, up.days_since, up.on_board, up.space_url,
    '"' + (up.sim_ups || '').replace(/"/g, '""') + '"',
    '"' + (up.summary || '').replace(/"/g, '""') + '"'
  ].join(','));
  const csv = BOM + header + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const lt = weeklySelTids.length === 0 ? '全部分区' : weeklySelTids.join('_');
  a.href = url; a.download = `充电新星UP榜_${lt}.csv`; a.click();
  URL.revokeObjectURL(url);
}

function weeklyBuildUpCard(up, rank) {
  const card = document.createElement('div');
  card.className = 'up-card';
  card.id = 'card-' + up.up_id;
  const rankClass = rank <= 3 ? `rank-${rank}` : 'rank-n';
  const boardLabel = up.on_board > 1
    ? `<span class="tag-chip tag-new">连续在榜${up.on_board}期</span>`
    : `<span class="tag-chip tag-new">🆕 本期新上榜</span>`;
  card.innerHTML = `
    <div class="up-card-head">
      <div class="up-rank ${rankClass}">${rank}</div>
      <div class="up-info">
        <div class="up-name-row">
          <span class="up-name">${up.uname}</span>
          <span class="up-id">UID: ${up.up_id}</span>
          <span class="up-fans">粉丝 ${fmtNum(up.fans)}</span>
        </div>
        <div class="up-tags">
          <span class="tag-chip tag-tid">${up.tid_gen}</span>
          ${up.tid_sub ? '<span class="tag-chip tag-sub">' + up.tid_sub + '</span>' : ''}
          ${boardLabel}
          <span class="tag-chip tag-days">${fmtDt(up.first_charge_date)}发布首个充电视频 · 距今${up.days_since}天</span>
          <span class="tag-chip" style="background:#f5f5f5;color:#666">充电稿件 ${up.charge_video_cnt}部</span>
        </div>
      </div>
      <a class="up-space-link" href="${up.space_url}" target="_blank">空间主页 →</a>
    </div>
    <div class="up-metrics">
      <div class="metric-item"><div class="metric-val pink">${fmtMoney(up.gmv)}</div><div class="metric-label">近30日GMV</div></div>
      <div class="metric-item"><div class="metric-val">${fmtNum(up.vv)}</div><div class="metric-label">近30日VV</div></div>
      <div class="metric-item"><div class="metric-val">${up.ecpvv || '-'}</div><div class="metric-label">ECPVV</div></div>
      <div class="metric-item"><div class="metric-val">${fmtNum(up.charge_users)}</div><div class="metric-label">充电人次</div></div>
      <div class="metric-item"><div class="metric-val">${fmtPct(up.cvr)}</div><div class="metric-label">充电转化率</div></div>
      <div class="metric-item"><div class="metric-val">${fmtMoney(up.avg_daily_gmv)}</div><div class="metric-label">日均GMV</div></div>
    </div>
    <div class="up-body">
      <div class="up-chart-wrap">
        <div class="up-chart-title">📈 充电视频 GMV & VV 日趋势</div>
        <canvas class="up-chart-canvas" id="chart-${up.up_id}"></canvas>
      </div>
      <div class="up-summary-wrap">
        <div class="up-summary-title">📝 内容主题分析 ${up.sim_ups ? '<span style="font-weight:400;color:var(--text-light);margin-left:8px;font-size:11px">👥 共粉UP: ' + up.sim_ups + '</span>' : ''}</div>
        <div class="up-summary-text">${up.summary || '暂无内容信息'}</div>
      </div>
    </div>
    <div class="expand-btn" id="expand-btn-${up.up_id}" onclick="weeklyToggleVideos('${up.up_id}')">
      <span>📋 稿件明细（展示Top5 GMV稿件，共${(VIDEOS[up.up_id] || []).length}部充电稿件）</span>
      <span class="arrow">▼</span>
    </div>
    <div class="video-list" id="video-list-${up.up_id}">
      ${weeklyBuildVideoList(up.up_id)}
    </div>
  `;
  return card;
}

function weeklyBuildVideoList(up_id) {
  const all = VIDEOS[up_id] || [];
  const videos = all.slice(0, 5);
  if (!videos.length) return '<div style="padding:16px;color:#999;text-align:center">暂无稿件数据</div>';
  let html = `
    <div class="video-list-header">
      <div>#</div><div>稿件信息</div><div>稿件类型</div><div>发布时间</div>
      <div>GMV</div><div>VV</div><div>ECPVV</div><div>充电人次</div>
    </div>`;
  videos.forEach((v, i) => {
    const typeClass = v.type.includes('进行中') ? 'type-live' : 'type-free';
    html += `
      <div class="video-row">
        <div class="video-rank">${i+1}</div>
        <div class="video-title">
          <a href="${v.play_url}" target="_blank">${v.title || '无标题'}</a>
          <div class="video-title-sub">AV${v.avid} · ${v.tag ? v.tag.split(',').slice(0,3).join(' · ') : ''}</div>
        </div>
        <div><span class="${typeClass}">${v.type}</span></div>
        <div class="video-val">${v.pubtime}</div>
        <div class="video-val pink">${fmtMoney(v.gmv)}</div>
        <div class="video-val">${fmtNum(v.vv)}</div>
        <div class="video-val">${v.ecpvv || '-'}</div>
        <div class="video-val">${fmtNum(v.charge_users)}</div>
      </div>`;
  });
  return html;
}

function weeklyToggleVideos(up_id) {
  const list = document.getElementById('video-list-' + up_id);
  const btn = document.getElementById('expand-btn-' + up_id);
  const open = list.classList.contains('open');
  list.classList.toggle('open', !open);
  btn.classList.toggle('open', !open);
}

function weeklyRenderChart(up_id) {
  const canvas = document.getElementById('chart-' + up_id);
  if (!canvas) return;
  canvas.width = canvas.parentElement.offsetWidth || 500;
  canvas.height = 120;
  const trend = TRENDS[up_id];
  if (!trend || !trend.dates.length) {
    canvas.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:120px;color:#ccc;font-size:12px">暂无趋势数据</div>';
    return;
  }
  if (weeklyChartInstances[up_id]) weeklyChartInstances[up_id].destroy();
  const labels = trend.dates.map(d => fmtDt(d));
  weeklyChartInstances[up_id] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        { label: 'GMV(¥)', data: trend.gmv, borderColor: '#FB7299', backgroundColor: 'rgba(251,114,153,0.08)', borderWidth: 2, pointRadius: 2, pointHoverRadius: 4, tension: 0.4, fill: true, yAxisID: 'y1' },
        { label: 'VV', data: trend.vv, borderColor: '#4A90E2', backgroundColor: 'rgba(74,144,226,0.05)', borderWidth: 2, pointRadius: 2, pointHoverRadius: 4, tension: 0.4, fill: false, yAxisID: 'y2' },
      ]
    },
    options: {
      responsive: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 10 } }, onClick: function(){} }, tooltip: { bodyFont: { size: 11 }, titleFont: { size: 11 } } },
      scales: {
        x: { ticks: { font: { size: 9 }, maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
        y1: { position: 'left', ticks: { font: { size: 9 }, callback: v => '¥' + v }, grid: { color: 'rgba(0,0,0,0.04)' } },
        y2: { position: 'right', ticks: { font: { size: 9 } }, grid: { display: false } }
      }
    }
  });
}

// ============================================================
// Tab2：稿件 Top100
// ============================================================
let videoSelTids = [];

function fn(n) { if (n == null) return '-'; if (n >= 1e4) return (n / 1e4).toFixed(1) + 'w'; return n.toLocaleString(); }
function fm(n) { if (!n) return '-'; return '¥' + n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function fr(n) { if (!n) return '-'; return (n * 100).toFixed(2) + '%'; }
function fd(s) { if (!s || s == 'nan') return '-'; return String(s).split(' ')[0]; }

function videoFilterByTid(el, tid) {
  if (tid === 'all') {
    videoSelTids = [];
    document.querySelectorAll('#tab-videos .ft[data-tid]').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
  } else {
    document.querySelector('#tab-videos .ft[data-tid="all"]').classList.remove('active');
    if (el.classList.contains('active')) {
      el.classList.remove('active');
      videoSelTids = videoSelTids.filter(t => t !== tid);
    } else {
      el.classList.add('active');
      videoSelTids.push(tid);
    }
    if (videoSelTids.length === 0) {
      document.querySelector('#tab-videos .ft[data-tid="all"]').classList.add('active');
    }
  }
  videoRenderBoard();
}

function videoRenderBoard() {
  const board = document.getElementById('vb');
  board.innerHTML = '';
  let filtered = VIDEO_DATA;
  if (videoSelTids.length > 0) filtered = VIDEO_DATA.filter(v => videoSelTids.includes(v['一级分区']));
  const lt = videoSelTids.length === 0 ? '全部分区' : videoSelTids.join('、');
  document.getElementById('bc').textContent = lt + ' · 共 ' + filtered.length + ' 部稿件';
  if (filtered.length === 0) {
    board.innerHTML = '<div class="nr"><div class="i">🔍</div>所选分区暂无稿件</div>';
    return;
  }
  filtered.forEach((v, i) => {
    const rank = i + 1;
    const rc = rank <= 3 ? 'r' + rank : 'rank-n';
    const url = v['播放页'] || '';
    const title = v['稿件标题'] || '';
    const tl = url ? '<a href="' + url + '" target="_blank">' + title + '</a>' : title;
    const c = document.createElement('div');
    c.className = 'vc';
    c.innerHTML = '<div class="vch"><div class="vr ' + rc + '">' + rank + '</div><div class="vi"><div class="vt">' + tl + '</div><div class="vmr"><span class="vn">' + (v['UP主昵称'] || '') + '</span><span class="vf">粉丝 ' + fn(v['粉丝数']) + '</span></div><div class="vtags"><span class="tc tt">' + (v['一级分区'] || '') + '</span><span class="tc ts">' + (v['二级分区'] || '') + '</span><span class="tc" style="background:#f5f5f5;color:#666">' + (v['稿件类型'] || '') + '</span><span class="tc td">' + fd(v['发布时间']) + '</span></div><div class="vtagl">' + (v['tag'] || '') + '</div></div><a class="vsl" href="https://space.bilibili.com/' + (v['UP主ID'] || '') + '" target="_blank">空间主页 →</a></div><div class="vm"><div class="mi"><div class="mv pink">' + fm(v['稿件近30日GMV']) + '</div><div class="ml">近30日GMV</div></div><div class="mi"><div class="mv">' + fn(v['稿件近30日播放量']) + '</div><div class="ml">播放量</div></div><div class="mi"><div class="mv">' + (v['稿件近30日ECPVV'] || '-') + '</div><div class="ml">ECPVV</div></div><div class="mi"><div class="mv">' + fn(v['稿件近30日充电人数']) + '</div><div class="ml">充电人数</div></div><div class="mi"><div class="mv">' + fr(v['稿件近30日转化率']) + '</div><div class="ml">转化率</div></div><div class="mi"><div class="mv">' + fn(v['粉丝数']) + '</div><div class="ml">粉丝数</div></div></div>';
    board.appendChild(c);
  });
}

function videoDownloadCSV() {
  let filtered = VIDEO_DATA;
  if (videoSelTids.length > 0) filtered = VIDEO_DATA.filter(v => videoSelTids.includes(v['一级分区']));
  if (!filtered.length) { alert('当前无数据可下载'); return; }
  const h = '﻿排名,UP主昵称,粉丝数,稿件ID,稿件标题,稿件类型,播放页,发布时间,一级分区,二级分区,tag,近30日GMV,近30日播放量,近30日ECPVV,近30日充电人数,近30日转化率';
  const rows = filtered.map((v, i) => [
    i + 1, '"' + (v['UP主昵称'] || '').replace(/"/g, '""') + '"', v['粉丝数'] || '', v['稿件ID'] || '',
    '"' + (v['稿件标题'] || '').replace(/"/g, '""') + '"', v['稿件类型'] || '', v['播放页'] || '',
    v['发布时间'] || '', v['一级分区'] || '', v['二级分区'] || '',
    '"' + (v['tag'] || '').replace(/"/g, '""') + '"',
    v['稿件近30日GMV'] || '', v['稿件近30日播放量'] || '', v['稿件近30日ECPVV'] || '',
    v['稿件近30日充电人数'] || '',
    v['稿件近30日转化率'] != null ? (v['稿件近30日转化率'] * 100).toFixed(2) + '%' : ''
  ].join(','));
  const csv = h + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const lt = videoSelTids.length === 0 ? '全部' : videoSelTids.join('_');
  a.href = url;
  a.download = '充电稿件Top100_' + lt + '_' + new Date().toISOString().slice(0, 10) + '.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ============================================================
// 初始化
// ============================================================
weeklyInitFilterTags();
weeklyRenderPene();
weeklyRenderBoard();
</script>

</body>
</html>
"""

html = html_head + html_css_2 + html_css_3 + html_body + html_js

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'\n✅ HTML 已生成: {OUT_PATH}')
print(f'   文件大小: {len(html)/1024:.0f} KB')






