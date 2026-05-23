"""Shared frozen spatial record types for layout modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RectSpec:
    """Resolved rectangle geometry."""

    x: float
    y: float
    w: float
    h: float
    rx: float = 0.0


@dataclass(frozen=True, slots=True)
class LineSpec:
    """Resolved line segment geometry."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class TextSpec:
    """Resolved text anchor point."""

    x: float
    y: float
    anchor: str = "start"
    text: str = ""
