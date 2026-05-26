import pandas as pd
import json
import math

path = 'C:/Users/dengyuting02/Desktop/需求：充电新星up/表汇总5.25.xlsx'
SUMMARY_PATH = 'c:/Users/dengyuting02/WorkBuddy/20260514140206/up_summaries.json'

# Excel sheet 名里有空格/数字前缀，以实际为准
xl = pd.ExcelFile(path)
sn = xl.sheet_names
print('实际sheet名:', sn)

df_up = pd.read_excel(path, sheet_name=sn[0])
df_trend = pd.read_excel(path, sheet_name=sn[1])
df_video = pd.read_excel(path, sheet_name=sn[2])
df_pene = pd.read_excel(path, sheet_name=sn[4])  # 表5 分区渗透

# 读取相似UP数据（表4 共粉up）
df_sim = pd.read_excel(path, sheet_name='表4 共粉up')
# 构建相似UP映射 {up_id: "UP名1,UP名2,UP名3"}
sim_map = {}
for _, r in df_sim.iterrows():
    uid = str(int(r['UP主ID']))
    sim_names = str(r['Top3共粉UP昵称']) if pd.notna(r['Top3共粉UP昵称']) else ''
    sim_map[uid] = sim_names
print(f'共粉UP数据: {len(sim_map)}个UP有共粉信息')

print('UP列:', df_up.columns.tolist())
print('趋势列:', df_trend.columns.tolist())
print('稿件列:', df_video.columns.tolist())
print('渗透列:', df_pene.columns.tolist())

# 统一趋势列名
df_trend.columns = ['up_id', 'dt', 'gmv', 'vv']
df_trend['dt'] = df_trend['dt'].astype(str)

# ---------- 读取离线生成的内容总结 ----------
print('读取内容总结...')
with open(SUMMARY_PATH, 'r', encoding='utf-8') as f:
    up_summaries = json.load(f)
print(f'已读取 {len(up_summaries)} 个UP的内容总结')

# ---------- 数据整理 ----------
def fmt_date(v):
    if pd.isna(v):
        return ''
    try:
        return pd.to_datetime(v).strftime('%Y-%m-%d')
    except:
        return str(v)

# UP榜单数据
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
        'first_charge_date': fmt_date(row['首充发布时间']),
        'days_since': int(row['首充距今天数']) if pd.notna(row['首充距今天数']) else 0,
        'charge_video_cnt': int(row['近30日充电稿件数']) if pd.notna(row['近30日充电稿件数']) else 0,
        'gmv': round(float(row['近30天gmv']), 0) if pd.notna(row['近30天gmv']) else 0,
        'avg_daily_gmv': round(float(row['近30日日均gmv']), 2) if pd.notna(row['近30日日均gmv']) else 0,
        'vv': int(row['近30日vv']) if pd.notna(row['近30日vv']) else 0,
        'ecpvv': round(float(row['近30日ecpvv']), 2) if pd.notna(row['近30日ecpvv']) else 0,
        'charge_users': int(row['近30日充电人数']) if pd.notna(row['近30日充电人数']) else 0,
        'cvr': round(float(row['近30日cvr']) * 100, 2) if pd.notna(row['近30日cvr']) else 0,
        'on_board': int(row['上榜次数']) if pd.notna(row['上榜次数']) else 1,
        'summary': up_summaries.get(up_id, ''),
        'sim_ups': sim_map.get(up_id, ''),
    })

# 趋势数据
df_video['pub_date'] = pd.to_datetime(df_video['发布时间']).dt.strftime('%Y%m%d')

trend_by_up = {}
for up_id, grp in df_trend.groupby('up_id'):
    grp_sorted = grp.sort_values('dt')
    uid = str(up_id)
    dates = grp_sorted['dt'].tolist()
    trend_by_up[uid] = {
        'dates': dates,
        'gmv': [round(float(v), 0) if pd.notna(v) else 0 for v in grp_sorted['gmv']],
        'vv': [int(v) if pd.notna(v) else 0 for v in grp_sorted['vv']],
    }

# 稿件明细
videos_by_up = {}
for up_id, grp in df_video.groupby('UP主ID'):
    grp_sorted = grp.sort_values('稿件近30日GMV', ascending=False)
    videos = []
    for _, r in grp_sorted.iterrows():
        videos.append({
            'avid': str(r['稿件ID']),
            'title': str(r['稿件标题']) if pd.notna(r['稿件标题']) else '',
            'type': str(r['稿件类型']) if pd.notna(r['稿件类型']) else '',
            'play_url': str(r['播放页']) if pd.notna(r['播放页']) else '',
            'pubtime': fmt_date(r['发布时间']),
            'tag': str(r['tag']) if pd.notna(r['tag']) else '',
            'gmv': round(float(r['稿件近30日GMV']), 0) if pd.notna(r['稿件近30日GMV']) else 0,
            'vv': int(r['稿件近30日播放量']) if pd.notna(r['稿件近30日播放量']) else 0,
            'ecpvv': round(float(r['稿件近30日ECPVV']), 2) if pd.notna(r['稿件近30日ECPVV']) else 0,
            'charge_users': int(r['稿件近30日充电人数']) if pd.notna(r['稿件近30日充电人数']) else 0,
            'cvr': round(float(r['稿件近30日转化率']) * 100, 3) if pd.notna(r['稿件近30日转化率']) else 0,
        })
    videos_by_up[str(up_id)] = videos

# 分区渗透数据（只保留一级）
pene_l1 = {}

for _, r in df_pene.iterrows():
    l1 = str(r['一级分区'])
    l2 = str(r['二级分区'])
    if l1 == 'all':
        continue
    rate = round(float(r['充电渗透率']) * 100, 3) if pd.notna(r['充电渗透率']) else 0
    charge_cnt = int(r['近30日充电稿件数']) if pd.notna(r['近30日充电稿件数']) else 0
    total_cnt = int(r['近30日总稿件数']) if pd.notna(r['近30日总稿件数']) else 0
    up_cnt = int(r['近30日有充电的UP主数']) if pd.notna(r['近30日有充电的UP主数']) else 0
    total_up_cnt = int(r['近30日总UP主数']) if pd.notna(r['近30日总UP主数']) else 0

    if l1 == l2 or l2 == 'all' or l2 == 'nan':
        pene_l1[l1] = {'rate': rate, 'charge_cnt': charge_cnt, 'total_cnt': total_cnt, 'up_cnt': up_cnt, 'total_up_cnt': total_up_cnt}

# 无一级汇总行则用二级聚合补充
pene_l2_tmp = {}
for _, r in df_pene.iterrows():
    l1 = str(r['一级分区'])
    l2 = str(r['二级分区'])
    if l1 == 'all' or l1 == l2 or l2 == 'all' or l2 == 'nan':
        continue
    rate = round(float(r['充电渗透率']) * 100, 3) if pd.notna(r['充电渗透率']) else 0
    charge_cnt = int(r['近30日充电稿件数']) if pd.notna(r['近30日充电稿件数']) else 0
    total_cnt = int(r['近30日总稿件数']) if pd.notna(r['近30日总稿件数']) else 0
    up_cnt = int(r['近30日有充电的UP主数']) if pd.notna(r['近30日有充电的UP主数']) else 0
    total_up_cnt = int(r['近30日总UP主数']) if pd.notna(r['近30日总UP主数']) else 0
    if l1 not in pene_l2_tmp:
        pene_l2_tmp[l1] = []
    pene_l2_tmp[l1].append({'charge_cnt': charge_cnt, 'total_cnt': total_cnt, 'up_cnt': up_cnt, 'total_up_cnt': total_up_cnt})

for l1, children in pene_l2_tmp.items():
    if l1 not in pene_l1:
        total_charge = sum(c['charge_cnt'] for c in children)
        total_total = sum(c['total_cnt'] for c in children)
        rate = round(total_charge / total_total * 100, 3) if total_total > 0 else 0
        pene_l1[l1] = {'rate': rate, 'charge_cnt': total_charge, 'total_cnt': total_total, 'up_cnt': 0, 'total_up_cnt': 0}

# 获取UP榜单中存在的一级分区（用于筛选器）
up_tids = sorted(df_up['一级分区'].dropna().unique().tolist())

# ---------- 读取热点主题总结 ----------
HOT_TOPICS_PATH = 'c:/Users/dengyuting02/WorkBuddy/20260514140206/hot_topics.json'
hot_topics_html = ''
try:
    with open(HOT_TOPICS_PATH, 'r', encoding='utf-8') as f:
        ht = json.load(f)
    raw = ht.get('hot_topics', '')
    if raw:
        # 解析格式：每个主题用 --- 分隔，首行 🔥 主题名，次行 代表UP：，三行 趋势描述：
        blocks = [b.strip() for b in raw.split('---') if b.strip()]
        cards = []
        for block in blocks:
            lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue
            title = lines[0].replace('🔥', '').strip()
            ups_line = ''
            desc_line = ''
            for l in lines[1:]:
                if l.startswith('代表UP：') or l.startswith('代表UP:'):
                    ups_line = l.replace('代表UP：', '').replace('代表UP:', '').strip()
                elif l.startswith('趋势描述：') or l.startswith('趋势描述:'):
                    desc_line = l.replace('趋势描述：', '').replace('趋势描述:', '').strip()
            ups_list = [u.strip() for u in ups_line.split('、') if u.strip()]
            ups_list = ups_list[:5]  # 最多5个案例UP
            ups_tags = ''.join(f'<span class="hot-up-tag">{u}</span>' for u in ups_list)
            cards.append(f'''<div class="hot-topic-card">
  <div class="hot-topic-title">🔥 {title}</div>
  <div class="hot-topic-ups">{ups_tags}</div>
  <div class="hot-topic-desc">{desc_line}</div>
</div>''')
        hot_topics_html = '\n'.join(cards)
    print(f'热点主题总结已加载，共{len(blocks)}个主题')
except FileNotFoundError:
    hot_topics_html = '<div class="hot-topics-placeholder"><div class="icon">✍️</div><p>热点总结文件未找到，请先运行 gen_hot_topics.py</p></div>'
    print('警告：hot_topics.json 不存在，热点模块使用占位内容')
except Exception as e:
    hot_topics_html = f'<div class="hot-topics-placeholder"><div class="icon">⚠️</div><p>加载失败: {e}</p></div>'
    print(f'热点总结加载异常: {e}')

# 序列化
ups_json = json.dumps(ups_data, ensure_ascii=False)
trend_json = json.dumps(trend_by_up, ensure_ascii=False)
videos_json = json.dumps(videos_by_up, ensure_ascii=False)
pene_l1_json = json.dumps(pene_l1, ensure_ascii=False)
up_tids_json = json.dumps(up_tids, ensure_ascii=False)

print('数据序列化完成')
print(f'UP数据: {len(ups_data)}条, 趋势: {len(trend_by_up)}个UP, 稿件: {len(videos_by_up)}个UP')
print(f'一级分区渗透: {len(pene_l1)}个, 含UP榜的分区: {len(up_tids)}个')

# ---------- 生成HTML ----------
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>充电新星UP主周榜</title>
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

  /* ===== 顶部 ===== */
  .header {{
    background: linear-gradient(135deg, #FC3D7E 0%, #FB7299 50%, #ff9bb5 100%);
    padding: 20px 32px 16px;
    color: white;
    box-shadow: 0 2px 12px rgba(251,114,153,0.3);
  }}
  .header-top {{ display: flex; align-items: center; justify-content: space-between; }}
  .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
  .header h1 span {{ font-size: 13px; font-weight: 400; opacity: 0.85; margin-left: 12px; }}
  .header-meta {{ font-size: 12px; opacity: 0.8; margin-top: 6px; }}
  .header-badge {{ display: none; }}

  /* ===== 主体布局 ===== */
  .main {{ max-width: 1280px; margin: 0 auto; padding: 20px 24px; }}

  /* ===== 筛选+渗透率 融合模块 ===== */
  .filter-panel {{
    background: var(--card);
    border-radius: 12px;
    padding: 14px 20px 12px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
    border: 2px solid var(--pink);
  }}
  .filter-row {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .filter-label {{ font-size: 12px; color: var(--pink); font-weight: 700; margin-right: 4px; white-space: nowrap; }}
  .filter-tag {{
    padding: 5px 14px;
    border-radius: 20px;
    border: 1.5px solid var(--border);
    background: white;
    color: var(--text-sub);
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.2s;
    user-select: none;
  }}
  .filter-tag:hover {{ border-color: var(--pink); color: var(--pink); }}
  .filter-tag.active {{ background: var(--pink); border-color: var(--pink); color: white; font-weight: 600; }}
  .filter-divider {{ border-top: 1px dashed var(--border); margin: 10px 0; }}

  /* 筛选下方的渗透率信息（纵向列表） */
  .pene-info-bar {{
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px dashed var(--border);
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
  }}
  .pene-info-bar.empty {{
    align-items: center;
    color: var(--text-light);
    font-size: 12px;
  }}
  .pene-row {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 6px 10px;
    background: #faf8ff;
    border-radius: 8px;
  }}
  .pene-row-all {{
    background: linear-gradient(135deg, #f3f0ff, #f8f5ff);
    border: 1px solid #e8e0f8;
  }}
  .pene-info-tag {{
    font-size: 12px;
    font-weight: 700;
    color: #764ba2;
    background: #ece7ff;
    padding: 3px 10px;
    border-radius: 6px;
    white-space: nowrap;
    min-width: 130px;
  }}
  .pene-info-item {{
    font-size: 11px;
    color: var(--text-sub);
    white-space: nowrap;
  }}
  .pene-info-item strong {{
    color: #764ba2;
    font-weight: 700;
  }}

  /* ===== 热点主题总结模块 ===== */
  .hot-topics-panel {{
    background: var(--card);
    border-radius: 12px;
    box-shadow: var(--shadow);
    overflow: hidden;
    margin-bottom: 16px;
  }}
  .hot-topics-header {{
    background: linear-gradient(135deg, #f093fb, #f5576c);
    color: white;
    padding: 12px 20px;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .hot-topics-header small {{ font-size: 11px; font-weight: 400; opacity: 0.85; }}
  .hot-topics-body {{
    padding: 16px 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .hot-topic-card {{
    flex: 1 1 220px;
    min-width: 200px;
    border: 1.5px solid #fbd0e0;
    border-radius: 10px;
    padding: 12px 14px;
    background: linear-gradient(135deg, #fff8fa, #fff0f5);
    transition: box-shadow 0.2s;
  }}
  .hot-topic-card:hover {{ box-shadow: 0 4px 16px rgba(245,87,108,0.15); border-color: var(--pink); }}
  .hot-topic-title {{ font-size: 13px; font-weight: 800; color: #f5576c; margin-bottom: 8px; }}
  .hot-topic-ups {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }}
  .hot-up-tag {{ font-size: 11px; background: #fde8ed; color: #c0284a; border-radius: 20px; padding: 2px 8px; font-weight: 600; }}
  .hot-topic-desc {{ font-size: 12px; color: var(--text-light); line-height: 1.5; }}
  .hot-topics-placeholder {{
    padding: 28px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: var(--text-light);
    width: 100%;
  }}
  .hot-topics-placeholder .icon {{ font-size: 28px; }}
  .hot-topics-placeholder p {{ font-size: 12px; }}

  /* ===== UP榜单 ===== */
  .board-panel {{ min-width: 0; }}
  .board-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }}
  .board-title {{ font-size: 20px; font-weight: 800; color: var(--text); letter-spacing: 0.5px; }}
  .board-right {{ display: flex; align-items: center; gap: 10px; }}
  .board-count {{ font-size: 12px; color: var(--text-sub); }}
  .download-btn {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 12px;
    border-radius: 8px;
    border: 1.5px solid var(--pink);
    background: white;
    color: var(--pink);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    text-decoration: none;
  }}
  .download-btn:hover {{ background: var(--pink); color: white; }}
  .download-btn svg {{ width: 14px; height: 14px; }}

  /* UP卡片 */
  .up-card {{
    background: var(--card);
    border-radius: 12px;
    box-shadow: var(--shadow);
    margin-bottom: 14px;
    overflow: hidden;
    transition: box-shadow 0.2s;
    border: 1px solid transparent;
  }}
  .up-card:hover {{ box-shadow: var(--shadow-hover); border-color: rgba(251,114,153,0.2); }}

  /* 卡片头部 */
  .up-card-head {{
    padding: 14px 18px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    border-bottom: 1px solid var(--border);
  }}
  .up-rank {{
    min-width: 32px; height: 32px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 800;
    flex-shrink: 0;
    background: var(--pink-light);
    color: var(--pink);
  }}
  .rank-1 {{ background: linear-gradient(135deg, #FB7299, #FF9BB5); color: white; }}
  .rank-2 {{ background: linear-gradient(135deg, #FB7299, #FF9BB5); color: white; }}
  .rank-3 {{ background: linear-gradient(135deg, #FB7299, #FF9BB5); color: white; }}
  .rank-n {{ background: var(--pink-light); color: var(--pink); }}

  .up-info {{ flex: 1; min-width: 0; }}
  .up-name-row {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }}
  .up-name {{ font-size: 15px; font-weight: 700; color: var(--text); }}
  .up-id {{ font-size: 11px; color: var(--text-light); }}
  .up-fans {{ font-size: 11px; color: var(--text-sub); background: #f5f5f5; border-radius: 10px; padding: 2px 8px; }}
  .up-tags {{ display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 6px; }}
  .tag-chip {{
    padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500;
  }}
  .tag-tid {{ background: #e8f4ff; color: #1890ff; }}
  .tag-sub {{ background: #f0fff4; color: #52c41a; }}
  .tag-new {{ background: var(--pink-light); color: var(--pink); font-weight: 700; }}
  .tag-days {{ background: #fff7e6; color: #fa8c16; }}
  .up-meta {{ font-size: 11px; color: var(--text-light); }}
  .up-space-link {{
    color: var(--pink); text-decoration: none; font-size: 11px;
    border: 1px solid var(--pink); border-radius: 12px; padding: 3px 10px;
    transition: all 0.2s; flex-shrink: 0; align-self: flex-start;
    white-space: nowrap;
  }}
  .up-space-link:hover {{ background: var(--pink); color: white; }}

  /* 指标行 */
  .up-metrics {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    border-bottom: 1px solid var(--border);
  }}
  .metric-item {{
    padding: 10px 8px;
    text-align: center;
    border-right: 1px solid var(--border);
  }}
  .metric-item:last-child {{ border-right: none; }}
  .metric-val {{ font-size: 15px; font-weight: 700; color: var(--text); line-height: 1.2; }}
  .metric-val.pink {{ color: var(--pink); }}
  .metric-label {{ font-size: 10px; color: var(--text-light); margin-top: 2px; }}

  /* 图表+总结区 */
  .up-body {{ display: flex; flex-direction: column; gap: 0; }}
  .up-chart-wrap {{ padding: 14px 18px; }}
  .up-chart-title {{ font-size: 11px; color: var(--text-sub); font-weight: 600; margin-bottom: 8px; }}
  .up-chart-canvas {{ display: block; width: 100% !important; height: 120px !important; }}

  .up-summary-wrap {{
    padding: 14px 18px;
    background: #fafbff;
    border-top: 1px solid var(--border);
  }}
  .up-summary-title {{ font-size: 11px; color: var(--text-sub); font-weight: 600; margin-bottom: 6px; }}
  .up-summary-text {{ font-size: 12px; color: var(--text); line-height: 1.7; }}

  /* 展开按钮 */
  .expand-btn {{
    padding: 9px 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    cursor: pointer;
    background: #f9f9fb;
    border-top: 1px solid var(--border);
    color: var(--text-sub);
    font-size: 12px;
    transition: all 0.2s;
    user-select: none;
  }}
  .expand-btn:hover {{ background: var(--pink-light); color: var(--pink); }}
  .expand-btn .arrow {{ font-size: 10px; transition: transform 0.2s; }}
  .expand-btn.open .arrow {{ transform: rotate(180deg); }}

  /* 稿件列表（去掉分区列，9列 → 8列） */
  .video-list {{
    display: none;
    border-top: 1px solid var(--border);
  }}
  .video-list.open {{ display: block; }}
  .video-list-header {{
    display: grid;
    grid-template-columns: 50px 1fr 80px 90px 70px 70px 70px 80px;
    padding: 6px 18px;
    background: #f5f6fa;
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-sub);
  }}
  .video-row {{
    display: grid;
    grid-template-columns: 50px 1fr 80px 90px 70px 70px 70px 80px;
    padding: 8px 18px;
    border-bottom: 1px solid #f5f5f5;
    align-items: center;
    font-size: 11px;
    transition: background 0.15s;
  }}
  .video-row:hover {{ background: #fafbff; }}
  .video-row:last-child {{ border-bottom: none; }}
  .video-rank {{ font-size: 12px; font-weight: 700; color: var(--text-sub); }}
  .video-title {{ font-size: 12px; color: var(--text); line-height: 1.4; padding-right: 8px; }}
  .video-title a {{ color: var(--text); text-decoration: none; }}
  .video-title a:hover {{ color: var(--pink); }}
  .video-title-sub {{ font-size: 10px; color: var(--text-light); margin-top: 2px; }}
  .video-type {{ font-size: 10px; }}
  .type-live {{ color: var(--pink); background: var(--pink-light); border-radius: 4px; padding: 2px 5px; }}
  .type-free {{ color: #52c41a; background: #f0fff4; border-radius: 4px; padding: 2px 5px; }}
  .video-val {{ font-size: 12px; color: var(--text); font-weight: 500; }}
  .video-val.pink {{ color: var(--pink); font-weight: 700; }}

  .no-results {{
    text-align: center; padding: 60px 20px; color: var(--text-light); font-size: 14px;
  }}
  .no-results .icon {{ font-size: 40px; margin-bottom: 12px; }}

  @media (max-width: 900px) {{
    .up-metrics {{ grid-template-columns: repeat(3, 1fr); }}
    .video-list-header, .video-row {{
      grid-template-columns: 40px 1fr 70px 70px 60px 60px;
    }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <h1>⚡ 充电新星UP主周榜</h1>
      <div class="header-meta">数据范围：近30日发布首个充电视频的新生充电UP主，且满足GMV > 1k元、粉丝量 &lt; 百万</div>
    </div>
    <div class="header-badge" id="total-badge"></div>
  </div>
</div>

<div class="main">

  <!-- 热点主题总结（页面最顶部） -->
  <div class="hot-topics-panel">
    <div class="hot-topics-header">
      <span>🔥 热点主题总结</span>
      <small>本期新星UP主内容趋势</small>
    </div>
    <div class="hot-topics-body">
      {hot_topics_html}
    </div>
  </div>

  <!-- 分区筛选 + 渗透率信息（融合模块） -->
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

  <!-- UP榜单 -->
  <div class="board-panel">
    <div class="board-header">
      <div class="board-title">🏆 新星UP榜单</div>
      <div class="board-right">
        <div class="board-count" id="board-count"></div>
        <a class="download-btn" id="download-btn" onclick="weeklyDownloadCSV()" title="下载筛选后全量数据">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载全量
        </a>
      </div>
    </div>
    <div id="up-board"></div>
  </div>

</div>

<script>
const UPS = {ups_json};
const TRENDS = {trend_json};
const VIDEOS = {videos_json};
const PENE_L1 = {pene_l1_json};
const UP_TIDS = {up_tids_json};

let selectedTids = [];  // 多选：空数组=全部
let selectedBoardType = 'all';  // 'all' | 'new' | 'continuous'
const chartInstances = {{}};

// ===== 格式化工具 =====
function fmtNum(n) {{
  if (n === null || n === undefined) return '-';
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n.toLocaleString();
}}
function fmtMoney(n) {{
  if (!n) return '-';
  return '¥' + n.toFixed(0).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ',');
}}
function fmtPct(n) {{
  if (!n) return '-';
  return n.toFixed(2) + '%';
}}
function fmtDt(s) {{
  if (!s) return s;
  s = String(s);
  if (s.length === 8) return s.slice(4,6) + '/' + s.slice(6,8);
  return s.slice(5, 10).replace('-', '/');
}}

// ===== 初始化筛选标签 =====
function weeklyInitFilterTags() {{
  const wrap = document.getElementById('filter-tags');
  UP_TIDS.forEach(tid => {{
    const span = document.createElement('span');
    span.className = 'filter-tag';
    span.dataset.tid = tid;
    span.textContent = tid;
    span.onclick = function() {{ weeklyFilterByTid(this, tid); }};
    wrap.appendChild(span);
  }});
}}

// ===== 筛选逻辑（多选） =====
function weeklyFilterByTid(el, tid) {{
  if (tid === 'all') {{
    // 点击"全部"：清除所有选中
    selectedTids = [];
    document.querySelectorAll('.filter-tag').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
  }} else {{
    // 点击具体分区：切换选中状态
    document.querySelector('.filter-tag[data-tid="all"]').classList.remove('active');
    if (el.classList.contains('active')) {{
      el.classList.remove('active');
      selectedTids = selectedTids.filter(t => t !== tid);
    }} else {{
      el.classList.add('active');
      selectedTids.push(tid);
    }}
    // 全部取消时自动回到"全部"
    if (selectedTids.length === 0) {{
      document.querySelector('.filter-tag[data-tid="all"]').classList.add('active');
    }}
  }}
  weeklyRenderBoard();
  weeklyRenderPene();
}}

// ===== 上榜类型筛选 =====
function weeklyFilterByBoardType(el, type) {{
  selectedBoardType = type;
  document.querySelectorAll('.filter-tag[data-board]').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  weeklyRenderBoard();
}}

// ===== 渲染渗透率信息（纵向多行模式） =====
function weeklyRenderPene() {{
  const wrap = document.getElementById('pene-info');
  wrap.innerHTML = '';
  wrap.classList.remove('empty');

  if (selectedTids.length === 0) {{
    // 默认状态：全分区综合汇总
    const allEntries = Object.entries(PENE_L1);
    const totalCharge = allEntries.reduce((s, [, v]) => s + v.charge_cnt, 0);
    const totalAll = allEntries.reduce((s, [, v]) => s + v.total_cnt, 0);
    const totalUpCharge = allEntries.reduce((s, [, v]) => s + v.up_cnt, 0);
    const totalUpAll = allEntries.reduce((s, [, v]) => s + v.total_up_cnt, 0);
    const overallRate = totalAll > 0 ? (totalCharge / totalAll * 100) : 0;

    wrap.innerHTML = `
      <div class="pene-row pene-row-all">
        <span class="pene-info-tag">📊 全分区综合 ${{overallRate.toFixed(2)}}%</span>
        <span class="pene-info-item">总稿件 <strong>${{fmtNum(totalAll)}}</strong></span>
        <span class="pene-info-item">充电稿件 <strong>${{fmtNum(totalCharge)}}</strong></span>
        <span class="pene-info-item">发稿UP <strong>${{fmtNum(totalUpAll)}}</strong></span>
        <span class="pene-info-item">充电UP <strong>${{fmtNum(totalUpCharge)}}</strong></span>
      </div>
    `;
  }} else {{
    // 多选状态：纵向列出每个选中分区
    selectedTids.forEach(tid => {{
      const info = PENE_L1[tid];
      if (!info) return;
      const row = document.createElement('div');
      row.className = 'pene-row';
      row.innerHTML = `
        <span class="pene-info-tag">📊 ${{tid}} ${{info.rate.toFixed(2)}}%</span>
        <span class="pene-info-item">总稿件 <strong>${{fmtNum(info.total_cnt)}}</strong></span>
        <span class="pene-info-item">充电稿件 <strong>${{fmtNum(info.charge_cnt)}}</strong></span>
        <span class="pene-info-item">发稿UP <strong>${{fmtNum(info.total_up_cnt)}}</strong></span>
        <span class="pene-info-item">充电UP <strong>${{fmtNum(info.up_cnt)}}</strong></span>
      `;
      wrap.appendChild(row);
    }});
    if (!wrap.children.length) {{
      wrap.classList.add('empty');
      wrap.textContent = '所选分区暂无渗透率数据';
    }}
  }}
}}

// ===== 获取当前筛选后的UP列表 =====
function weeklyGetFilteredUPS() {{
  let result = UPS;
  // 分区筛选
  if (selectedTids.length > 0) {{
    result = result.filter(u => selectedTids.includes(u.tid_gen));
  }}
  // 上榜类型筛选
  if (selectedBoardType === 'new') {{
    result = result.filter(u => u.on_board === 1);
  }} else if (selectedBoardType === 'continuous') {{
    result = result.filter(u => u.on_board > 1);
  }}
  return result;
}}

// ===== 渲染UP榜单（Top 20） =====
function weeklyRenderBoard() {{
  const board = document.getElementById('up-board');
  board.innerHTML = '';

  Object.keys(chartInstances).forEach(id => {{
    if (chartInstances[id]) {{ chartInstances[id].destroy(); delete chartInstances[id]; }}
  }});

  const filtered = weeklyGetFilteredUPS();
  const top20 = filtered.slice(0, 20);

  const labelTid = selectedTids.length === 0 ? '全部分区' : selectedTids.join('、');
  const boardTypeMap = {{ 'all': '', 'new': ' · 本期新上榜', 'continuous': ' · 连续上榜' }};
  const labelBoard = boardTypeMap[selectedBoardType] || '';
  document.getElementById('board-count').textContent = `${{labelTid}}${{labelBoard}} · 共 ${{filtered.length}} 位UP主，展示前 ${{top20.length}} 名`;

  if (top20.length === 0) {{
    board.innerHTML = '<div class="no-results"><div class="icon">🔍</div>所选分区暂无上榜UP主</div>';
    return;
  }}

  top20.forEach((up, idx) => {{
    board.appendChild(weeklyBuildUpCard(up, idx + 1));
  }});

  setTimeout(() => {{
    top20.forEach(up => weeklyRenderChart(up.up_id));
  }}, 50);
}}

// ===== 下载CSV（筛选后全量） =====
function weeklyDownloadCSV() {{
  const filtered = weeklyGetFilteredUPS();
  if (!filtered.length) {{ alert('当前无数据可下载'); return; }}

  const BOM = '\\uFEFF';
  const header = '排名,UP名,UID,粉丝数,一级分区,二级分区,近30日GMV,近30日VV,ECPVV,充电人次,充电转化率,日均GMV,充电稿件数,首充发布时间,首充距今天数,上榜次数,空间链接,共粉UP,内容总结';
  const rows = filtered.map((up, i) => [
    i + 1,
    '"' + up.uname.replace(/"/g, '""') + '"',
    up.up_id,
    up.fans,
    up.tid_gen,
    up.tid_sub,
    up.gmv,
    up.vv,
    up.ecpvv || '',
    up.charge_users,
    up.cvr + '%',
    up.avg_daily_gmv,
    up.charge_video_cnt,
    up.first_charge_date,
    up.days_since,
    up.on_board,
    up.space_url,
    '"' + (up.sim_ups || '').replace(/"/g, '""') + '"',
    '"' + (up.summary || '').replace(/"/g, '""') + '"'
  ].join(','));

  const csv = BOM + header + '\\n' + rows.join('\\n');
  const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const labelTid = selectedTids.length === 0 ? '全部分区' : selectedTids.join('_');
  a.href = url;
  a.download = `充电新星UP榜_${{labelTid}}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}}

// ===== 构建UP卡片 =====
function weeklyBuildUpCard(up, rank) {{
  const card = document.createElement('div');
  card.className = 'up-card';
  card.id = 'card-' + up.up_id;

  let rankClass = rank <= 3 ? `rank-${{rank}}` : 'rank-n';
  let boardLabel = up.on_board > 1
    ? `<span class="tag-chip tag-new">连续在榜${{up.on_board}}期</span>`
    : `<span class="tag-chip tag-new">🆕 本期新上榜</span>`;

  card.innerHTML = `
    <div class="up-card-head">
      <div class="up-rank ${{rankClass}}">${{rank}}</div>
      <div class="up-info">
        <div class="up-name-row">
          <span class="up-name">${{up.uname}}</span>
          <span class="up-id">UID: ${{up.up_id}}</span>
          <span class="up-fans">粉丝 ${{fmtNum(up.fans)}}</span>
        </div>
        <div class="up-tags">
          <span class="tag-chip tag-tid">${{up.tid_gen}}</span>
          ${{up.tid_sub ? '<span class="tag-chip tag-sub">' + up.tid_sub + '</span>' : ''}}
          ${{boardLabel}}
          <span class="tag-chip tag-days">${{fmtDt(up.first_charge_date)}}发布首个充电视频 · 距今${{up.days_since}}天</span>
          <span class="tag-chip" style="background:#f5f5f5;color:#666">充电稿件 ${{up.charge_video_cnt}}部</span>
        </div>
      </div>
      <a class="up-space-link" href="${{up.space_url}}" target="_blank">空间主页 →</a>
    </div>

    <div class="up-metrics">
      <div class="metric-item">
        <div class="metric-val pink">${{fmtMoney(up.gmv)}}</div>
        <div class="metric-label">近30日GMV</div>
      </div>
      <div class="metric-item">
        <div class="metric-val">${{fmtNum(up.vv)}}</div>
        <div class="metric-label">近30日VV</div>
      </div>
      <div class="metric-item">
        <div class="metric-val">${{up.ecpvv || '-'}}</div>
        <div class="metric-label">ECPVV</div>
      </div>
      <div class="metric-item">
        <div class="metric-val">${{fmtNum(up.charge_users)}}</div>
        <div class="metric-label">充电人次</div>
      </div>
      <div class="metric-item">
        <div class="metric-val">${{fmtPct(up.cvr)}}</div>
        <div class="metric-label">充电转化率</div>
      </div>
      <div class="metric-item">
        <div class="metric-val">${{fmtMoney(up.avg_daily_gmv)}}</div>
        <div class="metric-label">日均GMV</div>
      </div>
    </div>

    <div class="up-body">
      <div class="up-chart-wrap">
        <div class="up-chart-title">📈 充电视频 GMV & VV 日趋势</div>
        <canvas class="up-chart-canvas" id="chart-${{up.up_id}}"></canvas>
      </div>
      <div class="up-summary-wrap">
        <div class="up-summary-title">📝 内容主题分析 ${{up.sim_ups ? '<span style="font-weight:400;color:var(--text-light);margin-left:8px;font-size:11px">👥 共粉UP: ' + up.sim_ups + '</span>' : ''}}</div>
        <div class="up-summary-text">${{up.summary || '暂无内容信息'}}</div>
      </div>
    </div>

    <div class="expand-btn" id="expand-btn-${{up.up_id}}" onclick="weeklyToggleVideos('${{up.up_id}}')">
      <span>📋 稿件明细（展示Top5 GMV稿件，共${{(VIDEOS[up.up_id] || []).length}}部充电稿件）</span>
      <span class="arrow">▼</span>
    </div>

    <div class="video-list" id="video-list-${{up.up_id}}">
      ${{weeklyBuildVideoList(up.up_id)}}
    </div>
  `;
  return card;
}}

// ===== 稿件列表（Top 5，去掉分区列） =====
function weeklyBuildVideoList(up_id) {{
  const allVideos = VIDEOS[up_id] || [];
  const videos = allVideos.slice(0, 5);
  if (!videos.length) return '<div style="padding:16px;color:#999;text-align:center">暂无稿件数据</div>';

  let html = `
    <div class="video-list-header">
      <div>#</div>
      <div>稿件信息</div>
      <div>稿件类型</div>
      <div>发布时间</div>
      <div>GMV</div>
      <div>VV</div>
      <div>ECPVV</div>
      <div>充电人次</div>
    </div>
  `;

  videos.forEach((v, i) => {{
    const typeClass = v.type.includes('进行中') ? 'type-live' : 'type-free';
    html += `
      <div class="video-row">
        <div class="video-rank">${{i+1}}</div>
        <div class="video-title">
          <a href="${{v.play_url}}" target="_blank">${{v.title || '无标题'}}</a>
          <div class="video-title-sub">AV${{v.avid}} · ${{v.tag ? v.tag.split(',').slice(0,3).join(' · ') : ''}}</div>
        </div>
        <div><span class="${{typeClass}}">${{v.type}}</span></div>
        <div class="video-val">${{v.pubtime}}</div>
        <div class="video-val pink">${{fmtMoney(v.gmv)}}</div>
        <div class="video-val">${{fmtNum(v.vv)}}</div>
        <div class="video-val">${{v.ecpvv || '-'}}</div>
        <div class="video-val">${{fmtNum(v.charge_users)}}</div>
      </div>
    `;
  }});
  return html;
}}

// ===== 展开/收起稿件 =====
function weeklyToggleVideos(up_id) {{
  const list = document.getElementById('video-list-' + up_id);
  const btn = document.getElementById('expand-btn-' + up_id);
  const isOpen = list.classList.contains('open');
  list.classList.toggle('open', !isOpen);
  btn.classList.toggle('open', !isOpen);
}}

// ===== 渲染趋势图 =====
function weeklyRenderChart(up_id) {{
  const canvas = document.getElementById('chart-' + up_id);
  if (!canvas) return;

  canvas.width  = canvas.parentElement.offsetWidth || 500;
  canvas.height = 120;

  const trend = TRENDS[up_id];
  if (!trend || !trend.dates.length) {{
    canvas.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:120px;color:#ccc;font-size:12px">暂无趋势数据</div>';
    return;
  }}

  if (chartInstances[up_id]) {{ chartInstances[up_id].destroy(); }}

  const labels = trend.dates.map(d => fmtDt(d));
  chartInstances[up_id] = new Chart(canvas, {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [
        {{
          label: 'GMV(¥)',
          data: trend.gmv,
          borderColor: '#FB7299',
          backgroundColor: 'rgba(251,114,153,0.08)',
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.4,
          fill: true,
          yAxisID: 'y1',
        }},
        {{
          label: 'VV',
          data: trend.vv,
          borderColor: '#4A90E2',
          backgroundColor: 'rgba(74,144,226,0.05)',
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.4,
          fill: false,
          yAxisID: 'y2',
        }},
      ]
    }},
    options: {{
      responsive: false,
      animation: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{
          display: true,
          position: 'top',
          labels: {{ boxWidth: 12, font: {{ size: 10 }} }},
          onClick: function() {{}}
        }},
        tooltip: {{ bodyFont: {{ size: 11 }}, titleFont: {{ size: 11 }} }}
      }},
      scales: {{
        x: {{
          ticks: {{ font: {{ size: 9 }}, maxTicksLimit: 10, maxRotation: 0 }},
          grid: {{ display: false }}
        }},
        y1: {{
          position: 'left',
          ticks: {{ font: {{ size: 9 }}, callback: v => '¥' + v }},
          grid: {{ color: 'rgba(0,0,0,0.04)' }}
        }},
        y2: {{
          position: 'right',
          ticks: {{ font: {{ size: 9 }} }},
          grid: {{ display: false }}
        }}
      }}
    }}
  }});
}}

// ===== 初始化 =====
weeklyInitFilterTags();
weeklyRenderPene();
weeklyRenderBoard();
</script>
</body>
</html>"""

output_path = 'c:/Users/dengyuting02/WorkBuddy/20260514140206/charging_up_leaderboard.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'HTML已生成: {output_path}')
print(f'文件大小: {len(html)/1024:.0f} KB')
