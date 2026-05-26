import re

# 读取融合版HTML
with open('charging_up_leaderboard_merged.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 读取视频Tab片段
with open('video_tab_fragment.html', 'r', encoding='utf-8') as f:
    video_tab = f.read()

# 1. 添加CSS样式（在 .page-content.active 之后）
css_add = '''
/* ===== 视频表格样式 ===== */
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

html = html.replace('.page-content { display: none; }\n.page-content.active { display: block; }',
    '.page-content { display: none; }\n.page-content.active { display: block; }' + css_add)

# 2. 添加Tab按钮
old_tabs = '''<div class="page-tabs">
  <button class="page-tab-btn active" onclick="switchTab('weekly')">充电新星UP主周榜</button>
  <button class="page-tab-btn" onclick="switchTab('potential')">商业&充电潜力UP主榜</button>
</div>'''

new_tabs = '''<div class="page-tabs">
  <button class="page-tab-btn active" onclick="switchTab('weekly')">充电新星UP主周榜</button>
  <button class="page-tab-btn" onclick="switchTab('potential')">商业&充电潜力UP主榜</button>
  <button class="page-tab-btn" onclick="switchTab('video')">充电稿件Top100</button>
</div>'''

html = html.replace(old_tabs, new_tabs)

# 3. 在tab-potential之后插入视频Tab
# 找到tab-potential的结束位置（通过查找同事代码分隔线）
insert_marker = '<!-- Tab2: 商业&充电潜力UP主榜 -->\n<div id="tab-potential" class="page-content">'
# 我们需要在tab-potential的</div>之后插入，但要小心嵌套
# 用更可靠的方式：找到同事代码分隔线之前的那个</div>
# 实际上tab-potential是在同事代码之前的
# 让我找 "// ============================================================\n// 页面Tab切换"
# 视频Tab应该插入在tab-potential关闭之后，也就是同事代码之前

tab_potential_end = html.find('<div id="tab-potential" class="page-content">')
# 从tab-potential开始，用栈匹配找到对应的</div>
stack = 0
pos = tab_potential_end
while pos < len(html):
    div_open = html.find('<div', pos)
    div_close = html.find('</div>', pos)
    if div_open == -1: div_open = len(html)
    if div_close == -1: div_close = len(html)
    if div_open < div_close and div_open != -1:
        # 检查是否是自闭合
        tag_end = html.find('>', div_open)
        if tag_end != -1 and not html[tag_end-1] == '/':
            stack += 1
        pos = div_open + 4
    elif div_close < div_open and div_close != -1:
        stack -= 1
        pos = div_close + 6
        if stack == 0:
            # 找到了tab-potential的结束位置
            break
    else:
        break

# 在tab-potential的</div>之后插入视频Tab
html = html[:pos] + '\n\n' + video_tab + '\n' + html[pos:]

# 4. 修改switchTab函数
old_switch = '''function switchTab(name) {
  document.querySelectorAll('.page-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.page-content').forEach(c => c.classList.remove('active'));
  const btns = document.querySelectorAll('.page-tab-btn');
  btns.forEach(btn => { if (btn.getAttribute('onclick').includes(name)) btn.classList.add('active'); });
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'potential' && !potInited) potInit();
}'''

new_switch = '''function switchTab(name) {
  document.querySelectorAll('.page-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.page-content').forEach(c => c.classList.remove('active'));
  const btns = document.querySelectorAll('.page-tab-btn');
  btns.forEach(btn => { if (btn.getAttribute('onclick').includes(name)) btn.classList.add('active'); });
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'potential' && !potInited) potInit();
}'''

# switchTab其实不需要修改，因为它已经是通用的了
# 但检查一下

with open('charging_up_leaderboard_merged.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Inserted video tab into merged HTML')
print(f'New HTML size: {len(html)} chars')
