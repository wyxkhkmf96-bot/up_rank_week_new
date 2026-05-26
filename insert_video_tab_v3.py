import json

# 读取数据
with open('video_top100.json', 'r', encoding='utf-8') as f:
    videos = json.load(f)
with open('video_hot_topics.json', 'r', encoding='utf-8') as f:
    hot_topics = json.load(f)

# 读取稳定版融合HTML
with open('charging_up_leaderboard_merged.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f'Original size: {len(html)}')

# ========== 1. 删除旧的 const VIDEOS 数据块 ==========
script_tag_start = html.find('<script>')
script_tag_end = html.find('</script>', script_tag_start)
script_content = html[script_tag_start+8:script_tag_end]

vidx = script_content.find('const VIDEOS')
if vidx != -1:
    # 找到这个块的结束位置：下一个以 'const ' 或 'function ' 开头的行
    next_const = script_content.find('const ', vidx + 1)
    next_func = script_content.find('function ', vidx + 1)
    candidates = [x for x in [next_const, next_func] if x != -1]
    end_idx = min(candidates) if candidates else len(script_content)
    
    # 在完整HTML中的位置
    remove_start = script_tag_start + 8 + vidx
    remove_end = script_tag_start + 8 + end_idx
    
    print(f'Removing old VIDEOS: {remove_start}-{remove_end} ({remove_end - remove_start} chars)')
    html = html[:remove_start] + html[remove_end:]
    
    # 更新script范围
    script_tag_end = html.find('</script>', script_tag_start)
    script_content = html[script_tag_start+8:script_tag_end]
else:
    print('No old VIDEOS found')

# ========== 2. 生成热点主题HTML ==========
def parse_hot_topics(text):
    cards = []
    parts = text.split('---')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = [l.strip() for l in part.split('\n') if l.strip()]
        title = ''
        ups = ''
        desc = ''
        for line in lines:
            if line.startswith('🔥'):
                title = line.replace('🔥', '').strip()
            elif line.startswith('代表UP：'):
                ups = line.replace('代表UP：', '').strip()
            elif line.startswith('趋势描述：'):
                desc = line.replace('趋势描述：', '').strip()
        if title:
            cards.append({'title': title, 'ups': ups, 'desc': desc})
    return cards

cards = parse_hot_topics(hot_topics.get('hot_topics', ''))
hot_html = ''
for c in cards:
    up_tags = ''.join(f'<span class="hot-up-tag">{u.strip()}</span>' for u in c['ups'].split('、') if u.strip())
    hot_html += f'''<div class="hot-topic-card">
  <div class="hot-topic-title">🔥 {c['title']}</div>
  <div class="hot-topic-ups">{up_tags}</div>
  <div class="hot-topic-desc">{c['desc']}</div>
</div>\n'''

# ========== 3. 生成视频Tab JS代码 ==========
tids = sorted(list(set(str(v.get('一级分区', '')) for v in videos if v.get('一级分区'))))
video_cols = ['UP主ID', 'UP主昵称', '粉丝数', '稿件ID', '稿件标题', '稿件类型', '播放页', '发布时间', '一级分区', '二级分区', 'tag', '稿件近30日GMV', '稿件近30日播放量', '稿件近30日ECPVV', '稿件近30日充电人数', '稿件近30日转化率']
video_data = [{k: v.get(k, '') for k in video_cols} for v in videos]

js_videos = json.dumps(video_data, ensure_ascii=False, indent=2)
js_tids = json.dumps(tids, ensure_ascii=False)

video_js = f'''
// ===== 充电稿件Top100 数据 =====
const VIDEOS = {js_videos};
const VIDEO_TID_LIST = {js_tids};
let selectedVideoTid = 'all';

function initVideoFilterTags() {{
  const container = document.getElementById('video-filter-tags');
  VIDEO_TID_LIST.forEach(tid => {{
    const span = document.createElement('span');
    span.className = 'filter-tag';
    span.dataset.tid = tid;
    span.textContent = tid;
    span.onclick = function() {{ filterVideoByTid(this, tid); }};
    container.appendChild(span);
  }});
}}

function filterVideoByTid(el, tid) {{
  selectedVideoTid = tid;
  document.querySelectorAll('#video-filter-tags .filter-tag').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[data-vtid]').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  renderVideoBoard();
}}

function getFilteredVideos() {{
  if (selectedVideoTid === 'all') return VIDEOS;
  return VIDEOS.filter(v => v['一级分区'] === selectedVideoTid);
}}

function renderVideoBoard() {{
  const filtered = getFilteredVideos();
  const container = document.getElementById('video-board');
  const countEl = document.getElementById('video-board-count');
  const labelTid = selectedVideoTid === 'all' ? '' : ' · ' + selectedVideoTid;
  countEl.textContent = `${{labelTid}} · 共 ${{filtered.length}} 条稿件`;

  if (filtered.length === 0) {{
    container.innerHTML = '<div style="text-align:center;padding:40px;color:#999;">暂无数据</div>';
    return;
  }}

  let html = '<div class="video-table-wrap"><table class="video-table"><thead><tr>';
  const headers = ['排名', 'UP主', '稿件标题', '一级分区', '二级分区', 'GMV', '播放量', 'ECPVV', '充电人数', '转化率'];
  headers.forEach(h => {{ html += `<th>${{h}}</th>`; }});
  html += '</tr></thead><tbody>';

  filtered.forEach((v, i) => {{
    const rank = i + 1;
    const rankClass = rank <= 3 ? 'rank-' + rank : 'rank-n';
    const gmv = Number(v['稿件近30日GMV'] || 0).toLocaleString();
    const play = Number(v['稿件近30日播放量'] || 0).toLocaleString();
    const ecpvv = Number(v['稿件近30日ECPVV'] || 0).toFixed(2);
    const charge = Number(v['稿件近30日充电人数'] || 0).toLocaleString();
    const cvr = (Number(v['稿件近30日转化率'] || 0) * 100).toFixed(2) + '%';
    html += `<tr>
      <td><span class="up-rank ${{rankClass}}">${{rank}}</span></td>
      <td><div class="video-up"><div class="video-up-name">${{v['UP主昵称']}}</div><div class="video-up-fans">${{Number(v['粉丝数']||0).toLocaleString()}}粉</div></div></td>
      <td><a href="${{v['播放页']||'#'}}" target="_blank" class="video-title">${{v['稿件标题']}}</a></td>
      <td><span class="tag-chip tag-tid">${{v['一级分区']}}</span></td>
      <td><span class="tag-chip tag-sub">${{v['二级分区']}}</span></td>
      <td class="video-num">${{gmv}}</td>
      <td class="video-num">${{play}}</td>
      <td class="video-num">${{ecpvv}}</td>
      <td class="video-num">${{charge}}</td>
      <td class="video-num">${{cvr}}</td>
    </tr>`;
  }});

  html += '</tbody></table></div>';
  container.innerHTML = html;
}}

function downloadVideoCSV() {{
  const filtered = getFilteredVideos();
  const cols = ['UP主ID', 'UP主昵称', '粉丝数', '稿件ID', '稿件标题', '稿件类型', '播放页', '发布时间', '一级分区', '二级分区', 'tag', '稿件近30日GMV', '稿件近30日播放量', '稿件近30日ECPVV', '稿件近30日充电人数', '稿件近30日转化率'];
  let csv = '\\ufeff' + cols.join(',') + '\\n';
  filtered.forEach(v => {{
    const row = cols.map(c => {{
      let val = v[c] !== undefined ? String(v[c]) : '';
      if (val.includes(',') || val.includes('"') || val.includes('\\n')) {{
        val = '"' + val.replace(/"/g, '""') + '"';
      }}
      return val;
    }});
    csv += row.join(',') + '\\n';
  }});
  const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = '充电稿件Top100_筛选结果.csv';
  link.click();
}}

let videoTabInited = false;
function initVideoTab() {{
  if (videoTabInited) return;
  videoTabInited = true;
  initVideoFilterTags();
  renderVideoBoard();
}}
'''

# ========== 4. 插入CSS ==========
css_add = '''\n/* ===== 视频表格样式 ===== */
.video-table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }
.video-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.video-table thead { background: linear-gradient(135deg, #FC3D7E, #FB7299); color: white; }
.video-table th { padding: 10px 8px; text-align: left; font-weight: 600; white-space: nowrap; }
.video-table td { padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
.video-table tbody tr:hover { background: #fff8fa; }
.video-table tbody tr:nth-child(even) { background: #fafafa; }
.video-table tbody tr:nth-child(even):hover { background: #fff8fa; }
.video-title { color: var(--text); text-decoration: none; font-weight: 600; display: block; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.video-title:hover { color: var(--pink); text-decoration: underline; }
.video-up-name { font-weight: 600; color: var(--text); font-size: 12px; }
.video-up-fans { font-size: 11px; color: var(--text-light); }
.video-num { font-family: 'SF Mono', monospace; font-weight: 600; color: var(--pink); white-space: nowrap; text-align: right; }
'''

# 插入到 </style> 之前
style_end = html.find('</style>')
if style_end != -1:
    html = html[:style_end] + css_add + html[style_end:]
    print('CSS inserted')
else:
    print('Warning: </style> not found')

# ========== 5. 添加Tab按钮 ==========
old_tabs = '<button class="page-tab-btn" onclick="switchTab(\'potential\')">商业&充电潜力UP主榜</button>'
new_tabs = '<button class="page-tab-btn" onclick="switchTab(\'potential\')">商业&充电潜力UP主榜</button>\n  <button class="page-tab-btn" onclick="switchTab(\'video\')">充电稿件Top100</button>'
if old_tabs in html:
    html = html.replace(old_tabs, new_tabs)
    print('Tab button inserted')
else:
    print('Warning: Tab button target not found')

# ========== 6. 修改switchTab函数 ==========
old_switch = "if (name === 'potential' && !potInited) potInit();"
new_switch = "if (name === 'potential' && !potInited) potInit();\n  if (name === 'video') initVideoTab();"
if old_switch in html:
    html = html.replace(old_switch, new_switch)
    print('switchTab modified')
else:
    print('Warning: switchTab target not found')

# ========== 7. 插入视频Tab HTML到tab-potential之后 ==========
# 用栈匹配法找tab-potential的结束</div>
tab_potential_start = html.find('<div id="tab-potential" class="page-content">')
if tab_potential_start == -1:
    print('Error: tab-potential not found')
    exit(1)

stack = 0
pos = tab_potential_start
while pos < len(html):
    div_open = html.find('<div', pos)
    div_close = html.find('</div>', pos)
    if div_open == -1: div_open = len(html)
    if div_close == -1: div_close = len(html)
    if div_open < div_close:
        tag_end = html.find('>', div_open)
        if tag_end != -1 and html[tag_end-1] != '/':
            stack += 1
        pos = div_open + 4
    elif div_close < div_open:
        stack -= 1
        pos = div_close + 6
        if stack == 0:
            break
    else:
        break

tab_potential_end = pos
print(f'tab-potential ends at: {tab_potential_end}')

video_tab_html = f'''

<!-- Tab3: 充电稿件Top100 -->
<div id="tab-video" class="page-content">
<div class="main">

  <!-- 热点主题总结 -->
  <div class="hot-topics-panel">
    <div class="hot-topics-header">
      <span>🔥 热门主题总结</span>
      <small>本周充电稿件Top100内容趋势</small>
    </div>
    <div class="hot-topics-body">
      {hot_html.strip()}
    </div>
  </div>

  <!-- 一级分区筛选 -->
  <div class="filter-panel">
    <div class="filter-row">
      <span class="filter-label">📂 分区筛选：</span>
      <span class="filter-tag active" data-vtid="all" onclick="filterVideoByTid(this, 'all')">全部</span>
      <span id="video-filter-tags"></span>
    </div>
  </div>

  <!-- 稿件榜单 -->
  <div class="board-panel">
    <div class="board-header">
      <div class="board-title">🎬 充电稿件Top100</div>
      <div class="board-right">
        <div class="board-count" id="video-board-count"></div>
        <a class="download-btn" id="video-download-btn" onclick="downloadVideoCSV()" title="下载筛选后全量数据">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载全量
        </a>
      </div>
    </div>
    <div id="video-board"></div>
  </div>

</div>
</div>
'''

html = html[:tab_potential_end] + video_tab_html + html[tab_potential_end:]
print('Video tab HTML inserted')

# ========== 8. 插入视频Tab JS到现有script中 ==========
# 找到script中 switchTab 函数的位置，在它之前插入
script_tag_start = html.find('<script>')
script_tag_end = html.find('</script>', script_tag_start)

switch_func_pos = html.find('function switchTab', script_tag_start)
if switch_func_pos == -1 or switch_func_pos > script_tag_end:
    print('Warning: switchTab not found in script, inserting at script start')
    insert_pos = script_tag_start + 8
else:
    insert_pos = switch_func_pos
    print(f'Inserting JS before switchTab at {insert_pos}')

html = html[:insert_pos] + video_js + '\n' + html[insert_pos:]

with open('charging_up_leaderboard_merged.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Done. New HTML size: {len(html)} chars')

# ========== 9. 验证 ==========
print('\n--- Verification ---')
s = html.find('<script>')
e = html.find('</script>', s)
content = html[s+8:e]
matches = content.count('const VIDEOS =')
print(f'const VIDEOS occurrences: {matches}')
print(f'Has initVideoTab: {content.includes("function initVideoTab")}')
print(f'Script size: {len(content)}')
