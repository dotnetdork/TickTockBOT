"""
utils/heatmap.py
----------------
Generates a dynamic PNG heat-map image for a weekly availability schedule.

Grid layout
-----------
- Columns  : Days of the week (Monday … Sunday)
- Rows     : Hours of the day (00:00 … 23:00) — always in 24-hour format
- Each cell is coloured based on how many users are available at that slot.

Colour scale (relative to the maximum count in the grid)
---------------------------------------------------------
  0 users    : EMPTY_COLOUR   (light grey)
  > 0 users  : Linear interpolation between LOW_COLOUR and HIGH_COLOUR
               so the cell with the most respondents gets the darkest green.

Timezone handling
-----------------
The `grid` data arriving from the database is always in UTC.  When a display
timezone is supplied the function shifts each (day, hour) pair before
painting so the image reflects the user's local time.

Architecture note
-----------------
This module has no knowledge of Discord or aiosqlite; it is a pure
image-rendering utility.  Keep it that way so it can be unit-tested
independently and reused for Google-Calendar integration later.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytz
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Layout constants (pixels) - Dyslexia-friendly with larger cells and thicker borders
# ---------------------------------------------------------------------------

CELL_W = 72          # width of each day-column cell (increased for better readability)
CELL_H = 32          # height of each hour-row cell (increased for better readability)
LABEL_W = 68         # left column reserved for "HH:MM AM/PM" hour labels (wider for 12-hour format)
HEADER_H = 48        # top row reserved for day-name headers
PADDING = 16         # outer whitespace on all four sides (increased)
BORDER_WIDTH = 2     # thick cell borders for dyslexia-friendly design

# Total image dimensions (computed once)
IMG_W = PADDING + LABEL_W + 7 * CELL_W + PADDING
IMG_H = PADDING + HEADER_H + 24 * CELL_H + PADDING

# ---------------------------------------------------------------------------
# Colours  (R, G, B) - High contrast, dyslexia-friendly palette
# ---------------------------------------------------------------------------

BACKGROUND  = (255, 255, 255)   # pure white canvas for maximum contrast
GRID_LINE   = (60,  60,  60)    # dark grey for thick, visible borders
HEADER_BG   = (30,  58,  138)   # deep blue header bar (high contrast)
HEADER_TEXT = (255, 255, 255)   # white text inside the header
LABEL_TEXT  = (40,  40,  40)    # very dark grey hour labels on the left
EMPTY_CELL  = (240, 240, 240)   # light grey for no respondents
LOW_COLOUR  = (134, 239, 172)   # light saturated green – at least one person available
HIGH_COLOUR = (21,  128, 61)    # dark saturated green – maximum overlap

# ---------------------------------------------------------------------------
# Day / hour metadata
# ---------------------------------------------------------------------------

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _format_hour_12h(hour: int) -> str:
    """Convert 24-hour format to 12-hour AM/PM format."""
    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"


def _lerp_colour(
    low: tuple[int, int, int],
    high: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """
    Linearly interpolate between two RGB colours.

    t=0.0  → low colour
    t=1.0  → high colour
    """
    return tuple(int(low[i] + (high[i] - low[i]) * t) for i in range(3))  # type: ignore[return-value]


def _cell_colour(
    count: int,
    max_count: int,
) -> tuple[int, int, int]:
    """
    Return the fill colour for a cell that has `count` respondents,
    given that the busiest cell in the whole grid has `max_count`.
    """
    if count <= 0 or max_count <= 0:
        return EMPTY_CELL
    t = count / max_count          # 0 < t ≤ 1
    return _lerp_colour(LOW_COLOUR, HIGH_COLOUR, t)


def _shift_grid_to_timezone(
    utc_grid: dict[tuple[int, int], int],
    tz_name: str,
) -> dict[tuple[int, int], int]:
    """
    Convert a UTC (day, hour) grid into the target timezone.

    Strategy: for every cell in the UTC grid, compute the equivalent
    local (day, hour) by taking an arbitrary reference Monday 00:00 UTC
    and adding the UTC offset for the requested timezone.

    The offset is assumed to be constant (no DST detection per-slot) —
    this is a reasonable simplification for a weekly repeating schedule.
    """
    if tz_name == "UTC":
        return utc_grid

    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        return utc_grid  # fall back to UTC silently

    # 2024-01-01 is used as the reference Monday (it was indeed a Monday)
    # so weekday() on the shifted datetime correctly maps 0=Mon … 6=Sun.
    REFERENCE_MONDAY = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)

    local_grid: dict[tuple[int, int], int] = {}

    for (day, hour), count in utc_grid.items():
        utc_dt = REFERENCE_MONDAY + timedelta(days=day, hours=hour)
        local_dt = utc_dt.astimezone(tz)
        local_day  = local_dt.weekday()   # 0=Mon … 6=Sun
        local_hour = local_dt.hour
        # Accumulate counts in case two UTC slots map to the same local slot
        key = (local_day, local_hour)
        local_grid[key] = local_grid.get(key, 0) + count

    return local_grid


def generate_heatmap(
    grid: dict[tuple[int, int], int],
    title: str = "Team Availability",
    timezone_name: str = "UTC",
    participant_count: int = 0,
) -> bytes:
    """
    Render a 7×24 availability heat-map and return it as a PNG byte string.

    Parameters
    ----------
    grid:
        Mapping of (day_of_week, hour) → number_of_users (UTC).
        Produced by ``Database.get_availability_grid()``.
    title:
        Schedule title displayed at the top of the image.
    timezone_name:
        IANA timezone string used to shift UTC grid data before rendering.
        Defaults to "UTC" (no shift).
    participant_count:
        Total number of distinct users who have submitted availability.
        Displayed in a subtitle so viewers know how many people contributed.

    Returns
    -------
    bytes
        Raw PNG image data ready to be wrapped in a ``discord.File``.
    """
    # 1. Optionally shift the grid to the display timezone
    display_grid = _shift_grid_to_timezone(grid, timezone_name)

    # 2. Find the maximum count for normalising colours
    max_count = max(display_grid.values(), default=0)

    # 3. Build the image
    img = Image.new("RGB", (IMG_W, IMG_H), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # ------------------------------------------------------------------
    # Attempt to load a system font; fall back to the default PIL font.
    # ------------------------------------------------------------------
    font_regular = _load_font(size=13)
    font_bold    = _load_font(size=14, bold=True)
    font_title   = _load_font(size=16, bold=True)

    # ------------------------------------------------------------------
    # Title bar (above the header row)
    # ------------------------------------------------------------------
    title_y = PADDING
    draw.text(
        (PADDING + LABEL_W, title_y),
        title,
        fill=HEADER_BG,
        font=font_title,
    )
    subtitle = (
        f"Timezone: {timezone_name}  |  {participant_count} participant(s)"
    )
    draw.text(
        (PADDING + LABEL_W, title_y + 20),
        subtitle,
        fill=LABEL_TEXT,
        font=font_regular,
    )

    # ------------------------------------------------------------------
    # Day-name header row
    # ------------------------------------------------------------------
    header_y = PADDING + HEADER_H - CELL_H
    for col, day_name in enumerate(DAY_NAMES):
        x0 = PADDING + LABEL_W + col * CELL_W
        y0 = header_y
        x1 = x0 + CELL_W
        y1 = y0 + CELL_H
        draw.rectangle([x0, y0, x1, y1], fill=HEADER_BG, outline=GRID_LINE, width=BORDER_WIDTH)
        _draw_centered_text(draw, day_name, x0, y0, x1, y1, font_bold, HEADER_TEXT)

    # ------------------------------------------------------------------
    # Hour rows + cells
    # ------------------------------------------------------------------
    for row in range(24):
        y0 = PADDING + HEADER_H + row * CELL_H
        y1 = y0 + CELL_H

        # Hour label on the left (e.g. "2 PM")
        label = _format_hour_12h(row)
        label_x = PADDING
        try:
            label_bbox = draw.textbbox((0, 0), label, font=font_regular)
            label_h = label_bbox[3] - label_bbox[1]
        except AttributeError:
            _, label_h = draw.textsize(label, font=font_regular)  # type: ignore[attr-defined]
        label_y = y0 + (CELL_H - label_h) // 2
        draw.text((label_x, label_y), label, fill=LABEL_TEXT, font=font_regular)

        for col in range(7):
            x0 = PADDING + LABEL_W + col * CELL_W
            x1 = x0 + CELL_W

            count  = display_grid.get((col, row), 0)
            colour = _cell_colour(count, max_count)

            draw.rectangle([x0, y0, x1, y1], fill=colour, outline=GRID_LINE, width=BORDER_WIDTH)

            # Show the respondent count inside non-empty cells
            if count > 0:
                text_colour = (255, 255, 255) if count / max_count > 0.5 else (50, 50, 50)
                _draw_centered_text(
                    draw,
                    str(count),
                    x0, y0, x1, y1,
                    font_regular,
                    text_colour,
                )

    # ------------------------------------------------------------------
    # Colour legend (bottom-right corner)
    # ------------------------------------------------------------------
    _draw_legend(draw, font_regular, max_count)

    # ------------------------------------------------------------------
    # Encode to PNG bytes
    # ------------------------------------------------------------------
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_font(size: int = 13, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Try to load a TrueType font.  Falls back to PIL's built-in bitmap
    font if no suitable .ttf file is found on the system.
    """
    candidates = [
        # Linux paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS paths
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue

    # Last resort: PIL's built-in bitmap font (no size parameter)
    return ImageFont.load_default()


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    font,
    fill: tuple[int, int, int],
) -> None:
    """Draw `text` centred inside the rectangle defined by (x0,y0)-(x1,y1)."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        # PIL < 9.2 fallback
        tw, th = draw.textsize(text, font=font)  # type: ignore[attr-defined]

    x = x0 + (x1 - x0 - tw) // 2
    y = y0 + (y1 - y0 - th) // 2
    draw.text((x, y), text, fill=fill, font=font)


def _draw_legend(
    draw: ImageDraw.ImageDraw,
    font,
    max_count: int,
) -> None:
    """
    Draw a small colour legend at the bottom-left of the image so viewers
    can interpret the colour scale at a glance.
    """
    legend_x = PADDING
    legend_y = IMG_H - PADDING - 14

    swatch_size = 12
    gap = 4

    items = [
        (EMPTY_CELL, "0"),
        (LOW_COLOUR,  "1"),
    ]
    if max_count > 2:
        mid = _lerp_colour(LOW_COLOUR, HIGH_COLOUR, 0.5)
        items.append((mid, f"~{max_count // 2}"))
    if max_count > 0:
        items.append((HIGH_COLOUR, str(max_count)))

    label_prefix = "Scale: "
    draw.text((legend_x, legend_y), label_prefix, fill=LABEL_TEXT, font=font)

    try:
        prefix_w = draw.textbbox((0, 0), label_prefix, font=font)[2]
    except AttributeError:
        prefix_w, _ = draw.textsize(label_prefix, font=font)  # type: ignore[attr-defined]

    cx = legend_x + prefix_w
    for colour, label in items:
        draw.rectangle(
            [cx, legend_y, cx + swatch_size, legend_y + swatch_size],
            fill=colour,
            outline=GRID_LINE,
            width=BORDER_WIDTH,
        )
        cx += swatch_size + 2
        draw.text((cx, legend_y), label, fill=LABEL_TEXT, font=font)
        try:
            lw = draw.textbbox((0, 0), label, font=font)[2]
        except AttributeError:
            lw, _ = draw.textsize(label, font=font)  # type: ignore[attr-defined]
        cx += lw + gap
