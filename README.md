# 充电新星UP主周榜

B站充电新星UP主周榜自动化生成系统。每周输入新数据文件，自动输出含热点主题、分区筛选、趋势图、详细指标的交互式HTML报告。

## 文件说明

| 文件 | 作用 |
|------|------|
| `run_api.py` | 批量调用B站API，生成每个UP主的内容总结（up_summaries.json） |
| `gen_hot_topics.py` | 读取所有UP总结，二次调API识别热点主题（hot_topics.json） |
| `build_leaderboard.py` | 主脚本，读取Excel数据+JSON总结，生成最终HTML |
| `up_summaries.json` | 本周UP主的AI内容总结（中间产物） |
| `hot_topics.json` | 本周热点主题汇总（中间产物） |
| `charging_up_leaderboard.html` | 最终交付物 |

## 换周操作流程（SOP）

```bash
# Step 1: 修改 run_api.py 第22行 path 为新数据文件路径，然后运行（约10分钟）
python run_api.py

# Step 2: 人工确认 up_summaries.json 内容质量

# Step 3: 生成热点主题（约1分钟）
python gen_hot_topics.py

# Step 4: 人工确认热点是否准确

# Step 5: 生成最终HTML（约10秒）
python build_leaderboard.py
```

## 数据说明

- 数据文件：`表汇总MMDD.xlsx`，每周更新
- 包含字段：UP名称、UID、粉丝数、一级/二级分区、近30日GMV、VV、充电人次等

## 页面功能

- 🔥 热点主题总结（大模型生成，卡片式展示）
- 📂 分区多选筛选 + 渗透率数据联动
- 🏆 UP主榜单（Top20展示，GMV降序）
- 📥 下载筛选后全量数据（CSV格式）
- 📈 每个UP主的GMV趋势迷你图
