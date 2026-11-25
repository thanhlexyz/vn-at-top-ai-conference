import collections
import itertools
import math
import random

from common import PARENT, norm_title, slugify, vn_institutions

W, H = 1000, 720
BIG_GROUP = 5
BAND_HEIGHT = 360


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


def pull(w):
    return w ** 0.8


def force(ids, edges, size, seed=7, steps=700):
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
            f = d * d / k * pull(w)
            disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f
            disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
        for i in pos:
            d = max(math.hypot(*disp[i]), 0.01)
            pos[i][0] += disp[i][0] / d * min(d, temp)
            pos[i][1] += disp[i][1] / d * min(d, temp)
        temp = max(temp * 0.99, 0.5)
    return pos


def declutter(pos, labels, rounds=300):
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
                if oy < ox:
                    up, down = (a, b) if ay <= by else (b, a)
                    pos[up][1] -= oy / 2 + 0.5
                    pos[down][1] += oy / 2 + 0.5
                else:
                    pos[left][0] -= ox / 2 + 0.5
                    pos[right][0] += ox / 2 + 0.5
        if not moved:
            break
    return pos


def clear_edges(pos, edges, gap=36, rounds=200):
    edges = [e for e in edges if e[0] in pos and e[1] in pos]
    for _ in range(rounds):
        moved = False
        for (a, b) in edges:
            (ax, ay), (bx, by) = pos[a], pos[b]
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            if length2 < 1:
                continue
            for c, (cx, cy) in pos.items():
                if c in (a, b):
                    continue
                t = ((cx - ax) * dx + (cy - ay) * dy) / length2
                if not 0.05 < t < 0.95:
                    continue
                px, py = ax + t * dx, ay + t * dy
                d = math.hypot(cx - px, cy - py)
                if d >= gap:
                    continue
                nx, ny = (-dy, dx) if d < 0.5 else (cx - px, cy - py)
                norm = math.hypot(nx, ny)
                step = (gap - d) * 0.6 + 0.5
                pos[c][0] += nx / norm * step
                pos[c][1] += ny / norm * step
                moved = True
        if not moved:
            break
    return pos


def crosses(p1, p2, p3, p4):
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def crossings(pos, edges):
    edges = [e for e in edges if e[0] in pos and e[1] in pos]
    return sum(1 for (a, b), (x, y) in itertools.combinations(edges, 2)
               if len({a, b, x, y}) == 4 and crosses(pos[a], pos[b], pos[x], pos[y]))


def planar_starts(ids, edges):
    try:
        import networkx as nx
    except ImportError:
        return []
    G = nx.Graph([e for e in edges if e[0] in ids and e[1] in ids])
    if nx.check_planarity(G)[0]:
        graphs = [G]
    else:
        graphs = []
        for e in G.edges():
            H = G.copy()
            H.remove_edge(*e)
            if nx.check_planarity(H)[0]:
                graphs.append(H)
    out = []
    for H in graphs:
        p = nx.planar_layout(H)
        xs, ys = [v[0] for v in p.values()], [v[1] for v in p.values()]
        sc = min((W - 260) / max(max(xs) - min(xs), 1e-9), 640 / max(max(ys) - min(ys), 1e-9))
        out.append(({i: [40 + (p[i][0] - min(xs)) * sc, 40 + (p[i][1] - min(ys)) * sc] for i in ids}, set(H.edges())))
    return out


def rest_length(w):
    return REST * pull(w) ** (-1 / 3)


def kk_start(ids, edges):
    try:
        import networkx as nx
    except ImportError:
        return None
    G = nx.Graph()
    for (a, b), w in edges.items():
        if a in ids and b in ids:
            G.add_edge(a, b, length=rest_length(w))
    p = nx.kamada_kawai_layout(G, weight="length")
    return {i: list(p[i]) for i in ids}


def stress(pos, edges):
    pairs = [(math.dist(pos[a], pos[b]), rest_length(w)) for (a, b), w in edges.items() if a in pos and b in pos]
    if not pairs:
        return 0.0
    s = sum(d * l for d, l in pairs) / max(sum(d * d for d, _ in pairs), 1e-9)
    return sum((s * d - l) ** 2 for d, l in pairs) / sum(l * l for _, l in pairs)


def relax_planar(pos, edges, steps=400, weights=None):
    weights = weights if weights is not None else (edges if hasattr(edges, "items") else {})
    edges = [e for e in edges if e[0] in pos and e[1] in pos]
    ids = list(pos)
    k = math.sqrt((W - 260) * 640 / len(ids)) * 0.7
    temp = k

    def mine_crossing(p, i):
        return sum(1 for (a, b) in edges if i in (a, b) for (x, y) in edges
                   if len({a, b, x, y}) == 4 and crosses(p[a], p[b], p[x], p[y]))

    def creates_crossing(i, xy):
        trial = dict(pos)
        trial[i] = xy
        return mine_crossing(trial, i) > mine_crossing(pos, i)
    for _ in range(steps):
        for i in ids:
            fx = fy = 0.0
            for j in ids:
                if j == i:
                    continue
                dx, dy = pos[i][0] - pos[j][0], pos[i][1] - pos[j][1]
                d = max(math.hypot(dx, dy), 0.01)
                fx += dx / d * k * k / d
                fy += dy / d * k * k / d
            for (a, b) in edges:
                if i in (a, b):
                    j = b if a == i else a
                    dx, dy = pos[i][0] - pos[j][0], pos[i][1] - pos[j][1]
                    d = max(math.hypot(dx, dy), 0.01)
                    w = pull((weights or {}).get((a, b), (weights or {}).get((b, a), 1)))
                    fx -= dx / d * d * d / k * w
                    fy -= dy / d * d * d / k * w
            d = max(math.hypot(fx, fy), 0.01)
            step = min(d, temp)
            for scale in (1.0, 0.5, 0.25):
                xy = [pos[i][0] + fx / d * step * scale, pos[i][1] + fy / d * step * scale]
                if not creates_crossing(i, xy):
                    pos[i] = xy
                    break
        temp = max(temp * 0.985, 1.0)
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    s = min((W - 260) / max(max(xs) - min(xs), 1), 640 / max(max(ys) - min(ys), 1))
    return {i: [40 + (p[0] - min(xs)) * s, 40 + (p[1] - min(ys)) * s] for i, p in pos.items()}


def rule_breaks(pos, edges, labels, gap=40):
    box = {i: (18 + 8.4 * len(labels[i]), 24) for i in pos}
    n = 0
    for (a, b) in [e for e in edges if e[0] in pos and e[1] in pos]:
        (ax, ay), (bx, by) = pos[a], pos[b]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy or 1
        for c, (cx, cy) in pos.items():
            if c not in (a, b):
                t = ((cx - ax) * dx + (cy - ay) * dy) / l2
                n += 0 < t < 1 and math.hypot(cx - ax - t * dx, cy - ay - t * dy) < gap
    for a, b in itertools.combinations(pos, 2):
        (ax, ay), (bx, by) = pos[a], pos[b]
        left, right = (a, b) if ax <= bx else (b, a)
        n += pos[left][0] + box[left][0] > pos[right][0] and abs(ay - by) < 24
        n += math.hypot(ax - bx, ay - by) < 40
    return n


REST = 190


def untangle(pos, edges, labels, rounds=40, gap=40, cross_cost=100000):
    weight = {e: w for e, w in edges.items()} if hasattr(edges, "items") else {}
    edges = [e for e in edges if e[0] in pos and e[1] in pos]
    box = {i: (18 + 8.4 * len(labels[i]), 24) for i in pos}

    def cost(p, ids=None):
        c = 0.0
        for (a, b), (x, y) in itertools.combinations(edges, 2):
            if len({a, b, x, y}) == 4 and crosses(p[a], p[b], p[x], p[y]):
                c += cross_cost
        for (a, b) in edges:
            (ax, ay), (bx, by) = p[a], p[b]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy or 1
            c += 0.004 * (math.sqrt(l2) - rest_length(weight.get((a, b), 1))) ** 2
            for n, (cx, cy) in p.items():
                if n in (a, b):
                    continue
                t = ((cx - ax) * dx + (cy - ay) * dy) / l2
                if 0 < t < 1 and math.hypot(cx - ax - t * dx, cy - ay - t * dy) < gap:
                    c += 300
        for a, b in itertools.combinations(p, 2):
            (ax, ay), (bx, by) = p[a], p[b]
            left, right = (a, b) if ax <= bx else (b, a)
            if p[left][0] + box[left][0] > p[right][0] and abs(ay - by) < 24:
                c += 100
            if math.hypot(ax - bx, ay - by) < 40:
                c += 100
        return c

    current = cost(pos)
    home = {i: tuple(v) for i, v in pos.items()}
    degree = collections.Counter(n for e in edges for n in e)
    leaves = {i: [b if a == i else a for a, b in edges if i in (a, b) and degree[b if a == i else a] == 1]
              for i in pos}
    for _ in range(rounds):
        improved = False
        for i in sorted(pos):
            best, best_xy = current, None
            ox, oy = pos[i]
            carried = {j: list(pos[j]) for j in leaves[i]}
            spots = [(ox + r * math.cos(k * math.pi / 8), oy + r * math.sin(k * math.pi / 8))
                     for r in (15, 30, 50, 75, 110, 150, 210, 280, 360) for k in range(16)]
            for (a, b) in edges:
                if i not in (a, b):
                    continue
                for (x, y) in edges:
                    if len({a, b, x, y}) == 4 and crosses(pos[a], pos[b], pos[x], pos[y]):
                        (x1, y1), (x2, y2) = pos[x], pos[y]
                        dx, dy = x2 - x1, y2 - y1
                        t = ((ox - x1) * dx + (oy - y1) * dy) / (dx * dx + dy * dy or 1)
                        fx, fy = x1 + t * dx, y1 + t * dy
                        for push in (1.0, 1.4, 2.0):
                            spots.append((fx + (fx - ox) * push, fy + (fy - oy) * push))
            for nx, ny in spots:
                pos[i] = [nx, ny]
                for j, (jx, jy) in carried.items():
                    pos[j] = [jx + nx - ox, jy + ny - oy]
                c = cost(pos) + 0.05 * math.hypot(nx - home[i][0], ny - home[i][1])
                if c < best - 1:
                    best, best_xy = c, (nx, ny)
            pos[i] = [ox, oy] if best_xy is None else list(best_xy)
            for j, (jx, jy) in carried.items():
                pos[j] = [jx, jy] if best_xy is None else [jx + best_xy[0] - ox, jy + best_xy[1] - oy]
            if best_xy is not None:
                current = cost(pos)
                improved = True
        if not improved or current == 0:
            break
    return pos


def fan_hub(group, edges):
    if len(group) < 3:
        return None
    links = [(a, b) for a, b in edges if a in group and b in group]
    degree = {i: sum(i in e for e in links) for i in group}
    if max(degree.values()) < 3 and len(links) < len(group):
        return None
    return next((i for i in sorted(group, key=lambda i: -degree[i]) if degree[i] == len(group) - 1), None)


def lie_flat(pos):
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    angle = -0.5 * math.atan2(2 * sxy, sxx - syy)
    c, s = math.cos(angle), math.sin(angle)
    return {i: [(p[0] - mx) * c - (p[1] - my) * s, (p[0] - mx) * s + (p[1] - my) * c] for i, p in pos.items()}


def layout(nodes, edges, labels, prefer="weights"):
    groups = components(sorted(nodes), edges)
    if not groups:
        return {}, 200
    bands = [groups[0]] + [g for g in groups[1:] if len(g) >= BIG_GROUP]
    rest = [g for g in groups[1:] if len(g) < BIG_GROUP]

    def draw(members, cap, top):
        def fit(pos):
            xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
            span_x, span_y = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
            s = min((W - 260) / span_x, cap / span_y)
            return {i: [40 + (p[0] - min(xs)) * s, 40 + (p[1] - min(ys)) * s] for i, p in pos.items()}

        def attempt(seed):
            raw = force(members, edges, size=95, seed=seed)
            pos = fit(lie_flat(raw) if top > 70 else raw)
            for _ in range(4):
                pos = clear_edges(pos, edges)
                pos = declutter(pos, labels)
            pos = clear_edges(pos, edges)
            return untangle(pos, edges, labels, cross_cost=100000 if prefer == "rules" else 300)

        starts = [lambda seed=seed: attempt(seed) for seed in (7, 11, 23, 42, 101, 211)]
        kk = kk_start(members, edges)
        if kk:
            starts.append(lambda: untangle(fit(lie_flat(kk) if top > 70 else kk), edges, labels))
        best = None
        for make in starts:
            pos = make()
            score = (crossings(pos, edges), rule_breaks(pos, edges, labels), stress(pos, edges))
            if prefer != "rules":
                score = (rule_breaks(pos, edges, labels) + score[0], score[0], stress(pos, edges))
            if best is None or score < best[0]:
                best = (score, pos)
        if prefer == "rules" and best[0][0]:
            for start, kept in planar_starts(members, edges):
                pos = untangle(fit(relax_planar(start, edges)), edges, labels)
                score = (crossings(pos, edges), rule_breaks(pos, edges, labels), stress(pos, edges))
                if score < best[0]:
                    best = (score, pos)
        pos = best[1]
        xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
        margin = 20 + max(7.4 * len(labels[i]) for i in pos) / 2
        room = W - 2 * margin
        if max(xs) - min(xs) > room:
            s = room / (max(xs) - min(xs))
            pos = {i: [min(xs) + (p[0] - min(xs)) * s, min(ys) + (p[1] - min(ys)) * s] for i, p in pos.items()}
            xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
        shift_x = (W - (max(xs) - min(xs))) / 2 - min(xs)
        shift_y = top - min(ys)
        return {i: [p[0] + shift_x, p[1] + shift_y] for i, p in pos.items()}

    out, top = {}, 70
    for k, g in enumerate(bands):
        placed = draw(g, 760 if k == 0 else BAND_HEIGHT, top)
        out.update(placed)
        top = max(p[1] for p in placed.values()) + (70 if k == len(bands) - 1 else 110)
    longest = max((7.4 * len(labels[i]) for g in rest for i in g), default=0)
    cell_w, step = max(250, round(longest + 18 + 40 + 30)), 46
    cols = max(1, W // cell_w)
    row_y, col, row_h = top, 0, 0

    def walk(members):
        order = [members[0]]
        while len(order) < len(members):
            nxt = next((b for a in reversed(order) for b in members if b not in order and
                        ((a, b) in edges or (b, a) in edges)), next(b for b in members if b not in order))
            order.append(nxt)
        return order

    for g in rest:
        hub = fan_hub(g, edges)
        if hub:
            leaves = walk([i for i in g if i != hub])
            hub_w, reach = CHAR * len(labels[hub]) + 30, 110
            span = -(-round(hub_w + reach + max(7.4 * len(labels[i]) for i in leaves) + 50) // cell_w)
        else:
            span = 1
        if col and col + span > cols:
            col, row_y, row_h = 0, row_y + row_h, 0
        x0 = 30 + col * cell_w
        if hub:
            for k, i in enumerate(leaves):
                out[i] = [x0 + hub_w + reach, row_y + k * step]
            out[hub] = [x0 + hub_w, row_y + (len(leaves) - 1) * step / 2]
            row_h = max(row_h, (len(leaves) - 1) * step + 50)
        else:
            for k, i in enumerate(walk(g)):
                out[i] = [x0 + (18 if k % 2 else 0), row_y + k * step]
            row_h = max(row_h, (len(g) - 1) * step + 50)
        col += span
        if col >= cols:
            col, row_y, row_h = 0, row_y + row_h, 0
    height = (row_y + row_h if col else row_y) + 10
    return {i: (round(p[0], 1), round(p[1], 1)) for i, p in out.items()}, round(max(height, top))


CHAR, LINE = 8.2, 18


def seg_hits_box(x1, y1, x2, y2, bx0, by0, bx1, by1):
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


def weight_spots(pos, radius, edges, weights, avoid=()):
    out, boxes = {}, list(avoid)
    for (a, b) in sorted(edges, key=lambda e: -weights.get(e, 1)):
        if weights.get((a, b), 1) < 2:
            continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        best = None
        for t in (0.5, 0.42, 0.58, 0.35, 0.65, 0.28, 0.72):
            x, y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            box = (x - 13, y - 12, x + 13, y + 10)
            cost = 100 * sum(seg_hits_box(*pos[c], *pos[d], *box) for c, d in edges if {c, d} != {a, b})
            cost += 100 * sum(box[0] - r < cx < box[2] + r and box[1] - r < cy < box[3] + r
                              for i, (cx, cy) in pos.items() if (r := radius.get(i)) is not None)
            cost += 100 * sum(not (box[2] < o[0] or o[2] < box[0] or box[3] < o[1] or o[3] < box[1]) for o in boxes)
            cost += abs(t - 0.5)
            if best is None or cost < best[0]:
                best = (cost, x, y, box)
        out[(a, b)] = (round(best[1], 1), round(best[2], 1))
        boxes.append(best[3])
    return out


def place_labels(nodes, pos, radius, edges, labels, weights=None, right_only=(), spots=None, left_only=()):
    segs = [(pos[a][0], pos[a][1], pos[b][0], pos[b][1], a, b) for a, b in edges]
    out = {}
    mid = {(a, b): ((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2) for a, b in edges}
    placed = [(x - 13, y - 12, x + 13, y + 10) for e in edges if (weights or {}).get(e, 1) >= 2
              for x, y in [(spots or mid).get(e, mid[e])]]
    for i in sorted(nodes, key=lambda i: -radius[i]):
        x, y, r, w = pos[i][0], pos[i][1], radius[i], CHAR * len(labels[i])
        options = [("start", x + r + 4, y + 5, (x + r + 2, y - LINE / 2, x + r + 6 + w, y + LINE / 2)),
                   ("end", x - r - 4, y + 5, (x - r - 6 - w, y - LINE / 2, x - r - 2, y + LINE / 2)),
                   ("middle", x, y - r - 7, (x - w / 2 - 2, y - r - 6 - LINE, x + w / 2 + 2, y - r - 4)),
                   ("middle", x, y + r + 17, (x - w / 2 - 2, y + r + 4, x + w / 2 + 2, y + r + 6 + LINE)),
                   ("start", x + 0.7 * r + 2, y + 0.7 * r + 16, (x + 0.7 * r, y + 0.7 * r + 2, x + 0.7 * r + 4 + w, y + 0.7 * r + 2 + LINE)),
                   ("start", x + 0.7 * r + 2, y - 0.7 * r - 6, (x + 0.7 * r, y - 0.7 * r - 2 - LINE, x + 0.7 * r + 4 + w, y - 0.7 * r - 2)),
                   ("end", x - 0.7 * r - 2, y + 0.7 * r + 16, (x - 0.7 * r - 4 - w, y + 0.7 * r + 2, x - 0.7 * r, y + 0.7 * r + 2 + LINE)),
                   ("end", x - 0.7 * r - 2, y - 0.7 * r - 6, (x - 0.7 * r - 4 - w, y - 0.7 * r - 2 - LINE, x - 0.7 * r, y - 0.7 * r - 2))]
        if i in left_only:
            options = options[1:2]
        elif i in right_only:
            options = options[:1]
        best = None
        for k, (anchor, lx, ly, box) in enumerate(options):
            bx0, by0, bx1, by1 = box
            cost = 10 * sum(seg_hits_box(*sg[:4], *box) for sg in segs)
            cost += 10 * sum(1 for j in nodes if j != i and bx0 - radius[j] < pos[j][0] < bx1 + radius[j]
                             and by0 - radius[j] < pos[j][1] < by1 + radius[j])
            cost += 10 * sum(1 for p in placed if not (box[2] < p[0] or p[2] < box[0] or box[3] < p[1] or p[3] < box[1]))
            cost += 1000 * (box[0] < 0 or box[2] > W)
            cost += k * 0.5
            if best is None or cost < best[0]:
                best = (cost, anchor, lx, ly, box)
        placed.append(best[4])
        out[i] = (round(best[2], 1), round(best[3], 1), best[1])
    return out


def build(nodes, papers_of, color_of, legend):
    edges, count = collections.Counter(), collections.Counter()
    for members in papers_of.values():
        for m in members:
            count[m] += 1
        for a, b in itertools.combinations(sorted(members), 2):
            edges[(a, b)] += 1
    linked = {m for e in edges for m in e}
    text = {i: max(nodes[i]["name"], nodes[i].get("name_vi") or "", key=len) for i in nodes}
    pos, height = layout(linked, edges, {i: text[i] for i in linked})
    out_nodes = []
    for i, n in nodes.items():
        if not count[i]:
            continue
        x, y = pos.get(i, (None, None))
        out_nodes.append({**n, "id": i, "papers": count[i], "x": x, "y": y, "linked": i in linked,
                          "r": round(9 + 1.8 * math.sqrt(count[i]), 1), "color": color_of(n),
                          "degree": sum(1 for e in edges if i in e)})
    radius = {n["id"]: n["r"] for n in out_nodes if n["linked"]}
    groups = components(sorted(linked), edges)
    small = {i for g in groups[1:] if len(g) < BIG_GROUP for i in g}
    hubs = {h for g in groups[1:] if len(g) < BIG_GROUP and (h := fan_hub(g, edges))}
    numbers = weight_spots(pos, radius, list(edges), edges)
    spots = place_labels(list(radius), pos, radius, list(edges), {i: text[i] for i in radius}, edges,
                         right_only=small - hubs, spots=numbers, left_only=hubs)
    label_boxes = []
    for i, (lx, ly, anchor) in spots.items():
        w = CHAR * len(text[i])
        x0 = {"start": lx, "end": lx - w, "middle": lx - w / 2}[anchor]
        label_boxes.append((x0 - 2, ly - 14, x0 + w + 2, ly + 4))
    numbers = weight_spots(pos, radius, list(edges), edges, avoid=label_boxes)
    for n in out_nodes:
        if n["id"] in spots:
            n["lx"], n["ly"], n["anchor"] = spots[n["id"]]
    out_nodes.sort(key=lambda n: (-n["papers"], n["name"]))
    by_id = {n["id"]: n for n in out_nodes}
    out_edges = [{"a": a, "b": b, "weight": w, "x1": pos[a][0], "y1": pos[a][1], "x2": pos[b][0], "y2": pos[b][1],
                  "width": round(1 + 1.6 * math.sqrt(w - 1), 1),
                  "wx": numbers.get((a, b), (0, 0))[0], "wy": numbers.get((a, b), (0, 0))[1],
                  "a_name": by_id[a]["name"], "b_name": by_id[b]["name"],
                  "a_name_vi": by_id[a].get("name_vi") or by_id[a]["name"],
                  "b_name_vi": by_id[b].get("name_vi") or by_id[b]["name"]}
                 for (a, b), w in sorted(edges.items(), key=lambda e: (-e[1], e[0]))]
    return {"width": W, "height": height, "nodes": out_nodes, "edges": out_edges, "legend": legend,
            "papers": len(papers_of), "shared": sum(1 for m in papers_of.values() if len(m) > 1)}


BRAND = {"HUST": "c-red", "VinUni": "c-blue", "HCMUS": "c-cyan"}
REST_COLORS = ["g-ochre", "g-green", "g-purple", "ring g-ochre", "ring g-green", "ring g-purple"]


def color_of_group(g, top):
    rest = [x for x in top if x not in BRAND]
    return BRAND[g] if g in BRAND else REST_COLORS[rest.index(g)]


def researcher_graph(professors, records):
    papers_of = collections.defaultdict(set)
    for r, p in records:
        papers_of[paper_key(r)].add(p["slug"])
    nodes = {p["slug"]: {"name": p["name"], "name_vi": p.get("name_vi") or p["name"], "url": f"professors/{p['slug']}/",
                         "group": p["institution_short"]} for p in professors}
    size = collections.Counter(p["institution_short"] for p in professors if any(p["slug"] in m for m in papers_of.values()))
    ranked = [g for g, _ in size.most_common()]
    ranked = [g for g in ranked if size[g] > 1 or g in BRAND]
    top = [g for g in ranked if g in BRAND] + [g for g in ranked if g not in BRAND][:len(REST_COLORS)]
    top.sort(key=ranked.index)
    color = {g: color_of_group(g, top) for g in top}
    top.sort(key=lambda g: (color[g].startswith("ring"), ranked.index(g)))
    legend = [{"label": g, "color": color[g]} for g in top] + [{"label": "", "color": "c0"}]
    return build(nodes, papers_of, lambda n: color.get(n["group"], "c0"), legend)


def institution_links(professors, records):
    roster = {}
    for p in professors:
        roster.setdefault(p["institution_slug"], {"name": p["institution"], "short": p["institution_short"]})

    def resolve(full, short):
        exact = [s for s, i in roster.items() if i["short"] == short or i["name"] == full]
        return exact[0] if exact else None

    nodes = {s: {"name": i["short"], "full": i["name"], "url": f"universities/{s}/"} for s, i in roster.items()}
    papers_of = collections.defaultdict(set)
    for r, p in records:
        members = papers_of[paper_key(r)]
        members.add(p["institution_slug"])
        for a in r.get("people") or []:
            for full, short, _ in vn_institutions(a.get("aff") or ""):
                if full == short:
                    continue
                if resolve(full, short) is not None or any(PARENT.get(i["short"]) == short for i in roster.values()):
                    continue
                s = "x-" + slugify(short)
                nodes.setdefault(s, {"name": short, "full": full, "url": ""})
                members.add(s)
    for members in papers_of.values():
        shorts = {nodes[m]["name"] for m in members}
        for m in list(members):
            if any(PARENT.get(x) == nodes[m]["name"] for x in shorts):
                members.discard(m)
    edges = collections.Counter()
    for members in papers_of.values():
        for a, b in itertools.combinations(sorted(members), 2):
            edges[(a, b)] += 1
    linked = {m for e in edges for m in e}
    return {"nodes": [{"id": s, "name": n["name"], "full": n["full"], "url": n["url"]} for s, n in sorted(nodes.items()) if s in linked],
            "edges": [{"a": a, "b": b, "weight": w} for (a, b), w in sorted(edges.items(), key=lambda e: (-e[1], e[0]))]}
