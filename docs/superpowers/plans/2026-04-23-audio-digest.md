# 音频版新闻总结 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有文字推送流水线之上，追加"LLM 改写口播稿 → Edge-TTS 合成 MP3 → 上传 GitHub Release → 微信顶部挂链接"的音频支路；任何音频环节失败都不得影响原文字推送。

**Architecture:** 在 `main.py` / `main_hot.py` 的 Step 4（analyze）之后插入两个新模块：`audio_scripter` 用一次 LLM 调用生成自然口播文本；`audio_synth` 用 `edge-tts` 库合成 MP3 并通过 `gh release` 命令发布。`notifier.format_digest` 扩展一个可选 `audio_url` 参数，非空时在 Markdown 第一行追加 🎧 链接。

**Tech Stack:** Python 3.12, `edge-tts>=6.1.0`（新增依赖）, `subprocess` 调用 `gh` CLI（GitHub Actions runner 自带，本地测试需先 `brew install gh && gh auth login`）, pytest + `unittest.mock`（遵循现有测试风格）。

**Spec:** `docs/superpowers/specs/2026-04-23-audio-digest-design.md`

---

## 文件结构总览

新建：
- `src/audio_scripter.py` — 单函数 `build_audio_script(articles, llm, today, title_prefix) -> str`
- `src/audio_synth.py` — 含四个函数：`_synthesize_mp3`（async, Edge-TTS）、`_create_or_update_release`（subprocess gh）、`prune_old_releases`、`synthesize_and_upload`（async, 总入口）
- `tests/test_audio_scripter.py`
- `tests/test_audio_synth.py`
- `tests/test_config.py` — 新增，测 `get_config()` 对新音频环境变量的读取
- `test_edge_tts_live.py`（仓库根目录，手动跑，人工听音色；不进 pytest）

修改：
- `src/config.py` — `get_config()` 追加 3 个 key
- `src/notifier.py` — `format_digest` 加 `audio_url: str | None = None` 参数
- `main.py` — Step 4 之后插入音频支路（try/except 降级）
- `main_hot.py` — 同上，`tag_prefix="audio-hot"`
- `requirements.txt` — 追加 `edge-tts>=6.1.0`
- `.github/workflows/daily.yml` — 两个 job 加 `permissions.contents: write` 和 `GITHUB_TOKEN` env
- `tests/test_notifier.py` — 扩充 2 个 case（audio_url 两种状态）
- `tests/test_main.py`、`tests/test_main_hot.py` — mock 补齐新 config key，添加音频支路降级断言
- `CLAUDE.md` — 更新流水线图和环境变量表

---

## 实施前准备

运行一次确保虚拟环境和 pytest 可用：

```bash
source .venv/bin/activate
pytest tests/ -v 2>&1 | tail -5
```

Expected: 现有测试全绿（基线）。

---

### Task 1: 追加 edge-tts 依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 追加依赖行**

Edit `requirements.txt`，在最后追加一行：

```
edge-tts>=6.1.0
```

- [ ] **Step 2: 安装新依赖**

Run: `source .venv/bin/activate && pip install -r requirements.txt`
Expected: `Successfully installed edge-tts-6.*` 或 `Requirement already satisfied`。

- [ ] **Step 3: 验证 import**

Run: `python -c "import edge_tts; print(edge_tts.__version__)"`
Expected: 打印版本号（如 `6.1.12`），无异常。

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add edge-tts dependency for audio pipeline"
```

---

### Task 2: 扩展 config.get_config() 支持音频环境变量

**Files:**
- Modify: `src/config.py:17-27` (return dict)
- Create: `tests/test_config.py`

- [ ] **Step 1: 写失败测试（新建文件）**

Create `tests/test_config.py`:

```python
import os
from unittest.mock import patch

from src.config import get_config


class TestGetConfig:
    @patch.dict(os.environ, {}, clear=True)
    def test_audio_defaults(self):
        cfg = get_config()
        assert cfg["audio_enabled"] is True
        assert cfg["audio_voice"] == "zh-CN-YunjianNeural"
        assert cfg["audio_keep_releases"] == 7

    @patch.dict(os.environ, {"AUDIO_ENABLED": "false"}, clear=True)
    def test_audio_disabled_false(self):
        assert get_config()["audio_enabled"] is False

    @patch.dict(os.environ, {"AUDIO_ENABLED": "FALSE"}, clear=True)
    def test_audio_disabled_case_insensitive(self):
        assert get_config()["audio_enabled"] is False

    @patch.dict(os.environ, {"AUDIO_VOICE": "zh-CN-YunyangNeural"}, clear=True)
    def test_audio_voice_override(self):
        assert get_config()["audio_voice"] == "zh-CN-YunyangNeural"

    @patch.dict(os.environ, {"AUDIO_KEEP_RELEASES": "14"}, clear=True)
    def test_audio_keep_releases_override(self):
        assert get_config()["audio_keep_releases"] == 14
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_config.py -v`
Expected: 5 个测试全部 FAIL，错误是 `KeyError: 'audio_enabled'` 或类似。

- [ ] **Step 3: 实现**

Edit `src/config.py`，把 return dict 改成：

```python
    return {
        "page_url": os.environ.get(
            "PAGE_URL", "https://www.nytimes.com/athletic/football/premier-league/"
        ),
        "athletic_cookies": cookies,
        "llm_base_url": os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "llm_model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
        "top_n": int(os.environ.get("TOP_N", "5")),
        "audio_enabled": os.environ.get("AUDIO_ENABLED", "true").lower() != "false",
        "audio_voice": os.environ.get("AUDIO_VOICE", "zh-CN-YunjianNeural"),
        "audio_keep_releases": int(os.environ.get("AUDIO_KEEP_RELEASES", "7")),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): add AUDIO_ENABLED, AUDIO_VOICE, AUDIO_KEEP_RELEASES"
```

---

### Task 3: 新建 audio_scripter.py — LLM 生成口播稿

**Files:**
- Create: `src/audio_scripter.py`
- Create: `tests/test_audio_scripter.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_audio_scripter.py`:

```python
import pytest
from datetime import date
from unittest.mock import MagicMock

from src.audio_scripter import build_audio_script
from src.models import AnalyzedArticle


def _make_analyzed(title_cn="阿森纳争冠") -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn=title_cn, title_original="Arsenal title race",
        article_type="深度分析", importance=5,
        overview="阿森纳展现争冠实力。",
        detail="详细战术分析内容。",
        key_people_and_data="萨卡、厄德高",
        impact="对争冠产生影响。",
        link="https://example.com/a1",
    )


class TestBuildAudioScript:
    def test_empty_articles_raises(self):
        llm = MagicMock()
        with pytest.raises(ValueError, match="no articles"):
            build_audio_script([], llm, date(2026, 4, 23))

    def test_calls_llm_with_all_fields(self):
        llm = MagicMock()
        llm.complete.return_value = "大家好，今天是4月23日..."
        articles = [_make_analyzed()]

        build_audio_script(articles, llm, date(2026, 4, 23))

        llm.complete.assert_called_once()
        system, user = llm.complete.call_args[0]
        # system prompt should describe the task
        assert "口播" in system or "播报" in system
        # user prompt should include all five analyzed fields
        assert "阿森纳争冠" in user
        assert "Arsenal title race" in user
        assert "阿森纳展现争冠实力" in user
        assert "详细战术分析内容" in user
        assert "萨卡、厄德高" in user
        assert "对争冠产生影响" in user
        # date appears for opening line
        assert "2026" in user and "4" in user and "23" in user

    def test_passes_title_prefix(self):
        llm = MagicMock()
        llm.complete.return_value = "..."
        build_audio_script(
            [_make_analyzed()], llm, date(2026, 4, 23),
            title_prefix="英超热议文章",
        )
        _, user = llm.complete.call_args[0]
        assert "英超热议文章" in user

    def test_returns_llm_output_trimmed(self):
        llm = MagicMock()
        llm.complete.return_value = "  \n大家好，今天是4月23日...\n  "
        result = build_audio_script([_make_analyzed()], llm, date(2026, 4, 23))
        assert result == "大家好，今天是4月23日..."

    def test_multiple_articles_all_included(self):
        llm = MagicMock()
        llm.complete.return_value = "..."
        articles = [
            _make_analyzed(title_cn="文章A"),
            _make_analyzed(title_cn="文章B"),
            _make_analyzed(title_cn="文章C"),
        ]
        build_audio_script(articles, llm, date(2026, 4, 23))
        _, user = llm.complete.call_args[0]
        assert "文章A" in user and "文章B" in user and "文章C" in user
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_audio_scripter.py -v`
Expected: 5 FAIL with `ModuleNotFoundError: No module named 'src.audio_scripter'`.

- [ ] **Step 3: 实现 audio_scripter.py**

Create `src/audio_scripter.py`:

```python
import logging
from datetime import date

from src.llm import LLMClient
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一位资深英超足球主播，正在为每日播客节目撰写口播稿。

将下列结构化新闻分析改写为一段**自然、口语化**的中文播报稿，要求：

1. **开场**：以"大家好，今天是X月X日"开场，简短报出节目名称。
2. **每篇串讲**：按顺序介绍每篇新闻，每篇 2-4 段话，串讲自然过渡（"接下来看..."、"另一边..."、"最后一条..."）。
3. **结尾**：一句话收尾，例如"以上就是今天的英超早报，感谢收听"。
4. **保留人名和队名**：球员名、球队名、比分等**保留英文原文**（如 Manchester City、Arteta、3-1），便于 TTS 中英混读。
5. **不要**念任何 Markdown 符号、星号、井号、方括号、URL 链接。
6. **不要**说"本文""这篇文章""详情""影响与展望"等书面词，改用口语化表达。
7. **总长度**控制在 1500-2500 个汉字（约 8-15 分钟音频）。

直接输出可以直接朗读的纯文本，不要加任何标题、段落编号或附加说明。"""


def build_audio_script(
    articles: list[AnalyzedArticle],
    llm: LLMClient,
    today: date,
    title_prefix: str = "英超早报",
) -> str:
    if not articles:
        raise ValueError("no articles")

    sections = []
    for i, a in enumerate(articles, 1):
        sections.append(
            f"【第{i}篇】\n"
            f"中文标题：{a.title_cn}\n"
            f"英文原标题：{a.title_original}\n"
            f"类型：{a.article_type}\n"
            f"概述：{a.overview}\n"
            f"详细内容：{a.detail}\n"
            f"关键人物与数据：{a.key_people_and_data}\n"
            f"影响与展望：{a.impact}"
        )

    user_text = (
        f"今天是 {today.year} 年 {today.month} 月 {today.day} 日。\n"
        f"节目名称：{title_prefix}。\n"
        f"共 {len(articles)} 条新闻。\n\n"
        + "\n\n".join(sections)
    )

    logger.info("Requesting audio script from LLM (%d articles, %d chars input)",
                len(articles), len(user_text))
    result = llm.complete(_SYSTEM_PROMPT, user_text)
    return result.strip()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_audio_scripter.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audio_scripter.py tests/test_audio_scripter.py
git commit -m "feat(audio): add LLM-based audio script generator"
```

---

### Task 4: audio_synth.py — Edge-TTS 合成 MP3（内部 async 函数）

**Files:**
- Create: `src/audio_synth.py`
- Create: `tests/test_audio_synth.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_audio_synth.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock

from src.audio_synth import _synthesize_mp3


class TestSynthesizeMp3:
    @pytest.mark.asyncio
    async def test_calls_edge_tts_with_voice(self, tmp_path):
        out = tmp_path / "test.mp3"
        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()
        with patch("src.audio_synth.edge_tts.Communicate", return_value=mock_communicate) as mock_cls:
            await _synthesize_mp3("hello world", str(out), voice="zh-CN-YunjianNeural")

        mock_cls.assert_called_once_with("hello world", "zh-CN-YunjianNeural")
        mock_communicate.save.assert_awaited_once_with(str(out))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_audio_synth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.audio_synth'`.

- [ ] **Step 3: 实现最小 audio_synth.py**

Create `src/audio_synth.py`:

```python
import logging

import edge_tts

logger = logging.getLogger(__name__)


async def _synthesize_mp3(script: str, output_path: str, voice: str) -> None:
    logger.info("Synthesizing MP3 to %s (voice=%s, %d chars)", output_path, voice, len(script))
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audio_synth.py tests/test_audio_synth.py
git commit -m "feat(audio): add Edge-TTS synthesis helper"
```

---

### Task 5: audio_synth.py — `_create_or_update_release` helper (subprocess gh)

**Files:**
- Modify: `src/audio_synth.py`
- Modify: `tests/test_audio_synth.py`

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_audio_synth.py`:

```python
import subprocess
from unittest.mock import MagicMock, call

from src.audio_synth import _create_or_update_release


class TestCreateOrUpdateRelease:
    def test_creates_new_release_when_tag_missing(self):
        with patch("src.audio_synth.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            _create_or_update_release(
                tag="audio-digest-2026-04-23",
                asset_path="/tmp/audio.mp3",
                repo="linbing1/TAnews",
                title="英超早报 2026-04-23",
            )
            # Only one call: gh release create
            assert mock_run.call_count == 1
            args = mock_run.call_args_list[0][0][0]
            assert args[:3] == ["gh", "release", "create"]
            assert "audio-digest-2026-04-23" in args
            assert "/tmp/audio.mp3" in args
            assert "--repo" in args and "linbing1/TAnews" in args

    def test_falls_back_to_upload_when_tag_exists(self):
        # First call (create) fails with "already exists"; second call (upload) succeeds
        first = subprocess.CalledProcessError(
            returncode=1, cmd=["gh"], stderr="release already exists"
        )
        second = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.audio_synth.subprocess.run", side_effect=[first, second]) as mock_run:
            _create_or_update_release(
                tag="audio-digest-2026-04-23",
                asset_path="/tmp/audio.mp3",
                repo="linbing1/TAnews",
                title="英超早报 2026-04-23",
            )
            assert mock_run.call_count == 2
            second_args = mock_run.call_args_list[1][0][0]
            assert second_args[:3] == ["gh", "release", "upload"]
            assert "--clobber" in second_args

    def test_raises_on_non_exists_error(self):
        err = subprocess.CalledProcessError(
            returncode=1, cmd=["gh"], stderr="authentication failed"
        )
        with patch("src.audio_synth.subprocess.run", side_effect=err):
            with pytest.raises(subprocess.CalledProcessError):
                _create_or_update_release(
                    tag="audio-digest-2026-04-23",
                    asset_path="/tmp/audio.mp3",
                    repo="linbing1/TAnews",
                    title="...",
                )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 3 new tests FAIL with `ImportError` for `_create_or_update_release`.

- [ ] **Step 3: 实现**

Append to `src/audio_synth.py`:

```python
import subprocess


def _create_or_update_release(
    tag: str,
    asset_path: str,
    repo: str,
    title: str,
) -> None:
    """Create a GitHub release with the asset; if tag already exists, upload with --clobber."""
    create_cmd = [
        "gh", "release", "create", tag, asset_path,
        "--repo", repo,
        "--title", title,
        "--notes", f"Auto-generated audio digest for {tag}",
    ]
    try:
        subprocess.run(create_cmd, check=True, capture_output=True, text=True)
        logger.info("Created release %s with asset %s", tag, asset_path)
        return
    except subprocess.CalledProcessError as e:
        if "already exists" not in (e.stderr or ""):
            raise
        logger.info("Release %s already exists, uploading with --clobber", tag)

    upload_cmd = [
        "gh", "release", "upload", tag, asset_path,
        "--repo", repo,
        "--clobber",
    ]
    subprocess.run(upload_cmd, check=True, capture_output=True, text=True)
    logger.info("Re-uploaded asset to existing release %s", tag)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 4 passed (1 from Task 4 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/audio_synth.py tests/test_audio_synth.py
git commit -m "feat(audio): add gh release create/upload helper"
```

---

### Task 6: audio_synth.py — `prune_old_releases`

**Files:**
- Modify: `src/audio_synth.py`
- Modify: `tests/test_audio_synth.py`

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_audio_synth.py`:

```python
import json

from src.audio_synth import prune_old_releases


def _fake_release_list(entries):
    """Return a mock subprocess result matching gh release list --json output."""
    return MagicMock(returncode=0, stdout=json.dumps(entries), stderr="")


class TestPruneOldReleases:
    def test_deletes_releases_beyond_keep(self):
        # 10 audio-digest releases, newest first
        entries = [
            {"tagName": f"audio-digest-2026-04-{30-i:02d}", "createdAt": f"2026-04-{30-i:02d}T00:00:00Z"}
            for i in range(10)
        ]
        list_result = _fake_release_list(entries)
        delete_result = MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.audio_synth.subprocess.run",
                   side_effect=[list_result] + [delete_result] * 3) as mock_run:
            prune_old_releases(tag_prefix="audio-digest", keep=7, repo="linbing1/TAnews")

        # 1 list call + 3 delete calls (10 - 7 = 3 oldest)
        assert mock_run.call_count == 4
        deleted_tags = [
            mock_run.call_args_list[i][0][0][3]  # args[3] is the tag
            for i in range(1, 4)
        ]
        # The oldest 3: 2026-04-21, 2026-04-22, 2026-04-23
        assert sorted(deleted_tags) == [
            "audio-digest-2026-04-21",
            "audio-digest-2026-04-22",
            "audio-digest-2026-04-23",
        ]
        # Each delete uses --cleanup-tag
        for i in range(1, 4):
            args = mock_run.call_args_list[i][0][0]
            assert args[:3] == ["gh", "release", "delete"]
            assert "--cleanup-tag" in args
            assert "--yes" in args

    def test_keeps_everything_when_under_limit(self):
        entries = [
            {"tagName": f"audio-digest-2026-04-{30-i:02d}", "createdAt": f"2026-04-{30-i:02d}T00:00:00Z"}
            for i in range(5)
        ]
        list_result = _fake_release_list(entries)
        with patch("src.audio_synth.subprocess.run", side_effect=[list_result]) as mock_run:
            prune_old_releases(tag_prefix="audio-digest", keep=7, repo="linbing1/TAnews")
        # Only the list call
        assert mock_run.call_count == 1

    def test_ignores_other_prefixes(self):
        entries = [
            {"tagName": "v1.0.0", "createdAt": "2026-01-01T00:00:00Z"},
            {"tagName": "audio-hot-2026-04-20", "createdAt": "2026-04-20T00:00:00Z"},
            {"tagName": "audio-digest-2026-04-23", "createdAt": "2026-04-23T00:00:00Z"},
        ]
        list_result = _fake_release_list(entries)
        with patch("src.audio_synth.subprocess.run", side_effect=[list_result]) as mock_run:
            prune_old_releases(tag_prefix="audio-digest", keep=0, repo="linbing1/TAnews")
        # keep=0 → all audio-digest releases deleted, others untouched
        # 1 list + 1 delete (only audio-digest-2026-04-23)
        assert mock_run.call_count == 2
        deleted = mock_run.call_args_list[1][0][0][3]
        assert deleted == "audio-digest-2026-04-23"

    def test_swallows_list_error(self, caplog):
        err = subprocess.CalledProcessError(returncode=1, cmd=["gh"], stderr="boom")
        with patch("src.audio_synth.subprocess.run", side_effect=err):
            # Must not raise
            prune_old_releases(tag_prefix="audio-digest", keep=7, repo="linbing1/TAnews")
        assert any("prune" in r.message.lower() or "boom" in r.message for r in caplog.records)

    def test_swallows_individual_delete_error(self, caplog):
        entries = [
            {"tagName": f"audio-digest-2026-04-{30-i:02d}", "createdAt": f"2026-04-{30-i:02d}T00:00:00Z"}
            for i in range(9)
        ]
        list_result = _fake_release_list(entries)
        delete_err = subprocess.CalledProcessError(returncode=1, cmd=["gh"], stderr="fail")
        with patch("src.audio_synth.subprocess.run",
                   side_effect=[list_result, delete_err, delete_err]):
            # 9 entries, keep=7 → 2 deletes, both fail → must not raise
            prune_old_releases(tag_prefix="audio-digest", keep=7, repo="linbing1/TAnews")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 5 new tests FAIL with `ImportError` for `prune_old_releases`.

- [ ] **Step 3: 实现**

Append to `src/audio_synth.py`:

```python
def prune_old_releases(tag_prefix: str, keep: int, repo: str) -> None:
    """Delete releases with matching tag prefix beyond the most recent `keep`. Never raises."""
    list_cmd = [
        "gh", "release", "list",
        "--repo", repo,
        "--json", "tagName,createdAt",
        "--limit", "100",
    ]
    try:
        result = subprocess.run(list_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.warning("prune_old_releases: gh release list failed: %s", e.stderr or e)
        return

    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.warning("prune_old_releases: failed to parse gh output: %s", e)
        return

    prefix = f"{tag_prefix}-"
    matching = [e for e in entries if e.get("tagName", "").startswith(prefix)]
    # Newest first; gh release list returns newest first but re-sort defensively
    matching.sort(key=lambda e: e.get("createdAt", ""), reverse=True)
    to_delete = matching[keep:]

    for entry in to_delete:
        tag = entry["tagName"]
        delete_cmd = [
            "gh", "release", "delete", tag,
            "--repo", repo,
            "--cleanup-tag",
            "--yes",
        ]
        try:
            subprocess.run(delete_cmd, check=True, capture_output=True, text=True)
            logger.info("Pruned old release %s", tag)
        except subprocess.CalledProcessError as e:
            logger.warning("Failed to delete release %s: %s", tag, e.stderr or e)
```

Also add `import json` to the top of `src/audio_synth.py` (near existing `import logging`).

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 9 passed (1 + 3 + 5).

- [ ] **Step 5: Commit**

```bash
git add src/audio_synth.py tests/test_audio_synth.py
git commit -m "feat(audio): add release retention via prune_old_releases"
```

---

### Task 7: audio_synth.py — 顶层 `synthesize_and_upload`

**Files:**
- Modify: `src/audio_synth.py`
- Modify: `tests/test_audio_synth.py`

**Note:** 这是 async 函数，因为 Edge-TTS 的 `save()` 是 async。调用方 (`main.py`) 的 `run()` 本来就是 async，`await` 即可。

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_audio_synth.py`:

```python
from datetime import date

from src.audio_synth import synthesize_and_upload


class TestSynthesizeAndUpload:
    @pytest.mark.asyncio
    async def test_happy_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "linbing1/TAnews")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()
        gh_ok = MagicMock(returncode=0, stdout="[]", stderr="")

        with patch("src.audio_synth.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.audio_synth.subprocess.run", return_value=gh_ok) as mock_run:
            url = await synthesize_and_upload(
                script="hello",
                today=date(2026, 4, 23),
                voice="zh-CN-YunjianNeural",
                tag_prefix="audio-digest",
                keep=7,
            )

        assert url == (
            "https://github.com/linbing1/TAnews/releases/download/"
            "audio-digest-2026-04-23/audio-digest-2026-04-23.mp3"
        )
        # TTS save happened
        mock_communicate.save.assert_awaited_once()
        # At least one gh release create call
        create_calls = [c for c in mock_run.call_args_list
                        if c[0][0][:3] == ["gh", "release", "create"]]
        assert len(create_calls) == 1

    @pytest.mark.asyncio
    async def test_explicit_repo_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()
        gh_ok = MagicMock(returncode=0, stdout="[]", stderr="")

        with patch("src.audio_synth.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.audio_synth.subprocess.run", return_value=gh_ok):
            url = await synthesize_and_upload(
                script="hi",
                today=date(2026, 4, 23),
                voice="zh-CN-YunjianNeural",
                tag_prefix="audio-hot",
                repo="someone/other",
                keep=7,
            )

        assert url.startswith("https://github.com/someone/other/releases/download/audio-hot-2026-04-23/")

    @pytest.mark.asyncio
    async def test_missing_repo_raises(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        with pytest.raises(ValueError, match="repo"):
            await synthesize_and_upload(
                script="hi",
                today=date(2026, 4, 23),
                voice="zh-CN-YunjianNeural",
                tag_prefix="audio-digest",
            )

    @pytest.mark.asyncio
    async def test_prune_failure_does_not_break(self, monkeypatch, caplog):
        monkeypatch.setenv("GITHUB_REPOSITORY", "linbing1/TAnews")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        # create ok; list fails (prune swallows)
        create_ok = MagicMock(returncode=0, stdout="", stderr="")
        list_err = subprocess.CalledProcessError(returncode=1, cmd=["gh"], stderr="list boom")

        with patch("src.audio_synth.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.audio_synth.subprocess.run", side_effect=[create_ok, list_err]):
            url = await synthesize_and_upload(
                script="hi",
                today=date(2026, 4, 23),
                voice="zh-CN-YunjianNeural",
                tag_prefix="audio-digest",
                keep=7,
            )
        # URL still returned even if prune failed
        assert "audio-digest-2026-04-23" in url
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_audio_synth.py -v -k synthesize_and_upload`
Expected: 4 tests FAIL with `ImportError` for `synthesize_and_upload`.

- [ ] **Step 3: 实现**

Append to `src/audio_synth.py`:

```python
import os
from datetime import date


async def synthesize_and_upload(
    script: str,
    today: date,
    voice: str = "zh-CN-YunjianNeural",
    tag_prefix: str = "audio-digest",
    repo: str | None = None,
    keep: int = 7,
) -> str:
    """Synthesize script to MP3, upload to a GitHub Release, prune old releases, return download URL."""
    if repo is None:
        repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise ValueError("repo not provided and GITHUB_REPOSITORY env is empty")

    tag = f"{tag_prefix}-{today.isoformat()}"
    filename = f"{tag}.mp3"
    mp3_path = f"/tmp/{filename}"

    await _synthesize_mp3(script, mp3_path, voice)

    title = f"Audio digest {tag}"
    _create_or_update_release(tag=tag, asset_path=mp3_path, repo=repo, title=title)

    try:
        prune_old_releases(tag_prefix=tag_prefix, keep=keep, repo=repo)
    except Exception as e:
        logger.warning("prune_old_releases raised unexpectedly: %s", e)

    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_audio_synth.py -v`
Expected: 13 passed (9 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/audio_synth.py tests/test_audio_synth.py
git commit -m "feat(audio): compose synthesize_and_upload top-level entry"
```

---

### Task 8: notifier.format_digest 添加 audio_url 参数

**Files:**
- Modify: `src/notifier.py:10-47`
- Modify: `tests/test_notifier.py`

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_notifier.py`:

```python
class TestFormatDigestAudioUrl:
    def test_no_audio_line_when_url_is_none(self):
        articles = [_make_analyzed()]
        _, body = format_digest(articles, date(2026, 2, 15), audio_url=None)
        assert "🎧" not in body
        assert "音频版" not in body

    def test_audio_line_appears_right_after_title(self):
        articles = [_make_analyzed()]
        url = "https://github.com/linbing1/TAnews/releases/download/audio-digest-2026-02-15/audio-digest-2026-02-15.mp3"
        _, body = format_digest(articles, date(2026, 2, 15), audio_url=url)

        lines = body.splitlines()
        # First non-empty line is the title; the audio line must appear before the first "##" section
        first_section_idx = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
        audio_idx = next(i for i, ln in enumerate(lines) if "🎧" in ln)
        assert audio_idx < first_section_idx
        assert url in body
        assert "点击收听音频版" in body

    def test_audio_coexists_with_fallback_warning(self):
        articles = [_make_analyzed()]
        _, body = format_digest(
            articles, date(2026, 2, 15),
            audio_url="https://example.com/a.mp3",
            has_fallbacks=True,
        )
        assert "🎧" in body
        assert "Cookie 可能失效" in body
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_notifier.py -v`
Expected: 3 new tests FAIL with `TypeError: format_digest() got an unexpected keyword argument 'audio_url'`.

- [ ] **Step 3: 实现（同时改 `format_digest` 和 `notify`，让 audio_url 从调用方一路透传）**

Edit `src/notifier.py`，替换 `format_digest` 和 `notify` 两个函数：

```python
def format_digest(
    articles: list[AnalyzedArticle],
    today: date | None = None,
    title_prefix: str = "英超每日精选",
    has_fallbacks: bool = False,
    audio_url: str | None = None,
) -> tuple[str, str]:
    today = today or date.today()
    title = f"{title_prefix} - {today}"

    sections = []
    for i, a in enumerate(articles, 1):
        stars = "⭐" * a.importance
        section = f"""## {i}. {a.title_cn}
**原标题：** {a.title_original}
**类型：** {a.article_type}
**重要性：** {stars}

### 文章概述
{a.overview}

### 详细内容
{a.detail}

### 关键人物与数据
{a.key_people_and_data}

### 影响与展望
{a.impact}

🔗 [阅读原文]({a.link})"""
        sections.append(section)

    header = f"# ⚽ {title}"
    if audio_url:
        header += f"\n\n🎧 [点击收听音频版]({audio_url})"

    body = f"{header}\n\n" + "\n\n---\n\n".join(sections)

    if has_fallbacks:
        body += "\n\n---\n\n> ⚠️ Cookie 可能失效，部分文章未能获取全文，请及时更新 ATHLETIC_COOKIES"

    return title, body


def notify(
    articles: list[AnalyzedArticle],
    serverchan_key: str,
    today: date | None = None,
    title_prefix: str = "英超每日精选",
    has_fallbacks: bool = False,
    audio_url: str | None = None,
) -> bool:
    title, body = format_digest(
        articles, today,
        title_prefix=title_prefix,
        has_fallbacks=has_fallbacks,
        audio_url=audio_url,
    )

    url = f"https://sctapi.ftqq.com/{serverchan_key}.send"
    resp = httpx.post(url, data={"title": title, "desp": body}, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    if result.get("code") == 0:
        logger.info("Push notification sent successfully")
        return True

    logger.error("Server酱 push failed: %s", result)
    return False
```

- [ ] **Step 4: 运行测试确认通过（新测试 + 老测试全绿）**

Run: `pytest tests/test_notifier.py -v`
Expected: 所有 test_notifier 用例通过（原有 + 3 新增）。

- [ ] **Step 5: Commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat(notifier): add optional audio_url to digest header"
```

---

### Task 9: 接入 main.py（digest 流水线）

**Files:**
- Modify: `main.py` (在 Step 4 之后插入音频支路；把 audio_url 传给 notify)
- Modify: `tests/test_main.py`（补齐 config mock，添加音频断言）

- [ ] **Step 1: 先补齐现有测试的 config mock（不加新断言）**

Edit `tests/test_main.py`，在两个测试的 `mock_config.return_value` 字典末尾加 3 行（保持现有 case 绿色）：

```python
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
```

两个地方：`test_full_pipeline` 和 `test_no_articles_sends_no_notification`。

- [ ] **Step 2: 运行已有测试确认仍绿（尚未实现音频支路，`audio_enabled=False` 时应无影响）**

Run: `pytest tests/test_main.py -v`
Expected: 2 passed（现在还没实际调音频，但 config 字段齐全不影响现有逻辑）。

- [ ] **Step 3: 追加新测试——验证音频支路被调用且失败时降级**

Append to `tests/test_main.py`:

```python
class TestMainPipelineAudio:
    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock)
    @patch("main.build_audio_script")
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_enabled_calls_scripter_and_synth(
        self, mock_config, mock_collect, mock_rank, mock_scrape,
        mock_analyze, mock_script, mock_synth, mock_notify, mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page", "athletic_cookies": [],
            "llm_base_url": "https://api.example.com", "llm_api_key": "key",
            "llm_model": "test-model", "serverchan_key": "sc-key", "top_n": 5,
            "audio_enabled": True,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }
        article = Article(title="T", link="http://x", summary="",
                          published=datetime(2026, 2, 15, tzinfo=timezone.utc))
        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="T", article_type="新闻", importance=5,
            overview="", detail="", key_people_and_data="", impact="", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_script.return_value = "口播稿"
        mock_synth.return_value = "https://example.com/audio.mp3"
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        mock_script.assert_called_once()
        mock_synth.assert_awaited_once()
        # notify received the audio_url
        kwargs = mock_notify.call_args.kwargs
        assert kwargs.get("audio_url") == "https://example.com/audio.mp3"

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock)
    @patch("main.build_audio_script")
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_failure_falls_back_to_text_only(
        self, mock_config, mock_collect, mock_rank, mock_scrape,
        mock_analyze, mock_script, mock_synth, mock_notify, mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page", "athletic_cookies": [],
            "llm_base_url": "https://api.example.com", "llm_api_key": "key",
            "llm_model": "test-model", "serverchan_key": "sc-key", "top_n": 5,
            "audio_enabled": True,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }
        article = Article(title="T", link="http://x", summary="",
                          published=datetime(2026, 2, 15, tzinfo=timezone.utc))
        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="T", article_type="新闻", importance=5,
            overview="", detail="", key_people_and_data="", impact="", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_script.side_effect = RuntimeError("LLM boom")
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        # notify still called, but audio_url is None
        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        assert kwargs.get("audio_url") is None

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock)
    @patch("main.build_audio_script")
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_disabled_skips_entire_branch(
        self, mock_config, mock_collect, mock_rank, mock_scrape,
        mock_analyze, mock_script, mock_synth, mock_notify, mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page", "athletic_cookies": [],
            "llm_base_url": "https://api.example.com", "llm_api_key": "key",
            "llm_model": "test-model", "serverchan_key": "sc-key", "top_n": 5,
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }
        article = Article(title="T", link="http://x", summary="",
                          published=datetime(2026, 2, 15, tzinfo=timezone.utc))
        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="T", article_type="新闻", importance=5,
            overview="", detail="", key_people_and_data="", impact="", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        mock_script.assert_not_called()
        mock_synth.assert_not_awaited()
        kwargs = mock_notify.call_args.kwargs
        assert kwargs.get("audio_url") is None
```

Also add to the test_main.py imports (top of file) if not present:

```python
import asyncio
```

- [ ] **Step 4: 运行测试确认 3 个新测试失败**

Run: `pytest tests/test_main.py -v`
Expected: 2 old PASS, 3 new FAIL（`ImportError: cannot import name 'build_audio_script' from 'main'`）。

- [ ] **Step 5: 实现 main.py 改动**

Edit `main.py`。在 imports 追加：

```python
from src.audio_scripter import build_audio_script
from src.audio_synth import synthesize_and_upload
```

在 `Step 4: Analyze` 块**之后**、`Step 5: Push to WeChat` 块**之前**，插入：

```python
    # Step 4a/4b: Generate and upload audio (best-effort, never blocks text push)
    audio_url: str | None = None
    if config["audio_enabled"]:
        try:
            logger.info("Step 4a: Generating audio script...")
            script = build_audio_script(analyzed, llm, date.today())
            save_step("step4a_script", {"script": script}, output_dir)

            logger.info("Step 4b: Synthesizing and uploading audio...")
            audio_url = await synthesize_and_upload(
                script,
                date.today(),
                voice=config["audio_voice"],
                tag_prefix="audio-digest",
                keep=config["audio_keep_releases"],
            )
            save_step("step4b_audio", {"url": audio_url}, output_dir)
        except Exception as e:
            logger.error("Audio pipeline failed, falling back to text-only: %s", e)
            audio_url = None
```

Modify the `notify(...)` call to pass `audio_url`:

```python
    success = notify(analyzed, config["serverchan_key"], has_fallbacks=has_fallbacks, audio_url=audio_url)
```

- [ ] **Step 6: 运行所有测试**

Run: `pytest tests/ -v`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: integrate audio pipeline into main digest flow"
```

---

### Task 10: 接入 main_hot.py

**Files:**
- Modify: `main_hot.py`
- Modify: `tests/test_main_hot.py`

- [ ] **Step 1: 补齐现有 test_main_hot.py 的 config mock**

Edit `tests/test_main_hot.py`，给现有 `mock_config.return_value` 加：

```python
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
```

- [ ] **Step 2: 确认现有测试仍绿**

Run: `pytest tests/test_main_hot.py -v`
Expected: 现有 case 全绿。

- [ ] **Step 3: 追加新测试——验证 tag_prefix 是 `audio-hot`**

Append to `tests/test_main_hot.py`:

```python
class TestHotPipelineAudio:
    @patch("main_hot.save_step")
    @patch("main_hot.notify")
    @patch("main_hot.synthesize_and_upload", new_callable=AsyncMock)
    @patch("main_hot.build_audio_script")
    @patch("main_hot.analyze_articles")
    @patch("main_hot.scrape_full_texts", new_callable=AsyncMock)
    @patch("main_hot.collect_hot_articles", new_callable=AsyncMock)
    @patch("main_hot.get_config")
    def test_hot_uses_audio_hot_tag_prefix(
        self, mock_config, mock_collect, mock_scrape,
        mock_analyze, mock_script, mock_synth, mock_notify, mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page", "athletic_cookies": [],
            "llm_base_url": "https://api.example.com", "llm_api_key": "key",
            "llm_model": "test-model", "serverchan_key": "sc-key", "top_n": 5,
            "audio_enabled": True,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }
        article = Article(title="T", link="http://x", summary="",
                          published=datetime(2026, 2, 16, tzinfo=timezone.utc),
                          comment_count=42)
        mock_collect.return_value = [article]
        mock_scrape.return_value = ([article], False)
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="T", article_type="新闻", importance=5,
            overview="", detail="", key_people_and_data="", impact="", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_script.return_value = "口播稿"
        mock_synth.return_value = "https://example.com/hot.mp3"
        mock_notify.return_value = True

        from main_hot import run
        asyncio.run(run())

        mock_synth.assert_awaited_once()
        kwargs = mock_synth.call_args.kwargs
        assert kwargs["tag_prefix"] == "audio-hot"
        # notify got the URL
        notify_kwargs = mock_notify.call_args.kwargs
        assert notify_kwargs["audio_url"] == "https://example.com/hot.mp3"
        # And title_prefix preserved
        assert notify_kwargs["title_prefix"] == "英超热议文章"
```

- [ ] **Step 4: 运行测试确认新测试失败**

Run: `pytest tests/test_main_hot.py -v`
Expected: 新测试 FAIL with `ImportError`.

- [ ] **Step 5: 实现 main_hot.py 改动**

Edit `main_hot.py`. 追加 imports：

```python
from src.audio_scripter import build_audio_script
from src.audio_synth import synthesize_and_upload
```

在 `Step 3: Analyze` 之后、`Step 4: Push to WeChat` 之前插入：

```python
    # Step 3a/3b: Generate and upload audio (best-effort)
    audio_url: str | None = None
    if config["audio_enabled"]:
        try:
            logger.info("Step 3a: Generating audio script...")
            script = build_audio_script(
                analyzed, llm, date.today(), title_prefix="英超热议文章"
            )
            save_step("step3a_script", {"script": script}, output_dir)

            logger.info("Step 3b: Synthesizing and uploading audio...")
            audio_url = await synthesize_and_upload(
                script,
                date.today(),
                voice=config["audio_voice"],
                tag_prefix="audio-hot",
                keep=config["audio_keep_releases"],
            )
            save_step("step3b_audio", {"url": audio_url}, output_dir)
        except Exception as e:
            logger.error("Audio pipeline failed, falling back to text-only: %s", e)
            audio_url = None
```

Modify `notify(...)` call:

```python
    success = notify(
        analyzed, config["serverchan_key"],
        title_prefix="英超热议文章",
        has_fallbacks=has_fallbacks,
        audio_url=audio_url,
    )
```

- [ ] **Step 6: 运行所有测试**

Run: `pytest tests/ -v`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add main_hot.py tests/test_main_hot.py
git commit -m "feat: integrate audio pipeline into hot digest flow"
```

---

### Task 11: CI workflow — 开 release 权限

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: 修改两个 job**

Edit `.github/workflows/daily.yml`。在 `digest:` job 和 `hot-digest:` job 各自 `runs-on: ubuntu-latest` 下方加一行 `permissions`，并在各自 `Run ... pipeline` 步骤的 `env` 块补 `GITHUB_TOKEN`。

示例（两个 job 都要改）：

```yaml
  digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write    # required to create/delete audio releases
    if: >-
      ...
    steps:
      ...
      - name: Run digest pipeline
        run: python main.py
        env:
          ATHLETIC_COOKIES: ${{ secrets.ATHLETIC_COOKIES }}
          LLM_BASE_URL: ${{ vars.LLM_BASE_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL: ${{ vars.LLM_MODEL }}
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

`hot-digest:` job 同样加 `permissions.contents: write` 和 `GITHUB_TOKEN` env。

- [ ] **Step 2: 校验 YAML 语法**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml'))"`
Expected: 无输出，退出码 0。

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: grant contents:write and pass GITHUB_TOKEN for audio releases"
```

---

### Task 12: 手动脚本 `test_edge_tts_live.py`（人工听音色）

**Files:**
- Create: `test_edge_tts_live.py`（仓库根目录，与现有 `test_llm_live.py` 同层）

- [ ] **Step 1: 新建脚本**

Create `test_edge_tts_live.py`:

```python
"""Manual smoke test for Edge-TTS voice selection.

Usage:
    python test_edge_tts_live.py                            # default voice
    python test_edge_tts_live.py zh-CN-YunyangNeural        # try another voice

Outputs `./edge_tts_preview.mp3`. Listen to it to judge voice quality for
English-in-Chinese mixed speech (player names, team names, scores).
"""
import asyncio
import sys

import edge_tts

SAMPLE_TEXT = (
    "大家好，今天是4月23日，英超早报。"
    "上周末，Manchester City 客场2比1战胜 Arsenal，"
    "Erling Haaland 梅开二度，Arteta 赛后表示球队需要反思。"
    "接下来看一条关于 Liverpool 的转会动态。"
    "以上就是今天的英超早报，感谢收听。"
)


async def main(voice: str):
    out = "./edge_tts_preview.mp3"
    print(f"Synthesizing with voice={voice} → {out}")
    await edge_tts.Communicate(SAMPLE_TEXT, voice).save(out)
    print(f"Done. Play {out} to evaluate voice.")


if __name__ == "__main__":
    voice = sys.argv[1] if len(sys.argv) > 1 else "zh-CN-YunjianNeural"
    asyncio.run(main(voice))
```

- [ ] **Step 2: 手动运行验证**

Run: `python test_edge_tts_live.py`
Expected: 输出 `Synthesizing with voice=zh-CN-YunjianNeural → ./edge_tts_preview.mp3` 然后 `Done.`，本地生成 MP3 可播放。

- [ ] **Step 3: 清理本地生成的音频（别入库）**

Run: `rm -f edge_tts_preview.mp3` 并确认 `.gitignore` 已忽略或单独忽略：

```bash
grep -q "edge_tts_preview.mp3" .gitignore || echo "edge_tts_preview.mp3" >> .gitignore
```

- [ ] **Step 4: Commit**

```bash
git add test_edge_tts_live.py .gitignore
git commit -m "test: add manual Edge-TTS voice preview script"
```

---

### Task 13: 更新 CLAUDE.md 文档

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新"Project Overview"小节**

Edit `CLAUDE.md`。在"Digest pipeline:"行后追加一行（或替换现有行为新版）：

```
**Digest pipeline:** Collector → Ranker → Scraper → Analyzer → Audio Scripter (optional) → Audio Synth (optional) → Notifier
```

对 "Hot pipeline" 同样追加 "→ Audio Scripter → Audio Synth"（标注 optional）。

- [ ] **Step 2: 更新"Architecture"代码树**

在 `src/` 列表中追加：

```
  audio_scripter.py  # LLM rewrite AnalyzedArticle[] → natural TTS script
  audio_synth.py     # edge-tts + gh release: MP3 synth + upload + retention
```

- [ ] **Step 3: 更新"Environment Variables"表格**

追加 3 行：

```
| `AUDIO_ENABLED` | No | `true` | Set to `false` to skip the audio branch entirely |
| `AUDIO_VOICE` | No | `zh-CN-YunjianNeural` | Edge-TTS voice (sports-optimized by default) |
| `AUDIO_KEEP_RELEASES` | No | `7` | Retention per pipeline; older releases auto-deleted |
```

- [ ] **Step 4: 更新"Key Patterns"**

追加 2 条：

```
- Audio is best-effort: any failure in `audio_scripter` or `audio_synth` is caught in `main.py`/`main_hot.py`; `audio_url` stays `None` and text push proceeds
- Releases use tag prefix `audio-digest-*` (main) and `audio-hot-*` (main_hot); `prune_old_releases` keeps the most recent N and runs on every upload
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document audio pipeline in CLAUDE.md"
```

---

### Task 14: 端到端本地烟测（可选，非阻塞）

**Goal:** 在本地手动把整条链路跑一遍（不依赖 CI）。需要 `gh` CLI 已登录。

- [ ] **Step 1: 确认本地环境**

```bash
which gh || brew install gh
gh auth status || gh auth login
```

Expected: `Logged in to github.com as linbing1` 或类似。

- [ ] **Step 2: 单独验证 audio_synth 模块**

创建一次性验证脚本 `/tmp/verify_synth.py`：

```python
import asyncio, os
from datetime import date
os.environ["GITHUB_REPOSITORY"] = "linbing1/TAnews"

from src.audio_synth import synthesize_and_upload

async def main():
    url = await synthesize_and_upload(
        script="这是一条测试音频，用于验证 GitHub Release 上传链路。",
        today=date(2026, 4, 23),
        tag_prefix="audio-digest",
        voice="zh-CN-YunjianNeural",
        keep=7,
    )
    print("URL:", url)

asyncio.run(main())
```

Run: `python /tmp/verify_synth.py`
Expected: 打印 URL，https://github.com/linbing1/TAnews/releases/... 可访问（登录后）。

- [ ] **Step 3: 清理测试 release**

```bash
gh release delete audio-digest-2026-04-23 --cleanup-tag --yes --repo linbing1/TAnews
```

- [ ] **Step 4: 无提交**（验证步骤不改代码）

---

### Task 15: CI 烟测 + 上线后人工操作

- [ ] **Step 1: Push 所有 commits 到远端**

```bash
git push origin main
```

Expected: 推送成功。

- [ ] **Step 2: 手动触发 workflow 验证**

打开 GitHub → Actions → "Daily Premier League Digest" → "Run workflow"，选择 `digest`，运行。

Expected:
- Workflow 全绿
- 仓库 Releases 页面出现一个 `audio-digest-YYYY-MM-DD`，含 MP3 asset
- 微信收到文字推送，标题下方有 🎧 链接，点开可播放

- [ ] **Step 3: 同样触发 hot**

Run workflow 选择 `hot`。验证 `audio-hot-YYYY-MM-DD` release 出现。

- [ ] **Step 4: 关闭 Releases 邮件通知（必做）**

打开 `https://github.com/linbing1/TAnews` → 右上角 **Watch** → **Custom** → **取消勾选 "Releases"** → Apply。

- [ ] **Step 5: 观察 2-3 天**

连续两天让 cron 自动跑，确认：
- 每天两条流水线各产出一个 release（总共 2 个新 tag）
- 保留策略生效：跑到第 8 天以后，最老的 tag 应被自动删除
- 微信推送始终有文字（即使某天音频支路失败）

---

## 自审查清单

**Spec 覆盖：**
- ✅ `audio_scripter.py` — Task 3
- ✅ `audio_synth.py` 四个函数（`_synthesize_mp3` / `_create_or_update_release` / `prune_old_releases` / `synthesize_and_upload`）— Tasks 4, 5, 6, 7
- ✅ `notifier.format_digest` 扩展 — Task 8
- ✅ `config.py` 三个新变量 — Task 2
- ✅ `main.py` / `main_hot.py` 集成 — Tasks 9, 10
- ✅ `.github/workflows/daily.yml` — Task 11
- ✅ `requirements.txt` — Task 1
- ✅ 手动音色脚本 — Task 12
- ✅ CLAUDE.md — Task 13
- ✅ Release 保留策略 `keep=7` — Task 6
- ✅ `audio-digest` vs `audio-hot` 前缀 — Tasks 9, 10
- ✅ 错误降级路径（audio_scripter / audio_synth / prune 各自） — Tasks 7, 9
- ✅ 音频链接在 Markdown 顶部（不是底部） — Task 8 断言 `audio_idx < first_section_idx`
- ✅ 上线后人工操作（取消 Releases watch） — Task 15 Step 4

**无占位符：** 所有代码块都是可粘贴的完整实现；所有测试都是可运行的断言。

**类型一致性：**
- `build_audio_script` 签名 (articles, llm, today, title_prefix=…) → 在 Task 3 定义，在 Task 9 / 10 以 `(analyzed, llm, date.today())` 或 `(analyzed, llm, date.today(), title_prefix="英超热议文章")` 调用 — 一致。
- `synthesize_and_upload` 签名 (script, today, voice, tag_prefix, repo, keep) async → 在 Task 7 定义 async，在 Tasks 9, 10 以 `await synthesize_and_upload(...)` 调用 — 一致。
- `format_digest` 新增 `audio_url` kwarg → 在 Task 8 定义，Tasks 9, 10 以 `notify(..., audio_url=audio_url)` 调用，`notify` 透传给 `format_digest` — Task 8 也需确认 `notify` 本身原封不动把 kwargs 传进去。**核对：** 现有 `notifier.notify` 调 `format_digest(articles, today, title_prefix=..., has_fallbacks=...)`，没有透传 `audio_url`。必须修改 `notify` 函数签名也加 `audio_url` 并透传。

**已在 Task 8 Step 3 中一次性处理：** `format_digest` 和 `notify` 同步扩展 `audio_url` 参数，`notify` 透传给 `format_digest`。
