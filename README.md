# 充电新星UP主周榜 & 充电稿件Top100

---

## 一键工作流（推荐）

```bash
# 更新两个榜单
python pipeline.py --up-excel "C:/.../表汇总MM.DD.xlsx" --video-excel "C:/.../稿件榜MM.DD.xlsx"

# 只更新UP主榜单
python pipeline.py --up-excel "C:/.../表汇总MM.DD.xlsx"

# 只更新稿件榜单
python pipeline.py --video-excel "C:/.../稿件榜MM.DD.xlsx"

# 跳过API调用（使用现有JSON缓存，仅重生成HTML）
python pipeline.py --up-excel "..." --video-excel "..." --skip-api
```

**产出文件：**
- `charging_up_leaderboard.html` — 新星榜独立版
- `charging_up_videos.html` — 稿件榜独立版
- `charging_up_leaderboard_merged.html` — 三Tab融合版

---

## 分步工作流（手动控制各阶段）

### UP主榜单

| 步骤 | 脚本 | 说明 | 耗时 |
|------|------|------|------|
| 1 | `run_api.py` | 增量调用B站API生成UP内容总结 | ~10分钟 |
| 2 | `gen_hot_topics.py` | 调用API生成热点主题 | ~1分钟 |
| 3 | `build_leaderboard.py` | 生成新星榜独立版HTML | ~10秒 |

### 稿件榜单

| 步骤 | 脚本 | 说明 | 耗时 |
|------|------|------|------|
| 1 | `pipeline.py` 内联 | Excel → `video_top100.json` | ~5秒 |
| 2 | `pipeline.py` 内联 | 调用API生成稿件热点主题 | ~1分钟 |
| 3 | `build_video_leaderboard.py` | 生成稿件榜独立版HTML | ~10秒 |

### 融合版组装

| 步骤 | 脚本 | 说明 |
|------|------|------|
| 组装 | `pipeline.py` 内联 | 精确替换 merged.html 中的Tab内容和JS |

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `pipeline.py` | **主控脚本**，一键完成全工作流 |
| `run_api.py` | 调用B站Chatbot API生成UP内容总结 |
| `gen_hot_topics.py` | 读取summary生成热点主题 |
| `build_leaderboard.py` | 生成新星榜独立版HTML |
| `build_video_leaderboard.py` | 生成稿件榜独立版HTML |
| `up_summaries.json` | UP总结缓存（保留，增量更新） |
| `hot_topics.json` | 热点主题缓存 |
| `video_top100.json` | 稿件数据缓存 |
| `video_hot_topics.json` | 稿件热点主题缓存 |
| `colleague_backup.html` | 同事潜力榜备份（只读） |

---

## 页面功能

| 页面 | 功能 |
|------|------|
| 新星榜独立版 | 热点主题、上榜类型筛选、分区多选+渗透率、UP榜单(TOP20)、共粉UP、趋势图、下载CSV |
| 稿件榜独立版 | 5个热点主题(各5案例)、分区多选筛选、全量100条稿件榜单、下载CSV |
| 融合版-新星Tab | 同新星榜独立版 |
| 融合版-稿件Tab | 同稿件榜独立版 |
| 融合版-潜力Tab | 同事维护，pipeline只读不修改 |

---

## 关键约束

- **融合版 merged.html**：三Tab结构，pipeline精确替换对应Tab的HTML和JS，同事潜力Tab完全不动
- **变量名隔离**：新星榜JS使用 `weekly` 前缀（`weeklyFilterByTid`/`weeklyRenderBoard`），稿件榜使用原始名（`filterByTid`/`renderVideos`/`VIDEOS`），无冲突
- **缓存文件**：`up_summaries.json`、`hot_topics.json`、`video_top100.json`、`video_hot_topics.json` 需保留，支持增量更新
