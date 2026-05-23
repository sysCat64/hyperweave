"""Stats-card spatial layout.

The stats resolver prepares semantic data; this module freezes every repeated
coordinate list that stats templates consume. Templates should iterate these
records directly instead of deriving positions with Jinja arithmetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from hyperweave.compose.spatial_records import LineSpec, RectSpec, TextSpec
from hyperweave.core.text import measure_text, measure_text_ink_width

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from hyperweave.core.paradigm import ParadigmStatsConfig


MIN_IDENTITY_BIO_VISIBLE_GAP = 8.0
"""Minimum visible gap between header identity ink and bio text."""


@dataclass(frozen=True, slots=True)
class MetricSlot:
    """Resolved metric value/label placement."""

    value_x: float
    label_x: float
    value_y: float
    label_y: float
    css_value: str
    value_display: str
    label_text: str
    text_anchor: str = "start"
    value_text_length: float = 0.0


@dataclass(frozen=True, slots=True)
class ActivityBar:
    """Resolved weekly activity bar rectangle."""

    x: float
    y: float
    w: float
    h: float
    opacity: float


@dataclass(frozen=True, slots=True)
class LanguageSegment:
    """Resolved proportional language band segment."""

    x: float
    y: float
    w: float
    h: float
    opacity: float
    label_x: float
    label_y: float
    label_text: str
    show_label: bool


@dataclass(frozen=True, slots=True)
class InlineLanguageEntry:
    """Resolved cellular inline language legend entry."""

    swatch_x: float
    swatch_y: float
    swatch_w: float
    swatch_h: float
    swatch_rx: float
    swatch_color: str
    label_x: float
    label_y: float
    label_text: str


@dataclass(frozen=True, slots=True)
class HeatmapCell:
    """Resolved cellular contribution heatmap cell."""

    x: float
    y: float
    w: float
    h: float
    rx: float
    fill: str
    css_class: str


@dataclass(frozen=True, slots=True)
class LegendCell:
    """Resolved heatmap legend cell."""

    x: float
    y: float
    w: float
    h: float
    rx: float
    fill: str


@dataclass(frozen=True, slots=True)
class StatsLayout:
    """Frozen stats-card layout consumed by resolver context."""

    width: int
    height: int
    identity_x: int
    bio_x: int
    identity_text_length: float
    bio_text_length: float
    metric_slots: list[MetricSlot]
    metric_divider_xs: list[float]
    activity_bars: list[ActivityBar]
    language_segments: list[LanguageSegment]
    inline_language_entries: list[InlineLanguageEntry]
    heatmap_cells: list[HeatmapCell]
    heatmap_legend_cells: list[LegendCell]
    commits_text_length: float
    prs_text_length: float
    issues_text_length: float
    streak_text_length: float
    activity_baseline_y: float
    activity_present_x: float
    activity_present_y: float
    right_zone_w: float
    dark_perimeter: RectSpec
    light_perimeter: RectSpec
    light_bottom_strip_y: float
    chrome_outer_rect: RectSpec
    chrome_well_rect: RectSpec
    chrome_rail_rect: RectSpec
    chrome_top_highlight_rect: RectSpec
    cellular_outer_rect: RectSpec
    full_rect: RectSpec
    rects: dict[str, RectSpec]
    lines: dict[str, LineSpec]
    texts: dict[str, TextSpec]
    grain_right_rect: RectSpec
    header_right_rect: RectSpec
    language_shell_rect: RectSpec
    chrome_hero_rule: LineSpec
    chrome_activity_baseline: LineSpec
    chrome_footer_rule: LineSpec


def _float_value(value: object, default: float = 0.0) -> float:
    if not isinstance(value, int | float | str | bytes | bytearray):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: object, default: int = 0) -> int:
    if not isinstance(value, int | float | str | bytes | bytearray):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_value(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _count_value(entry: Mapping[str, object]) -> int:
    return _int_value(entry.get("count"), 0)


def _pct_value(entry: Mapping[str, object]) -> float:
    return _float_value(entry.get("pct"), 0.0)


def _language_name(entry: Mapping[str, object]) -> str:
    return _string_value(entry.get("name"), "")


def compute_identity_layout(
    *,
    username: str,
    bio_text: str,
    stats: ParadigmStatsConfig,
    card_width: int,
) -> tuple[int, int, float, float]:
    """Compute identity/bio x positions and shrink-to-fit lengths."""
    identity_measure_text = username.upper() if stats.identity_text_transform == "uppercase" else username
    identity_natural = measure_text(
        identity_measure_text,
        font_family=stats.identity_font_family,
        font_size=stats.identity_font_size,
        font_weight=stats.identity_font_weight,
        letter_spacing_em=stats.identity_letter_spacing_em,
    )
    identity_zone_w = max(0, stats.bio_x - stats.identity_x - stats.identity_padding)
    identity_text_length = float(identity_zone_w) if identity_zone_w > 0 and identity_natural > identity_zone_w else 0.0

    identity_ink_w = measure_text_ink_width(
        identity_measure_text,
        font_family=stats.identity_font_family,
        font_size=stats.identity_font_size,
        font_weight=stats.identity_font_weight,
        letter_spacing_em=stats.identity_letter_spacing_em,
    )
    rendered_ink_w = float(identity_zone_w) if identity_text_length else identity_ink_w
    breathing_margin = max(float(stats.identity_breathing_margin), MIN_IDENTITY_BIO_VISIBLE_GAP)
    adaptive_bio_x = stats.identity_x + rendered_ink_w + breathing_margin
    bio_x = math.ceil(min(adaptive_bio_x, stats.bio_x)) if stats.bio_x > 0 else math.ceil(adaptive_bio_x)

    bio_text_length = 0.0
    if stats.bio_collision_clamp and bio_text:
        branding_w = measure_text(
            "HYPERWEAVE",
            font_family="JetBrains Mono",
            font_size=6.5,
            font_weight=700,
            letter_spacing_em=0.14,
        )
        branding_left = card_width - 20 - branding_w
        bio_max_width = branding_left - bio_x - 10
        bio_natural = measure_text(
            bio_text,
            font_family="JetBrains Mono",
            font_size=8.5,
            font_weight=400,
            letter_spacing_em=0.03,
        )
        if bio_max_width > 0 and bio_natural > bio_max_width:
            bio_text_length = round(bio_max_width, 1)

    return stats.identity_x, bio_x, identity_text_length, bio_text_length


def _build_chrome_slots(
    displays: Mapping[str, str],
    stats: ParadigmStatsConfig,
) -> tuple[list[MetricSlot], dict[str, float]]:
    centers = (62.0, 186.0, 309.0, 433.0)
    labels = (("commits", "COMMITS"), ("prs", "PRS"), ("issues", "ISSUES"), ("streak", "STREAK"))
    slots: list[MetricSlot] = []
    lengths: dict[str, float] = {}
    for center, (key, label) in zip(centers, labels, strict=True):
        display = displays[key]
        natural = measure_text(
            display,
            font_family=stats.metric_value_font_family,
            font_size=stats.metric_value_font_size,
            font_weight=stats.metric_value_font_weight,
            letter_spacing_em=stats.metric_value_letter_spacing_em,
        )
        text_length = float(stats.metric_value_budget) if natural > stats.metric_value_budget else 0.0
        lengths[f"{key}_text_length"] = text_length
        slots.append(
            MetricSlot(
                value_x=center,
                label_x=center,
                value_y=158.0,
                label_y=135.0,
                css_value="mval",
                value_display=display,
                label_text=label,
                text_anchor="middle",
                value_text_length=text_length,
            )
        )
    return slots, lengths


def _build_brutalist_slots(displays: Mapping[str, str]) -> list[MetricSlot]:
    return [
        MetricSlot(238.0, 24.0, 154.0, 154.0, "sv", displays["commits"], "COMMITS", "end"),
        MetricSlot(238.0, 24.0, 190.0, 190.0, "sv", displays["prs"], "PRS", "end"),
        MetricSlot(480.0, 270.0, 154.0, 154.0, "sv", displays["issues"], "ISSUES", "end"),
        MetricSlot(480.0, 270.0, 190.0, 190.0, "sv", displays["streak"], "STREAK", "end"),
    ]


def _measure_cellular_label(label_text: str, stats: ParadigmStatsConfig) -> float:
    return measure_text(
        label_text,
        font_family=stats.metric_label_font_family,
        font_size=stats.metric_label_font_size,
        font_weight=stats.metric_label_font_weight,
        letter_spacing_em=stats.metric_label_letter_spacing_em,
    )


def _build_cellular_slots(
    displays: Mapping[str, str],
    stats: ParadigmStatsConfig,
    card_width: int,
) -> list[MetricSlot]:
    left_metrics: tuple[tuple[str, float, int, float, str, str], ...] = (
        ("mvh", 26.0, 700, -0.02, displays["stars"], "STARS"),
        ("mvm", 20.0, 700, -0.02, displays["commits"], "COMMITS"),
        ("mvs", 15.0, 600, 0.0, displays["prs"], "PRS"),
        ("mvs", 15.0, 600, 0.0, displays["contrib"], "CONTRIB"),
    )
    streak_slot = ("mvg", 15.0, 600, 0.0, displays["streak"], "STREAK")

    slots: list[MetricSlot] = []
    cursor = round(float(stats.cellular_metric_left_x), 3)
    for css_value, val_size, val_weight, val_ls, value_display, label_text in left_metrics:
        value_w = measure_text(
            value_display,
            font_family=stats.cellular_metric_value_font_family,
            font_size=val_size,
            font_weight=val_weight,
            letter_spacing_em=val_ls,
        )
        label_w = _measure_cellular_label(label_text, stats)
        value_x = round(cursor, 3)
        label_x = round(cursor + value_w + stats.cellular_metric_value_label_gap, 3)
        slots.append(
            MetricSlot(
                value_x,
                label_x,
                stats.cellular_metric_y,
                stats.cellular_metric_y,
                css_value,
                value_display,
                label_text,
            )
        )
        cursor = round(label_x + label_w + stats.cellular_metric_inter_slot_gap, 3)

    css_value, val_size, val_weight, val_ls, value_display, label_text = streak_slot
    value_w = measure_text(
        value_display,
        font_family=stats.cellular_metric_value_font_family,
        font_size=val_size,
        font_weight=val_weight,
        letter_spacing_em=val_ls,
    )
    label_w = _measure_cellular_label(label_text, stats)
    slot_w = value_w + stats.cellular_metric_value_label_gap + label_w
    value_x = round(card_width - stats.cellular_metric_right_margin - slot_w, 3)
    label_x = round(value_x + value_w + stats.cellular_metric_value_label_gap, 3)
    slots.append(
        MetricSlot(
            value_x,
            label_x,
            stats.cellular_metric_y,
            stats.cellular_metric_y,
            css_value,
            value_display,
            label_text,
        )
    )
    return slots


def _build_activity_bars(
    activity_bars: Sequence[Mapping[str, object]],
    *,
    activity_peak: int,
    stats: ParadigmStatsConfig,
    substrate_kind: str,
) -> list[ActivityBar]:
    peak = activity_peak if activity_peak > 0 else 1
    if substrate_kind == "light":
        op_min = stats.activity_bar_opacity_min_light
        op_max = stats.activity_bar_opacity_max_light
    else:
        op_min = stats.activity_bar_opacity_min
        op_max = stats.activity_bar_opacity_max
    out: list[ActivityBar] = []
    for idx, bar in enumerate(activity_bars):
        count = _count_value(bar)
        if count <= 0:
            height = stats.activity_bar_min_h
            opacity = op_min
        else:
            ratio = math.sqrt(count / peak)
            height = max(stats.activity_bar_min_h, float(int(ratio * stats.activity_bar_max_h)))
            opacity = op_min + (ratio * (op_max - op_min))
        x = stats.activity_bar_start_x + idx * stats.activity_bar_stride
        y = stats.activity_bar_baseline_y - height
        out.append(ActivityBar(round(x, 3), round(y, 3), stats.activity_bar_w, round(height, 3), round(opacity, 2)))
    return out


def _build_language_segments(
    languages: Sequence[Mapping[str, object]],
    *,
    card_width: int,
    stats: ParadigmStatsConfig,
    substrate_kind: str,
) -> list[LanguageSegment]:
    opacities = (
        stats.language_segment_opacities_light if substrate_kind == "light" else stats.language_segment_opacities
    )
    label_y = stats.language_label_y_light if substrate_kind == "light" else stats.language_label_y_dark
    cursor = stats.language_zone_x
    total_w = card_width - stats.language_zone_x
    out: list[LanguageSegment] = []
    for idx, lang in enumerate(languages):
        pct = max(0.0, min(100.0, _pct_value(lang)))
        width = int((pct / 100.0) * total_w)
        opacity = opacities[idx] if idx < len(opacities) else opacities[-1]
        name = _language_name(lang).upper()
        label = f"{name} · {math.floor(pct)}%"
        out.append(
            LanguageSegment(
                x=round(cursor, 3),
                y=stats.language_zone_y,
                w=float(width),
                h=stats.language_zone_h,
                opacity=opacity,
                label_x=round(cursor + stats.language_label_offset_x, 3),
                label_y=label_y,
                label_text=label,
                show_label=idx < 2,
            )
        )
        cursor += width
    return out


def _build_inline_languages(
    languages: Sequence[Mapping[str, object]],
    *,
    card_width: int,
    stats: ParadigmStatsConfig,
    area_tiers: Sequence[str],
) -> list[InlineLanguageEntry]:
    if len(area_tiers) < 5:
        return []
    swatch_cycle = [area_tiers[2], area_tiers[0], area_tiers[1], area_tiers[3], area_tiers[4]]
    x = stats.inline_language_zone_left
    zone_right = card_width - stats.inline_language_zone_right_margin
    out: list[InlineLanguageEntry] = []
    for idx, lang in enumerate(languages[:4]):
        name = _language_name(lang)
        pct = int(_pct_value(lang))
        label = f"{name} {pct}%"
        label_w = measure_text(label, font_family="JetBrains Mono", font_size=7)
        entry_w = stats.inline_language_swatch_w + stats.inline_language_swatch_text_gap + label_w
        if x + entry_w > zone_right:
            break
        out.append(
            InlineLanguageEntry(
                swatch_x=round(x, 3),
                swatch_y=stats.inline_language_swatch_y,
                swatch_w=stats.inline_language_swatch_w,
                swatch_h=stats.inline_language_swatch_h,
                swatch_rx=stats.inline_language_swatch_rx,
                swatch_color=swatch_cycle[idx % len(swatch_cycle)],
                label_x=round(x + stats.inline_language_swatch_w + stats.inline_language_swatch_text_gap, 3),
                label_y=stats.inline_language_label_y,
                label_text=label,
            )
        )
        x += entry_w + stats.inline_language_entry_gap
    return out


def _build_heatmap_cells(
    heatmap_grid: Sequence[Mapping[str, object]],
    *,
    stats: ParadigmStatsConfig,
    area_tiers: Sequence[str],
) -> list[HeatmapCell]:
    if not area_tiers or stats.heatmap_rows <= 0 or stats.heatmap_cols <= 0 or stats.heatmap_cell_size <= 0:
        return []
    grid_len = len(heatmap_grid)
    window_cells = stats.heatmap_cols * stats.heatmap_rows
    offset = grid_len - window_cells if grid_len > window_cells else 0
    anim_classes = ("b1", "b2", "b3", "b4")
    stride = stats.heatmap_cell_size + stats.heatmap_cell_gap
    out: list[HeatmapCell] = []
    for col in range(stats.heatmap_cols):
        for row in range(stats.heatmap_rows):
            idx = offset + col * stats.heatmap_rows + row
            level = _int_value(heatmap_grid[idx].get("level"), 0) if 0 <= idx < grid_len else 0
            level = max(0, min(4, level))
            fill = area_tiers[4 - level] if len(area_tiers) > 4 - level else area_tiers[-1]
            css_class = anim_classes[(col + row) % len(anim_classes)] if level >= 1 else ""
            out.append(
                HeatmapCell(
                    x=round(stats.heatmap_x0 + col * stride, 3),
                    y=round(stats.heatmap_y0 + row * stride, 3),
                    w=stats.heatmap_cell_size,
                    h=stats.heatmap_cell_size,
                    rx=stats.heatmap_cell_rx,
                    fill=fill,
                    css_class=css_class,
                )
            )
    return out


def _build_legend_cells(stats: ParadigmStatsConfig, area_tiers: Sequence[str]) -> list[LegendCell]:
    if len(area_tiers) < 5:
        return []
    return [
        LegendCell(
            x=x,
            y=stats.heatmap_legend_y,
            w=stats.heatmap_legend_size,
            h=stats.heatmap_legend_size,
            rx=stats.heatmap_legend_rx,
            fill=area_tiers[4 - idx],
        )
        for idx, x in enumerate(stats.heatmap_legend_xs[:5])
    ]


def _slot_layout(
    *,
    displays: Mapping[str, str],
    stats: ParadigmStatsConfig,
    card_width: int,
) -> tuple[list[MetricSlot], dict[str, float]]:
    if stats.metric_layout_mode == "chrome_columns":
        return _build_chrome_slots(displays, stats)
    if stats.metric_layout_mode == "cellular_inline":
        return _build_cellular_slots(displays, stats, card_width), {}
    return _build_brutalist_slots(displays), {}


def compute_stats_layout(
    *,
    stats: ParadigmStatsConfig,
    card_width: int,
    card_height: int,
    username: str,
    bio_text: str,
    displays: Mapping[str, str],
    activity_bars: Sequence[Mapping[str, object]],
    activity_peak: int,
    languages: Sequence[Mapping[str, object]],
    heatmap_grid: Sequence[Mapping[str, object]],
    area_tiers: Sequence[str],
    substrate_kind: Literal["dark", "light"] | str = "dark",
) -> StatsLayout:
    """Compute all resolver-owned stats geometry for the active paradigm."""
    is_light = substrate_kind == "light"
    identity_x, bio_x, identity_text_length, bio_text_length = compute_identity_layout(
        username=username,
        bio_text=bio_text,
        stats=stats,
        card_width=card_width,
    )
    metric_slots, text_lengths = _slot_layout(displays=displays, stats=stats, card_width=card_width)
    activity = _build_activity_bars(
        activity_bars,
        activity_peak=activity_peak,
        stats=stats,
        substrate_kind=substrate_kind,
    )
    full_rect = RectSpec(0.0, 0.0, float(card_width), float(card_height))
    dark_perimeter = RectSpec(0.75, 0.75, card_width - 1.5, card_height - 1.5)
    light_perimeter = RectSpec(0.5, 0.5, card_width - 1.0, card_height - 1.0)
    light_bottom_strip_y = card_height - 2.0
    right_zone_w = card_width - 6.0
    grain_right_rect = RectSpec(6.0, 0.0, right_zone_w, float(card_height))
    header_right_rect = RectSpec(6.0, 0.0, right_zone_w, 32.0)
    language_shell_rect = RectSpec(6.0, stats.language_zone_y, right_zone_w, stats.language_zone_h)
    chrome_outer_rect = RectSpec(2.0, 2.0, card_width - 4.0, card_height - 4.0, 4.5)
    chrome_well_rect = RectSpec(4.0, 4.0, card_width - 8.0, card_height - 8.0, 3.0)
    chrome_rail_rect = RectSpec(4.0, 4.0, 6.0, card_height - 8.0)
    chrome_top_highlight_rect = RectSpec(40.0, 4.0, card_width - 80.0, 0.6, 0.3)
    cellular_outer_rect = RectSpec(0.5, 0.5, card_width - 1.0, card_height - 1.0, 8.0)
    hero_label_y = 54.0 if is_light else 52.0
    hero_value_y = 116.0 if is_light else 114.0
    chrome_hero_rule = LineSpec(22.0, 120.0, card_width - 22.0, 120.0)
    chrome_activity_baseline = LineSpec(22.0, 222.4, card_width - 22.0, 222.4)
    chrome_footer_rule = LineSpec(22.0, 232.0, card_width - 22.0, 232.0)
    rects = {
        "left_rail": RectSpec(0.0, 0.0, 6.0, float(card_height)),
        "brutalist_glyph": RectSpec(24.0, 11.0, 14.0, 14.0),
        "brutalist_status_dot": RectSpec(card_width - 23.0, 12.0, 8.0, 8.0),
        "light_top_strip": RectSpec(6.0, 0.0, right_zone_w, 2.0),
        "light_bottom_strip": RectSpec(6.0, light_bottom_strip_y, right_zone_w, 2.0),
        "light_header_panel": RectSpec(6.0, 2.0, right_zone_w, 30.0),
        "light_header_seam": RectSpec(6.0, 30.0, right_zone_w, 2.0),
        "chrome_glyph": RectSpec(22.0, 22.0, 14.0, 14.0),
        "chrome_horizon": RectSpec(22.0, 167.0, card_width - 44.0, 2.0),
        "chrome_status_anchor": RectSpec(30.0, 249.0, 0.0, 0.0),
        "chrome_status_diamond": RectSpec(-3.2, -3.2, 6.4, 6.4, 0.6),
        "chrome_present": RectSpec(-1.0, 0.0, 2.0, 4.0, 0.6),
        "chrome_clip": RectSpec(0.0, 0.0, float(card_width), float(card_height), 6.0),
        "cellular_clip": RectSpec(0.0, 0.0, float(card_width), float(card_height), cellular_outer_rect.rx),
        "cellular_header_band": RectSpec(0.0, 0.0, float(card_width), float(stats.header_band_height)),
    }
    lines = {
        "header_rule": LineSpec(6.0, 32.0, float(card_width), 32.0),
        "hero_rule": LineSpec(6.0, 128.0, float(card_width), 128.0),
        "metric_vertical": LineSpec(250.0, 128.0, 250.0, 200.0),
        "metric_row": LineSpec(6.0, 164.0, float(card_width), 164.0),
        "activity_top": LineSpec(6.0, 200.0, float(card_width), 200.0),
        "activity_baseline": LineSpec(
            22.0,
            stats.activity_bar_baseline_y,
            card_width - 4.0,
            stats.activity_bar_baseline_y,
        ),
        "language_top": LineSpec(6.0, stats.language_zone_y, float(card_width), stats.language_zone_y),
        "language_footer": LineSpec(
            6.0,
            stats.language_zone_y + stats.language_zone_h,
            float(card_width),
            stats.language_zone_y + stats.language_zone_h,
        ),
        "chrome_metric_divider_span": LineSpec(0.0, 128.0, 0.0, 162.0),
        "chrome_hero_rule": chrome_hero_rule,
        "chrome_activity_baseline": chrome_activity_baseline,
        "chrome_footer_rule": chrome_footer_rule,
        "cellular_header_rule": LineSpec(
            0.0,
            float(stats.header_band_height),
            float(card_width),
            float(stats.header_band_height),
        ),
    }
    texts = {
        "identity": TextSpec(float(identity_x), 22.0),
        "bio": TextSpec(float(bio_x), 22.0),
        "hero_label": TextSpec(24.0, hero_label_y),
        "hero_delta": TextSpec(card_width - 17.0, hero_label_y, "end"),
        "hero_value": TextSpec(22.0, hero_value_y),
        "activity_label": TextSpec(24.0, 214.0),
        "activity_peak": TextSpec(card_width - 17.0, 214.0, "end"),
        "language_empty": TextSpec(14.0, stats.language_label_y_light if is_light else stats.language_label_y_dark),
        "footer_url": TextSpec(14.0, card_height - 5.0),
        "footer_brand": TextSpec(card_width - 17.0, card_height - 5.0, "end"),
        "chrome_identity": TextSpec(42.0, 33.0),
        "chrome_hero_value": TextSpec(24.0, 98.0),
        "chrome_hero_label": TextSpec(26.0, 114.0),
        "chrome_activity_label": TextSpec(22.0, 181.0),
        "chrome_activity_peak": TextSpec(card_width - 22.0, 181.0, "end"),
        "chrome_footer_url": TextSpec(44.0, 252.0),
        "chrome_footer_brand": TextSpec(card_width - 22.0, 252.0, "end"),
        "cellular_identity": TextSpec(float(identity_x), 24.0),
        "cellular_bio": TextSpec(float(bio_x), 24.0),
        "cellular_brand": TextSpec(card_width - 20.0, 221.0, "end"),
        "cellular_year": TextSpec(20.0, 106.6),
    }
    return StatsLayout(
        width=card_width,
        height=card_height,
        identity_x=identity_x,
        bio_x=bio_x,
        identity_text_length=identity_text_length,
        bio_text_length=bio_text_length,
        metric_slots=metric_slots,
        metric_divider_xs=[124.0, 248.0, 371.0] if stats.metric_layout_mode == "chrome_columns" else [],
        activity_bars=activity,
        language_segments=_build_language_segments(
            languages,
            card_width=card_width,
            stats=stats,
            substrate_kind=substrate_kind,
        ),
        inline_language_entries=_build_inline_languages(
            languages,
            card_width=card_width,
            stats=stats,
            area_tiers=area_tiers,
        ),
        heatmap_cells=_build_heatmap_cells(heatmap_grid, stats=stats, area_tiers=area_tiers),
        heatmap_legend_cells=_build_legend_cells(stats, area_tiers),
        commits_text_length=text_lengths.get("commits_text_length", 0.0),
        prs_text_length=text_lengths.get("prs_text_length", 0.0),
        issues_text_length=text_lengths.get("issues_text_length", 0.0),
        streak_text_length=text_lengths.get("streak_text_length", 0.0),
        activity_baseline_y=stats.activity_bar_baseline_y,
        activity_present_x=round(stats.activity_bar_start_x + len(activity_bars) * stats.activity_bar_stride, 3),
        activity_present_y=round(stats.activity_bar_baseline_y - stats.activity_bar_min_h, 3),
        right_zone_w=right_zone_w,
        dark_perimeter=dark_perimeter,
        light_perimeter=light_perimeter,
        light_bottom_strip_y=light_bottom_strip_y,
        chrome_outer_rect=chrome_outer_rect,
        chrome_well_rect=chrome_well_rect,
        chrome_rail_rect=chrome_rail_rect,
        chrome_top_highlight_rect=chrome_top_highlight_rect,
        cellular_outer_rect=cellular_outer_rect,
        full_rect=full_rect,
        rects=rects,
        lines=lines,
        texts=texts,
        grain_right_rect=grain_right_rect,
        header_right_rect=header_right_rect,
        language_shell_rect=language_shell_rect,
        chrome_hero_rule=chrome_hero_rule,
        chrome_activity_baseline=chrome_activity_baseline,
        chrome_footer_rule=chrome_footer_rule,
    )
