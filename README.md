# 充电新星UP主周榜

B站充电新星UP主周榜自动化生成系统。每周输入新数据文件，自动输出含热点主题、分区筛选、趋势图、详细指标的交互式HTML报告。

## 文件说明

| 文件 | 作用 |
|------|------|
| `run_api.py` | 批量调用B站API，生成每个UP主的内容总结 |
| `gen_hot_topics.py` | 读取所有UP总结，二次调API识别热点主题 |
| `build_leaderboard.py` | 主脚本，读取Excel数据+API总结，生成最终HTML |
| `charging_up_leaderboard.html` | 独立版（新星榜 only） |
| `charging_up_leaderboard_merged.html` | 合并版（新星榜+同事潜力榜双Tab） |
| `colleague_backup.html` | 同事潜力榜备份（只读，更新时从GitHub拉取） |

## 换周操作流程（SOP）

```bash
# Step 1: 修改 run_api.py 第5行 path 为新数据文件路径，然后运行（约10分钟）
python run_api.py

# Step 2: 生成热点主题（约1分钟）
python gen_hot_topics.py

# Step 3: 修改 build_leaderboard.py 第5行路径，生成最终HTML（约10秒）
python build_leaderboard.py

# Step 4: 如需合并同事潜力榜，运行合并脚本
python merge_colleague_tab.py

# Step 5: git add + commit + push
```

## 数据说明

- 数据文件：`表汇总MMDD.xlsx`，每周更新
- 包含字段：UP名称、UID、粉丝数、一级/二级分区、近30日GMV、VV、充电人次等
- 共粉UP数据：表4 共粉up（如有）

## 页面功能

- 🔥 热点主题总结（大模型生成，卡片式展示）
- 📂 分区多选筛选 + 渗透率数据联动
- 🏆 UP主榜单（Top20展示，GMV降序）
- 👥 共粉UP信息（内容分析旁显示相似UP）
- 📥 下载筛选后全量数据（CSV格式）
- 📈 每个UP主的GMV趋势迷你图
