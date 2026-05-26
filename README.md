# 充电新星UP主周榜 & 充电稿件Top100

---

## 工作流①：UP主榜单 → Merge → Push

### 产出物
- `charging_up_leaderboard.html` — 新星榜独立版（单Tab）
- `charging_up_leaderboard_merged.html` — 融合版（新星榜 + 稿件榜 + 同事潜力榜三Tab）

### 依赖文件
| 文件 | 说明 |
|------|------|
| `表汇总MMDD.xlsx` | 每周新数据（UP维度） |
| `run_api.py` | 调用B站API生成UP内容总结 |
| `gen_hot_topics.py` | 生成热点主题 |
| `build_leaderboard.py` | 生成新星榜HTML |
| `up_summaries.json` | UP总结缓存（脚本产出，需保留） |
| `hot_topics.json` | 热点主题缓存（脚本产出，需保留） |
| `colleague_backup.html` | 同事潜力榜备份（只读，更新时从GitHub拉取最新） |

### 操作步骤

```bash
# Step 1: 修改 run_api.py 第5行 path 为新Excel路径，运行（~10分钟，增量更新）
python run_api.py

# Step 2: 生成热点主题（~1分钟）
python gen_hot_topics.py

# Step 3: 修改 build_leaderboard.py 第5行路径，生成独立版HTML（~10秒）
python build_leaderboard.py
# 产出: charging_up_leaderboard.html

# Step 4: 【Merge】把独立版新星榜内容同步到 merged.html
# ⚠️ 只替换新星榜Tab的内容部分（tab-weekly），保留稿件榜Tab和同事潜力榜Tab完全不动
# 具体：用独立版中 <div class="tab-content" id="tab-weekly"> ... </div> 内的全部内容
#       替换 merged.html 中对应 tab-weekly 的内容
# ⚠️ 不要动 script 标签中的同事代码（以 "=================================================\nconst POT_DATA" 为界）

# Step 5: Push
# git add charging_up_leaderboard.html charging_up_leaderboard_merged.html up_summaries.json hot_topics.json
# git commit -m "update: YYYY-MM-DD UP主榜单"
# git push
```

---

## 工作流②：稿件榜单 → Merge → Push

### 产出物
- `charging_up_videos.html` — 稿件榜独立版（单页）
- `charging_up_leaderboard_merged.html` — 融合版中的稿件榜Tab（同步更新）

### 依赖文件
| 文件 | 说明 |
|------|------|
| `稿件榜MMDD.xlsx` | 每周新数据（稿件维度） |
| `build_video_leaderboard.py` | 生成稿件榜HTML |
| `merge_video_tab.py` | 将稿件榜融合到 merged.html 的脚本 |

### 操作步骤

```bash
# Step 1: Excel → JSON（手动执行，见脚本内注释）
# 用Python读取Excel，导出 video_top100.json

# Step 2: 调用B站API生成热点主题
# 使用 build_video_leaderboard.py 中注释掉的API调用代码（或手动调用）
# 产出: video_hot_topics.json

# Step 3: 确认 video_top100.json 和 video_hot_topics.json 存在后，生成独立版HTML（~10秒）
python build_video_leaderboard.py
# 产出: charging_up_videos.html

# Step 4: 【Merge】把稿件榜融合到 merged.html
# 运行融合脚本，自动处理变量名前缀、CSS合并、Tab插入
python merge_video_tab.py
# 产出: charging_up_leaderboard_merged.html（已包含三Tab）

# Step 5: Push
# git add charging_up_videos.html charging_up_leaderboard_merged.html video_top100.json video_hot_topics.json
# git commit -m "update: YYYY-MM-DD 稿件榜单"
# git push
```

---

## 页面功能速查

| 页面 | 功能 |
|------|------|
| 新星榜独立版 / 融合版-新星Tab | 热点主题、上榜类型筛选、分区多选+渗透率、UP榜单(TOP20)、共粉UP、趋势图、下载CSV |
| 融合版-稿件Tab | 5个热点主题(各5案例)、分区多选筛选、全量100条稿件榜单、下载CSV |
| 融合版-潜力Tab | 同事维护，只读不修改 |
| 稿件榜独立版 | 同融合版-稿件Tab，独立页面 |

## 关键约束

- **融合版 merged.html**：三Tab结构，修改时只动对应Tab的内容，其他Tab完全不动
- **变量名隔离**：稿件榜JS变量和函数均已加 `video` 前缀（videoFilterByTid/videoRenderBoard/videoDownloadCSV/videoSelTids/VIDEO_DATA），避免与新星榜冲突
- **缓存文件**：`up_summaries.json`、`hot_topics.json`、`video_top100.json`、`video_hot_topics.json` 需保留
