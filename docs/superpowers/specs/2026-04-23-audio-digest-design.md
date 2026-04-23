# 音频版新闻总结 — 设计文档

**日期：** 2026-04-23
**状态：** 待实施
**影响流水线：** `main.py`（digest）、`main_hot.py`（hot）

## 背景与目标

现有流水线把英超新闻的中文深度分析以 Markdown 形式通过 Server 酱推送到微信。用户希望**同时生成音频版本**，点开微信消息即可收听，适合通勤场景。

**目标：**
- 每期摘要额外产出一个 MP3 文件，URL 挂在微信 Markdown **顶部**
- 音频失败**不得影响**文字推送（降级优雅）
- 零新增运维成本（不引入云存储、付费 API）

**非目标：**
- 不做播客 RSS 订阅
- 不做多语种
- 不做听众互动（评论、反馈）

## 方案概览

**交付：** 微信 Markdown 顶部追加 `🎧 [点击收听音频版](URL)` 链接
**TTS：** Edge-TTS（免费、Python 库），默认声音 `zh-CN-YunjianNeural`（云健，微软官方标注 Sports 场景）
**口播稿：** 新增一次 LLM 调用，把结构化分析改写为自然播报文本（含开场/串场/结尾）
**托管：** GitHub Releases，每期一个 tag

## 流水线变更

在 Step 4（analyzer）之后、Step 5（notifier）之前插入两步：

```
Step 1  collect
Step 2  rank
Step 3  scrape
Step 4  analyze          现有 → AnalyzedArticle[]
Step 4a audio_scripter   新：LLM 改写为口播稿（str）
Step 4b audio_synth      新：Edge-TTS 合成 MP3 + 上传 Release → URL
Step 5  notify           现有，Markdown 顶部追加 🎧 音频行
```

`main.py` 与 `main_hot.py` 都接入。

## 新增与修改的文件

```
src/
  audio_scripter.py   新建：build_audio_script(articles, llm, today) -> str
  audio_synth.py      新建：synthesize_and_upload(script, date, voice, tag_prefix) -> str
  notifier.py         修改：format_digest 增加 audio_url 参数，插入顶部
  config.py           修改：读取 AUDIO_ENABLED、AUDIO_VOICE
main.py               修改：调用 4a、4b，传 audio_url 给 notifier
main_hot.py           修改：同上，tag_prefix="audio-hot"
requirements.txt      追加：edge-tts>=6.1.0
.github/workflows/daily.yml  修改：两个 job 加 contents:write 权限
tests/
  test_audio_scripter.py   新建
  test_audio_synth.py      新建
  test_notifier.py         扩充（audio_url 参数的两种 case）
test_edge_tts_live.py      新建（手动跑，人工听音色）
```

`models.py` 不变——口播稿和 URL 是流水线中间值，不入 dataclass。

## 模块详细设计

### `audio_scripter.py`

```python
def build_audio_script(
    articles: list[AnalyzedArticle],
    llm: LLMClient,
    today: date,
    title_prefix: str = "英超早报",
) -> str
```

**行为：**
- 构造 prompt，把每篇 `AnalyzedArticle` 的 title_cn / overview / detail / key_people_and_data / impact 喂给 LLM
- 要求 LLM 产出：开场白（含日期、标题）+ 每篇一段自然串讲 + 结尾
- 明确指令：不念星级符号、不念链接、中英混读（球队/球员原文保留）、总时长目标 8-15 分钟（约 1500-2500 汉字）
- 返回纯文本（无 Markdown）

**失败：** 抛异常。调用方捕获后降级。

**边界：** `articles=[]` 抛 `ValueError("no articles")`。

### `audio_synth.py`

```python
def synthesize_and_upload(
    script: str,
    today: date,
    voice: str = "zh-CN-YunjianNeural",
    tag_prefix: str = "audio-digest",
    repo: str | None = None,  # "owner/repo"，None 时从 GITHUB_REPOSITORY 读
    keep: int = 7,             # 保留最近 N 个同前缀 release，其余自动清理
) -> str
```

**行为：**
1. `edge_tts.Communicate(script, voice)` 合成到 `/tmp/{tag_prefix}-{today}.mp3`
2. `gh release create {tag_prefix}-{today} /tmp/...mp3 --title "..." --notes "..."`
3. 若 tag 已存在（同日重跑），回退到 `gh release upload {tag} /tmp/...mp3 --clobber`
4. 调用 `prune_old_releases(tag_prefix, keep, repo)` 清理旧 release（失败仅记 warning，不影响主流程）
5. 返回 asset 下载 URL：`https://github.com/{repo}/releases/download/{tag}/{filename}`

**失败：** 步骤 1-3 抛异常，调用方捕获后降级。步骤 4 失败不抛。

### `prune_old_releases` 辅助函数（同文件）

```python
def prune_old_releases(tag_prefix: str, keep: int, repo: str) -> None
```

**行为：**
1. `gh release list --repo {repo} --json tagName,createdAt --limit 100`
2. 过滤出 `tagName` 以 `{tag_prefix}-` 开头的 release
3. 按 `createdAt` 倒序，跳过最新的 `keep` 个
4. 对剩余的逐个调用 `gh release delete {tag} --repo {repo} --cleanup-tag --yes`（连同 git tag 一并删除）
5. 任何 `gh` 错误 → 记 `logger.warning`，不抛

**保留策略：** `audio-digest` 和 `audio-hot` 各自独立计数（前缀区分）。默认 `keep=7`。

### `notifier.py` 改动

```python
def format_digest(
    articles, today=None,
    title_prefix="英超每日精选",
    has_fallbacks=False,
    audio_url: str | None = None,  # 新增
) -> tuple[str, str]
```

`audio_url` 非空时，在 `# ⚽ {title}` 下方插入一行：

```markdown
🎧 [点击收听音频版]({audio_url})
```

`audio_url=None` 时输出与现状完全一致（回归安全）。

### `main.py` / `main_hot.py` 改动

在 Step 4 之后插入：

```python
audio_url: str | None = None
if config["audio_enabled"]:
    try:
        script = build_audio_script(analyzed, llm, date.today())
        save_step("step4a_script", {"script": script}, output_dir)
        audio_url = synthesize_and_upload(
            script, date.today(),
            voice=config["audio_voice"],
            tag_prefix="audio-digest",  # main_hot.py 用 "audio-hot"
        )
        save_step("step4b_audio", {"url": audio_url}, output_dir)
    except Exception as e:
        logger.error("Audio pipeline failed, falling back to text-only: %s", e)
```

`notify(..., audio_url=audio_url, ...)`。

## 配置

新增环境变量：

| 变量 | 必需 | 默认 | 用途 |
|---|---|---|---|
| `AUDIO_ENABLED` | 否 | `true` | 应急开关，`false` 时跳过 4a+4b |
| `AUDIO_VOICE` | 否 | `zh-CN-YunjianNeural` | Edge-TTS 声音 |
| `AUDIO_KEEP_RELEASES` | 否 | `7` | 每条流水线保留的最近 N 个 release，其余自动清理 |
| `GITHUB_TOKEN` | CI 自动注入 | - | `gh` CLI 上传/删除 release |
| `GITHUB_REPOSITORY` | CI 自动注入 | - | `owner/repo`，拼 URL 用 |

现有环境变量不动。

## CI 变更

`.github/workflows/daily.yml` 两个 job 均需：

```yaml
permissions:
  contents: write   # 创建 release

env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # 传给 gh CLI
```

Release tag 命名：
- digest 流水线：`audio-digest-YYYY-MM-DD`
- hot 流水线：`audio-hot-YYYY-MM-DD`

## 错误处理与降级

| 失败点 | 行为 |
|---|---|
| `audio_scripter` 抛异常 | 记 `logger.error`，`audio_url=None`，继续走文字推送 |
| `audio_synth` — Edge-TTS 网络错误 | try/except 捕获，降级 |
| `audio_synth` — `gh release create` tag 已存在 | 回退 `gh release upload --clobber` |
| `audio_synth` — 其他 `gh` 错误 | 记 `logger.error`，降级 |
| `audio_synth` — `prune_old_releases` 失败 | 记 `logger.warning`，不中断，下次运行再试 |
| `notifier` 失败 | `sys.exit(1)`（现有行为，不变） |

`AUDIO_ENABLED=false` 整条支路 skip，等价于今日行为。

**中间产物落盘：**
- `output/{date}/step4a_script.json` — 口播稿文本
- `output/{date}/step4b_audio.json` — `{"url": "...", "size_bytes": ...}`
- MP3 本身用 `/tmp/`，上传后不保留（避免仓库膨胀）

## 测试策略

遵循现有 `tests/` 的 pytest + AsyncMock 模式。

**`tests/test_audio_scripter.py`**
- mock `LLMClient.complete` 返回固定口播稿
- 断言：prompt 含所有 `AnalyzedArticle` 字段、日期正确、输出无 Markdown/emoji
- `articles=[]` 抛 `ValueError`

**`tests/test_audio_synth.py`**
- mock `edge_tts.Communicate`（不调网络，产假字节）
- mock `subprocess.run`（`gh` 调用返回假 URL / 假 release 列表）
- 断言：tag 命名、`--clobber` 回退路径、异常抛出
- `prune_old_releases`：给 10 个假 release，`keep=7` 时恰好删 3 个最旧的；`gh list` 失败时不抛；prefix 不同的 release 不被误删

**`tests/test_notifier.py`（扩充）**
- 新 case：`audio_url` 非空时 Markdown 顶部有 `🎧` 行
- 新 case：`audio_url=None` 时输出与现状完全一致

**`test_edge_tts_live.py`（手动脚本，不进 pytest）**
- 真合成一段测试文本，输出到本地，人工听音色
- 用于切换 voice/语速时快速预览

**不测：** 真实 `gh` 上传（依赖 CI 运行时验证）、LLM 返回质量（项目一贯不测）。

## 开放问题

无。所有决策在本文档内明确。

## 里程碑

1. 新增 `audio_scripter.py` + 测试 → 本地跑通口播稿生成
2. 新增 `audio_synth.py` + 测试 → 本地用 `gh` 上传通一次
3. 修改 `notifier.py` + 回归测试 → 保证 `audio_url=None` 时输出不变
4. 接入 `main.py` → 手动 dispatch workflow 验证端到端
5. 接入 `main_hot.py` → 同上
6. 更新 `CLAUDE.md` 和 `README`（若存在）记录新变量与流水线图
