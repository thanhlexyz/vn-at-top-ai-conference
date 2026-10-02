"""SVG figures for the blog post, drawn without any library so the site stays free of JavaScript.

Colours are classes (s1, s2, s3, hollow) styled in frontend/static/style.css. The three hues were
checked with a colour-blindness validator on a white surface. Every mark carries a <title>, which
browsers show on hover, and the value is printed next to the mark.
"""
import html
import math

WIDTH = 640


def _esc(text):
    return html.escape(str(text))


def _fmt(value):
    return f"{value:.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def _legend(series, y=16, x=0):
    out = []
    for cls, name in series:
        out.append(f'<rect class="{cls}" x="{x}" y="{y - 10}" width="12" height="12"/>'
                   f'<text x="{x + 18}" y="{y}">{_esc(name)}</text>')
        x += 30 + 6.4 * len(name)
    return "".join(out)


def _bar(cls, x, y, w, h, tip, round_end=False):
    """A horizontal segment; the free end of a bar is rounded, the rest stays square."""
    r = min(4, w) if round_end else 0
    d = (f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h - r:.1f} "
         f"Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z")
    return f'<path class="{cls}" d="{d}"><title>{_esc(tip)}</title></path>'


def share_bar(label, segments):
    """One wide bar split into parts of a whole, each part named and numbered underneath.

    segments: [(css class, name, value)]
    """
    total = sum(v for _, _, v in segments)
    left, right, top, h = 0, 0, 8, 28
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} 86" role="img" aria-label="{_esc(label)}">']
    x = left
    shown = [s for s in segments if s[2] > 0]
    for k, (cls, name, value) in enumerate(shown):
        w = (WIDTH - left - right) * value / total - (2 if k < len(shown) - 1 else 0)
        out.append(_bar(cls, x, top, w, h, f"{value} {name}", round_end=k == len(shown) - 1))
        out.append(f'<text class="value" x="{x:.1f}" y="{top + h + 18}">{value}</text>'
                   f'<text x="{x:.1f}" y="{top + h + 34}">{_esc(name)}</text>')
        x += w + 2
    out.append("</svg>")
    return "".join(out)


def stacked_rows(label, rows, series, unit=""):
    """One horizontal stacked bar per row, the total printed at its end.

    rows: [(name, [value per series])]   series: [(css class, legend name)]
    """
    name_w, right, top, row_h, bar_h = 170, 46, 30, 26, 14
    peak = max((sum(values) for _, values in rows), default=0) or 1
    scale = (WIDTH - name_w - right) / peak
    height = top + row_h * len(rows) + 6
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{_esc(label)}">',
           _legend(series)]
    for k, (name, values) in enumerate(rows):
        y = top + k * row_h
        out.append(f'<text class="value" x="{name_w - 8}" y="{y + bar_h - 2}" text-anchor="end">{_esc(name)}</text>')
        x = name_w
        shown = [(cls, title, v) for (cls, title), v in zip(series, values) if v > 0]
        for n, (cls, title, v) in enumerate(shown):
            w = max(v * scale - (2 if n < len(shown) - 1 else 0), 1)
            out.append(_bar(cls, x, y, w, bar_h, f"{name}: {_fmt(v)} {title}", round_end=n == len(shown) - 1))
            x += w + 2
        out.append(f'<text x="{x + 4:.1f}" y="{y + bar_h - 2}">{_fmt(sum(values))}{unit}</text>')
    out.append(f'<line class="axis" x1="{name_w}" y1="{top - 4}" x2="{name_w}" y2="{height - 4}"/></svg>')
    return "".join(out)


def year_panels(label, panels):
    """Small multiples: one column per year in each panel, first and last value printed.

    panels: [(title, [(year, value, note under the title tooltip, provisional)])]
    """
    gap, top, plot_h, bottom = 16, 40, 110, 22
    panel_w = (WIDTH - gap * (len(panels) - 1)) / len(panels)
    peak = max(v for _, years in panels for _, v, _, _ in years) or 1
    base = top + plot_h
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {base + bottom}" role="img" aria-label="{_esc(label)}">']
    for p, (title, years) in enumerate(panels):
        x0 = p * (panel_w + gap)
        out.append(f'<text class="value" x="{x0:.1f}" y="14">{_esc(title)}</text>'
                   f'<line class="axis" x1="{x0:.1f}" y1="{base}" x2="{x0 + panel_w:.1f}" y2="{base}"/>')
        band = panel_w / len(years)
        bar = min(16, band * 0.6)
        for k, (year, value, note, provisional) in enumerate(years):
            cx = x0 + band * (k + 0.5)
            h = max(value / peak * plot_h, 0.5 if value else 0)
            if value:
                r = min(4, h)
                x, y = cx - bar / 2, base - h
                d = (f"M{x:.1f},{base} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + bar - r:.1f} "
                     f"Q{x + bar:.1f},{y:.1f} {x + bar:.1f},{y + r:.1f} V{base} Z")
                out.append(f'<path class="{"hollow" if provisional else "s1"}" d="{d}">'
                           f'<title>{_esc(title)} {year}: {value}{" so far" if provisional else ""}. {_esc(note)}</title></path>')
            if k in (0, len(years) - 1):
                out.append(f'<text class="value" x="{cx:.1f}" y="{base - h - 6:.1f}" text-anchor="middle">'
                           f'{value}{"+" if provisional else ""}</text>')
                out.append(f'<text x="{cx:.1f}" y="{base + 16}" text-anchor="middle">{year}</text>')
    out.append("</svg>")
    return "".join(out)


def pies(label, charts):
    """Pie charts side by side, each with two or three slices named and numbered beside it.

    charts: [(title, [(css class, name, value)])]
    """
    cell, r, top = WIDTH / len(charts), 70, 34
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {top + 2 * r + 16}" role="img" aria-label="{_esc(label)}">']
    for k, (title, slices) in enumerate(charts):
        cx, cy = k * cell + r + 4, top + r
        total = sum(v for _, _, v in slices) or 1
        out.append(f'<text class="value" x="{k * cell + 4:.1f}" y="16">{_esc(title)}</text>')
        angle = -math.pi / 2
        for n, (cls, name, value) in enumerate(slices):
            share = value / total
            end = angle + 2 * math.pi * share
            x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
            tip = f"{title}: {_fmt(value)} {name}, {share:.0%}"
            if share >= 0.999:
                out.append(f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r}"><title>{_esc(tip)}</title></circle>')
            elif value:
                out.append(f'<path class="{cls} slice" d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} A{r},{r} 0 '
                           f'{int(share > 0.5)} 1 {x2:.1f},{y2:.1f} Z"><title>{_esc(tip)}</title></path>')
            y = cy - 22 + n * 40
            out.append(f'<rect class="{cls}" x="{cx + r + 18:.1f}" y="{y - 10:.1f}" width="12" height="12"/>'
                       f'<text class="value" x="{cx + r + 36:.1f}" y="{y:.1f}">{_fmt(value)} ({share:.0%})</text>'
                       f'<text x="{cx + r + 36:.1f}" y="{y + 15:.1f}">{_esc(name)}</text>')
            angle = end
    out.append("</svg>")
    return "".join(out)


def lines(label, years, series):
    """One line per series over the years, with a legend on top and a light grid.

    series: [(css class, name, [value per year])]
    """
    left, right, top, plot_h, bottom = 34, 14, 34, 190, 24
    peak = max((v for _, _, values in series for v in values), default=0) or 1
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100) if peak / s <= 5)
    top_value = step * -(-peak // step)
    base, plot_w = top + plot_h, WIDTH - left - right
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {base + bottom}" role="img" aria-label="{_esc(label)}">',
           _legend([(cls, name) for cls, name, _ in series], x=left)]
    value = 0
    while value <= top_value:
        y = base - value / top_value * plot_h
        out.append(f'<line class="{"axis" if value == 0 else "grid"}" x1="{left}" y1="{y:.1f}" x2="{WIDTH - right}" y2="{y:.1f}"/>'
                   f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        value += step
    xs = [left + plot_w * (k + 0.5) / len(years) for k in range(len(years))]
    for x, year in zip(xs, years):
        out.append(f'<text x="{x:.1f}" y="{base + 17}" text-anchor="middle">{year}</text>')
    for cls, name, values in series:
        pts = [(x, base - v / top_value * plot_h) for x, v in zip(xs, values)]
        out.append(f'<polyline class="line {cls}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
        for (x, y), year, v in zip(pts, years, values):
            out.append(f'<circle class="dot {cls}" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{_esc(name)} {year}: {v}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def stacked_area(label, years, series, provisional=(), short=None):
    """Stacked areas over the years, the first series at the bottom, with a legend on top, each band
    named at its right end, and a hover column per year whose <title> gives that year's numbers.

    series: [(css class, name, [value per year])]. The band classes are styled in style.css; a 2px
    surface line separates the bands. Years in `provisional` are still being counted and say so.
    `short` gives shorter band names for the labels at the right end; the legend keeps the full names.
    """
    left, right, top, plot_h, bottom = 34, 120, 34, 200, 24
    totals = [sum(values[k] for _, _, values in series) for k in range(len(years))]
    peak = max(totals, default=0) or 1
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000) if peak / s <= 5)
    top_value = step * -(-peak // step)
    base, plot_w = top + plot_h, WIDTH - left - right
    xs = [left + plot_w * k / (len(years) - 1) for k in range(len(years))] if len(years) > 1 else [left]

    def y_of(v):
        return base - v / top_value * plot_h

    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {base + bottom}" role="img" aria-label="{_esc(label)}">',
           _legend([(cls, name) for cls, name, _ in series], x=left)]
    value = 0
    while value <= top_value:
        y = y_of(value)
        out.append(f'<line class="{"axis" if value == 0 else "grid"}" x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" '
                   f'y2="{y:.1f}"/><text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        value += step
    for x, year in zip(xs, years):
        out.append(f'<text x="{x:.1f}" y="{base + 17}" text-anchor="middle">{year}{"*" if year in provisional else ""}</text>')

    lower = [0.0] * len(years)
    edges, ends = [], []
    for cls, name, values in series:
        upper = [lo + v for lo, v in zip(lower, values)]
        pts = [f"{x:.1f},{y_of(v):.1f}" for x, v in zip(xs, upper)]
        back = [f"{x:.1f},{y_of(v):.1f}" for x, v in reversed(list(zip(xs, lower)))]
        out.append(f'<polygon class="band {cls}" points="{" ".join(pts + back)}"/>')
        edges.append((cls, " ".join(pts)))
        ends.append([(short or {}).get(name, name), (y_of(lower[-1]) + y_of(upper[-1])) / 2, values[-1]])
        lower = upper
    for k, (cls, pts) in enumerate(edges):  # surface gap between bands, then the band's own top edge
        if k < len(edges) - 1:
            out.append(f'<polyline class="gap" points="{pts}"/>')
        out.append(f'<polyline class="edge {cls}" points="{pts}"/>')

    # names at the right end, pushed apart so that thin bands do not overlap their neighbours
    for k in range(1, len(ends)):
        ends[k][1] = min(ends[k][1], ends[k - 1][1] - 15)
    for name, y, last in ends:
        out.append(f'<text x="{xs[-1] + 8:.1f}" y="{y + 4:.1f}"><tspan class="value">{_fmt(last)}</tspan> {_esc(name)}</text>')

    band = plot_w / max(len(years) - 1, 1)
    for k, (x, year) in enumerate(zip(xs, years)):
        parts = ", ".join(f"{_fmt(values[k])} {name}" for _, name, values in series)
        note = " (list still being completed)" if year in provisional else ""
        out.append(f'<rect class="hit" x="{max(x - band / 2, left):.1f}" y="{top}" '
                   f'width="{min(band, x + band / 2 - left, left + plot_w - x + band / 2):.1f}" height="{plot_h}">'
                   f'<title>{year}{note}: {parts}; total {_fmt(totals[k])}</title></rect>')
    out.append("</svg>")
    return "".join(out)
