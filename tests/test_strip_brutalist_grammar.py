"""Brutalist strip grammar (v0.3.2 Phase C, updated v0.3.9 additive).

When a paradigm declares `owns_strip: true` in its YAML config, the parent
strip.svg.j2 wraps its shared zone pipeline (icon-box, glyph, identity,
metric cells, status indicator) in `{% if not paradigm_owns_strip %}` and
the paradigm content partial assumes full responsibility for body composition.

This test pins the contract on three axes:
1. Brutalist strips render the brutalist strip grammar (brand panel +
   ACCENT-VOID-ACCENT triple divider + ornament + bookend + Barlow Condensed
   metric numerals).
2. Other paradigms (chrome, cellular) leave `paradigm_owns_strip` False and
   continue rendering through the shared zone pipeline — no brand panel rect,
   no brutalist strip CSS classes, no bookend ornament.
3. Brutalist strip canvas WIDTH adapts to metric content AND identity
   content: brand panel sizes to identity text width with
   ``brand_panel_width`` as the MAX ceiling;
   triple_divider_x and brand_divider_x follow the panel right edge.
   Cells march at cell_min_width=100 stride. Bookend snaps to
   ``cells_end + 16`` (gap), canvas width = bookend + 40 (trailing pad).
   HEIGHT stays pinned at 52. For the 3-metric reference render
   (title=HYPERWEAVE, identity ~100px wide): brand_panel_w=136,
   triple_divider_x=142, brand_divider_x=150, cells at 150/250/350,
   last cell ends at 450, bookend at 466, canvas 506x52.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hyperweave.compose.engine import compose
from hyperweave.core.models import ComposeSpec

if TYPE_CHECKING:
    import pytest


def _render(genome: str, variant: str | None = None) -> str:
    spec = ComposeSpec(
        type="strip",
        genome_id=genome,
        title="HYPERWEAVE",
        value="STARS:2898,FORKS:283,ISSUES:64",
        variant=variant or "",
    )
    return compose(spec).svg


def test_brutalist_brand_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Brutalist celadon strip brand panel sizes to identity content.

    For title='HYPERWEAVE' (~100px wide content-driven), brand_panel_w=136
    (< YAML max 156). The panel shrinks to fit content rather than holding
    a fixed width — same algorithm clamps to 156 for longer identities and
    triggers shrink-to-fit textLength when content overflows.
    """
    body = _render("brutalist", "celadon")
    assert re.search(
        r'<rect\s+x="6"\s+y="0"\s+width="136"\s+height="52"\s+fill="var\(--dna-brand-panel-fill\)"',
        body,
    ), "brutalist HYPERWEAVE strip must render content-driven brand panel at x=6 width=136"


def test_brutalist_triple_divider(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACCENT-VOID-ACCENT triple divider follows the content-driven brand panel
    right edge (x=142 for HYPERWEAVE: brand_panel_x 6 + brand_panel_w 136).
    Width 3px + 2px + 3px = 8px total triple-divider span.
    """
    body = _render("brutalist", "celadon")
    assert re.search(r'<rect\s+x="142"\s+y="0"\s+width="3"', body), "missing left accent bar of triple divider"
    assert re.search(r'<rect\s+x="145"\s+y="0"\s+width="2"', body), "missing center void of triple divider"
    assert re.search(r'<rect\s+x="147"\s+y="0"\s+width="3"', body), "missing right accent bar of triple divider"


def test_brutalist_ornament_and_bookend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identity ornament at (22,19) 14x14 + bookend snaps after cells.

    ornament_size stays at 14 because it also controls the right bookend
    square. The left identity GitHub glyph uses a separate
    ``identity_glyph_size`` field; the fallback ornament square and right
    bookend stay at 14.

    For the 3-metric reference render (HYPERWEAVE identity → brand_divider_x
    150): cells end at 150 + 3*100 = 450, bookend at 450 + 16 gap = 466.
    """
    body = _render("brutalist", "celadon")
    assert re.search(
        r'<rect\s+x="22"\s+y="19"\s+width="14"\s+height="14"',
        body,
    ), "brutalist strip must render identity ornament at (22,19) size 14"
    assert "translate(466,26)" in body, (
        "brutalist 3-metric strip must render bookend at x=466 (=cells_end 450 + 16 gap)"
    )


def test_brutalist_canvas_height_invariant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip height pinned at 52 regardless of metric count (additive layout)."""
    body = _render("brutalist", "celadon")
    assert re.search(r'viewBox="0\s+0\s+\d+\s+52"', body), "brutalist strip canvas height must stay 52"


def test_brutalist_canvas_width_additive(monkeypatch: pytest.MonkeyPatch) -> None:
    """3-metric brutalist strip is 506 wide (bookend 466 + 40px trailing pad).

    Width = brand_panel_x 6 + brand_panel_w 136 + triple_divider_w 8 +
    3 cells * 100 + bookend_gap 16 + trailing_pad 40 = 506.
    """
    body = _render("brutalist", "celadon")
    assert re.search(r'viewBox="0\s+0\s+506\s+52"', body), (
        "brutalist 3-metric strip canvas must be 506x52 under content-driven layout"
    )


def test_brutalist_typography_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Metric cells use the unprefixed strip-grammar CSS classes."""
    body = _render("brutalist", "celadon")
    assert "brand-text" in body, "brutalist strip must use brand-text class on identity"
    assert "metric-label" in body, "brutalist strip must use metric-label class on metric labels"
    assert "metric-value" in body, "brutalist strip must use metric-value class on metric values"


def test_brutalist_light_substrate_inversion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Light variant uses url(#panel) gradient + INK-SEAM-INK (dark+gold+dark)."""
    body = _render("brutalist", "pulse")
    assert "url(#hw-" in body and "-panel)" in body, "brutalist light strip must reference panel gradient"
    # Verify INK-SEAM-INK polarity: outer bars use ink-primary, center uses seam-color.
    # Triple divider x follows content-driven brand panel (HYPERWEAVE → x=142).
    assert re.search(
        r'<rect\s+x="142"\s+y="0"\s+width="3"\s+height="52"\s+fill="var\(--dna-ink-primary\)"',
        body,
    ), "light variant triple divider outer must use --dna-ink-primary"
    assert re.search(
        r'<rect\s+x="145"\s+y="0"\s+width="2"\s+height="52"\s+fill="var\(--dna-seam-color\)"',
        body,
    ), "light variant triple divider center must use --dna-seam-color"


def test_chrome_strip_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chrome paradigm leaves owns_strip at default False — no brutalist artifacts."""
    spec = ComposeSpec(
        type="strip",
        genome_id="chrome",
        title="HYPERWEAVE",
        value="STARS:2898,FORKS:283",
        variant="",  # horizon flagship
    )
    body = compose(spec).svg
    assert "dna-brand-panel-fill" not in body, "chrome strip must NOT carry brand-panel CSS var (no brutalist grammar)"
    # CSS class match for the brutalist-strip-grammar identity class. Pattern
    # matches `class="..."` references, not the `--dna-brand-text` CSS var
    # which chrome's own genome legitimately defines.
    assert not re.search(r'class="hw-[0-9a-f]+-brand-text"', body), (
        "chrome strip must NOT use the brutalist strip grammar `.brand-text` class"
    )
    # Chrome strip uses chrome-specific identity/metric classes from chrome-defs.j2 —
    # presence of metric cell zones confirms parent pipeline ran.
    assert 'data-hw-zone="metric-' in body, "chrome strip must render metric cells via parent zone pipeline"
