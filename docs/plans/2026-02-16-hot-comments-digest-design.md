# Hot Comments Digest Design

## Goal

新增一条独立流水线，每天北京时间 7:30 推送评论数最多的 5 篇英超文章摘要到微信。

## Data Flow

```
hot_collector (爬列表页获取文章 → 逐篇获取评论数 → 按评论数排序 → top 5)
  → scraper (复用，抓全文)
  → analyzer (复用，LLM 中文分析)
  → notifier (推送，标题 "英超热议文章 - YYYY-MM-DD")
```

不需要 ranker，评论数本身就是排序依据。

## New Files

- `src/hot_collector.py` — 评论数采集器
  - 复用 `_is_premier_league` 和 `_ARTICLE_URL_PATTERN` 从列表页获取英超文章
  - 逐篇打开文章页，用 CSS selector 获取评论数
  - 返回 `list[Article]`，按 `comment_count` 降序，取前 5
- `main_hot.py` — 独立入口，编排 hot_collector → scraper → analyzer → notifier

## Model Change

`Article` dataclass 新增字段：
```python
comment_count: int = 0
```

## Notifier Change

`format_digest` 支持自定义标题前缀参数，热评推送显示评论数。

## Workflow Change

`.github/workflows/daily.yml` 新增 cron `30 23 * * *`（UTC 23:30 = 北京 07:30），运行 `python main_hot.py`。

## Key Risk

评论数 CSS selector 未知，需要先探查页面结构确认。实施第一步应该是写探查脚本找到评论数元素。

## Files to Create/Modify

- Create: `src/hot_collector.py`
- Create: `main_hot.py`
- Modify: `src/models.py` — Article 加 `comment_count`
- Modify: `src/notifier.py` — 支持自定义标题前缀
- Modify: `.github/workflows/daily.yml` — 新增 job
- Create: `tests/test_hot_collector.py`
