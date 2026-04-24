# Digest v2 Design

**Date:** 2026-04-24
**Branch:** `refactor/digest-v2`
**Status:** Approved for planning

## Goals

1. 推送正文瘦身：删除"关键人物与数据"和"影响与展望"两段，把有价值信息融入 detail。
2. 正文流畅度：detail 使用 `**加粗段首：**` 结构化分段，关键数据加粗，直接引语独立成行。
3. 语音播报略长：按篇计字（每篇 500-700），总时长随文章数量自然浮动。
4. 代码重构：合并 main.py / main_hot.py 共享逻辑；prompt 外挂为独立文件；清理根目录历史调试脚本。
5. 为后续迭代让 prompt 文案变更不再需要改 Python 代码。

## Non-Goals

- 不做 prompt 版本化管理。
- 不做 token 成本监控。
- 不做 output 历史 JSON 的向后兼容（中间调试快照，不保留旧结构）。
- 不引入 git worktree 隔离（单分支足够）。
- 不重构 `save_step` / output 落盘机制。

## Data Model

`src/models.py`

```python
@dataclass
class AnalyzedArticle:
    title_cn: str
    title_original: str
    article_type: str
    importance: int
    overview: str
    detail: str
    link: str
```

删除字段：`key_people_and_data`、`impact`。`Article` 保持不变。

## Prompts（外挂为独立文件）

新增目录 `src/prompts/`，两个 UTF-8 文本文件。模块用 `Path(__file__).parent / "prompts" / "<name>.md"` 加载，不打包、不走资源加载器。

### `src/prompts/analyzer.md`

````markdown
你是一位资深英超足球记者和分析师。请对以下英超文章进行深度中文分析。

核心原则：尽量保留原文的丰富内容，不要过度精简。读者希望通过你的分析获取接近原文的信息量，而不仅仅是摘要。

返回一个 JSON 对象，仅包含以下字段：
- title_cn: 中文标题翻译
- title_original: 英文原标题
- article_type: 文章类型（深度分析/新闻报道/战术解读/转会动态/赛后分析）
- importance: 重要性 1-5
- overview: 3-5 句话概述核心论点，独立成立——读完这一段就能知道发生了什么、作者的核心判断是什么（中文）
- detail: 深度转述原文内容（中文）
- link: 原文链接

detail 字段的写作要求：

1. 长度：深度分析类 800-1200 字，普通新闻 400-600 字。宁可不到下限也不要注水。
2. 结构：分 3-5 个小段，每段用 `**加粗段首：**` 起头（如 `**战术转折：**`、`**数据与对比：**`、`**球员状态：**`、`**背景与影响：**`）。不要使用任何 Markdown 标题符号（不要用 #、##、###、####）。
3. 引语：原文中的直接引语用独立一行的 `> ` 起头，不要把引语揉进叙述段落里。
4. 重点：关键数据、比分、转折性事实用 `**粗体**` 标出（例如 **3-2**、**xG 2.41**、**本赛季第 12 球**）。
5. 人名与专名：首次出现的球员名、主教练名、俱乐部名、赛事名保留英文原文，可在其后括注中文（如 `Erling Haaland（哈兰德）`）；同一实体在 detail 中再次出现时，用英文或中文任一种均可，但保持一致。比分始终用数字形式（3-2，而非"三比二"）。
6. 内容覆盖：把原文中的关键人物、核心数据、战术细节、影响与展望有机地融入各段落，不要专设"人物"或"影响"段落——这些信息应该分散在 3-5 个 `**加粗段首：**` 小段里。不要为了结构而结构，段落划分服从内容逻辑。

仅返回 JSON 对象，不要添加任何其他文字，不要包裹 ``` 代码块。
````

### `src/prompts/audio_scripter.md`

```markdown
你是一名中文足球音频节目撰稿人。请根据给定资讯整理成自然、流畅、适合直接口播的中文播报稿。

要求：

1. 结构：开场问候 + 逐篇播报（每篇之间要有自然转场） + 结尾收束。
2. 长度：每篇文章 500-700 汉字，整稿长度按文章数量自然上浮（例如 5 篇 ≈ 2500-3500 字，3 篇 ≈ 1500-2100 字）。不要为了凑字数注水，也不要草草带过。
3. 内容：把每篇 overview 和 detail 的关键论据、数据、引语、战术细节展开讲，像主播在给听众解读，而不是读稿。可以适度加入过渡性评论（"这里值得注意的是……"、"换句话说……"），但不要编造原文没有的事实。
4. 人名与专名：保留英文人名、队名、赛事名、比分原样，不要误译或省略（如 Haaland、Manchester City、3-2、Champions League）。中文听众能听懂英文读音，刻意翻译反而会失真。
5. 风格：像主播在说话——简洁、自然、有节奏感。不要使用 Markdown、项目符号、URL，不要出现"概述"、"详情"、"影响"等书面标签。避免长句堆砌，多用短句和口语化连接词。
6. 输出：只返回播报稿正文，不要任何元信息、标题或说明。
```

## Module Changes

### `src/analyzer.py`

- 删除硬编码 `_SYSTEM_PROMPT`。
- 加载：`_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "analyzer.md").read_text(encoding="utf-8")`。
- `_ANALYZED_FIELDS = {f.name for f in fields(AnalyzedArticle)}` 保持不变；字段白名单会自动随 dataclass 收缩为 7 个。
- 其他逻辑（解析、重试、错误处理）零改动。

### `src/audio_scripter.py`

- 删除硬编码 `_SYSTEM_PROMPT`，改从 `src/prompts/audio_scripter.md` 加载。
- 给 LLM 的 source 字典仅填：`title_cn / title_original / article_type / importance / overview / detail / link`，删去 `key_people_and_data` 和 `impact`。

### `src/notifier.py`

`format_digest` 的 section 模板删除两段：

```python
section = f"""## {i}. {a.title_cn}
**原标题：** {a.title_original}
**类型：** {a.article_type}
**重要性：** {stars}

### 文章概述
{a.overview}

### 详细内容
{a.detail}

🔗 [阅读原文]({a.link})"""
```

### `src/pipeline.py`（新增）

```python
async def run_pipeline(*, mode: Literal["digest", "hot"], config: dict) -> None: ...
```

内部统一流程：collect → (rank 仅 digest) → scrape → analyze → audio(opt) → notify。mode 决定的 4 处差异：

| 维度 | digest | hot |
|---|---|---|
| collect | `collect_articles(page_url, cookies)` | `collect_hot_articles(page_url, cookies, top_n=...)` |
| rank 步骤 | 是，调用 `rank_articles` | 否 |
| `title_prefix` | `英超每日精选` | `英超热议文章` |
| audio `tag_prefix` | `audio-digest` | `audio-hot` |
| output 子目录 | `output/<date>` | `output/hot/<date>` |

保留并瘦身 `main.py` / `main_hot.py` 为 5-10 行入口（logging 初始化 + 调用 `run_pipeline`）。CI workflow、本地命令不变。

### 根目录清理

删除（均为历史调试脚本，pytest 不收集）：

- `test_cookie.py`
- `test_page_structure.py`
- `test_comment_structure.py`
- `test_llm_live.py`
- `test_edge_tts_live.py`

## Tests

| 文件 | 动作 |
|---|---|
| `tests/test_analyzer.py` | fixture 删 `key_people_and_data` / `impact`；断言同步；加一条断言验证 prompt 从文件加载成功 |
| `tests/test_notifier.py` | 删两段渲染断言；新增断言确认 `**加粗段首：**` 和 `> ` 引语原样输出 |
| `tests/test_audio_scripter.py` | fixture 删两字段；打桩 `LLMClient.complete`；断言 source 字典只含剩余字段 |
| `tests/test_main.py` + `tests/test_main_hot.py` | **合并为** `tests/test_pipeline.py`，参数化 `mode="digest"` / `mode="hot"`；断言 rank 只在 digest 模式调用、tag_prefix 和 title_prefix 正确 |
| 其他测试 | 无改动 |

## Risks & Mitigations

- **LLM 不听 detail 结构指令**（出现 `##`、漏加粗段首、英文名被翻译）：prompt 外挂后可零代码迭代；第一次 live 跑后看实际输出再收紧措辞。
- **微信 Markdown 渲染 `**加粗段首：**` 放段首的效果**：Server酱 走标准 Markdown，`**粗体**` 安全。第一次 live 跑重点肉眼检查。
- **回退路径**：分支 PR 合并后若大面积翻车，`git revert` 单个 merge commit 即可全量回退。

## Implementation Order

粗骨架（实施计划里再细化）：

1. 建分支 `refactor/digest-v2`
2. 改 `src/models.py`（删字段）
3. 新增 `src/prompts/analyzer.md` 和 `src/prompts/audio_scripter.md`
4. 改 `src/analyzer.py`（加载文件 prompt）
5. 改 `src/audio_scripter.py`（加载文件 prompt + 精简 source 字典）
6. 改 `src/notifier.py`（删两段）
7. 更新 `test_analyzer.py` / `test_notifier.py` / `test_audio_scripter.py` 并跑通
8. 新增 `src/pipeline.py`，瘦身 `main.py` / `main_hot.py`
9. 合并 `test_main.py` + `test_main_hot.py` → `test_pipeline.py`
10. 删根目录 5 个旧脚本
11. `pytest -v` 全绿
12. Live 手动跑 `python main.py`，肉眼核对微信推送样式和音频稿长度
