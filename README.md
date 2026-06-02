# 充电UP榜单工作流

B 站充电 UP 主 & 稿件分析看板的全自动生成流水线。

## 流水线（7 步）

```bash
python run_all.py                # 1. 取数：6 SQL，串/并行
python update_board_count.py     # 2. 累加上榜次数（天粒度）
python run_api.py                # 3. UP 内容总结（增量调 LLM）
python gen_hot_topics.py         # 4. UP 热点主题
python gen_video_hot_topics.py   # 5. 稿件热点主题
python build_dashboard.py        # 6. 生成双 tab dashboard
python merge_tab3.py             # 7. 拉取并注入「商业&充电潜力UP主榜」Tab3
```

## 环境

跑 `run_all.py` 前需设置 berserker 平台 token：

```powershell
# Windows PowerShell
$env:ADHOC_TOKEN="your_token"

# Windows cmd
set ADHOC_TOKEN=your_token
```

## 文件说明

| 类别 | 文件 |
|---|---|
| 取数 SQL | `code1_up_rank.sql` ~ `code6_top100.sql` |
| 主流程脚本 | `run_all.py` / `update_board_count.py` / `run_api.py` / `gen_hot_topics.py` / `gen_video_hot_topics.py` / `build_dashboard.py` / `merge_tab3.py` |
| 最终产物 | `charging_up_dashboard_3tab.html` |

中间数据（result_*.json、up_summaries.json、board_count.json 等）按 `.gitignore` 排除，本地生成不入库。

## 上榜次数计数

- 当前：天粒度（`update_board_count.py` 第 31 行 `GRANULARITY = 'day'`）
- 切换周粒度：`python update_board_count.py --reset` 后改 `GRANULARITY = 'week'`
- 同周期重复跑幂等不重加；本期未出现的 UP 自动从状态文件清理（脱榜清理）

## 增量调用

- `run_api.py`：用稿件指纹（标题+分区+tag+ASR）的 sha1 决定是否重跑某 UP；`--force` 强制全跑
- `gen_hot_topics.py` / `gen_video_hot_topics.py`：用输入 hash 判断；`--force` 强制重算
