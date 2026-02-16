# Observability & Data Fix Design

## Problem

推送的新闻质量不佳：可能不够新、不够深度。当前流水线缺少可观测性，无法定位问题出在哪一步。

## Root Cause Analysis

1. **Collector 丢失时间信息** — `published` 全部设为 `datetime.now()`，真实发布时间丢失
2. **Collector 无摘要** — `summary` 直接复制 `title`，ranker 只能看到标题
3. **Ranker 信息匮乏** — LLM 只拿到标题和标题的复制品，无法判断时效性和深度
4. **无中间结果** — 流水线跑完只看到最终推送，无法定位问题步骤

## Design

### 1. Collector: 从 URL 解析真实发布日期

URL 格式：`/athletic/6271893/2026/02/15/slug`

- 用现有的 `_ARTICLE_URL_PATTERN` 捕获组提取 `YYYY/MM/DD`
- 构造真实 `published` datetime
- 尝试提取链接父容器中的摘要文本作为 `summary`

### 2. Ranker: 增强 LLM 上下文

- 传递发布时间给 LLM
- System prompt 增加时效性权重："优先选择最近 24 小时发布的文章"
- 如果 summary 和 title 不同，一并传递

### 3. 全流程日志增强

| 步骤 | INFO 级别日志 | DEBUG 级别日志 |
|------|--------------|---------------|
| Collector | 每篇文章标题+日期列表 | 完整 Article 对象 |
| Ranker | 选中的文章标题列表 | 发送给 LLM 的完整 prompt、LLM 原始返回 |
| Scraper | 每篇全文长度、是否 fallback | - |
| Analyzer | 解析结果数量 | LLM 原始返回 |

### 4. 中间结果文件输出

`main.py` 每步完成后写入 `output/YYYY-MM-DD/`:

- `step1_collected.json` — 所有采集文章
- `step2_ranked.json` — 排序后选中文章
- `step3_scraped.json` — 全文（截断前 200 字）
- `step4_analyzed.json` — 分析结果

`output/` 目录加入 `.gitignore`。

## Files to Modify

- `src/collector.py` — 解析 URL 日期、提取摘要、增强日志
- `src/ranker.py` — prompt 增加时间上下文、增强日志
- `src/scraper.py` — 增强日志
- `src/analyzer.py` — 增强日志
- `main.py` — 中间结果文件输出
- `.gitignore` — 添加 `output/`
