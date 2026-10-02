"""Collaboration graphs for the site: researchers on the roster, and institutions in Vietnam.

An edge joins two nodes that share papers; its weight is the number of distinct papers they share. Papers are
every counted submission (accepted, rejected, withdrawn) plus workshop papers, from the years a person worked in
Vietnam. The layout is computed here, once, with a seeded force simulation, so the page needs no script to draw it.
"""
import collections
import itertools
import math
import random

from common import PARENT, norm_title, slugify, vn_institutions

W, H = 1000, 720   # layout box; the page scales the SVG to its width


def paper_key(r):
    return (r["venue"], r["year"], norm_title(r["title"]))


def components(ids, edges):
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in edges:
        parent[find(a)] = find(b)
    groups = collections.defaultdict(list)
    for i in ids:
        groups[find(i)].append(i)
    return sorted(groups.values(), key=lambda g: (-len(g), sorted(g)))


def force(ids, edges, size, seed=7, steps=700):
    """Fruchterman-Reingold positions for one connected group, in arbitrary units."""
    rng = random.Random(seed)
    n = len(ids)
    pos = {i: [math.cos(2 * math.pi * k / n) * 100 + rng.uniform(-3, 3),
               math.sin(2 * math.pi * k / n) * 100 + rng.uniform(-3, 3)] for k, i in enumerate(sorted(ids))}
    k = size
    temp = 4 * k
    mine = {e: w for e, w in edges.items() if e[0] in pos}
    for _ in range(steps):
        disp = {i: [0.0, 0.0] for i in pos}
        for a, b in itertools.combinations(pos, 2):
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = max(math.hypot(dx, dy), 0.01)
            f = k * k / d
            disp[a][0] += dx / d * f; disp[a][1] += dy / d * f
            disp[b][0] -= dx / d * f; disp[b][1] -= dy / d * f
        for (a, b), w in mine.items():
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = max(math.hypot(dx, dy), 0.01)
            f = d * d / k * (1 + 0.5 * math.log(w))
            disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f
            disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
        for i in pos:
            d = max(math.hypot(*disp[i]), 0.01)
            pos[i][0] += disp[i][0] / d * min(d, temp)
            pos[i][1] += disp[i][1] / d * min(d, temp)
        temp = max(temp * 0.99, 0.5)
    return pos


def declutter(pos, labels, rounds=300):
    """Pushes apart nodes whose labels (drawn to the right of the circle) overlap."""
    box = {i: (18 + 8.4 * len(labels[i]), 24) for i in pos}
    for _ in range(rounds):
        moved = False
        for a, b in itertools.combinations(pos, 2):
            (ax, ay), (bx, by) = pos[a], pos[b]
            left, right = (a, b) if ax <= bx else (b, a)
            ox = pos[left][0] + box[left][0] - pos[right][0]
            oy = (box[a][1] + box[b][1]) / 2 - abs(ay - by)
            if ox > 0 and oy > 0:
                moved = True
                if oy < ox:   # cheaper to move apart vertically
                    up, down = (a, b) if ay <= by else (b, a)
                    pos[up][1] -= oy / 2 + 0.5
                    pos[down][1] += oy / 2 + 0.5
                else:
                    pos[left][0] -= ox / 2 + 0.5
                    pos[right][0] += ox / 2 + 0.5
        if not moved:
            break
    return pos


def layout(nodes, edges, labels):
    """{id: (x, y)} and the drawing's height. The largest group is drawn with a force layout across the full
    width; smaller groups go underneath in a grid, each a short column, so their labels never collide."""
    groups = components(sorted(nodes), edges)
    if not groups:
        return {}, 200
    main, rest = groups[0], groups[1:]
    pos = force(main, edges, size=95)
    # scale the main group to the width, keeping its proportions, then remove label overlaps
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    span_x, span_y = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
    s = min((W - 260) / span_x, 640 / span_y)
    pos = {i: [40 + (p[0] - min(xs)) * s, 40 + (p[1] - min(ys)) * s] for i, p in pos.items()}
    pos = declutter(pos, labels)
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    shift_x = (W - (max(xs) - min(xs)) - max(7.4 * len(labels[i]) for i in pos)) / 2 - min(xs)
    shift_y = 40 - min(ys)
    out = {i: [p[0] + shift_x, p[1] + shift_y] for i, p in pos.items()}
    top = max(p[1] for p in out.values()) + 70
    # small groups: columns of nodes 34 px apart, laid out in cells across the width
    cell_w, step = 250, 34
    cols = max(1, W // cell_w)
    row_y, col, row_h = top, 0, 0
    for g in rest:
        order = [g[0]]
        while len(order) < len(g):   # walk along the links so neighbours sit next to each other
            nxt = next((b for a in reversed(order) for b in g if b not in order and
                        ((a, b) in edges or (b, a) in edges)), next(b for b in g if b not in order))
            order.append(nxt)
        x0 = 30 + col * cell_w
        for k, i in enumerate(order):
            out[i] = [x0 + (18 if k % 2 else 0), row_y + k * step]
        row_h = max(row_h, (len(g) - 1) * step + 50)
        col += 1
        if col == cols:
            col, row_y, row_h = 0, row_y + row_h, 0
    height = (row_y + row_h if col else row_y) + 10
    return {i: (round(p[0], 1), round(p[1], 1)) for i, p in out.items()}, round(max(height, top))


CHAR, LINE = 8.2, 18   # approximate label size at 14px, in layout units


def seg_hits_box(x1, y1, x2, y2, bx0, by0, bx1, by1):
    """True if the segment (x1, y1)-(x2, y2) passes through the rectangle."""
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def place_labels(nodes, pos, radius, edges, labels, weights=None):
    """{id: (x, y, anchor)}: for each node the label position, out of right, left, above and below, that crosses
    the fewest edges, circles and labels already placed. Bigger nodes choose first."""
    segs = [(pos[a][0], pos[a][1], pos[b][0], pos[b][1], a, b) for a, b in edges]
    out = {}
    # the weight printed in the middle of a line counts as a label already there
    placed = [((pos[a][0] + pos[b][0]) / 2 - 8, (pos[a][1] + pos[b][1]) / 2 - 9,
               (pos[a][0] + pos[b][0]) / 2 + 8, (pos[a][1] + pos[b][1]) / 2 + 7)
              for (a, b) in edges if (weights or {}).get((a, b), 1) >= 2]
    for i in sorted(nodes, key=lambda i: -radius[i]):
        x, y, r, w = pos[i][0], pos[i][1], radius[i], CHAR * len(labels[i])
        options = [("start", x + r + 4, y + 5, (x + r + 2, y - LINE / 2, x + r + 6 + w, y + LINE / 2)),
                   ("end", x - r - 4, y + 5, (x - r - 6 - w, y - LINE / 2, x - r - 2, y + LINE / 2)),
                   ("middle", x, y - r - 7, (x - w / 2 - 2, y - r - 6 - LINE, x + w / 2 + 2, y - r - 4)),
                   ("middle", x, y + r + 17, (x - w / 2 - 2, y + r + 4, x + w / 2 + 2, y + r + 6 + LINE))]
        best = None
        for k, (anchor, lx, ly, box) in enumerate(options):
            bx0, by0, bx1, by1 = box
            cost = 10 * sum(seg_hits_box(*sg[:4], *box) for sg in segs)
            cost += 10 * sum(1 for j in nodes if j != i and bx0 - radius[j] < pos[j][0] < bx1 + radius[j]
                             and by0 - radius[j] < pos[j][1] < by1 + radius[j])
            cost += 10 * sum(1 for p in placed if not (box[2] < p[0] or p[2] < box[0] or box[3] < p[1] or p[3] < box[1]))
            cost += 20 * (box[0] < 0 or box[2] > W)
            cost += k * 0.5   # prefer the right, then the left
            if best is None or cost < best[0]:
                best = (cost, anchor, lx, ly, box)
        placed.append(best[4])
        out[i] = (round(best[2], 1), round(best[3], 1), best[1])
    return out


def build(nodes, papers_of, color_of, legend):
    """nodes: {id: dict}; papers_of: {paper key: set of node ids}. Returns the page data."""
    edges, count = collections.Counter(), collections.Counter()
    for members in papers_of.values():
        for m in members:
            count[m] += 1
        for a, b in itertools.combinations(sorted(members), 2):
            edges[(a, b)] += 1
    linked = {m for e in edges for m in e}
    pos, height = layout(linked, edges, {i: nodes[i]["name"] for i in linked})
    out_nodes = []
    for i, n in nodes.items():
        if not count[i]:
            continue
        x, y = pos.get(i, (None, None))
        out_nodes.append({**n, "id": i, "papers": count[i], "x": x, "y": y, "linked": i in linked,
                          "r": round(5 + 2.2 * math.sqrt(count[i]), 1), "color": color_of(n),
                          "degree": sum(1 for e in edges if i in e)})
    radius = {n["id"]: n["r"] for n in out_nodes if n["linked"]}
    spots = place_labels(list(radius), pos, radius, list(edges), {i: nodes[i]["name"] for i in radius}, edges)
    for n in out_nodes:
        if n["id"] in spots:
            n["lx"], n["ly"], n["anchor"] = spots[n["id"]]
    out_nodes.sort(key=lambda n: (-n["papers"], n["name"]))
    by_id = {n["id"]: n for n in out_nodes}
    out_edges = [{"a": a, "b": b, "weight": w, "x1": pos[a][0], "y1": pos[a][1], "x2": pos[b][0], "y2": pos[b][1],
                  "width": round(1 + 1.6 * math.sqrt(w - 1), 1),
                  "a_name": by_id[a]["name"], "b_name": by_id[b]["name"],
                  "a_name_vi": by_id[a].get("name_vi") or by_id[a]["name"],
                  "b_name_vi": by_id[b].get("name_vi") or by_id[b]["name"]}
                 for (a, b), w in sorted(edges.items(), key=lambda e: (-e[1], e[0]))]
    return {"width": W, "height": height, "nodes": out_nodes, "edges": out_edges, "legend": legend,
            "papers": len(papers_of), "shared": sum(1 for m in papers_of.values() if len(m) > 1)}


PALETTE = ["c1", "c2", "c3", "c4"]   # classes styled in style.css; the rest are "c0" (other)


def researcher_graph(professors, records):
    """records: [(paper record, professor entry)] for every counted and workshop paper."""
    papers_of = collections.defaultdict(set)
    for r, p in records:
        papers_of[paper_key(r)].add(p["slug"])
    nodes = {p["slug"]: {"name": p["name"], "name_vi": p.get("name_vi") or p["name"], "url": f"professors/{p['slug']}/",
                         "group": p["institution_short"]} for p in professors}
    size = collections.Counter(p["institution_short"] for p in professors if any(p["slug"] in m for m in papers_of.values()))
    top = [g for g, _ in size.most_common(len(PALETTE))]
    color = {g: PALETTE[k] for k, g in enumerate(top)}
    legend = [{"label": g, "color": color[g]} for g in top] + [{"label": "", "color": "c0"}]
    return build(nodes, papers_of, lambda n: color.get(n["group"], "c0"), legend)


def institution_graph(professors, records):
    """Institutions in Vietnam: the roster institution of every listed author on a paper, plus the Vietnamese
    institutions printed on the paper where the source gives affiliations. Institutions abroad are left out."""
    roster = {}
    for p in professors:
        roster.setdefault(p["institution_slug"], {"name": p["institution"], "short": p["institution_short"]})

    def resolve(full, short):
        exact = [s for s, i in roster.items() if i["short"] == short or i["name"] == full]
        return exact[0] if exact else None

    nodes = {s: {"name": i["short"], "name_vi": i["short"], "full": i["name"], "url": f"institutions/{s}/",
                 "group": "roster"} for s, i in roster.items()}
    papers_of = collections.defaultdict(set)
    for r, p in records:
        members = papers_of[paper_key(r)]
        members.add(p["institution_slug"])
        for a in r.get("people") or []:
            for full, short, _ in vn_institutions(a.get("aff") or ""):
                if full == short:   # a generic match ("University of ... Vietnam"), not a known institution
                    continue
                s = resolve(full, short)
                if s is None:
                    s = "x-" + slugify(short)
                    nodes.setdefault(s, {"name": short, "name_vi": short, "full": full, "url": "", "group": "other"})
                members.add(s)
    for members in papers_of.values():   # "University of Science, VNU-HCM" is one institution, not two
        shorts = {nodes[m]["name"] for m in members}
        for m in list(members):
            if any(PARENT.get(x) == nodes[m]["name"] for x in shorts):
                members.discard(m)
    legend = [{"label": "roster", "color": "c1"}, {"label": "other", "color": "c2"}]
    return build(nodes, papers_of, lambda n: "c1" if n["group"] == "roster" else "c2", legend)
