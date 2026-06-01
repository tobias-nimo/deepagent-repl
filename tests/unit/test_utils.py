"""Pure helpers in utils/ and the cost arithmetic on Session.

- tokens.extract_usage — reads usage_metadata or response_metadata.usage.
- cost.format_cost / format_tokens — display formatting.
- images — path detection/extraction, media types, multimodal payloads, and the
  terminal-protocol escape builders (driven via env, no real terminal needed).
- session.add_usage — accumulates tokens always, cost only when prices are known.
"""

from __future__ import annotations

from deepagent_tui.session import Session
from deepagent_tui.utils import images
from deepagent_tui.utils.cost import format_cost, format_tokens
from deepagent_tui.utils.tokens import extract_usage

# ── tokens ────────────────────────────────────────────────────────────────


def test_extract_usage_from_usage_metadata():
    assert extract_usage({"usage_metadata": {"input_tokens": 10, "output_tokens": 3}}) == (10, 3)


def test_extract_usage_from_response_metadata_prompt_completion():
    msg = {"response_metadata": {"usage": {"prompt_tokens": 7, "completion_tokens": 2}}}
    assert extract_usage(msg) == (7, 2)


def test_extract_usage_absent_returns_zeroes():
    assert extract_usage({}) == (0, 0)


# ── cost / token formatting ───────────────────────────────────────────────


def test_format_cost_small_uses_four_decimals():
    assert format_cost(0.0012) == "$0.0012"


def test_format_cost_large_uses_two_decimals():
    assert format_cost(1.5) == "$1.50"


def test_format_tokens_scales():
    assert format_tokens(950) == "950"
    assert format_tokens(1500) == "1.5k"
    assert format_tokens(2_500_000) == "2.5M"


# ── session.add_usage ─────────────────────────────────────────────────────


def test_add_usage_accumulates_tokens_without_prices():
    s = Session()
    s.add_usage(100, 20)
    s.add_usage(50, 10)
    assert (s.input_tokens, s.output_tokens) == (150, 30)
    assert s.total_cost == 0.0  # no prices → no false cost


def test_add_usage_computes_cost_when_prices_known():
    s = Session()
    s.input_price_per_mtok = 3.0
    s.output_price_per_mtok = 15.0
    s.add_usage(1_000_000, 1_000_000)
    assert s.total_cost == 18.0


# ── images: detection & payloads ──────────────────────────────────────────


def test_is_image_path():
    assert images.is_image_path("/a/b.png") is True
    assert images.is_image_path("/a/b.txt") is False


def test_get_image_media_type():
    assert images.get_image_media_type("/x.png") == "image/png"
    assert images.get_image_media_type("/x.jpeg") == "image/jpeg"
    assert images.get_image_media_type("/x.unknown") == "image/png"  # fallback


def test_detect_image_paths_only_returns_existing(tmp_path):
    real = tmp_path / "shot.png"
    real.write_bytes(b"\x89PNG")
    text = f"see {real} and /nope/missing.png"
    assert images.detect_image_paths(text) == [str(real)]


def test_extract_image_paths_strips_token_and_resolves(tmp_path):
    real = tmp_path / "pic.png"
    real.write_bytes(b"\x89PNG")
    cleaned, paths = images.extract_image_paths(f"look '{real}' please")
    assert paths == [str(real)]
    assert str(real) not in cleaned
    assert cleaned == "look please"


def test_build_multimodal_content_includes_image_and_text(tmp_path):
    real = tmp_path / "pic.png"
    real.write_bytes(b"\x89PNG\r\n")
    content = images.build_multimodal_content("hello", [str(real)])
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[-1] == {"type": "text", "text": "hello"}


def test_build_multimodal_content_skips_unreadable_image():
    content = images.build_multimodal_content("hi", ["/does/not/exist.png"])
    assert content == [{"type": "text", "text": "hi"}]


# ── images: terminal protocol detection (env-driven) ──────────────────────


def _fresh_support():
    # The module caches detection on a singleton; build a fresh instance so each
    # test sees the env we set rather than a cached result.
    return images._TerminalImageSupport()


def test_protocol_detects_iterm2(monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert _fresh_support().protocol == "iterm2"


def test_protocol_detects_kitty(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.setenv("TERM_PROGRAM", "")
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert _fresh_support().protocol == "kitty"


def test_protocol_none_when_unsupported(monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert _fresh_support().protocol is None


def test_render_image_inline_iterm2(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr(images, "_terminal", _fresh_support())
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    seq = images.render_image_inline(str(img))
    assert seq is not None
    assert seq.startswith("\033]1337;File=")


def test_render_image_inline_returns_none_when_unsupported(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr(images, "_terminal", _fresh_support())
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert images.render_image_inline(str(img)) is None


def test_render_image_inline_kitty_chunks(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG" * 4000)  # large enough to span multiple kitty chunks
    monkeypatch.setattr(images, "_terminal", _fresh_support())
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.setenv("TERM_PROGRAM", "")
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    seq = images.render_image_inline(str(img))
    assert seq is not None
    assert seq.startswith("\033_Ga=T")
    assert "\033_Gm=" in seq  # continuation chunk present


def test_write_inline_image_writes_when_supported(tmp_path, monkeypatch, capsys):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr(images, "_terminal", _fresh_support())
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert images.write_inline_image(str(img)) is True
    assert "\033]1337;File=" in capsys.readouterr().out


def test_write_inline_image_false_when_unsupported(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr(images, "_terminal", _fresh_support())
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert images.write_inline_image(str(img)) is False
