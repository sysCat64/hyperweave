"""Strip layout invariance pins (v0.3.9 additive layout).

Three behaviors locked here:

1. **Height invariance under metric-count variation.** Both brutalist and
   chrome strip canvases must stay 52px tall regardless of metric count.
   Width grows with content (additive slot assembly); height does not.
   Pre-v0.3.9, my first-pass redistribution stretched cells to fill a
   pinned canvas, producing 350px cells for n=1 with text floating in
   the center. The additive layout sizes each cell to its content + pad,
   leaving no dead space inside cells or between cells and the bookend.

2. **Cell positions follow additive assembly.** Cell n+1's x-coordinate
   equals cell n's x plus cell n's content-width. No reshuffling, no
   redistribution. For brutalist with cell_min_width=100, cells march
   at 170, 270, 370, 470 (100px stride). For chrome with cell_min_width
   =106, cells march at 107, 213, 319, 425 (~106px stride).

3. **State-indicator gating on per-metric STATEFUL_TITLES presence.**
   Data-only strips (STARS, FORKS, ISSUES, PRS, DOWNLOADS, VERSION)
   render without the ``<g data-hw-zone="status">`` element. Strips
   containing at least one state-bearing title (BUILD, CI, COVERAGE,
   STATUS, HEALTH, etc.) render the indicator. Per-metric inference
   rolls up via ``compose/layout.py:decide_strip_mode``.
"""

from __future__ import annotations

import re

import pytest

from hyperweave.compose.engine import compose
from hyperweave.core.models import ComposeSpec

_VIEWBOX_RE = re.compile(r'viewBox="0 0 (\d+) (\d+)"')
_CELL_POS_RE = re.compile(r'data-hw-zone="metric-(\d+)" transform="translate\((\d+),')
_GLYPH_RE = re.compile(
    r'data-hw-zone="glyph" transform="translate\(([\d.]+),([\d.]+)\)">\s*'
    r'<svg x="-?[\d.]+"\s+y="-?[\d.]+"\s+width="([\d.]+)"\s+height="([\d.]+)"',
    re.S,
)
_IDENTITY_X_RE = re.compile(r'<text data-hw-zone="identity" x="([\d.]+)"')


def _render_strip(genome: str, metrics: list[str]) -> str:
    spec = ComposeSpec(
        type="strip",
        genome_id=genome,
        title="eli64s/readme-ai",
        value=",".join(metrics),
    )
    return compose(spec).svg


def _viewbox(svg: str) -> tuple[int, int]:
    m = _VIEWBOX_RE.search(svg)
    assert m, f"no viewBox found in:\n{svg[:300]}"
    return int(m.group(1)), int(m.group(2))


def _has_status_indicator(svg: str) -> bool:
    return '<g data-hw-zone="status"' in svg


METRIC_POOL = ["STARS:2.9k", "FORKS:278", "ISSUES:14", "PRS:7"]


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_brutalist_height_invariant(n: int) -> None:
    """Brutalist strip height MUST stay 52px at any metric count.

    Width adapts to content (additive); height does not.
    """
    svg = _render_strip("brutalist", METRIC_POOL[:n])
    _, height = _viewbox(svg)
    assert height == 52, f"brutalist n={n}: height drifted from 52"


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_chrome_height_invariant(n: int) -> None:
    """Chrome strip height MUST stay 52px at any metric count.

    Width adapts to content; height does not.
    """
    svg = _render_strip("chrome", METRIC_POOL[:n])
    _, height = _viewbox(svg)
    assert height == 52, f"chrome n={n}: height drifted from 52"


def test_brutalist_width_grows_with_metric_count() -> None:
    """Brutalist canvas WIDTH grows monotonically as metrics are added.

    Pre-v0.3.9 additive rewrite: cells were stretched to fill a pinned
    560 canvas, producing identical widths for any n (and elongated
    cells for low n). Post-rewrite: each cell adds its content-width,
    so n=1 < n=2 < n=3 < n=4.
    """
    widths = [_viewbox(_render_strip("brutalist", METRIC_POOL[:n]))[0] for n in (1, 2, 3, 4)]
    assert widths == sorted(widths) and len(set(widths)) == 4, (
        f"brutalist widths {widths} should grow strictly monotonically with n"
    )


def test_chrome_width_grows_with_metric_count() -> None:
    """Chrome canvas WIDTH grows monotonically as metrics are added."""
    widths = [_viewbox(_render_strip("chrome", METRIC_POOL[:n]))[0] for n in (1, 2, 3, 4)]
    assert widths == sorted(widths) and len(set(widths)) == 4, (
        f"chrome widths {widths} should grow strictly monotonically with n"
    )


def test_brutalist_cells_march_at_cell_min_width_stride() -> None:
    """Brutalist cells advance at cell_min_width stride (100px floor).

    Cell 0 starts at brand_divider_x (170). Each subsequent cell advances
    by the prior cell's width, which equals max(content_w + cell_pad,
    cell_min_w=100). For the METRIC_POOL test values (STARS:2.9k etc.)
    content fits comfortably under 100px so the floor wins everywhere.
    """
    expected = {
        1: [(0, 170)],
        2: [(0, 170), (1, 270)],
        3: [(0, 170), (1, 270), (2, 370)],
        4: [(0, 170), (1, 270), (2, 370), (3, 470)],
    }
    for n, want in expected.items():
        svg = _render_strip("brutalist", METRIC_POOL[:n])
        got = [(int(i), int(x)) for i, x in _CELL_POS_RE.findall(svg)]
        assert got == want, f"brutalist n={n}: positions {got} != {want}"


@pytest.mark.parametrize(
    "metrics,expected,case",
    [
        (["STARS:373k", "FORKS:12k", "ISSUES:234"], False, "data-only (3)"),
        (["STARS:2.9k", "FORKS:278", "ISSUES:14", "PRS:7"], False, "data-only (4)"),
        (["VERSION:v0.3.9", "DOWNLOADS:1.2M"], False, "data-only (version + downloads)"),
        (["BUILD:passing", "STARS:2.9k"], True, "state + data"),
        (["BUILD:failing"], True, "state-only"),
        (["COVERAGE:94"], True, "coverage-only"),
    ],
)
def test_brutalist_state_indicator_gates_on_stateful_titles(metrics: list[str], expected: bool, case: str) -> None:
    """Brutalist state indicator renders ONLY when at least one metric
    title is in ``data/badge_modes.yaml`` (STATEFUL_TITLES set).

    Per-metric inference via ``compose/layout.py:decide_strip_mode``;
    no per-strip "force-indicator" override. Data-only strips (high-
    star repos like openclaw 373k, n8n 189k) must render without the
    indicator — the indicator is exclusively for state metrics
    (build/ci/coverage/health), not for data magnitude.
    """
    svg = _render_strip("brutalist", metrics)
    assert _has_status_indicator(svg) is expected, f"brutalist {case}: indicator presence != {expected}"


@pytest.mark.parametrize(
    "metrics,expected,case",
    [
        (["STARS:373k", "FORKS:12k", "ISSUES:234"], False, "data-only"),
        (["BUILD:passing", "STARS:2.9k"], True, "state + data"),
    ],
)
def test_chrome_state_indicator_gates_on_stateful_titles(metrics: list[str], expected: bool, case: str) -> None:
    """Chrome strip honors the same state-indicator gate as brutalist.

    The gate lives in ``compose/resolver.py:resolve_strip`` and
    ``compose/layout.py:decide_strip_mode`` — paradigm-agnostic.
    """
    svg = _render_strip("chrome", metrics)
    assert _has_status_indicator(svg) is expected, f"chrome {case}: indicator presence != {expected}"


# ─────────────────────────────────────────────────────────────────────
# Identity overflow shrink-to-fit + chrome min-width
# ─────────────────────────────────────────────────────────────────────

_IDENTITY_TEXTLENGTH_RE = re.compile(r'data-hw-zone="identity"[^>]*textLength="([\d.]+)"')


def test_brutalist_long_identity_emits_textlength() -> None:
    """Bug 5a fix: when identity text exceeds brand_panel_width - 2*pad,
    the resolver populates identity_text_length and the brutalist template
    emits ``textLength`` + ``lengthAdjust="spacingAndGlyphs"`` on the
    identity ``<text>`` element. The value equals the available text width
    inside the brand panel.

    Before shrink-to-fit, "SIGNIFICANT-GRAVITAS/AUTOGPT" identity
    (~240px wide) bled past the 156-wide brand panel into the first metric
    cell. The current clamp limits it to the available panel width.
    """
    spec = ComposeSpec(
        type="strip",
        genome_id="brutalist",
        title="SIGNIFICANT-GRAVITAS/AUTOGPT",
        value="STARS:184k,FORKS:46k,ISSUES:428,PRS:42",
    )
    svg = compose(spec).svg
    m = _IDENTITY_TEXTLENGTH_RE.search(svg)
    assert m is not None, (
        "brutalist long-identity strip MUST emit textLength on identity <text> "
        "for shrink-to-fit. The Bug 5a fix is geometrically gone if this "
        "assertion fails."
    )
    text_length_value = float(m.group(1))
    # Content-driven: brand_panel_right (brand_panel_x 6 +
    # brand_panel_width 156) - identity_text_x 50 - identity_panel_pad 8 = 104.
    # identity_text_x=50 anchors text 44px from the panel left edge, leaving
    # 104px of available width before the panel's right edge.
    assert text_length_value == 104.0, (
        f"identity textLength={text_length_value}, expected 104.0 "
        f"(brand_panel_right 162 - identity_text_x 50 - identity_panel_pad 8)."
    )
    # lengthAdjust must be present on the same element (Camo-safe attribute set).
    assert 'lengthAdjust="spacingAndGlyphs"' in svg, (
        "lengthAdjust='spacingAndGlyphs' MUST accompany textLength for consistent rendering across renderers."
    )


def test_brutalist_short_identity_does_not_emit_textlength() -> None:
    """Short identities fit within the brand panel without shrink — the
    template MUST NOT emit textLength when identity_text_length=0.
    Otherwise short identities render with unnecessary letter-spacing
    distortion."""
    spec = ComposeSpec(
        type="strip",
        genome_id="brutalist",
        title="hyperweave",
        value="STARS:15",
    )
    svg = compose(spec).svg
    m = _IDENTITY_TEXTLENGTH_RE.search(svg)
    assert m is None, f"short identity should NOT emit textLength, found {m.group(1) if m else None}"


def test_chrome_strip_glyph_identity_gap_is_rendered_from_zone_geometry() -> None:
    """Chrome glyph and identity text render with the computed 9px gap."""
    spec = ComposeSpec(
        type="strip",
        genome_id="chrome",
        title="eli64s/readme-ai",
        value="STARS:2.9k,FORKS:278",
        glyph="github",
    )
    svg = compose(spec).svg
    glyph = _GLYPH_RE.search(svg)
    identity = _IDENTITY_X_RE.search(svg)
    assert glyph is not None
    assert identity is not None
    glyph_cx = float(glyph.group(1))
    glyph_w = float(glyph.group(3))
    identity_x = float(identity.group(1))
    assert identity_x == glyph_cx + glyph_w / 2 + 9


@pytest.mark.parametrize("n", [1, 2, 3])
def test_chrome_strip_clamps_to_min_width(n: int) -> None:
    """Bug 5b fix: chrome.yaml declares ``strip_min_width: 320`` so 1-metric
    chrome strips don't aspect-warp in README columns. The clamp applies to
    the natural width when below 320; wider strips pass through unchanged."""
    svg = _render_strip("chrome", METRIC_POOL[:n])
    width, _ = _viewbox(svg)
    assert width >= 320, f"chrome n={n}: width={width} below strip_min_width=320"


def test_brutalist_strip_unaffected_by_chrome_min_width() -> None:
    """The strip_min_width clamp is paradigm-scoped (chrome.yaml only).
    Brutalist strips compute their own minimum via the owns_strip bookend
    grammar — they should not adopt chrome's 320 floor."""
    svg = _render_strip("brutalist", METRIC_POOL[:1])
    width, _ = _viewbox(svg)
    # Brutalist 1-metric natural width: brand_divider_x 170 + cell_min_width 100
    # + bookend_gap 16 + bookend_pad_right 40 = ~326. Independent of chrome's clamp.
    # Test only confirms brutalist isn't being force-clamped to 320 by a stray
    # paradigm cross-leak.
    assert width != 320, (
        f"brutalist width={width} suspiciously matches chrome strip_min_width "
        "— possible paradigm config cross-contamination"
    )
