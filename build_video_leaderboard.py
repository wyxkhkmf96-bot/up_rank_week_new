import json
import re
from datetime import datetime

VIDEO_JSON = 'video_top100.json'
HOT_JSON = 'video_hot_topics.json'
OUT_HTML = 'charging_up_videos.html'

with open(VIDEO_JSON, 'r', encoding='utf-8') as f:
    videos = json.load(f)

with open(HOT_JSON, 'r', encoding='utf-8') as f:
    hot_data = json.load(f)
    hot_topics_raw = hot_data.get('hot_topics', '')

# 解析热点主题
hot_topics = []
for block in hot_topics_raw.split('---'):
    block = block.strip()
    if not block: continue
    lines = [l.strip() for l in block.split('\n') if l.strip()]
    topic = {'name': '', 'trend': '', 'cases': []}
    in_cases = False
    for line in lines:
        if line.startswith('🔥'):
            topic['name'] = line.replace('🔥', '').strip()
        elif line.startswith('趋势描述：'):
            topic['trend'] = line.replace('趋势描述：', '').strip()
        elif '趋势描述' in line and '：' in line and not line.startswith('代表'):
            topic['trend'] = line.split('：', 1)[1].strip()
        elif line.startswith('代表'):
            in_cases = True
        elif in_cases and re.match(r'^\d+\.', line):
            topic['cases'].append(line)
    if topic['name']:
        hot_topics.append(topic)

all_tids = sorted({v['一级分区'] for v in videos if v.get('一级分区')})

def fmt_num(n):
    if n is None: return '-'
    if n >= 10000: return f'{n/10000:.1f}w'
    return f'{int(n):,}'

def fmt_money(n):
    if n is None: return '-'
    return f'¥{n:,.0f}'

def fmt_rate(n):
    if n is None: return '-'
    return f'{n*100:.2f}%'

def fmt_date(s):
    if not s or s == 'nan': return '-'
    return str(s).split()[0]

# 热点主题HTML（竖列，每个带5个case）
hot_html = ''
for topic in hot_topics:
    cases = ''
    for case in topic['cases'][:5]:
        m = re.search(r'(.+?)《(.+?)》', case)
        if m:
            up_name = m.group(1).strip()
            vid_title = m.group(2).strip()
            play_url = ''
            for v in videos:
                if v.get('UP主昵称') == up_name and v.get('稿件标题') == vid_title:
                    play_url = v.get('播放页', '')
                    break
            if play_url:
                cases += f'<a href="{play_url}" target="_blank" class="case-link">{up_name}《{vid_title}》</a>'
            else:
                cases += f'<span class="case-link no-link">{up_name}《{vid_title}》</span>'
        else:
            cases += f'<span class="case-link no-link">{case}</span>'
    hot_html += f'''
<div class="ht-v">
  <div class="ht-h">
    <div class="ht-name">🔥 {topic['name']}</div>
    <div class="ht-trend">{topic['trend']}</div>
  </div>
  <div class="ht-cases">
    <div class="cases-label">代表稿件：</div>
    {cases}
  </div>
</div>'''

# 分区标签
tid_tags = ''.join(f'<span class="ft" data-tid="{t}" onclick="filterByTid(this, \'{t}\')">{t}</span>' for t in all_tids)

# 初始卡片
init_cards = ''
for rank, v in enumerate(videos, 1):
    url = v.get('播放页', '')
    title = v.get('稿件标题', '')
    tl = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    rc = f'rank-{rank}' if rank <= 3 else 'rank-n'
    init_cards += f'''
<div class="vc" data-tid="{v.get('一级分区','')}">
  <div class="vch">
    <div class="vr {rc}">{rank}</div>
    <div class="vi">
      <div class="vt">{tl}</div>
      <div class="vmr"><span class="vn">{v.get('UP主昵称','')}</span><span class="vf">粉丝 {fmt_num(v.get('粉丝数'))}</span></div>
      <div class="vtags"><span class="tc tt">{v.get('一级分区','')}</span><span class="tc ts">{v.get('二级分区','')}</span><span class="tc" style="background:#f5f5f5;color:#666">{v.get('稿件类型','')}</span><span class="tc td">{fmt_date(v.get('发布时间',''))}</span></div>
      <div class="vtagl">{v.get('tag','')}</div>
    </div>
    <a class="vsl" href="https://space.bilibili.com/{v.get('UP主ID','')}" target="_blank">空间主页 →</a>
  </div>
  <div class="vm">
    <div class="mi"><div class="mv pink">{fmt_money(v.get('稿件近30日GMV'))}</div><div class="ml">近30日GMV</div></div>
    <div class="mi"><div class="mv">{fmt_num(v.get('稿件近30日播放量'))}</div><div class="ml">播放量</div></div>
    <div class="mi"><div class="mv">{v.get('稿件近30日ECPVV') or '-'}</div><div class="ml">ECPVV</div></div>
    <div class="mi"><div class="mv">{fmt_num(v.get('稿件近30日充电人数'))}</div><div class="ml">充电人数</div></div>
    <div class="mi"><div class="mv">{fmt_rate(v.get('稿件近30日转化率'))}</div><div class="ml">转化率</div></div>
    <div class="mi"><div class="mv">{fmt_num(v.get('粉丝数'))}</div><div class="ml">粉丝数</div></div>
  </div>
</div>'''

VIDEO_DATA_JS = json.dumps(videos, ensure_ascii=False, indent=2)
TIDS_JS = json.dumps(all_tids, ensure_ascii=False)

gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>充电稿件Top100</title>
<style>
:root{{--pink:#FB7299;--pl:#fff0f5;--pd:#e05a7a;--blue:#4A90E2;--bg:#f7f8fc;--card:#fff;--bd:#eef0f5;--t:#1a1a2e;--ts:#6b7280;--tl:#9ca3af;--sh:0 2px 12px rgba(0,0,0,0.06);--shh:0 6px 24px rgba(251,114,153,0.15);}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--t);font-size:13px}}
.header{{background:linear-gradient(135deg,#FC3D7E 0%,#FB7299 50%,#ff9bb5 100%);padding:20px 32px 16px;color:#fff;box-shadow:0 2px 12px rgba(251,114,153,0.3)}}
.header h1{{font-size:22px;font-weight:700}}
.header-meta{{font-size:12px;opacity:.8;margin-top:6px}}
.main{{max-width:1280px;margin:0 auto;padding:20px 24px}}

.fp{{background:var(--card);border-radius:12px;padding:14px 20px 12px;margin-bottom:16px;box-shadow:var(--sh);border:2px solid var(--pink)}}
.fr{{display:flex;align-items:center;flex-wrap:wrap;gap:8px}}
.fl{{font-size:12px;color:var(--pink);font-weight:700;margin-right:4px;white-space:nowrap}}
.ft{{padding:5px 14px;border-radius:20px;border:1.5px solid var(--bd);background:#fff;color:var(--ts);cursor:pointer;font-size:12px;font-weight:500;transition:all .2s;user-select:none}}
.ft:hover{{border-color:var(--pink);color:var(--pink)}}
.ft.active{{background:var(--pink);border-color:var(--pink);color:#fff;font-weight:600}}

.htp{{background:var(--card);border-radius:12px;box-shadow:var(--sh);overflow:hidden;margin-bottom:16px}}
.hth{{background:linear-gradient(135deg,#f093fb,#f5576c);color:#fff;padding:12px 20px;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:space-between}}
.hth small{{font-size:11px;font-weight:400;opacity:.85}}
.htb{{padding:16px 20px;display:flex;flex-direction:column;gap:14px}}
.ht-v{{background:linear-gradient(135deg,#fff8fa,#fff0f5);border:1.5px solid #fbd0e0;border-radius:10px;padding:14px 18px;transition:box-shadow .2s}}
.ht-v:hover{{box-shadow:0 4px 16px rgba(245,87,108,.15);border-color:var(--pink)}}
.ht-name{{font-size:15px;font-weight:800;color:#f5576c;margin-bottom:6px}}
.ht-trend{{font-size:13px;color:var(--ts);line-height:1.6}}
.ht-cases{{display:flex;flex-direction:column;gap:5px;padding-top:10px;border-top:1px dashed #fbd0e0;margin-top:10px}}
.cl{{font-size:12px;font-weight:600;color:var(--pink);margin-bottom:2px}}
.ca{{font-size:12px;color:var(--t);text-decoration:none;padding:4px 10px;background:#fff;border-radius:6px;border:1px solid var(--bd);display:block;transition:all .15s;line-height:1.4}}
.ca:hover{{color:var(--pink);border-color:var(--pink);background:var(--pl)}}
.ca.nl{{color:var(--ts);cursor:default}}
.ca.nl:hover{{color:var(--ts);border-color:var(--bd);background:#fff}}

.bp{{min-width:0}}
.bh{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
.bt{{font-size:20px;font-weight:800;color:var(--t);letter-spacing:.5px}}
.br{{display:flex;align-items:center;gap:10px}}
.bc{{font-size:12px;color:var(--ts)}}
.db{{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:8px;border:1.5px solid var(--pink);background:#fff;color:var(--pink);font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;user-select:none;text-decoration:none}}
.db:hover{{background:var(--pink);color:#fff}}
.db svg{{width:14px;height:14px}}

.vc{{background:var(--card);border-radius:12px;box-shadow:var(--sh);margin-bottom:14px;overflow:hidden;transition:box-shadow .2s;border:1px solid transparent}}
.vc:hover{{box-shadow:var(--shh);border-color:rgba(251,114,153,.2)}}
.vch{{padding:14px 18px;display:flex;align-items:flex-start;gap:14px;border-bottom:1px solid var(--bd)}}
.vr{{min-width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;flex-shrink:0;background:var(--pl);color:var(--pink)}}
.r1{{background:linear-gradient(135deg,#FB7299,#FF9BB5);color:#fff}}
.r2{{background:linear-gradient(135deg,#FB7299,#FF9BB5);color:#fff}}
.r3{{background:linear-gradient(135deg,#FB7299,#FF9BB5);color:#fff}}
.vi{{flex:1;min-width:0}}
.vt{{font-size:16px;font-weight:700;color:var(--t);line-height:1.5;margin-bottom:6px}}
.vt a{{color:var(--blue);text-decoration:none}}
.vt a:hover{{color:var(--pink);text-decoration:underline}}
.vmr{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}}
.vn{{font-size:13px;font-weight:600;color:var(--ts)}}
.vf{{font-size:11px;color:var(--tl);background:#f5f5f5;border-radius:10px;padding:2px 8px}}
.vtags{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:4px}}
.tc{{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}}
.tt{{background:#e8f4ff;color:#1890ff}}
.ts{{background:#f0fff4;color:#52c41a}}
.td{{background:#fff7e6;color:#fa8c16}}
.vtagl{{font-size:11px;color:var(--tl);line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.vsl{{color:var(--pink);text-decoration:none;font-size:11px;border:1px solid var(--pink);border-radius:12px;padding:3px 10px;transition:all .2s;flex-shrink:0;align-self:flex-start;white-space:nowrap}}
.vsl:hover{{background:var(--pink);color:#fff}}
.vm{{display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid var(--bd)}}
.mi{{padding:10px 8px;text-align:center;border-right:1px solid var(--bd)}}
.mi:last-child{{border-right:none}}
.mv{{font-size:15px;font-weight:700;color:var(--t);line-height:1.2}}
.mv.pink{{color:var(--pink)}}
.ml{{font-size:10px;color:var(--tl);margin-top:2px}}

.nr{{text-align:center;padding:60px 20px;color:var(--tl);font-size:14px}}
.nr .i{{font-size:40px;margin-bottom:12px}}

@media(max-width:900px){{.vm{{grid-template-columns:repeat(3,1fr)}}.vt{{font-size:14px}}}}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div><h1>🎬 充电稿件Top100</h1><div class="header-meta">数据范围：近30日充电稿件Top100，按GMV降序排列 · 生成时间：{gen_time}</div></div>
  </div>
</div>

<div class="main">

<div class="htp">
  <div class="hth"><span>🔥 热门主题总结</span><small>本周充电稿件内容趋势</small></div>
  <div class="htb">{hot_html}</div>
</div>

<div class="fp">
  <div class="fr"><span class="fl">📂 分区筛选：</span><span class="ft active" data-tid="all" onclick="filterByTid(this,'all')">全部</span>{tid_tags}</div>
</div>

<div class="bp">
  <div class="bh">
    <div class="bt">🏆 稿件榜单</div>
    <div class="br">
      <div class="bc" id="bc">共 {len(videos)} 部稿件</div>
      <a class="db" onclick="downloadCSV()" title="下载筛选后全量数据">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        下载全量
      </a>
    </div>
  </div>
  <div id="vb">{init_cards}</div>
</div>

</div>

<script>
const VIDEOS={VIDEO_DATA_JS};
const TIDS={TIDS_JS};
let selTids=[];

function fn(n){{if(n==null)return'-';if(n>=1e4)return(n/1e4).toFixed(1)+'w';return n.toLocaleString()}}
function fm(n){{if(!n)return'-';return'¥'+n.toFixed(0).replace(/\B(?=(\d{{3}})+(?!\d))/g,',')}}
function fr(n){{if(!n)return'-';return(n*100).toFixed(2)+'%'}}
function fd(s){{if(!s||s=='nan')return'-';return String(s).split(' ')[0]}}

function filterByTid(el,tid){{
  if(tid==='all'){{selTids=[];document.querySelectorAll('.ft[data-tid]').forEach(t=>t.classList.remove('active'));el.classList.add('active')}}
  else{{
    document.querySelector('.ft[data-tid="all"]').classList.remove('active');
    if(el.classList.contains('active')){{el.classList.remove('active');selTids=selTids.filter(t=>t!==tid)}}
    else{{el.classList.add('active');selTids.push(tid)}}
    if(selTids.length===0){{document.querySelector('.ft[data-tid="all"]').classList.add('active')}}
  }}
  renderVideos();
}}

function renderVideos(){{
  const board=document.getElementById('vb');board.innerHTML='';
  let filtered=VIDEOS;
  if(selTids.length>0){{filtered=VIDEOS.filter(v=>selTids.includes(v['一级分区']))}}
  const lt=selTids.length===0?'全部分区':selTids.join('、');
  document.getElementById('bc').textContent=lt+' · 共 '+filtered.length+' 部稿件';
  if(filtered.length===0){{board.innerHTML='<div class="nr"><div class="i">🔍</div>所选分区暂无稿件</div>';return}}
  filtered.forEach((v,i)=>{{
    const rank=i+1,rc=rank<=3?'r'+rank:'rank-n',url=v['播放页']||'',title=v['稿件标题']||'';
    const tl=url?'<a href="'+url+'" target="_blank">'+title+'</a>':title;
    const c=document.createElement('div');c.className='vc';
    c.innerHTML='<div class="vch"><div class="vr '+rc+'">'+rank+'</div><div class="vi"><div class="vt">'+tl+'</div><div class="vmr"><span class="vn">'+(v['UP主昵称']||'')+'</span><span class="vf">粉丝 '+fn(v['粉丝数'])+'</span></div><div class="vtags"><span class="tc tt">'+(v['一级分区']||'')+'</span><span class="tc ts">'+(v['二级分区']||'')+'</span><span class="tc" style="background:#f5f5f5;color:#666">'+(v['稿件类型']||'')+'</span><span class="tc td">'+fd(v['发布时间'])+'</span></div><div class="vtagl">'+(v['tag']||'')+'</div></div><a class="vsl" href="https://space.bilibili.com/'+(v['UP主ID']||'')+'" target="_blank">空间主页 →</a></div><div class="vm"><div class="mi"><div class="mv pink">'+fm(v['稿件近30日GMV'])+'</div><div class="ml">近30日GMV</div></div><div class="mi"><div class="mv">'+fn(v['稿件近30日播放量'])+'</div><div class="ml">播放量</div></div><div class="mi"><div class="mv">'+(v['稿件近30日ECPVV']||'-')+'</div><div class="ml">ECPVV</div></div><div class="mi"><div class="mv">'+fn(v['稿件近30日充电人数'])+'</div><div class="ml">充电人数</div></div><div class="mi"><div class="mv">'+fr(v['稿件近30日转化率'])+'</div><div class="ml">转化率</div></div><div class="mi"><div class="mv">'+fn(v['粉丝数'])+'</div><div class="ml">粉丝数</div></div></div>';
    board.appendChild(c);
  }});
}}

function downloadCSV(){{
  let filtered=VIDEOS;
  if(selTids.length>0){{filtered=VIDEOS.filter(v=>selTids.includes(v['一级分区']))}}
  if(!filtered.length){{alert('当前无数据可下载');return}}
  const h='\\uFEFF排名,UP主昵称,粉丝数,稿件ID,稿件标题,稿件类型,播放页,发布时间,一级分区,二级分区,tag,近30日GMV,近30日播放量,近30日ECPVV,近30日充电人数,近30日转化率';
  const rows=filtered.map((v,i)=>[i+1,'"'+(v['UP主昵称']||'').replace(/"/g,'""')+'"',v['粉丝数']||'',v['稿件ID']||'','"'+(v['稿件标题']||'').replace(/"/g,'""')+'"',v['稿件类型']||'',v['播放页']||'',v['发布时间']||'',v['一级分区']||'',v['二级分区']||'','"'+(v['tag']||'').replace(/"/g,'""')+'"',v['稿件近30日GMV']||'',v['稿件近30日播放量']||'',v['稿件近30日ECPVV']||'',v['稿件近30日充电人数']||'',v['稿件近30日转化率']!=null?(v['稿件近30日转化率']*100).toFixed(2)+'%':''].join(','));
  const csv=h+'\\n'+rows.join('\\n');
  const blob=new Blob([csv],{{type:'text/csv;charset=utf-8'}});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  const lt=selTids.length===0?'全部':selTids.join('_');
  a.href=url;a.download='充电稿件Top100_'+lt+'_'+new Date().toISOString().slice(0,10)+'.csv';a.click();URL.revokeObjectURL(url);
}}
</script>
</body>
</html>'''

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'✅ 已生成: {OUT_HTML}')
print(f'   稿件数: {len(videos)}')
print(f'   热点主题: {len(hot_topics)} 个（每个5个案例）')
print(f'   一级分区: {all_tids}')
