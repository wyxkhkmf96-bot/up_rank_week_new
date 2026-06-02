"""Step 7: 拉取仓库 main 分支最新的 charging_up_dashboard_3tab.html，
从中切出 Tab3「商业&充电潜力UP主榜」，注入到本地刚生成的双 tab dashboard，
输出最终的三 tab dashboard。

原理：
- 双 tab 部分用本地 charging_up_dashboard.html（数据是最新的）
- Tab3 部分从 github 上拉的版本里切（仓库版本可能被同事或脚本更新）
- 不依赖上游别人的仓库，只读自己仓库

拉取失败时降级使用上次的本地缓存（如果有）。
"""
import os
import re
import sys
import urllib.request
import urllib.error

BASE = r'C:\Users\dengyuting02\WorkBuddy\20260514140206'
REPO_URL = 'https://raw.githubusercontent.com/wyxkhkmf96-bot/up_rank_week_new/main/charging_up_dashboard_3tab.html'
LOCAL_DASHBOARD = os.path.join(BASE, 'charging_up_dashboard.html')          # 本地双 tab
REMOTE_CACHE = os.path.join(BASE, '.charging_up_dashboard_3tab.remote.html')  # 远程缓存
OUT = os.path.join(BASE, 'charging_up_dashboard_3tab.html')                 # 本地最终三 tab


def fetch_remote():
    """拉取仓库最新三 tab html，缓存到本地。失败时降级用上次缓存。"""
    print(f'📥 拉取仓库三 tab dashboard: {REPO_URL}')
    try:
        req = urllib.request.Request(REPO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read().decode('utf-8')
        with open(REMOTE_CACHE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'   ✓ 已缓存: {REMOTE_CACHE} ({len(content)/1024:.0f} KB)')
        return content
    except Exception as e:
        print(f'   ✗ 拉取失败 ({e.__class__.__name__}: {e})')
        if os.path.exists(REMOTE_CACHE):
            print(f'   ⚠ 降级使用上次缓存: {REMOTE_CACHE}')
            with open(REMOTE_CACHE, 'r', encoding='utf-8') as f:
                return f.read()
        print('   ✗ 本地无缓存，无法继续', file=sys.stderr)
        sys.exit(1)


def extract_pot_blocks(remote_html):
    """从远程三 tab html 切出 Tab3 的 CSS / HTML / JS 三块。

    兼容两种格式：
    - 上游 leaderboard_merged 格式：pot CSS 后面紧跟 Tab2 短类名（.fp .vc 等）
    - 我们的 dashboard_3tab 格式：pot CSS 在整个 style 块末尾
    """
    lines = remote_html.splitlines(keepends=True)

    def find_idx(needle, start=0):
        for i in range(start, len(lines)):
            if needle in lines[i]:
                return i
        raise RuntimeError(f'远程 html 中未找到锚点: {needle!r}')

    # CSS 起点：潜力榜筛选注释（pot 块第一个独有标记）
    css_start = find_idx('/* ===== 潜力榜筛选')
    # CSS 终点：优先用 .fp{（上游格式），找不到就用 </style>（我们的格式）
    css_end = None
    for i in range(css_start, len(lines)):
        if '.fp{' in lines[i]:
            css_end = i
            break
        if '</style>' in lines[i]:
            css_end = i
            break
    if css_end is None:
        raise RuntimeError('未找到 pot CSS 块结束位置')
    pot_css = ''.join(lines[css_start:css_end])
    # 移除源文件中改写 .page-tab-btn padding 的 @media 条款（dashboard 用底边线条样式）
    pot_css = re.sub(
        r'@media \(max-width: 900px\) \{\s*\n\s*\.pot-metrics[^}]+\}\s*\n\s*\.page-tab-btn[^}]+\}\s*\n\}\s*\n',
        '@media (max-width: 900px) { .pot-metrics { grid-template-columns: repeat(3, 1fr); } }\n',
        pot_css,
    )

    # HTML 起点：Tab3 容器注释
    html_start = find_idx('<!-- Tab2: 商业&充电潜力UP主榜 -->')
    # HTML 终点：下一个 <script>（数据注入块）
    html_end = find_idx('<script>', html_start)
    pot_html = ''.join(lines[html_start:html_end]).rstrip() + '\n'

    # JS 起点：商业&充电潜力UP主榜 注释行往前 2 行（含分隔符）
    js_start = find_idx('// 商业&充电潜力UP主榜')
    # JS 终点：优先到第一个"// 初始化"之前（避免把双 tab 的 weeklyInitFilterTags() 调用拖回来），
    # 找不到再退回 </script>
    js_end = None
    for i in range(js_start, len(lines)):
        if '// 初始化' in lines[i]:
            js_end = i
            # 回退到上一个分隔注释行（"// ====="之前），保持代码块整洁
            while js_end > js_start and lines[js_end - 1].strip().startswith('//'):
                js_end -= 1
            break
    if js_end is None:
        js_end = find_idx('</script>', js_start)
    pot_js = ''.join(lines[js_start - 2:js_end])

    return pot_css, pot_html, pot_js


def inject_into_dashboard(dashboard_html, pot_css, pot_html, pot_js):
    """把 Tab3 三块注入到本地双 tab dashboard。"""
    out = dashboard_html

    # A) CSS：在 </style> 之前
    css_inject = '\n  /* ===== Tab3: 商业&充电潜力UP主榜 ===== */\n' + pot_css + '\n'
    assert '</style>' in out
    out = out.replace('</style>', css_inject + '</style>', 1)

    # B) tab 按钮：在 darkhorse 按钮之后追加（顺序：新星/黑马/潜力）
    btn_old = '<button class="page-tab-btn" onclick="switchTab(\'darkhorse\')">🐎 黑马UP</button>'
    assert btn_old in out, '未找到 darkhorse tab 按钮锚点'
    btn_new = (btn_old +
               '\n  <button class="page-tab-btn" onclick="switchTab(\'potential\')">'
               '📈 商业&充电潜力UP主榜</button>')
    out = out.replace(btn_old, btn_new, 1)

    # C) tab HTML 容器：在末尾数据 <script> 前
    data_anchor = '<script>\nconst UPS = '
    assert data_anchor in out, '未找到数据 <script> 锚点'
    out = out.replace(data_anchor, pot_html + '\n' + data_anchor, 1)

    # D) switchTab 钩子：整行追加避免破坏模板字符串
    sw_old_line = "  document.querySelector(`.page-tab-btn[onclick*=\"'${name}'\"]`).classList.add('active');\n"
    assert sw_old_line in out, '未找到 switchTab 函数末行锚点'
    sw_new_line = sw_old_line + "  if (name === 'potential' && !potInited) potInit();\n"
    out = out.replace(sw_old_line, sw_new_line, 1)

    # E) POT JS 块：在 weeklyInitFilterTags() 初始化前
    init_anchor = '// 初始化\n// ============================================================\nweeklyInitFilterTags();'
    assert init_anchor in out, '未找到末尾初始化锚点'
    out = out.replace(init_anchor, pot_js + '\n' + init_anchor, 1)

    return out


# ---------- 主流程 ----------
remote_html = fetch_remote()
pot_css, pot_html, pot_js = extract_pot_blocks(remote_html)
print(f'\nCSS  {len(pot_css):>8,} chars')
print(f'HTML {len(pot_html):>8,} chars')
print(f'JS   {len(pot_js):>8,} chars')

if not os.path.exists(LOCAL_DASHBOARD):
    print(f'\n✗ 找不到本地双 tab: {LOCAL_DASHBOARD}', file=sys.stderr)
    print(f'  请先运行 python build_dashboard.py', file=sys.stderr)
    sys.exit(1)

with open(LOCAL_DASHBOARD, 'r', encoding='utf-8') as f:
    dashboard = f.read()

merged = inject_into_dashboard(dashboard, pot_css, pot_html, pot_js)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(merged)

print(f'\n✅ 三tab HTML 已生成: {OUT}')
print(f'   本地双 tab: {len(dashboard):>10,} bytes')
print(f'   最终三 tab: {len(merged):>10,} bytes (+{len(merged)-len(dashboard):,})')
