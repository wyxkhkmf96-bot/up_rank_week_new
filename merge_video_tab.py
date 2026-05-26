import re

# ========== 1. 读取 videos.html ==========
with open('charging_up_videos.html', 'r', encoding='utf-8') as f:
    v_html = f.read()

# 提取CSS
style_match = re.search(r'<style>(.*?)</style>', v_html, re.DOTALL)
if not style_match:
    raise ValueError('无法在 videos.html 中找到 <style>')
v_css = style_match.group(1)

# 去掉已在 merged.html 中定义的重复部分 (:root, body, .header 等)
v_css = re.sub(r'\s*:root\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\*\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*body\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
# 去掉 .header 相关（merged.html 已有）
v_css = re.sub(r'\s*\.header\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\.header-top\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\.header\s+h1\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\.header\s+h1\s+span\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\.header-meta\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
v_css = re.sub(r'\s*\.header-badge\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)
# 去掉 .main（merged.html 已有）
v_css = re.sub(r'\s*\.main\s*\{[^{}]*\}', '', v_css, flags=re.DOTALL)

# 提取 main div 内容
main_start = v_html.find('<div class="main">')
main_tag_end = v_html.find('>', main_start)
pos = main_tag_end + 1
depth = 1
main_end = None
while pos < len(v_html) and depth > 0:
    next_open = v_html.find('<div', pos)
    next_close = v_html.find('</div>', pos)
    if next_close == -1:
        break
    if next_open != -1 and next_open < next_close:
        depth += 1
        pos = next_open + 4
    else:
        depth -= 1
        pos = next_close + 6
        if depth == 0:
            main_end = next_close
            break

main_content = v_html[main_tag_end + 1 : main_end].strip()

# 提取JS
script_match = re.search(r'<script>(.*?)</script>', v_html, re.DOTALL)
if not script_match:
    raise ValueError('无法在 videos.html 中找到 <script>')
v_js = script_match.group(1)

# ========== 2. 重命名JS变量和函数（加video前缀避免冲突） ==========
# 函数定义
v_js = re.sub(r'\bfunction filterByTid\b', 'function videoFilterByTid', v_js)
v_js = re.sub(r'\bfunction renderVideos\b', 'function videoRenderBoard', v_js)
v_js = re.sub(r'\bfunction downloadCSV\b', 'function videoDownloadCSV', v_js)
# 变量定义
v_js = re.sub(r'\blet selTids\b', 'let videoSelTids', v_js)
v_js = re.sub(r'\bconst VIDEOS\b', 'const VIDEO_DATA', v_js)
# 所有引用（单词边界）
v_js = re.sub(r'\bselTids\b', 'videoSelTids', v_js)
v_js = re.sub(r'\bVIDEOS\b', 'VIDEO_DATA', v_js)

# ========== 3. 重命名HTML中的onclick ==========
main_content = main_content.replace('onclick="filterByTid', 'onclick="videoFilterByTid')
main_content = main_content.replace('onclick="downloadCSV()', 'onclick="videoDownloadCSV()')

# ========== 4. 读取 merged.html ==========
with open('charging_up_leaderboard_merged.html', 'r', encoding='utf-8') as f:
    m_html = f.read()

# ========== 5. 插入CSS（在 </style> 之前） ==========
m_html = m_html.replace('</style>', v_css.strip() + '\n</style>')

# ========== 6. 插入Tab按钮 ==========
m_html = m_html.replace(
    '<button class="page-tab-btn" onclick="switchTab(\'potential\')">商业&充电潜力UP主榜</button>',
    '<button class="page-tab-btn" onclick="switchTab(\'videos\')">🎬 充电稿件Top100</button>\n  <button class="page-tab-btn" onclick="switchTab(\'potential\')">商业&充电潜力UP主榜</button>'
)

# ========== 7. 插入Tab内容（在tab-weekly和tab-potential之间） ==========
tab_videos_html = f'''<!-- Tab2: 充电稿件Top100 -->
<div id="tab-videos" class="page-content">
<div class="main">
{main_content}
</div>
</div>

'''
m_html = m_html.replace('<!-- Tab2: 商业&充电潜力UP主榜 -->', tab_videos_html + '<!-- Tab2: 商业&充电潜力UP主榜 -->')

# ========== 8. 插入JS（在同事代码分隔线之前） ==========
video_js_block = f'''// ============================================================
// 充电稿件Top100
// ============================================================
{v_js}

'''
# 在第一个 "商业&充电潜力UP主榜" 分隔线之前插入
marker = '// ============================================================\n// 商业&充电潜力UP主榜\n// ============================================================'
m_html = m_html.replace(marker, video_js_block + marker)

# ========== 9. 在script末尾添加videoRenderBoard初始化调用 ==========
# 找到 renderPene();\nrenderBoard(); 之后添加
m_html = m_html.replace(
    'renderPene();\nrenderBoard();',
    'renderPene();\nrenderBoard();\nvideoRenderBoard();'
)

# ========== 10. 写入 ==========
with open('charging_up_leaderboard_merged.html', 'w', encoding='utf-8') as f:
    f.write(m_html)

# ========== 11. 验证 ==========
print('=== 验证 ===')
print(f'1. 文件大小: {len(m_html):,} chars')

# 检查div标签平衡
div_opens = m_html.count('<div')
div_closes = m_html.count('</div>')
ok = div_opens == div_closes
print(f'2. <div> tags: {div_opens} open / {div_closes} close {"OK" if ok else "MISMATCH"}')

# 检查script标签
scripts = re.findall(r'<script[^>]*>', m_html)
print(f'3. <script> 标签: {len(scripts)} 个')

# 检查变量名冲突
conflicts = []
if re.search(r'\bconst\s+VIDEOS\b', m_html):
    conflicts.append('const VIDEOS (重复声明)')
if re.search(r'\blet\s+selTids\b', m_html):
    conflicts.append('let selTids (重复声明)')
if m_html.count('function filterByTid(') > 1:
    conflicts.append('function filterByTid (重复定义)')
if m_html.count('function downloadCSV(') > 1:
    conflicts.append('function downloadCSV (重复定义)')
if conflicts:
    print(f'4. Variable conflicts: FAIL {conflicts}')
else:
    print('4. Variable conflicts: OK none')

# 检查Tab结构
tabs = re.findall(r'id="tab-[^"]+"', m_html)
print(f'5. Tab内容区: {tabs}')

btns = re.findall(r'switchTab\(\'([^\']+)\'\)', m_html)
print(f'6. Tab按钮: {btns}')

print('\nDONE: charging_up_leaderboard_merged.html')
