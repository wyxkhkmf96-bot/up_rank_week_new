"""Step 6: 拉取最新 charging_up_leaderboard_merged.html 并把"商业&充电潜力UP主榜"
作为第3个 tab 注入到 charging_up_dashboard.html 的副本，输出到
charging_up_dashboard_3tab.html。

不改动原双 tab 文件 charging_up_dashboard.html。

拉取失败时降级使用本地已缓存的 charging_up_leaderboard_merged.html。
"""
import os
import re
import urllib.request
import urllib.error

BASE = r'C:\Users\dengyuting02\claude output\charging_up_newstar'
LEADERBOARD_URL = 'https://raw.githubusercontent.com/wyxkhkmf96-bot/up_rank_week_new/main/charging_up_leaderboard_merged.html'
SRC_LEADERBOARD = os.path.join(BASE, 'charging_up_leaderboard_merged.html')
SRC_DASHBOARD = os.path.join(BASE, 'charging_up_dashboard.html')
OUT = os.path.join(BASE, 'charging_up_dashboard_3tab.html')


def fetch_leaderboard():
    """拉最新 leaderboard_merged.html 覆盖本地。失败时降级用本地缓存。"""
    try:
        print(f'📥 拉取最新 leaderboard_merged: {LEADERBOARD_URL}')
        req = urllib.request.Request(LEADERBOARD_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')
        with open(SRC_LEADERBOARD, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'   ✓ 已覆盖本地: {SRC_LEADERBOARD} ({len(content)/1024:.0f} KB)')
        return content
    except Exception as e:
        print(f'   ✗ 拉取失败 ({e.__class__.__name__}: {e})')
        if os.path.exists(SRC_LEADERBOARD):
            print(f'   ⚠ 降级使用本地缓存: {SRC_LEADERBOARD}')
            with open(SRC_LEADERBOARD, 'r', encoding='utf-8') as f:
                return f.read()
        raise RuntimeError('GitHub 拉取失败且本地无缓存，无法继续') from e


leaderboard_html = fetch_leaderboard()
src_lines = leaderboard_html.splitlines(keepends=True)
with open(SRC_DASHBOARD, 'r', encoding='utf-8') as f:
    dashboard = f.read()


def find_idx(needle, start=0):
    for i in range(start, len(src_lines)):
        if needle in src_lines[i]:
            return i
    raise RuntimeError(f'未在 leaderboard 中找到: {needle!r}')


# 1) CSS: "/* ===== 潜力榜筛选" 起 → ".fp{" 之前（潜力榜 CSS 之后是 Tab2 短类名，不能并入）
css_start = find_idx('/* ===== 潜力榜筛选')
css_end = find_idx('.fp{', css_start)
pot_css = ''.join(src_lines[css_start:css_end])
# 移除源文件中改写 .page-tab-btn 的 @media 条款（dashboard 用底边线条样式）
pot_css = re.sub(
    r'@media \(max-width: 900px\) \{\s*\n\s*\.pot-metrics[^}]+\}\s*\n\s*\.page-tab-btn[^}]+\}\s*\n\}\s*\n',
    '@media (max-width: 900px) { .pot-metrics { grid-template-columns: repeat(3, 1fr); } }\n',
    pot_css,
)

# 2) HTML: "<!-- Tab2: 商业&充电潜力UP主榜 -->" 起 → 紧跟的 <script>
html_start = find_idx('<!-- Tab2: 商业&充电潜力UP主榜 -->')
html_end = find_idx('<script>', html_start)
pot_html = ''.join(src_lines[html_start:html_end]).rstrip() + '\n'

# 3) JS: "// 商业&充电潜力UP主榜" 注释行往前 2 行（含分隔符）→ </script>
js_start = find_idx('// 商业&充电潜力UP主榜')
js_end = find_idx('</script>', js_start)
pot_js = ''.join(src_lines[js_start - 2:js_end])

print(f'\nCSS  {len(pot_css):>8,} chars')
print(f'HTML {len(pot_html):>8,} chars')
print(f'JS   {len(pot_js):>8,} chars')

# ============== 注入到 dashboard ==============
out = dashboard

# A) CSS: 在 </style> 之前
css_inject = '\n  /* ===== Tab3: 商业&充电潜力UP主榜 ===== */\n' + pot_css + '\n'
assert '</style>' in out
out = out.replace('</style>', css_inject + '</style>', 1)

# B) tab 按钮: 在 videos 按钮之后追加
btn_old = '<button class="page-tab-btn" onclick="switchTab(\'videos\')">🎬 新充电稿件Top100</button>'
assert btn_old in out, '未找到 videos tab 按钮锚点'
btn_new = (btn_old +
           '\n  <button class="page-tab-btn" onclick="switchTab(\'potential\')">'
           '📈 商业&充电潜力UP主榜</button>')
out = out.replace(btn_old, btn_new, 1)

# C) tab HTML 容器: 在末尾数据 <script> 前
data_anchor = '<script>\nconst UPS = '
assert data_anchor in out, '未找到数据 <script> 锚点'
out = out.replace(data_anchor, pot_html + '\n' + data_anchor, 1)

# D) switchTab 钩子: 整行追加避免破坏模板字符串中的 ${name}
sw_old_line = "  document.querySelector(`.page-tab-btn[onclick*=\"'${name}'\"]`).classList.add('active');\n"
assert sw_old_line in out, '未找到 switchTab 函数末行锚点'
sw_new_line = sw_old_line + "  if (name === 'potential' && !potInited) potInit();\n"
out = out.replace(sw_old_line, sw_new_line, 1)

# E) POT JS 块: 在 weeklyInitFilterTags() 初始化前
init_anchor = '// 初始化\n// ============================================================\nweeklyInitFilterTags();'
assert init_anchor in out, '未找到末尾初始化锚点'
out = out.replace(init_anchor, pot_js + '\n' + init_anchor, 1)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(out)

print(f'\n✅ 三tab HTML 已生成: {OUT}')
print(f'   原 dashboard: {len(dashboard):>10,} bytes')
print(f'   新 3-tab    : {len(out):>10,} bytes (+{len(out)-len(dashboard):,})')
