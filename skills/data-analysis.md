---
title: 数据分析
description: 使用 Python pandas/matplotlib 进行数据清洗、统计分析、可视化图表生成
category: data
capabilities: [data_analysis, visualization, statistics, pandas, matplotlib]
triggers: [数据分析, 统计, 图表, pandas, matplotlib, 可视化, 数据清洗, 报表]
---

# 数据分析流程

## 标准步骤

1. **数据加载**：CSV/Excel/JSON/数据库/SQL
2. **数据探索**：head(), info(), describe(), 缺失值检查
3. **数据清洗**：去重、填充缺失值、格式统一、异常值处理
4. **特征工程**：衍生变量、编码、标准化
5. **分析建模**：聚合统计、相关性分析、分组对比
6. **可视化**：柱状图、折线图、散点图、热力图
7. **报告输出**：结论 + 图表 + 建议

## 常用代码模板

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取数据
df = pd.read_csv("data.csv", encoding="utf-8")

# 基本信息
print(df.shape)
print(df.dtypes)
print(df.isnull().sum())
print(df.describe())

# 分组聚合
result = df.groupby("category").agg({
    "value": ["count", "mean", "sum", "std"]
}).round(2)

# 时间趋势图
df["date"] = pd.to_datetime(df["date"])
daily = df.groupby("date")["value"].sum()
daily.plot(figsize=(12, 4), title="Daily Trend")
plt.tight_layout()
plt.savefig("trend.png", dpi=150)

# Top N 分析
top10 = df["category"].value_counts().head(10)
top10.plot(kind="barh", title="Top 10 Categories")
plt.tight_layout()
plt.savefig("top10.png", dpi=150)
```

## 输出格式
- 分析结论用中文 bullet points
- 图表保存为 PNG（dpi=150）
- 数据文件导出为 UTF-8 CSV
- 不确定的数据标注"待验证"
