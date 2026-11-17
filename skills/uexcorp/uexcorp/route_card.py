"""Render UEX trade route data as an image that Wingman can show in chat."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from services.image_generation import vision_base64


WIDTH = 1280
HEIGHT = 960
BACKGROUND = (6, 16, 29)
PANEL = (10, 27, 44)
BORDER = (32, 75, 100)
CYAN = (46, 213, 245)
TEAL = (69, 225, 199)
GREEN = (65, 220, 131)
AMBER = (255, 181, 64)
WHITE = (238, 247, 252)
MUTED = (139, 174, 194)
RED = (255, 99, 99)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _short(value: str | None, limit: int = 25) -> str:
    text = str(value or "Unknown").replace("Admin - ", "")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _money(value: object) -> str:
    try:
        return f"{int(round(float(value or 0))):,} aUEC"
    except (TypeError, ValueError):
        return "—"


def _age_label(seconds: int | None) -> tuple[str, tuple[int, int, int]]:
    if seconds is None or seconds < 0:
        return "Price age unavailable", AMBER
    if seconds < 60:
        minutes = 0
        label = "Prices less than 1 min old"
    elif seconds < 3600:
        minutes = seconds // 60
        label = f"Prices {minutes} min old"
    elif seconds < 86400:
        hours = seconds // 3600
        label = f"Prices {hours} hr old"
    else:
        days = seconds // 86400
        label = f"Prices {days} days old"
    return label, GREEN if seconds <= 2 * 3600 else AMBER if seconds <= 4 * 3600 else RED


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, outline=BORDER, radius=16):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _opportunities(stops: list[dict]) -> list[dict]:
    opportunities = []
    for buy_index, stop in enumerate(stops):
        buys = stop.get("buy") if isinstance(stop.get("buy"), list) else []
        for buy in buys:
            commodity = str(buy.get("commodity") or "Commodity")
            target = buy.get("sell_at")
            sale = None
            sale_stop = None
            for candidate in stops[buy_index + 1 :]:
                if target and candidate.get("terminal") != target:
                    continue
                sale = next(
                    (entry for entry in candidate.get("sell", [])
                     if str(entry.get("commodity", "")).casefold() == commodity.casefold()),
                    None,
                )
                if sale:
                    sale_stop = candidate
                    break
            buy_scu = int(buy.get("scu") or 0)
            sell_scu = int(sale.get("scu") or 0) if sale else 0
            buy_price = float(buy.get("price_per_scu") or (buy.get("total_aUEC", 0) / buy_scu if buy_scu else 0))
            sell_price = float(sale.get("price_per_scu") or (sale.get("total_aUEC", 0) / sell_scu if sell_scu else 0)) if sale else 0
            volume_note = str(buy.get("volume_note") or "")
            available_scu = min(buy_scu, sell_scu) if sale else buy_scu
            profit_per_scu = round(sell_price - buy_price) if sale else 0
            opportunities.append({
                "commodity": commodity,
                "origin": stop.get("terminal", "Unknown"),
                "destination": sale_stop.get("terminal", "Unknown") if sale_stop else (target or "Unknown"),
                "buy_price": round(buy_price),
                "sell_price": round(sell_price),
                "profit_per_scu": profit_per_scu,
                "scu": available_scu,
                "profit": profit_per_scu * available_scu,
                "availability_limited": "estimated availability" in volume_note.casefold(),
            })
    return sorted(opportunities, key=lambda item: item["profit"], reverse=True)


def render_route_card(
    route: dict,
    current_step: int | None = None,
    data_age_seconds: int | None = None,
    output_path: str | None = None,
) -> str:
    """Return a JPEG base64 string for a route search result or active route.

    Every value and stop label comes from the UEX route object. The drawing is
    deliberately schematic; it shows stop order, not travel geography.
    """
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    title_font = _font(34)
    heading_font = _font(21)
    body_font = _font(18)
    small_font = _font(15)

    route = route if isinstance(route, dict) else {}
    stops = route.get("stops") if isinstance(route.get("stops"), list) else []
    if not stops:
        draw.text((48, 54), "UEX TRADE ROUTE", font=title_font, fill=WHITE)
        draw.text((48, 120), "No route stops were returned by UEX.", font=body_font, fill=MUTED)
        if output_path:
            image.save(output_path, format="JPEG", quality=94, optimize=True)
        return vision_base64(image)

    step_count = len(stops)
    active_step = min(max(int(current_step or 1), 1), step_count)
    route_number = route.get("route_number")
    route_label = f"ROUTE {route_number}" if route_number else "ACTIVE TRADE RUN"
    system_path = str(route.get("systems") or "UEX community market data")

    draw.text((48, 34), "UEX CORPORATION", font=small_font, fill=CYAN)
    draw.text((48, 60), route_label, font=title_font, fill=WHITE)
    draw.text((48, 111), _fit(draw, system_path, body_font, 860), font=body_font, fill=MUTED)
    draw.text((930, 55), "UEX COMMUNITY DATA", font=small_font, fill=CYAN)
    freshness, freshness_color = _age_label(data_age_seconds)
    draw.text((930, 82), _fit(draw, freshness, body_font, 300), font=body_font, fill=freshness_color)

    stat_y, stat_h, gap = 156, 105, 16
    stat_w = (WIDTH - 96 - 2 * gap) // 3
    stats = (
        ("EST. ROUTE PROFIT", _money(route.get("estimated_profit")), GREEN),
        ("CAPITAL REQUIRED", _money(route.get("max_investment")), WHITE),
        ("STOPS / SYSTEM JUMPS", f"{step_count} / {route.get('system_jumps', '—')}", CYAN),
    )
    for index, (label, value, color) in enumerate(stats):
        x = 48 + index * (stat_w + gap)
        _rounded(draw, (x, stat_y, x + stat_w, stat_y + stat_h), PANEL)
        draw.text((x + 18, stat_y + 16), label, font=small_font, fill=MUTED)
        draw.text((x + 18, stat_y + 48), _fit(draw, value, heading_font, stat_w - 36), font=heading_font, fill=color)

    map_top, map_bottom = 288, 510
    _rounded(draw, (48, map_top, WIDTH - 48, map_bottom), PANEL)
    draw.text((70, map_top + 18), "ROUTE STOPS · IN ORDER", font=heading_font, fill=CYAN)
    left, right = 170, WIDTH - 170
    node_y = map_top + 107
    usable = right - left
    spacing = usable / max(step_count - 1, 1)
    node_xs = [int(left + spacing * i) if step_count > 1 else WIDTH // 2 for i in range(step_count)]

    for index, (stop, x) in enumerate(zip(stops, node_xs)):
        if index < step_count - 1:
            next_x = node_xs[index + 1]
            line_color = TEAL if index < active_step - 1 else BORDER
            draw.line((x + 18, node_y, next_x - 18, node_y), fill=line_color, width=5)
            draw.polygon(
                [(next_x - 23, node_y - 9), (next_x - 8, node_y), (next_x - 23, node_y + 9)],
                fill=line_color,
            )
        selected = index + 1 == active_step
        node_color = GREEN if selected else CYAN if index == 0 or index == step_count - 1 else TEAL
        radius = 18 if selected else 14
        draw.ellipse((x - radius, node_y - radius, x + radius, node_y + radius), fill=BACKGROUND, outline=node_color, width=4)
        if selected:
            draw.ellipse((x - 6, node_y - 6, x + 6, node_y + 6), fill=node_color)
        label = _short(stop.get("terminal"), 22)
        label_width = min(210, max(130, int(spacing) - 18))
        draw.text((x - label_width // 2, node_y + 27), _fit(draw, label, body_font, label_width), font=body_font, fill=WHITE)
        location = _short(stop.get("location"), 25)
        draw.text((x - label_width // 2, node_y + 55), _fit(draw, location, small_font, label_width), font=small_font, fill=MUTED)
        actions = []
        buys = stop.get("buy") if isinstance(stop.get("buy"), list) else []
        sells = stop.get("sell") if isinstance(stop.get("sell"), list) else []
        if buys:
            actions.append(f"BUY {len(buys)}")
        if sells:
            actions.append(f"SELL {len(sells)}")
        if stop.get("has_refuel"):
            actions.append("REFUEL")
        if not actions:
            actions.append("STOP")
        draw.text((x - label_width // 2, node_y + 81), "  ·  ".join(actions), font=small_font, fill=GREEN if selected else CYAN)

    if current_step is not None:
        stop = stops[active_step - 1]
        state_text = f"CURRENT · {active_step}/{step_count} · {_short(stop.get('terminal'), 30)}"
        draw.text((805, map_top + 24), _fit(draw, state_text, small_font, WIDTH - 875), font=small_font, fill=GREEN)

    cargo_top = 532
    _rounded(draw, (48, cargo_top, WIDTH - 48, HEIGHT - 103), PANEL)
    draw.text((70, cargo_top + 18), "TRADE OPPORTUNITIES", font=heading_font, fill=CYAN)
    columns = [70, 205, 330, 435, 575, 680, 810, 910]
    header_y = cargo_top + 59
    headers = (
        "COMMODITY", "BUY AT", "BUY / SCU", "SELL AT", "SELL / SCU",
        "PROFIT / SCU", "CARGO", "EST. PROFIT",
    )
    for x, label in zip(columns, headers):
        draw.text((x, header_y), label, font=small_font, fill=MUTED)
    draw.line((70, header_y + 28, WIDTH - 70, header_y + 28), fill=BORDER, width=1)

    opportunities = _opportunities(stops)
    visible_rows = opportunities[:4]
    row_y = header_y + 43
    for index, opportunity in enumerate(visible_rows):
        y = row_y + index * 43
        values = (
            (columns[0], opportunity["commodity"], columns[1] - columns[0] - 10, False),
            (columns[1], _short(opportunity["origin"], 24), columns[2] - columns[1] - 10, False),
            (columns[2], f"{opportunity['buy_price']:,}", columns[3] - columns[2] - 10, False),
            (columns[3], _short(opportunity["destination"], 24), columns[4] - columns[3] - 10, False),
            (columns[4], f"{opportunity['sell_price']:,}", columns[5] - columns[4] - 10, False),
            (columns[5], f"+{opportunity['profit_per_scu']:,}", columns[6] - columns[5] - 10, True),
            (columns[6], f"{opportunity['scu']:,} SCU" + ("*" if opportunity["availability_limited"] else ""), columns[7] - columns[6] - 10, False),
            (columns[7], f"+{opportunity['profit']:,}", WIDTH - columns[7] - 70, True),
        )
        for x, value, max_width, is_profit in values:
            draw.text((x, y), _fit(draw, value, body_font, max_width), font=body_font,
                      fill=GREEN if is_profit else WHITE)
        if index < len(visible_rows) - 1:
            draw.line((70, y + 34, WIDTH - 70, y + 34), fill=BORDER, width=1)

    if not visible_rows:
        draw.text((70, row_y), "No commodity purchases were returned for this route.", font=body_font, fill=MUTED)
    if len(opportunities) > len(visible_rows):
        draw.text((70, HEIGHT - 126), f"+ {len(opportunities) - len(visible_rows)} more trade lines", font=small_font, fill=MUTED)

    warnings = []
    if route.get("warning"):
        warnings.append(str(route["warning"]))
    elif route.get("volume_limited"):
        warnings.append("Cargo volume is limited by estimated availability.")
    if any(item["availability_limited"] for item in opportunities):
        warnings.append("* Planned SCU is limited by estimated stock or demand.")
    if warnings:
        warning = _fit(draw, " · ".join(warnings), small_font, WIDTH - 140)
        draw.text((70, HEIGHT - 75), warning, font=small_font, fill=AMBER if not route.get("illegal_commodities") else RED)
    else:
        draw.text((70, HEIGHT - 75), "UEX market values are estimates; confirm stock and price at the terminal.", font=small_font, fill=MUTED)

    if output_path:
        image.save(output_path, format="JPEG", quality=94, optimize=True)
    return vision_base64(image)
