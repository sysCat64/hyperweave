"""Stats card frame resolver — GitHub profile summary.

Consumes ``spec.connector_data`` (produced by ``fetch_user_stats``) and
routes the rendering context to one of the declared stats paradigms:

    brutalist  → brutalist hero-left layout (emerald mockups)
    chrome     → chrome material stack layout

For the ``chrome`` paradigm the resolver also calls the shared chart engine
to produce an embedded compact chart fragment (star history strip) that the
template drops into its bottom zone. This is the mechanism that makes the
stats card a COMPOSITION of stats + chart, not two separate artifacts.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any

from hyperweave.render.chart_engine import Viewport, build_chart_svg

if TYPE_CHECKING:
    from hyperweave.core.models import ComposeSpec


_STATS_WIDTH = 495


def _format_count(n: int | None) -> str:
    """Compact integer formatting with K/M/B cascade.

    0..9,999       → '2,850'   (comma-grouped)
    10K..999,999   → '12.8K'
    1M..999M       → '45.3M'
    1B+            → '2.1B'

    ``None`` is the staleness sentinel: it renders as ``"—"`` (em dash) so
    a failed sub-fetch surfaces visibly instead of being misrepresented as
    a real zero.
    """
    if n is None:
        return "—"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    if n <= 0:
        return "0"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    if n >= 10_000:
        return f"{n / 1_000:.1f}K".rstrip("0").rstrip(".")
    return f"{n:,}"


def _build_activity_bars(heatmap_grid: list[dict[str, Any]]) -> list[dict[str, int]]:
    """Aggregate daily heatmap cells into 52 weekly totals.

    Returns a list of ``{"week": 0..51, "count": N}`` entries.
    """
    if not heatmap_grid:
        return []
    # Group by week (every 7 consecutive days).
    weeks: list[dict[str, int]] = []
    for i in range(0, len(heatmap_grid), 7):
        chunk = heatmap_grid[i : i + 7]
        total = sum(int(c.get("count", 0) or 0) for c in chunk)
        weeks.append({"week": len(weeks), "count": total})
    return weeks[:52]  # cap at 52 weeks


def _placeholder_languages() -> list[dict[str, Any]]:
    return [
        {"name": "Python", "pct": 62.0, "count": 31},
        {"name": "TypeScript", "pct": 22.0, "count": 11},
        {"name": "Rust", "pct": 16.0, "count": 8},
    ]


def resolve_stats(
    spec: ComposeSpec,
    genome: dict[str, Any],
    profile: dict[str, Any],
    paradigm_spec: Any = None,
    **_kw: Any,
) -> dict[str, Any]:
    """Build the stats card context for the chosen paradigm."""
    connector = spec.connector_data or {}
    # ``_stale_fields`` is populated by ``fetch_user_stats`` when sub-fetches
    # fail (rate limits, breaker open, network errors). Stale fields render
    # as ``—`` rather than misrepresenting failure as a real ``0`` — the bug
    # that produced v0.2.10's silent COMMITS=0/PRS=0 readings under search-
    # API quota exhaustion. Empty list / missing key → fully live data.
    stale_fields: set[str] = set(connector.get("_stale_fields") or ())
    stale = not bool(connector) or bool(stale_fields)

    def _value_or_none(field: str) -> Any:
        """Pass through ``None`` for stale fields, raw value otherwise.

        ``_format_count(None)`` already returns ``"—"``, so this is the only
        change needed at the formatting layer to surface staleness visually.
        """
        if field in stale_fields:
            return None
        return connector.get(field)

    stars_total = _value_or_none("stars_total")
    commits_total = _value_or_none("commits_total")
    prs_total = _value_or_none("prs_total")
    issues_total = _value_or_none("issues_total")
    contrib_total = _value_or_none("contrib_total")
    streak_days = _value_or_none("streak_days")

    languages_raw = connector.get("language_breakdown") or _placeholder_languages()
    heatmap_grid = connector.get("heatmap_grid") or []
    username = connector.get("username") or spec.stats_username or "anonymous"
    bio = connector.get("bio") or ""
    top_language = connector.get("top_language") or ""
    repo_count_raw = _value_or_none("repo_count")
    repo_count = repo_count_raw if isinstance(repo_count_raw, int) else 0

    # Aggregate 365 daily cells into 52 weekly totals for the activity bar chart.
    activity_bars = _build_activity_bars(heatmap_grid)
    activity_peak = max((b["count"] for b in activity_bars), default=0)

    # Heatmap year label — cellular "CONTRIBUTIONS YYYY" caption. Prefer the
    # tail of the heatmap_grid (most recent cell date) so the label stays
    # truthful when the connector returns a back-dated series. Falls back
    # to current calendar year when the grid is empty or unparseable.
    import contextlib
    from datetime import datetime

    heatmap_year = datetime.now(UTC).year
    if heatmap_grid:
        tail = heatmap_grid[-1]
        if isinstance(tail, dict):
            tail_date = tail.get("date")
            if isinstance(tail_date, str) and len(tail_date) >= 4:
                with contextlib.suppress(ValueError):
                    heatmap_year = int(tail_date[:4])

    # Streak rendering: ``"47d"`` for live, ``"—"`` for stale. Don't coerce
    # ``None`` to ``0`` — that's the silent-zero anti-pattern this whole
    # change exists to eliminate.
    streak_display = "—" if streak_days is None else f"{int(streak_days)}d"

    # Cellular v0.3.0 refresh: surface paradigm constants (genome-independent)
    # and per-tone accent stops. Constants flow as named template variables
    # so the variant-blind hex gate stays effective and overrides apply via
    # paradigm config rather than hex spelunking. Cellular palette (info_accent
    # / mid_accent / header_band) injected by the dispatcher via _kw.
    cellular_palette: dict[str, Any] = _kw.get("cellular_palette") or {}
    primary_tone: dict[str, Any] = cellular_palette.get("primary") or {}
    stats_info_accent = primary_tone.get("info_accent", "")
    stats_mid_accent = primary_tone.get("mid_accent", "")
    stats_header_band = primary_tone.get("header_band", "")

    if paradigm_spec is not None:
        ps = paradigm_spec.stats
        streak_green = ps.streak_green
        mid_gray = ps.mid_gray
        hero_white = ps.hero_white
        header_band_height = int(ps.header_band_height)
        heatmap_rows = int(ps.heatmap_rows) if ps.heatmap_rows else 0
        heatmap_cols = int(ps.heatmap_cols) if ps.heatmap_cols else 0
        heatmap_cell_size = float(ps.heatmap_cell_size) if ps.heatmap_cell_size else 0.0
        heatmap_cell_gap = float(ps.heatmap_cell_gap) if ps.heatmap_cell_gap else 0.0
        heatmap_zone_height = float(ps.heatmap_zone_height) if ps.heatmap_zone_height else 0.0
        card_width_for_layout = ps.card_width if ps.card_width > 0 else _STATS_WIDTH
    else:
        streak_green = ""
        mid_gray = ""
        hero_white = ""
        header_band_height = 0
        heatmap_rows = 0
        heatmap_cols = 0
        heatmap_cell_size = 0.0
        heatmap_cell_gap = 0.0
        heatmap_zone_height = 0.0
        card_width_for_layout = _STATS_WIDTH

    # Language footer layout — v0.3.0 redesign replaces the proportional bar
    # with inline swatch+label pairs walked left-to-right. Each entry is sized
    # by measure_text against JBM 7px (the .lt class) and dropped from the end
    # if it would overflow the zone's right edge. Languages are pre-sorted by
    # descending pct, so dropping from the end drops the lowest-percentage
    # language first — exactly what the user wants when the footer can't fit
    # all four. No alias dictionaries, no truncation, no abbreviation: full
    # canonical names exactly as the GitHub API returns them, with explicit
    # % suffix on every percentage.
    from hyperweave.core.text import measure_text as _measure_text

    language_layout: list[dict[str, Any]] = []
    if primary_tone:
        _area_tiers_palette = primary_tone.get("area_tiers", [])
        # Swatch palette mirrors the prior bar segment color cycle so the
        # chromatic identity carries through the redesign unchanged.
        if len(_area_tiers_palette) >= 5:
            _swatch_cycle = [
                _area_tiers_palette[2],
                _area_tiers_palette[0],
                _area_tiers_palette[1],
                _area_tiers_palette[3],
                _area_tiers_palette[4],
            ]
            _swatch_w = 5.0
            _swatch_text_gap = 4.0  # gap between swatch and label text
            _entry_gap = 24.0  # gap between adjacent entries
            _zone_left = 20.0
            _zone_right = float(card_width_for_layout) - 20.0  # symmetric margins
            _x = _zone_left
            for _idx, _lang in enumerate(languages_raw[:4]):
                _name = str(_lang.get("name", ""))
                _pct = int(_lang.get("pct", 0) or 0)
                _label = f"{_name} {_pct}%"
                _label_w = _measure_text(_label, font_family="JetBrains Mono", font_size=7)
                _entry_w = _swatch_w + _swatch_text_gap + _label_w
                if _x + _entry_w > _zone_right:
                    break  # overflow — drop this and remaining (lower-pct) entries
                language_layout.append(
                    {
                        "swatch_x": round(_x, 2),
                        "swatch_color": _swatch_cycle[_idx % 5],
                        "label_x": round(_x + _swatch_w + _swatch_text_gap, 2),
                        "label_text": _label,
                    }
                )
                _x += _entry_w + _entry_gap

    stats_context: dict[str, Any] = {
        "stats_username": username,
        "stats_bio": bio,
        "stats_top_language": top_language,
        "stats_repo_count": repo_count,
        "stats_repo_label": f"{top_language} / {repo_count} repos" if top_language else "",
        "stars_display": _format_count(stars_total),
        "stars_raw": int(stars_total) if isinstance(stars_total, int) else 0,
        "commits_display": _format_count(commits_total),
        "prs_display": _format_count(prs_total),
        "issues_display": _format_count(issues_total),
        "contrib_display": _format_count(contrib_total),
        "streak_display": streak_display,
        "languages": languages_raw[:4],
        "heatmap_grid": heatmap_grid,
        "stats_heatmap_year": str(heatmap_year),
        "activity_bars": activity_bars,
        "activity_peak": activity_peak,
        "stale_fields": sorted(stale_fields),
        # v0.3.0 cellular refresh — paradigm constants + per-tone accents.
        "stats_info_accent": stats_info_accent,
        "stats_mid_accent": stats_mid_accent,
        "stats_header_band": stats_header_band,
        "streak_green": streak_green,
        "mid_gray": mid_gray,
        "hero_white": hero_white,
        "stats_header_band_height": header_band_height,
        "heatmap_rows": heatmap_rows,
        "heatmap_cols": heatmap_cols,
        "heatmap_cell_size": heatmap_cell_size,
        "heatmap_cell_gap": heatmap_cell_gap,
        "heatmap_zone_height": heatmap_zone_height,
        "language_layout": language_layout,
    }
    if paradigm_spec is not None:
        stats_context.update(
            {
                "identity_font_family": paradigm_spec.stats.identity_font_family,
                "identity_font_size": paradigm_spec.stats.identity_font_size,
                "identity_font_weight": paradigm_spec.stats.identity_font_weight,
                "identity_letter_spacing_em": paradigm_spec.stats.identity_letter_spacing_em,
            }
        )

    if stale:
        stats_context["data_hw_status"] = "stale"
        stats_context["status"] = "stale"

    # Profile visual context (envelope/well/chrome+hero text gradients) is
    # now injected universally by the dispatcher at resolver.resolve(), so
    # per-frame resolvers no longer need to call _genome_material_context.

    # Spatial layout math: measure each metric value at the nominal font
    # size (20px Orbitron, bold) and cap with SVG textLength when a value
    # would overflow its column budget. Prevents "409457.1K" from blowing
    # past the PRS column on torvalds-tier accounts. Budget = column_width
    # minus 12px breathing room (124px columns, 112px interior).
    from hyperweave.core.text import measure_text

    _VALUE_FONT_SIZE = 20
    _COLUMN_BUDGET = 112
    # Stats value font family comes from paradigm config (chrome → Orbitron,
    # brutalist → Inter). Phase 3 extended measure_text to be font-aware;
    # Phase 4A routes the decision through paradigm_spec instead of an
    # inline ``genome.paradigms.stats == "chrome"`` branch.
    _stats_value_family = "Inter"
    if paradigm_spec is not None:
        # Chrome paradigm declares Orbitron for its hero value size zone.
        # For paradigms without a dedicated stats.value_font_family we use
        # the badge value font family as a sensible proxy (same display font).
        _stats_value_family = paradigm_spec.badge.value_font_family
    for key in ("commits", "prs", "issues", "streak"):
        display = stats_context[f"{key}_display"]
        natural = measure_text(
            display,
            font_family=_stats_value_family,
            font_size=_VALUE_FONT_SIZE,
            font_weight=700,
        )
        stats_context[f"{key}_text_length"] = _COLUMN_BUDGET if natural > _COLUMN_BUDGET else 0
    # Username identity — content-driven shrink-to-fit. Measurement reads
    # the paradigm's actual identity CSS font (family,
    # size, weight, letter-spacing). Previously hardcoded Inter 13/700/0 which
    # under-measured Orbitron-with-letter-spacing renders by ~50%+ and missed
    # overflow on usernames like KARPATHY (Orbitron 13/0.16em ≈ 110px natural
    # vs Inter 13/0 = 53px). When natural > identity_zone_width, emit
    # identity_text_length so the template applies SVG textLength + lengthAdjust.
    #
    # v0.3.9 algorithmic upgrade: identity_zone_width is DERIVED from the
    # neighboring layout constants (``bio_x - identity_x - identity_padding``)
    # instead of carrying a magic number that has to be re-synced every time
    # bio_x shifts. Single computation site so regression tests can pin the
    # derivation.
    if paradigm_spec is not None:
        _stats = paradigm_spec.stats
        identity_measure_text = username.upper() if _stats.identity_text_transform == "uppercase" else username
        identity_natural = measure_text(
            identity_measure_text,
            font_family=_stats.identity_font_family,
            font_size=_stats.identity_font_size,
            font_weight=_stats.identity_font_weight,
            letter_spacing_em=_stats.identity_letter_spacing_em,
        )
        identity_zone_w = max(0, _stats.bio_x - _stats.identity_x - _stats.identity_padding)
    else:
        identity_natural = measure_text(username, font_family="Inter", font_size=13, font_weight=700)
        identity_zone_w = 0
    stats_context["identity_text_length"] = (
        identity_zone_w if identity_zone_w > 0 and identity_natural > identity_zone_w else 0
    )

    # Plumb x positions so templates consume computed coordinates instead of
    # hardcoded literals (per feedback_compose_owns_geometry_template_renders.md).
    #
    # v0.3.9 adaptive bio_x — bio snaps close to the username's visible-ink
    # end for short names and reproduces the v0.3.8 fixed bio_x for clamped
    # long names. Formula:
    #
    #     adaptive_bio_x = identity_x + identity_rendered_ink_w + breathing_margin
    #
    # ``identity_rendered_ink_w`` is:
    #   * the username's visible-ink width (measure_text_ink_width) when the
    #     natural advance fits within identity_zone_w (no clamp), OR
    #   * identity_zone_w when the clamp fires (textLength forces this width)
    #
    # The static ``bio_x`` paradigm value remains the CEILING — when the
    # adaptive computation would exceed it, bio sits at the static value.
    # Substituting identity_zone_w into the adaptive formula gives:
    #     identity_x + (bio_x_static - identity_x - padding) + breathing
    #     = bio_x_static - padding + breathing
    # For brutalist (padding=20, breathing=8): bio_x = 134-12 = 122, the
    # v0.3.8 visual exactly. For ELI64S (~52px ink): bio = 44+52+8 = 104,
    # much tighter than the v0.3.9 static 134.
    from hyperweave.core.text import measure_text_ink_width

    if paradigm_spec is not None:
        _stats = paradigm_spec.stats
        stats_context["identity_x"] = _stats.identity_x
        identity_measure_text = username.upper() if _stats.identity_text_transform == "uppercase" else username
        identity_ink_w = measure_text_ink_width(
            identity_measure_text,
            font_family=_stats.identity_font_family,
            font_size=_stats.identity_font_size,
            font_weight=_stats.identity_font_weight,
            letter_spacing_em=_stats.identity_letter_spacing_em,
        )
        if identity_zone_w > 0 and identity_natural > identity_zone_w:
            # Clamp fires: rendered width is the zone width (textLength forces it).
            identity_rendered_ink_w = float(identity_zone_w)
        else:
            identity_rendered_ink_w = identity_ink_w
        adaptive_bio_x = _stats.identity_x + identity_rendered_ink_w + _stats.identity_breathing_margin
        # Cap at the static paradigm bio_x (the ceiling).
        bio_x_static = _stats.bio_x
        stats_context["bio_x"] = round(min(adaptive_bio_x, bio_x_static)) if bio_x_static > 0 else round(adaptive_bio_x)
    else:
        stats_context["identity_x"] = 0
        stats_context["bio_x"] = 0

    # v0.3.9 bio collision clamp — when bio + HYPERWEAVE branding share the
    # header band row (cellular paradigm), measure the available width
    # between bio_x and the branding's visible left edge, and emit
    # bio_text_length so the template applies SVG textLength shrink-to-fit
    # when a long bio would visually collide with the branding text.
    # Brutalist places branding in the footer row (y=275 vs header y=22-24)
    # so bio_collision_clamp stays False there and no measurement runs.
    bio_text_length = 0.0
    if paradigm_spec is not None and paradigm_spec.stats.bio_collision_clamp:
        repo_label_str = f"{top_language} / {repo_count} repos" if top_language else ""
        bio_str = bio or ""
        bio_full = f"{repo_label_str} · {bio_str}" if repo_label_str and bio_str else repo_label_str or bio_str
        if bio_full:
            card_width_px = paradigm_spec.stats.card_width or 530
            # HYPERWEAVE branding renders right-anchored at x=card_width-20.
            # Cellular CSS uses JBM 6.5/700/0.14em (cellular-defs.j2:36) and
            # bio uses JBM 8.5/400/0.03em (cellular-defs.j2:35). These font
            # constants are paradigm-specific; v0.3.10 promotes them to
            # ParadigmStatsConfig fields alongside ink-width measurement.
            branding_w = measure_text(
                "HYPERWEAVE",
                font_family="JetBrains Mono",
                font_size=6.5,
                font_weight=700,
                letter_spacing_em=0.14,
            )
            branding_left = card_width_px - 20 - branding_w
            bio_margin = 10
            bio_max_width = branding_left - paradigm_spec.stats.bio_x - bio_margin
            bio_natural = measure_text(
                bio_full,
                font_family="JetBrains Mono",
                font_size=8.5,
                font_weight=400,
                letter_spacing_em=0.03,
            )
            if bio_max_width > 0 and bio_natural > bio_max_width:
                bio_text_length = round(bio_max_width, 1)
    stats_context["bio_text_length"] = bio_text_length

    # v0.3.9 Bug B: algorithmic metric slot allocation (cellular only — the
    # other paradigms use structurally different layouts). Each of the 5
    # cellular metrics (STARS hero, COMMITS medium, PRS small, CONTRIB small,
    # STREAK green) renders as a value+label pair. Pre-v0.3.9 the template
    # hardcoded all 10 x positions (e.g., STREAK value at x=459, STREAK label
    # at x=479 with only 20px gap), so a "1000d" streak value overflowed
    # into the STREAK label. Now: resolver measures each value at its CSS
    # font (.mvh/.mvm/.mvs/.mvg) and each label at .mlb, packs the four
    # left-side metrics from x=20 with inter-slot gap, and right-anchors
    # STREAK so the value floats left to make room for arbitrary widths.
    # Cellular paradigm uniquely declares a heatmap (rows > 0); brutalist
    # and chrome stats omit it. This is a structural marker (no string
    # comparison on paradigm name — Invariant 12) that identifies cellular
    # for paradigm-specific layout decisions like the metric slot strip.
    cellular_paradigm = paradigm_spec is not None and int(paradigm_spec.stats.heatmap_rows) > 0
    if cellular_paradigm:
        _CARD_W = paradigm_spec.stats.card_width or 530
        _METRIC_Y = 72.8
        _LEFT_X = 20
        _RIGHT_MARGIN = 20
        _VALUE_LABEL_GAP = 4
        _INTER_SLOT_GAP = 12
        _LABEL_FONT_FAMILY = "JetBrains Mono"
        _LABEL_FONT_SIZE = 6.5
        _LABEL_FONT_WEIGHT = 500
        _LABEL_LETTER_SPACING_EM = 0.22
        # (css_class, value_font_size, value_font_weight, value_letter_spacing_em,
        #  value_display, label_text)
        _value_font_family = "Chakra Petch"
        _left_metrics = [
            ("mvh", 26, 700, -0.02, stats_context["stars_display"], "STARS"),
            ("mvm", 20, 700, -0.02, stats_context["commits_display"], "COMMITS"),
            ("mvs", 15, 600, 0.0, stats_context["prs_display"], "PRS"),
            ("mvs", 15, 600, 0.0, stats_context["contrib_display"], "CONTRIB"),
        ]
        _streak_slot = ("mvg", 15, 600, 0.0, stats_context["streak_display"], "STREAK")

        def _measure_label(label_text: str) -> float:
            return measure_text(
                label_text,
                font_family=_LABEL_FONT_FAMILY,
                font_size=_LABEL_FONT_SIZE,
                font_weight=_LABEL_FONT_WEIGHT,
                letter_spacing_em=_LABEL_LETTER_SPACING_EM,
            )

        metric_layouts: list[dict[str, Any]] = []
        cursor = float(_LEFT_X)
        for css_value, val_size, val_weight, val_ls, value_display, label_text in _left_metrics:
            value_w = measure_text(
                str(value_display),
                font_family=_value_font_family,
                font_size=val_size,
                font_weight=val_weight,
                letter_spacing_em=val_ls,
            )
            label_w = _measure_label(label_text)
            value_x = cursor
            label_x = cursor + value_w + _VALUE_LABEL_GAP
            metric_layouts.append(
                {
                    "value_x": round(value_x, 1),
                    "label_x": round(label_x, 1),
                    "css_value": css_value,
                    "value_display": value_display,
                    "label_text": label_text,
                }
            )
            cursor = label_x + label_w + _INTER_SLOT_GAP

        # STREAK right-aligned: compute its slot width and place from the
        # right edge backward. Supports arbitrary streak widths (1d, 21d,
        # 1000d, 100000d) without overlapping the STREAK label.
        css_value, val_size, val_weight, val_ls, value_display, label_text = _streak_slot
        value_w = measure_text(
            str(value_display),
            font_family=_value_font_family,
            font_size=val_size,
            font_weight=val_weight,
            letter_spacing_em=val_ls,
        )
        label_w = _measure_label(label_text)
        slot_w = value_w + _VALUE_LABEL_GAP + label_w
        value_x = _CARD_W - _RIGHT_MARGIN - slot_w
        label_x = value_x + value_w + _VALUE_LABEL_GAP
        metric_layouts.append(
            {
                "value_x": round(value_x, 1),
                "label_x": round(label_x, 1),
                "css_value": css_value,
                "value_display": value_display,
                "label_text": label_text,
            }
        )
        stats_context["metric_layouts"] = metric_layouts
        stats_context["metric_y"] = _METRIC_Y
    else:
        stats_context["metric_layouts"] = []
        stats_context["metric_y"] = 0.0

    # Embedded compact chart — enablement flag + viewport sourced from
    # paradigm YAML. Chrome paradigm embeds; brutalist does not. Zero
    # string comparisons in Python; adding a new paradigm that also wants
    # an embed is purely a YAML change.
    embeds_chart = bool(paradigm_spec.stats.embeds_chart) if paradigm_spec is not None else False
    if embeds_chart:
        ec = paradigm_spec.stats
        embed_vp = Viewport(x=ec.embed_viewport_x, y=ec.embed_viewport_y, w=ec.embed_viewport_w, h=ec.embed_viewport_h)
        # Zero-guard: never default to a 1200-star synthetic curve. When
        # stars_total is zero, the truthful state is an empty embedded chart.
        # Stale-guard: when ``stars_total`` is ``None`` (sub-fetch failed),
        # the embedded chart is empty too — synthesizing a curve from a
        # known-bad value would compound the silent-zero misrepresentation.
        stars_int = int(stars_total) if isinstance(stars_total, int) else 0
        real_points = connector.get("points") or connector.get("star_history")
        if real_points:
            chart_points: list[dict[str, Any]] = list(real_points)
        elif stars_int > 0 and "stars_total" not in stale_fields:
            # Only synthesize when we know the total — this approximates a
            # plausible growth curve rather than fabricating it from nothing.
            chart_points = _synthetic_series_from_total(stars_int)
        else:
            chart_points = []
        embed = build_chart_svg(
            chart_points,
            embed_vp,
            genome.get("structural") or {},
        )
        stats_context["embedded_chart_defs"] = embed["defs"]
        stats_context["embedded_chart_area"] = embed["area"]
        stats_context["embedded_chart_polyline"] = embed["polyline"]
        stats_context["embedded_chart_markers"] = embed["markers"]
        stats_context["embedded_chart_viewport_x"] = embed_vp.x
        stats_context["embedded_chart_viewport_y"] = embed_vp.y
        stats_context["embedded_chart_viewport_w"] = embed_vp.w
        stats_context["embedded_chart_viewport_h"] = embed_vp.h

    # Card dimensions — paradigm config drives both axes. Cellular v0.3.0 uses
    # 530x233; brutalist + chrome use their own widths via the `card_width` /
    # `card_height` fields. Paradigms that leave `card_width` at the schema
    # default (0) fall back to the historical _STATS_WIDTH=495 baseline.
    card_height = paradigm_spec.stats.card_height if paradigm_spec is not None else 260
    if paradigm_spec is not None and paradigm_spec.stats.card_width > 0:
        card_width = paradigm_spec.stats.card_width
    else:
        card_width = _STATS_WIDTH
    return {
        "width": card_width,
        "height": card_height,
        "template": "frames/stats.svg.j2",
        "context": stats_context,
    }


def _synthetic_series_from_total(total: int) -> list[dict[str, Any]]:
    """Generate a six-point monotonic curve that ends at ``total``.

    Used when connector_data lacks a full star history (e.g. a stats fetch
    succeeded but the caller didn't also run fetch_stargazer_history). The
    shape is plausible but deterministic — no randomness, so cached renders
    are identical.
    """
    from datetime import datetime, timedelta

    today = datetime.now(UTC)
    fractions = (0.08, 0.18, 0.34, 0.52, 0.76, 1.0)
    months_ago = (360, 300, 240, 180, 120, 60)
    return [
        {
            "date": (today - timedelta(days=days)).isoformat(),
            "count": max(1, int(total * frac)),
        }
        for days, frac in zip(months_ago, fractions, strict=True)
    ]
