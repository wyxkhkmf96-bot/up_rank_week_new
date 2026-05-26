import json

# 读取数据
with open('video_top100.json', 'r', encoding='utf-8') as f:
    videos = json.load(f)
with open('video_hot_topics.json', 'r', encoding='utf-8') as f:
    hot_topics = json.load(f)

# 提取一级分区
tids = sorted(list(set(str(v.get('一级分区', '')) for v in videos if v.get('一级分区'))))

# 处理热点主题文本为卡片格式
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

# 生成热点主题HTML
hot_html = ''
for c in cards:
    up_tags = ''.join(f'<span class="hot-up-tag">{u.strip()}</span>' for u in c['ups'].split('、') if u.strip())
    hot_html += f'''<div class="hot-topic-card">
  <div class="hot-topic-title">🔥 {c['title']}</div>
  <div class="hot-topic-ups">{up_tags}</div>
  <div class="hot-topic-desc">{c['desc']}</div>
</div>\n'''

# 生成视频数据JSON（去掉asr_data）
video_cols = ['UP主ID', 'UP主昵称', '粉丝数', '稿件ID', '稿件标题', '稿件类型', '播放页', '发布时间', '一级分区', '二级分区', 'tag', '稿件近30日GMV', '稿件近30日播放量', '稿件近30日ECPVV', '稿件近30日充电人数', '稿件近30日转化率']
video_data = []
for v in videos:
    row = {k: v.get(k, '') for k in video_cols}
    video_data.append(row)

# 生成JavaScript数据
js_videos = json.dumps(video_data, ensure_ascii=False, indent=2)
js_tids = json.dumps(tids, ensure_ascii=False)

# 生成Tab HTML
tab_html = f'''<!-- Tab3: 充电稿件Top100 -->
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

<script>
// ===== 充电稿件Top100 数据 =====
const VIDEOS = {js_videos};
const VIDEO_TID_LIST = {js_tids};
let selectedVideoTid = 'all';

// ===== 初始化分区筛选标签 =====
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

// ===== 分区筛选 =====
function filterVideoByTid(el, tid) {{
  selectedVideoTid = tid;
  document.querySelectorAll('#video-filter-tags .filter-tag').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[data-vtid]').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  renderVideoBoard();
}}

// ===== 获取筛选后数据 =====
function getFilteredVideos() {{
  if (selectedVideoTid === 'all') return VIDEOS;
  return VIDEOS.filter(v => v['一级分区'] === selectedVideoTid);
}}

// ===== 渲染稿件榜单 =====
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

// ===== 下载CSV =====
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

// ===== 初始化 =====
initVideoFilterTags();
renderVideoBoard();
</script>
'''

with open('video_tab_fragment.html', 'w', encoding='utf-8') as f:
    f.write(tab_html)

print('video_tab_fragment.html generated')
print(f'Videos: {len(videos)}, TIDs: {len(tids)}, Hot topics: {len(cards)}')
