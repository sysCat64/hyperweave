"""Centralized spatial-layout engine for badge / strip frames.

Single source of truth for badge AND strip geometry. Replaces the inline
arithmetic that lived in ``compose/resolver.py:resolve_badge`` and
``resolve_strip``, and the duplicated geometry derivations in
``templates/frames/{badge,strip}/*.j2``.

Per Invariant 6 (CLAUDE.md): templates render, compose computes geometry.
Per ``feedback_compose_owns_geometry_template_renders.md``: layout
decisions belong in compose/, not Jinja2.

v0.3.9 equal-spacing rule:

    Every gap between PRESENT zones equals ``pad``. Absent zones collapse
    entirely — no phantom slot, no reserved width. The rule is paradigm-
    agnostic; ``pad`` comes from ``ParadigmBadgeConfig.pad`` so each
    paradigm tunes its visual rhythm without touching the layout code.

    Sequence (left → right) for a badge:
        accent_w  +  pad  +  [glyph + pad]  +  label + pad  +  [sep+seam]
                  +  pad  +  value + pad  +  [state_indicator + pad]
                  +  right_canvas_inset

    Glyph zone and state-indicator zone are gated by ``has_glyph`` and
    ``has_state_indicator``. When False, the cursor never advances into
    them — the badge shrinks accordingly.

Public surface:

- ``BadgeZones`` / ``compute_badge_zones`` — badge geometry (the v0.3.9
  zone-based replacement for the prior ``BadgeLayout`` / ``compute_badge_layout``).
- ``StripZones`` / ``compute_strip_zones`` — strip geometry (the v0.3.9
  introduction; supersedes inline arithmetic in ``resolve_strip``).
- ``resolve_badge_mode`` — three-mode classification (stateful / stateless
  / explicit) keyed off the spec and a title allowlist.
- ``decide_strip_mode`` — same classification rolled up over a strip's
  metric labels.
- ``data_hw_statemode_for`` — maps mode to the ``data-hw-statemode``
  SVG-root attribute that gates threshold-CSS auto-tinting in
  ``data/css/expression.css``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hyperweave.core.models import ComposeSpec


BadgeMode = Literal["stateful", "stateless", "explicit"]


def compute_strip_glyph_size(strip_height: int, strip_glyph_ratio: float) -> int:
    """Derive the strip identity glyph size from its container.

    The identity glyph is sized as a fraction of strip height so all
    paradigms scale uniformly. Default ratio 0.346 yields 18px at
    strip_height=52 — the v0.3.9 design constant established by brutalist's
    specimen (an 18px identity glyph in a 52px strip).

    Replaces v0.3.9-and-prior hand-synced pair
    (chrome ``glyph_size: 22`` + brutalist ``identity_glyph_size: 18``) that
    had to stay in proportional agreement by manual update. Single
    computation site so regression tests can pin the derivation.
    """
    return round(strip_height * strip_glyph_ratio)


def compute_badge_glyph_size(badge_height: int, badge_glyph_ratio: float, glyph_size_max: int = 0) -> int:
    """Derive a badge glyph render-box size from the badge height.

    Badges across paradigms share the same identity-glyph weight instead of
    carrying per-template magic sizes. ``glyph_size_max`` lets taller badge
    variants keep the canonical compact glyph weight while still using the
    same proportional rule for 20px badges.
    """
    size = round(badge_height * badge_glyph_ratio)
    if glyph_size_max > 0:
        size = min(size, glyph_size_max)
    return max(1, size)


@dataclass(frozen=True, slots=True)
class BadgeZones:
    """Resolved zone layout for a badge frame.

    Templates consume these directly via ``{{ width }}``, ``{{ label_x }}``,
    ``{{ value_x }}``, etc. — no template-side arithmetic. ``label_text_length``
    and ``value_text_length`` carry the SVG ``textLength`` attribute value
    when shrink-to-fit is active (0.0 = render natural width).

    Equal-spacing rule (v0.3.9): every gap between PRESENT zones equals
    ``pad``. Absent zones (no glyph, no state indicator) collapse fully —
    no reserved width, no phantom gap.
    """

    width: int
    height: int
    glyph_x: float
    """Left edge of glyph zone. 0.0 when ``has_glyph=False``."""
    glyph_y: float
    """Top edge of glyph zone (vertically centered in badge). 0.0 when absent."""
    glyph_size: int
    """Glyph render-box side length. 0 when ``has_glyph=False``."""
    label_x: float
    """SVG x for label ``<text>``. ``text_anchor='middle'``: center of label.
    ``text_anchor='start'``: first character x. Determined by paradigm config."""
    label_w: float
    """Measured label render width (after any shrink-to-fit clamp)."""
    label_text_length: float
    """SVG ``textLength`` attribute value. 0.0 = no shrink-to-fit."""
    seam_x: float
    """x of the seam midline (left_panel_w + sep_w/2)."""
    value_x: float
    """SVG x for value ``<text>`` center."""
    value_w: float
    """Measured value render width (after any shrink-to-fit clamp)."""
    value_text_length: float
    """SVG ``textLength`` for value. 0.0 = no shrink-to-fit."""
    indicator_x: float
    """Left edge of state indicator. 0.0 when ``has_state_indicator=False``."""
    indicator_y: float
    """Top edge of state indicator. 0.0 when absent."""
    indicator_size: int
    """State indicator side length. 0 when absent."""
    left_panel_w: int
    """Width of the left panel (glyph + label + interior padding)."""
    right_panel_x: int
    """x of the right panel's left edge (left_panel_w + sep_w + seam_w)."""
    right_panel_w: int
    """Right panel width (total_w - right_panel_x)."""
    text_y: float
    """Baseline y for label + value text."""
    show_indicator: bool
    """Mirror of ``has_state_indicator`` (kept for template compatibility)."""
    inner_bit_w: int
    """Inner bit side length inside the indicator's outer ring."""
    inner_bit_offset: float
    """Offset from indicator's outer ring to inner bit (= (size - bit_w) / 2)."""
    value_zone_left: float
    """Left bound of value text zone (kept for backward-compat with assertion tests)."""
    value_zone_right: float
    """Right bound of value text zone."""
    value_zone_width: float
    """value_zone_right - value_zone_left."""
    # Chrome etched seam (paradigm with seam_render_w > 0; 0 for other paradigms).
    seam_left_x: float = 0
    """Left hairline of the chrome etched seam (dark cut). 0 when no etched seam."""
    seam_specular_x: float = 0
    """Right hairline of the chrome etched seam (specular catch). 0 when no etched seam."""
    text_anchor: str = "middle"
    """SVG text-anchor for label/value. Paradigm-declared: ``middle`` (brutalist/cellular)
    centers text on ``label_x``/``value_x``; ``start`` (chrome) anchors first-character x."""


def compute_badge_zones(
    *,
    height: int,
    pad: int,
    measured_label_w: float,
    measured_value_w: float,
    has_glyph: bool,
    has_state_indicator: bool,
    accent_w: int,
    glyph_size: int,
    glyph_left_offset: int,
    sep_w: int,
    seam_w: int,
    indicator_size: int,
    right_canvas_inset: int = 0,
    min_total_w: int = 60,
    inner_bit_ratio: float = 0.5,
    text_y_factor: float = 0.69,
    label_font_size: float = 11,
    value_font_size: float = 11,
    max_label_w: float = 0,
    max_value_w: float = 0,
    label_w_floor: int = 30,
    text_anchor: str = "middle",
    seam_render_w: float = 0.0,
    seam_specular_offset: float = 0.0,
    label_end_bearing: float = 0.0,
    value_end_bearing: float = 0.0,
    glyph_y_offset: float = 0.0,
    text_visual_center_offset_em: float = 0.3,
) -> BadgeZones:
    """Compute badge zone layout under the unified additive algorithm.

    Algorithm
    ---------
    Single additive cursor walk for ALL paradigms. Removes the prior
    fixed/budget mode split; paradigm-specific structural differences flow
    through config (``text_anchor``, ``seam_render_w``, ``seam_specular_offset``,
    ``pad``).

    Cursor walks left to right. Starts at ``accent_w + glyph_left_offset + pad``
    (structural frame). For each PRESENT zone, the cursor advances by the
    zone's content width plus ``pad``. Absent zones (no glyph, no state
    indicator) are skipped entirely — the cursor never advances into a
    reserved slot.

    Panel separator handling (two orthogonal modes):

    * ``seam_render_w > 0`` (chrome): etched-seam slot between label and
      value zones with half-gaps on each side (``pad/2`` left + ``pad/2``
      right). Emits ``seam_left_x`` (dark cut) and ``seam_specular_x`` (catch,
      offset by ``seam_specular_offset``). Synthetic ``left_panel_w`` /
      ``right_panel_x`` derived from seam center for template backward-compat.
    * ``seam_render_w == 0`` (brutalist + cellular): structural panel
      separator (``sep_w`` stroke + ``seam_w`` mark). Full pad on each side
      of the panel boundary. No etched seam hairlines emitted.

    Shrink-to-fit
    -------------
    When ``max_label_w > 0`` and ``measured_label_w > max_label_w``, the
    returned ``label_w`` clamps to ``max_label_w`` and ``label_text_length``
    is populated so templates emit ``textLength`` + ``lengthAdjust=
    "spacingAndGlyphs"``. Same logic for value.

    SVG text anchoring
    ------------------
    Paradigm declares ``text_anchor``. ``middle`` (brutalist/cellular):
    ``label_x``/``value_x`` are zone centers. ``start`` (chrome): they are
    first-character positions. Templates render
    ``<text text-anchor="{{ text_anchor }}" x="{{ label_x }}">``.
    """
    # Clamp label and value to shrink-to-fit ceilings before geometry.
    label_w = measured_label_w
    label_text_length = 0.0
    if max_label_w > 0 and measured_label_w > max_label_w:
        label_w = max_label_w
        label_text_length = max_label_w

    value_w = measured_value_w
    value_text_length = 0.0
    if max_value_w > 0 and measured_value_w > max_value_w:
        value_w = max_value_w
        value_text_length = max_value_w

    # Text baseline (label + value share the same y for consistent reading line).
    text_y = round(height * text_y_factor, 1)

    # Structural frame ends at accent + paradigm-specific left-decoration
    # offset (cellular pattern strip at x=2..~20 sets glyph_left_offset=18).
    structural_left = accent_w + glyph_left_offset

    # Cursor starts at structural_left + pad — that's the equal-spacing
    # gap between left edge and the first content zone (glyph or label).
    cursor = float(structural_left + pad)

    # Glyph zone (skip if absent — collapse entirely, no phantom gap).
    if has_glyph:
        glyph_x = cursor
        # Align the glyph box to the label's visual center, not the frame's
        # geometric center. Alphabetic-baseline text sits roughly 0.3em above
        # its baseline; dominant-baseline=central text declares a zero offset.
        text_visual_center = text_y - label_font_size * text_visual_center_offset_em
        glyph_y = round(text_visual_center - glyph_size / 2 + glyph_y_offset, 1)
        cursor = glyph_x + glyph_size + pad
    else:
        glyph_x = 0.0
        glyph_y = 0.0

    # Label zone: cursor at first char.
    label_first_x = cursor
    label_x = round(label_first_x, 1) if text_anchor == "start" else round(label_first_x + label_w / 2, 1)
    # Algorithmic bearing correction: subtract the font's trailing
    # side-bearing from the cursor advance so the seam (placed at
    # cursor + pad/2) sits at ``visible_ink_end + pad/2`` instead of
    # ``advance_end + pad/2``. Closes the label-to-seam gap uniformly across
    # all chrome badges including the 28-char BUILD-PASSING-WITH-WARNINGS
    # case. Centered paradigms (text_anchor=middle) pass 0.0 because their
    # text balances bearing across both edges; only text_anchor=start
    # accumulates the bearing on the right side.
    cursor = label_first_x + label_w - label_end_bearing

    # Panel separator: two orthogonal modes (etched seam OR structural separator).
    seam_left_x = 0.0
    seam_specular_x = 0.0
    if seam_render_w > 0:
        # Chrome etched seam: half-gaps on each side, two-hairline rendering.
        cursor += pad / 2.0
        seam_left_x = cursor
        seam_specular_x = cursor + seam_specular_offset
        cursor += seam_render_w + pad / 2.0
        # Synthetic left_panel / right_panel boundary for template backward-compat.
        seam_center_x = seam_left_x + seam_render_w / 2.0
        seam_x = round(seam_center_x, 1)
        left_panel_w = round(seam_center_x)
        right_panel_x = round(seam_center_x + seam_render_w / 2.0)
    else:
        # Brutalist/cellular: structural separator (sep_w stroke + seam_w mark).
        # Full pad after label, then sep+seam, then full pad before value.
        cursor += pad
        left_panel_w = max(round(cursor), label_w_floor)
        seam_x = left_panel_w + sep_w / 2.0
        right_panel_x = left_panel_w + sep_w + seam_w
        cursor = float(right_panel_x + pad)

    # Value zone: cursor at first char.
    value_first_x = cursor
    value_x = round(value_first_x, 1) if text_anchor == "start" else round(value_first_x + value_w / 2, 1)
    # v0.3.9 algorithmic bearing correction (mirror of label): subtract
    # value-text trailing bearing before the trailing pad so the right edge
    # sits at ``visible_ink_end + pad`` instead of ``advance_end + pad``.
    cursor = value_first_x + value_w - value_end_bearing + pad

    # Optional state-indicator zone. Every gap including the final one
    # (last content zone → right edge) is ``pad``. The cursor walk advances
    # by ``content + pad`` for each PRESENT zone, and the final pad added
    # after the last zone is the right-edge gap itself.
    if has_state_indicator:
        indicator_x = cursor  # cursor sits at start of state-indicator slot (pad already added after value)
        cursor = indicator_x + indicator_size + pad  # trailing pad after state
    else:
        indicator_x = 0.0

    # Total width includes any paradigm-specific right-canvas inset (cellular: 2px
    # structural slab inset — adds on top of the right-edge pad gap).
    # v0.3.9 algorithmic: bearing correction is applied per-text in the cursor
    # walk above, NOT as a final-cursor trim. This produces a uniform
    # ``pad/2`` seam gap and uniform ``pad`` right-edge gap for ALL chrome
    # badges — including the 28-char BUILD-PASSING-WITH-WARNINGS case that
    # the prior flat-3px final-trim approach left visually broken (seam gap
    # was unchanged because trim affected total_w only).
    total_w = max(round(cursor + right_canvas_inset), min_total_w)
    right_panel_w = total_w - right_panel_x

    # Indicator vertical center pinned to value-text visual midline.
    # cap_height ≈ 70% of font_size; visual_center = text_y - 0.3 * font_size.
    if has_state_indicator:
        indicator_y = round(text_y - value_font_size * 0.3 - indicator_size / 2, 1)
        inner_bit_w = round(indicator_size * inner_bit_ratio)
        inner_bit_offset = (indicator_size - inner_bit_w) / 2
    else:
        indicator_y = 0.0
        inner_bit_w = 0
        inner_bit_offset = 0.0

    # Backward-compat value zone bounds (assertion tests + templates that
    # still reference these). Chrome: starts at synthetic right_panel_x (the
    # etched-seam half-gap already accounted for spacing). Brutalist/cellular:
    # right_panel_x + pad (full pad gutter after the structural separator).
    value_zone_left = float(right_panel_x) if seam_render_w > 0 else float(right_panel_x + pad)
    # Trailing pad is part of the right-edge gap. When
    # state indicator is present, value zone ends one pad before it. When
    # absent, value zone ends one pad before the right edge (= total_w -
    # right_canvas_inset - pad).
    value_zone_right = float(indicator_x - pad) if has_state_indicator else float(total_w - right_canvas_inset - pad)
    value_zone_width = value_zone_right - value_zone_left

    return BadgeZones(
        width=total_w,
        height=height,
        glyph_x=glyph_x,
        glyph_y=glyph_y,
        glyph_size=glyph_size if has_glyph else 0,
        label_x=label_x,
        label_w=label_w,
        label_text_length=label_text_length,
        seam_x=seam_x,
        value_x=value_x,
        value_w=value_w,
        value_text_length=value_text_length,
        indicator_x=indicator_x,
        indicator_y=indicator_y,
        indicator_size=indicator_size if has_state_indicator else 0,
        left_panel_w=left_panel_w,
        right_panel_x=right_panel_x,
        right_panel_w=right_panel_w,
        text_y=text_y,
        show_indicator=has_state_indicator,
        inner_bit_w=inner_bit_w,
        inner_bit_offset=inner_bit_offset,
        value_zone_left=value_zone_left,
        value_zone_right=value_zone_right,
        value_zone_width=value_zone_width,
        seam_left_x=round(seam_left_x, 1) if seam_render_w > 0 else 0.0,
        seam_specular_x=round(seam_specular_x, 1) if seam_render_w > 0 else 0.0,
        text_anchor=text_anchor,
    )


# ─────────────────────────────────────────────────────────────────────
# Strip zone layout (v0.3.9)
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StripZones:
    """Resolved zone layout for a strip frame.

    Templates consume these directly via ``{{ width }}``, ``{{ identity_x }}``,
    ``{{ first_divider_x }}``, ``{{ seam_positions }}``, etc. — zero
    template-side arithmetic.

    Two paradigm modes handled by one dataclass:

    * **Adaptive paradigms** (chrome, cellular, default): identity zone width
      grows to fit content; bookend_x = 0; cells march from first_divider_x.
    * **Owns_strip paradigms** (brutalist): brand panel is fixed-width;
      identity_text_length emits ``textLength`` attribute when measured
      identity exceeds the available panel space; bookend_x snaps dynamically
      to the right edge of the last cell + ``bookend_gap``.
    """

    width: int
    height: int
    glyph_zone_width: int
    """Width reserved for identity glyph (icon-box or bare). 0 when no glyph."""
    glyph_zone_x_offset: float
    """Additional x-shift for the glyph when bifamily flanks push everything right."""
    icon_box_x: float
    """Left edge of the optional icon box. 0.0 when absent."""
    icon_box_y: float
    """Top edge of the optional icon box. 0.0 when absent."""
    glyph_cx: float
    """Glyph center x in the template coordinate frame. 0.0 when absent."""
    glyph_cy: float
    """Glyph center y in the template coordinate frame. 0.0 when absent."""
    glyph_size: int
    """Rendered identity glyph size. 0 when absent."""
    identity_x: float
    """Left edge of the identity text zone (or fixed brand-panel coordinate for owns_strip)."""
    identity_text_length: float
    """SVG ``textLength`` attribute value for identity ``<text>``. 0.0 = no shrink-to-fit.
    Non-zero only on ``owns_strip`` paradigms when identity exceeds brand panel."""
    identity_zone_width: float
    """Measured content width of identity zone (= max(identity_w, subtitle_w))."""
    subtitle_text: str
    """Raw subtitle string for templates that gate on ``show_subtitle``. Empty when absent."""
    first_divider_x: int
    """x of the first vertical divider (where the metric grid begins)."""
    cell_widths: list[int]
    """Per-cell pitch (one int per metric)."""
    cell_layouts_records: list[dict]  # type: ignore[type-arg]
    """One ``CellLayout`` per metric, serialized as dict for template consumption."""
    seam_positions: list[float]
    """Cumulative seam x-coordinates: first_divider_x, then one per cell trailing edge."""
    status_x: float
    """Left edge of status indicator. 0 when no status indicator."""
    status_zone_width: int
    """Width of the status indicator zone (pre_gap + indicator + post_gap). 0 when absent."""
    content_right: int
    """Right edge of the content panel (= width - flank_width when flanked)."""
    bookend_x: int
    """Bookend ornament x for ``owns_strip`` paradigms. 0 for adaptive paradigms."""
    metric_pitch: int
    """Widest-cell scalar (fallback for consumers wanting uniform pitch)."""
    metrics_zone_width: int
    """Sum of all cell_widths (or n * metric_pitch when no cells)."""
    content_width: int = 0
    """Width where visible strip content ends. ``width`` may exceed this when
    ``strip_min_width`` clamps the SVG viewBox — chrome templates render
    envelope/well/rail at ``content_width`` so trailing pixels stay transparent."""
    # Content-driven owns_strip overrides. Resolver consumes these
    # in place of the YAML constants when owns_strip=True. brand_panel_width is a
    # MAX ceiling; the panel shrinks to content for short identities (N8N, 3
    # chars), and triple_divider_x / brand_divider_x follow the panel's right
    # edge. For adaptive paradigms these stay 0 — the resolver ignores them.
    brand_panel_x: int = 0
    """Brand panel left edge (owns_strip only; 0 otherwise). Mirrors YAML constant."""
    brand_panel_w: int = 0
    """Content-driven brand panel width (owns_strip only). ≤ YAML brand_panel_width."""
    triple_divider_x: int = 0
    """Triple-divider left edge (= brand_panel_x + brand_panel_w for owns_strip)."""
    brand_divider_x: int = 0
    """First metric cell seam (= triple_divider_x + 2*bar_w + void_w for owns_strip)."""


def compute_strip_zones(
    *,
    height: int,
    # Paradigm-resolved structural inputs (owns_strip flag drives major branch).
    owns_strip: bool,
    # Adaptive-paradigm fields (used when owns_strip=False).
    accent_w: int,
    show_icon_box: bool,
    icon_box_size: int,
    icon_box_pad: int,
    has_identity_glyph: bool,
    strip_glyph_size: int = 18,
    # Owns_strip fields (used when owns_strip=True).
    brand_panel_x: int = 0,
    brand_panel_width: int = 0,
    identity_text_x: int = 0,
    brand_divider_x: int = 0,
    triple_divider_bar_width: int = 3,
    triple_divider_void_width: int = 2,
    bookend_x_fallback: int = 0,
    bookend_gap: int = 16,
    bookend_pad_right: int = 40,
    identity_panel_pad: int = 8,
    # Identity zone measurement (paradigm-agnostic).
    identity_w: float = 0,
    subtitle_w: float = 0,
    subtitle_text: str = "",
    # Per-cell layouts (pre-computed via compute_cell_layout).
    cell_widths: list[int] | None = None,
    cell_layouts_records: list[dict] | None = None,  # type: ignore[type-arg]
    metric_pitch_fallback: int = 0,
    # Status indicator zone.
    has_status_indicator: bool = False,
    status_indicator_size: int = 14,
    status_indicator_pre_gap: int = 16,
    status_indicator_post_gap: int = 4,
    # Bifamily flank widths (automata strips).
    flank_width: int = 0,
    # Strip-min-width clamp (chrome's 320).
    strip_min_width: int = 0,
    # Identity-zone right padding (adaptive paradigms — gap after identity content).
    identity_right_pad: int = 14,
    # Minimum first_divider_x floor (legacy invariant).
    first_divider_x_floor: int = 80,
    # Cell start offset past first_divider_x (legacy non-zero in older releases).
    cell_offset: int = 0,
) -> StripZones:
    """Compute strip zone layout for both adaptive and owns_strip paradigms.

    Two-branch dispatch on ``owns_strip``:

    * **owns_strip=False** (chrome / cellular / default): identity zone is
      content-driven; ``first_divider_x = identity_x + identity_zone_w +
      identity_right_pad`` (floored at ``first_divider_x_floor``). Cells march
      from first_divider_x. Bookend not used.

    * **owns_strip=True** (brutalist): identity sits inside a fixed
      ``brand_panel_width`` zone. If ``identity_w > brand_panel_width -
      2 * identity_panel_pad``, ``identity_text_length`` is populated so the
      template emits ``textLength`` + ``lengthAdjust="spacingAndGlyphs"`` on
      the identity ``<text>`` element. Cells start at ``brand_divider_x``.
      Bookend snaps to right edge of last cell + ``bookend_gap``; total width
      = bookend_x + bookend_pad_right.

    Min-width clamp
    ---------------
    When ``strip_min_width > 0`` and the computed width is below the floor,
    width clamps to ``strip_min_width``. Adaptive paradigms apply this clamp;
    owns_strip ignores it (brutalist brand-panel grammar has its own minimum
    via brand_panel_width + cells + bookend_pad).
    """
    cell_widths = list(cell_widths or [])
    cell_layouts_records = list(cell_layouts_records or [])
    n_cells = len(cell_widths)

    # Bifamily flank handling: every coordinate downstream of identity shifts
    # right by flank_width when flanks render (automata strips reserve 36px
    # of pattern cells on each side).
    has_flanks = flank_width > 0
    seam_offset = flank_width if has_flanks else 0
    flank_total = 2 * flank_width if has_flanks else 0

    # ── Identity / glyph zone width ──
    # Adaptive paradigms: icon_box wraps glyph; bare glyph reserves left
    # padding + rendered glyph + post-glyph gap; no glyph collapses entirely.
    # Coordinates emitted here are already shifted past any bifamily left
    # flank so templates can render them verbatim.
    # Owns_strip: identity glyph is part of the brand-panel grammar; we don't
    # reserve a separate zone — the partial draws the ornament at its own
    # paradigm-defined coordinates.
    icon_box_x = 0.0
    icon_box_y = 0.0
    glyph_cx = 0.0
    glyph_cy = 0.0
    glyph_size_resolved = 0
    if owns_strip:
        glyph_zone_width = 0
    elif show_icon_box and has_identity_glyph:
        glyph_zone_width = icon_box_pad + icon_box_size + 8
        icon_box_x = float(seam_offset + accent_w + icon_box_pad)
        icon_box_y = float((height - icon_box_size) // 2)
        glyph_size_resolved = max(1, icon_box_size - 10)
        glyph_cx = icon_box_x + icon_box_size / 2.0
        glyph_cy = icon_box_y + icon_box_size / 2.0
    elif show_icon_box:
        glyph_zone_width = icon_box_pad
    elif has_identity_glyph:
        glyph_size_resolved = max(1, strip_glyph_size)
        glyph_zone_width = 12 + glyph_size_resolved + 9
        glyph_cx = seam_offset + accent_w + 12 + glyph_size_resolved / 2.0
        glyph_cy = height / 2.0
    else:
        glyph_zone_width = 0

    # ── Identity x + zone width + shrink-to-fit ──
    identity_text_length = 0.0
    # Owns_strip-only outputs (populated below for brutalist; 0 for adaptive).
    brand_panel_x_resolved = 0
    brand_panel_w_resolved = 0
    triple_divider_x_resolved = 0
    brand_divider_x_resolved = 0
    identity_x_for_template = 0.0
    if owns_strip:
        # Content-driven brand panel sizing. brand_panel_width
        # is a MAX ceiling — the panel shrinks to content when identity is short
        # (N8N, 3 chars), and shrink-to-fit triggers via textLength when content
        # would overflow the ceiling (SIGNIFICANT-GRAVITAS/AUTOGPT, 28 chars).
        # All downstream geometry (triple_divider_x, brand_divider_x, bookend_x)
        # follows the resolved panel right edge so cells march compactly.
        identity_x_resolved = identity_text_x
        identity_x_for_template = float(identity_x_resolved)
        identity_left_inset = identity_text_x - brand_panel_x  # gap inside panel before text
        triple_divider_total_w = 2 * triple_divider_bar_width + triple_divider_void_width
        # Minimum panel width: text starts at identity_text_x, needs at least
        # identity_panel_pad to right edge for any content. min_w guards against
        # collapsing the panel entirely on zero-content edge cases.
        min_panel_w = identity_left_inset + identity_panel_pad
        # Required panel width to fit measured content with right pad. Ceiling
        # so a measured width of 23.4 lands at integer 24 — without it, panel
        # truncation would clip content by < 1px and falsely trigger shrink.
        required_panel_w = math.ceil(identity_left_inset + identity_w + identity_panel_pad)
        # Content-driven panel: between min and brand_panel_width (the YAML max).
        effective_panel_w = max(min_panel_w, min(required_panel_w, brand_panel_width))
        effective_panel_right = brand_panel_x + effective_panel_w
        # Shrink-to-fit when content exceeds the clamped panel's available text width.
        # 0.5px tolerance absorbs measurement noise from font-metric LUT
        # rounding and browser text rendering.
        available_text_w = effective_panel_right - identity_text_x - identity_panel_pad
        if identity_w > available_text_w + 0.5 and available_text_w > 0:
            identity_text_length = float(available_text_w)
        # Downstream geometry follows the resolved panel right edge.
        brand_panel_x_resolved = brand_panel_x
        brand_panel_w_resolved = effective_panel_w
        triple_divider_x_resolved = effective_panel_right
        brand_divider_x_resolved = triple_divider_x_resolved + triple_divider_total_w
        identity_zone_width = float(effective_panel_w)
        first_divider_x = brand_divider_x_resolved
    else:
        # Adaptive: identity sits after the resolved glyph zone. Bare-glyph
        # zones already include the post-glyph gap; glyphless bare strips use
        # the legacy 14px identity inset after the accent rail.
        identity_x_resolved = accent_w + glyph_zone_width if show_icon_box or has_identity_glyph else accent_w + 14
        identity_x_for_template = identity_x_resolved + seam_offset
        identity_zone_width = max(identity_w, subtitle_w)
        first_divider_x = max(
            int(identity_x_resolved + identity_zone_width + identity_right_pad),
            first_divider_x_floor,
        )

    # ── Per-cell positions + seam cumulator ──
    # First seam at first_divider_x + seam_offset (shifted by flank when present).
    # Then one seam per cell trailing edge, cumulative widths.
    metric_pitch = max(cell_widths) if cell_widths else max(metric_pitch_fallback, 0)
    metrics_zone_width = sum(cell_widths) if cell_widths else (max(n_cells, 1) * metric_pitch)

    seams: list[float] = [float(first_divider_x + seam_offset)]
    cell_start = first_divider_x + cell_offset + seam_offset
    running = 0
    for cw in cell_widths:
        running += cw
        seams.append(float(cell_start + running))
    if not cell_widths:
        # Pad seam list for zero-metric strips (preserves legacy single-divider behavior).
        seams.append(float(cell_start + metric_pitch))

    # ── Status indicator zone ──
    if has_status_indicator:
        status_zone_width = status_indicator_pre_gap + status_indicator_size + status_indicator_post_gap
    else:
        status_zone_width = 0

    # ── Total width (additive layout) ──
    if owns_strip:
        # Dynamic bookend snaps to right edge of last cell + bookend_gap;
        # fallback to YAML constant for zero-cell strips. Uses the content-
        # driven brand_divider_x_resolved so short identities → tight strips
        # (N8N: bookend at ~120 not 520) and long identities → standard layout
        # (AUTOGPT: bookend follows the clamped 170 baseline).
        bookend_x = brand_divider_x_resolved + sum(cell_widths) + bookend_gap if cell_widths else bookend_x_fallback
        width = bookend_x + bookend_pad_right
    else:
        # Adaptive layout: identity + cells + status + flanks. The trailing
        # pad moves outside content_width as transparent SVG canvas instead
        # of visible dead space between the last cell and envelope edge.
        # Chrome uses that transparent pad when strip_min_width clamps the
        # canvas wider than natural; cellular paints cells to the full viewBox,
        # so gating on strip_min_width keeps cellular motion aligned with the
        # painted cell extent.
        natural_content_width = first_divider_x + cell_offset + metrics_zone_width + status_zone_width + flank_total
        adaptive_trailing_pad = bookend_gap if (strip_min_width > 0 and not has_status_indicator) else 0
        width = natural_content_width + adaptive_trailing_pad
        bookend_x = 0

    # content_width tracks where strip content visually ends. The adaptive
    # trailing pad sits outside content_width so chrome envelope/well/rim snap
    # to the last cell with no visible dead space inside the envelope. Strip-
    # min-width clamp extends SVG viewBox only; content remains at content_width.
    # owns_strip paradigms (brutalist) render their own bookend ornament —
    # content_width matches width. Adaptive paradigms separate content from
    # trailing transparent canvas via natural_content_width.
    content_width = width if owns_strip else natural_content_width
    if strip_min_width > 0 and width < strip_min_width:
        width = strip_min_width

    # Status indicator x: last_seam + pre_gap when stateful; 0 otherwise.
    if has_status_indicator:
        last_seam_x = seams[-1] if seams else float(first_divider_x)
        status_x = last_seam_x + status_indicator_pre_gap
    else:
        status_x = 0.0

    # Content right edge (= width minus flank on right side, when flanked).
    content_right = width - (flank_width if has_flanks else 0)

    # Glyph zone x-offset: when bifamily flanks present, glyph must be pushed
    # past the left flank so it doesn't overlap pattern cells.
    glyph_zone_x_offset = float(flank_width if has_flanks else 0)

    # First divider x shifted into flank-aware coordinate frame (matches what
    # templates consume — identity, dividers, cells all in the same frame).
    first_divider_x_shifted = first_divider_x + seam_offset

    return StripZones(
        width=width,
        height=height,
        glyph_zone_width=glyph_zone_width,
        glyph_zone_x_offset=glyph_zone_x_offset,
        icon_box_x=round(icon_box_x, 1),
        icon_box_y=round(icon_box_y, 1),
        glyph_cx=round(glyph_cx, 1),
        glyph_cy=round(glyph_cy, 1),
        glyph_size=glyph_size_resolved if has_identity_glyph else 0,
        identity_x=identity_x_for_template,
        identity_text_length=identity_text_length,
        identity_zone_width=identity_zone_width,
        subtitle_text=subtitle_text,
        first_divider_x=first_divider_x_shifted,
        cell_widths=cell_widths,
        cell_layouts_records=cell_layouts_records,
        seam_positions=seams,
        status_x=status_x,
        status_zone_width=status_zone_width,
        content_right=content_right,
        bookend_x=bookend_x,
        metric_pitch=metric_pitch,
        metrics_zone_width=metrics_zone_width,
        brand_panel_x=brand_panel_x_resolved,
        brand_panel_w=brand_panel_w_resolved,
        triple_divider_x=triple_divider_x_resolved,
        brand_divider_x=brand_divider_x_resolved,
        content_width=content_width,
    )


# ─────────────────────────────────────────────────────────────────────
# Three-mode state architecture
# ─────────────────────────────────────────────────────────────────────


def normalize_title(title: str | None) -> str:
    """Lowercase + strip hyphens/underscores so allowlist lookup is
    insensitive to common separator variants.

    ``BUILD-STATUS`` → ``buildstatus``; ``CI_CD`` → ``cicd``. URL slashes
    can't appear in path segments (they'd split into separate parts), so
    we don't need slash handling. Empty / None → empty string.
    """
    if not title:
        return ""
    return title.lower().replace("-", "").replace("_", "")


def resolve_badge_mode(spec: ComposeSpec, allowlist: frozenset[str]) -> BadgeMode:
    """Classify a badge as stateful / stateless / explicit.

    Three modes drive two orthogonal behaviors at render time:

    * Indicator rendering: ``show_indicator = mode != "stateless"``
    * Threshold-CSS auto-inference: gated by ``data-hw-statemode="auto"``
      on the SVG root, which fires only for ``stateful`` (auto-inferred
      from leading-digit value). ``stateless`` and ``explicit`` skip it.

    Title lookup normalizes via ``normalize_title`` (lowercase, strip
    hyphens/underscores) so ``BUILD-STATUS`` and ``BUILD_STATUS`` both
    match the canonical ``buildstatus`` allowlist entry without bloating
    the YAML with every separator variant.

    Note on ``spec.state == "active"``: ComposeSpec defaults ``state`` to
    the truthy sentinel ``"active"`` (Pydantic default in
    core/models.py:98), NOT empty string. Treat that sentinel as "user
    did not opine" — fall through to the allowlist check. Any other
    value (including ``"active"`` if explicitly re-set, which is fine)
    means the caller asked for a specific state → explicit mode.
    """
    if spec.state and spec.state != "active":
        return "explicit"
    title = normalize_title(spec.title)
    if title and title in allowlist:
        return "stateful"
    return "stateless"


def decide_strip_mode(
    metric_titles: Iterable[str | None],
    spec: ComposeSpec,
    allowlist: frozenset[str],
) -> BadgeMode:
    """Roll up the strip's mode from its metric cells' titles.

    Strip's right-edge indicator is the strip's overall health pixel.
    If ANY metric is stateful, the indicator renders with rolled-up
    state. Stateless cells coexist; per-cell indicators were already
    rejected (memory: ``feedback_strip_single_diamond.md``).

    Metric titles are normalized via ``normalize_title`` for the same
    reasons as ``resolve_badge_mode`` — ``BUILD-STATUS`` cell matches
    the same canonical ``buildstatus`` allowlist entry.
    """
    if spec.state and spec.state != "active":
        return "explicit"
    for title in metric_titles:
        if title and normalize_title(title) in allowlist:
            return "stateful"
    return "stateless"


def data_hw_statemode_for(mode: BadgeMode) -> str:
    """Map ``BadgeMode`` to the SVG-root ``data-hw-statemode`` attribute value.

    The CSS in ``data/css/expression.css`` qualifies its threshold
    selectors with ``[data-hw-statemode="auto"]`` so auto-inference
    only applies to ``stateful``. ``stateless`` ("off") and ``explicit``
    ("explicit") bypass auto-tinting; explicit-mode badges still get
    state colors via the ``[data-hw-status="..."]`` cascade.
    """
    return {"stateful": "auto", "explicit": "explicit", "stateless": "off"}[mode]
