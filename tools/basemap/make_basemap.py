"""바다 지도 자료 만들기 → deploy/data/basemap.json
OpenStreetMap(© OpenStreetMap 기여자, ODbL) 육지·갯벌·섬 이름을 앱에 넣을 크기로 줄인다.
- 육지 두 단계: 멀리 볼 때(L0, 약 60m 단순화)와 가까이 볼 때(L1, 약 11m 단순화)
- 갯벌 두 단계
- 이름표: 섬(크기 순), 만(灣). 화면에 이 배율 이상일 때만 보이도록 최소 배율(minS, 1도당 화면 점 수)을 미리 계산
"""
import json, math, re
D = 'osm/'
LON0, LAT0, Q = 125.30, 35.10, 100000
KX = math.cos(math.radians(36.6))

def dp(pts, tol):
    if len(pts) < 4: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i][0] * KX, pts[i][1]; bx, by = pts[j][0] * KX, pts[j][1]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
        best, bi = -1, -1
        for m in range(i + 1, j):
            px, py = pts[m][0] * KX, pts[m][1]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L > 1e-12 else math.hypot(px - ax, py - ay)
            if d > best: best, bi = d, m
        if best > tol:
            keep[bi] = True; stack += [(i, bi), (bi, j)]
    return [p for p, f in zip(pts, keep) if f]

def simp_ring(r, tol):
    r = r[:-1] if r[0] == r[-1] else r
    if len(r) < 4: return r
    h = len(r) // 2
    return dp(r[:h + 1], tol)[:-1] + dp(r[h:] + [r[0]], tol)[:-1]

def area(r):   # 도² (경도는 KX 곱)
    a = 0
    for i in range(len(r)):
        x1, y1 = r[i - 1]; x2, y2 = r[i]
        a += (x1 * KX) * y2 - (x2 * KX) * y1
    return abs(a) / 2

def bbox(r):
    xs = [p[0] for p in r]; ys = [p[1] for p in r]
    return min(xs), min(ys), max(xs), max(ys)

def enc(r):
    q = [(round((x - LON0) * Q), round((y - LAT0) * Q)) for x, y in r]
    out = [q[0][0], q[0][1]]
    for a, b in zip(q, q[1:]):
        if a != b: out += [b[0] - a[0], b[1] - a[1]]
    return out

def polys_of(g):
    if g['type'] == 'GeometryCollection':
        out = []
        for x in g['geometries']: out += polys_of(x) if x['type'] in ('Polygon', 'MultiPolygon', 'GeometryCollection') else []
        return out
    return g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]

def level(g, tol, min_diag):
    out, npts = [], 0
    for poly in polys_of(g):
        outer = poly[0]; x0, y0, x1, y1 = bbox(outer)
        if math.hypot((x1 - x0) * KX, y1 - y0) < min_diag: continue
        rings = []
        for k, r in enumerate(poly):
            if k and (lambda b: math.hypot((b[2] - b[0]) * KX, b[3] - b[1]))(bbox(r)) < min_diag: continue
            s = simp_ring(r, tol)
            if len(s) >= 3: rings.append(enc(s)); npts += len(s)
        if rings: out.append(rings)
    return out, npts

land = json.load(open(D + 'land_union.geojson'))['geometry']
flats = json.load(open(D + 'flats_union.geojson'))['geometry']
L0, n0 = level(land, 0.0006, 0.004)
L1, n1 = level(land, 0.0001, 0.0004)
F0, m0 = level(flats, 0.0008, 0.01)
F1, m1 = level(flats, 0.00025, 0.002)
# 방조제 안 호수·저수지·큰 강 (OSM 육지 자료에는 땅으로 들어가 있어서 물로 다시 칠한다)
water = json.load(open(D + 'water_union.geojson'))['geometry']
# 바다와 먼 내륙(동경 127.05도 동쪽) 물은 빼고, 멀리 볼 때는 큰 것만
water = {'type': 'MultiPolygon', 'coordinates': [p for p in polys_of(water) if (lambda b: (b[0] + b[2]) / 2 < 127.05)(bbox(p[0]))]}
W0, w0 = level(water, 0.0008, 0.02)
W1, w1 = level(water, 0.0002, 0.003)
print('호수·강 W0', len(W0), w0, 'W1', len(W1), w1)
print('육지 L0', len(L0), n0, 'L1', len(L1), n1, '갯벌', m0, m1)

# ---------- 이름표
HAN = re.compile('[가-힣]')
def clean(name):
    name = re.sub(r'\s*[\(（].*?[\)）]\s*', '', name or '').strip()
    return name if HAN.search(name) and len(name) <= 8 else None

land_polys = [(bbox(p[0]), p[0], area(p[0])) for p in polys_of(land)]
def land_area_at(x, y):
    best = 0
    for (x0, y0, x1, y1), r, a in land_polys:
        if not (x0 <= x <= x1 and y0 <= y <= y1): continue
        c = False
        for i in range(len(r)):
            ax, ay = r[i - 1]; bx, by = r[i]
            if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay): c = not c
        if c: best = max(best, a)
    return best

def inside(r, x, y):
    c = False
    for i in range(len(r)):
        ax, ay = r[i - 1]; bx, by = r[i]
        if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay): c = not c
    return c

def edge_dist(r, x, y):
    best = 9e9
    for i in range(len(r)):
        ax, ay = r[i - 1]; bx, by = r[i]
        ax, bx, px = ax * KX, bx * KX, x * KX
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(px - ax - t * dx, y - ay - t * dy))
    return best

def label_point(r):
    """섬 안쪽에서 가장자리와 가장 먼 점 (격자로 찾고 한 번 더 좁힘)"""
    x0, y0, x1, y1 = bbox(r)
    best = None
    for it in range(2):
        n = 9
        for i in range(n + 1):
            for j in range(n + 1):
                x = x0 + (x1 - x0) * i / n; y = y0 + (y1 - y0) * j / n
                if not inside(r, x, y): continue
                d = edge_dist(r, x, y)
                if best is None or d > best[0]: best = (d, x, y)
        if not best: break
        w, h = (x1 - x0) / 5, (y1 - y0) / 5
        x0, x1, y0, y1 = best[1] - w, best[1] + w, best[2] - h, best[2] + h
    if best: return best[1], best[2]
    xs = [p[0] for p in r]; ys = [p[1] for p in r]
    return sum(xs) / len(xs), sum(ys) / len(ys)

labs = []
for line in open(D + 'places.geojsonseq'):
    line = line.strip().strip('\x1e')
    if not line: continue
    f = json.loads(line); p = f['properties']; g = f['geometry']
    kind = 'bay' if p.get('natural') == 'bay' else 'island' if p.get('place') in ('island', 'islet', 'archipelago') else None
    if not kind: continue
    name = clean(p.get('name:ko') or p.get('name'))
    if not name: continue
    if g['type'] == 'Point':
        x, y = g['coordinates']; a = land_area_at(x, y) if kind == 'island' else 0
        if a > 0.003: a = 0   # 육지와 이어진 섬(다리·매립)이라 큰 땅 안에 있으면 크기를 모름
    else:
        if g['type'] == 'LineString':
            rr = g['coordinates']
            if rr[0] != rr[-1] and kind == 'island': continue
            ring = rr
        else:
            ring = max((pp[0] for pp in polys_of(g)), key=area)
        a = area(ring); x, y = label_point(ring)
        if p.get('place') == 'archipelago': kind = 'group'
    if not (LON0 <= x <= 127.4 and LAT0 <= y <= 38.1): continue
    labs.append([name, x, y, a, kind])
for nm, x, y, a, typ in json.load(open(D + 'water_names.json')):
    nm = clean(nm)
    if nm and typ in ('lake', 'reservoir', 'lagoon') and a * KX > 3 / 12392 * 0.8 and x < 127.05: labs.append([nm, x, y, a * KX, 'lake'])
# 같은 이름이 가까이 겹치면 큰 쪽만
labs.sort(key=lambda l: -l[3])
keep = []
for l in labs:
    if any(k[0] == l[0] and math.hypot((k[1] - l[1]) * KX, k[2] - l[2]) < 0.02 for k in keep): continue
    keep.append(l)
out_l = []
for name, x, y, a, kind in keep:
    # 섬이 화면에서 대략 지름 18점 이상 보일 때부터 이름 (작은 섬·점 자료는 많이 당겼을 때만)
    if kind in ('bay', 'lake'): minS = max(600, min(5000, 20 / math.sqrt(max(a, 1e-6))))
    elif kind == 'group': minS = 900
    else: minS = max(250, min(60000, 10 / math.sqrt(a))) if a > 0 else 5000
    out_l.append([name, round(x, 5), round(y, 5), round(minS), {'island': 0, 'bay': 1, 'group': 2, 'lake': 1}[kind]])
print('이름표', len(out_l), '예:', [l[:1] + l[3:4] for l in out_l[:25]])
js = json.dumps({'src': '© OpenStreetMap 기여자 (ODbL)', 'date': open(D + 'when.txt').read().split('timestamp=')[-1][:10] if 'timestamp=' in open(D + 'when.txt').read() else '',
                 'o': [LON0, LAT0], 'q': Q, 'L': [L0, L1], 'F': [[], []], 'W': [W0, W1], 'lab': out_l}, ensure_ascii=False, separators=(',', ':'))
open('deploy/data/basemap.json', 'w').write(js)
print('크기', len(js.encode()) // 1024, 'KB')
