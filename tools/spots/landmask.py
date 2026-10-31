import json, math
SP = '/tmp/claude-0/-home-claude/9ec8b963-99f7-50b6-9d59-55e76d707139/scratchpad/'
_c = json.load(open(SP + 'deploy/data/coast.json'))
O, Q = _c['o'], _c['q']
RINGS = []
for flat in _c['r']:
    x, y = flat[0], flat[1]; pts = [(O[0] + x / Q, O[1] + y / Q)]
    for i in range(2, len(flat), 2):
        x += flat[i]; y += flat[i + 1]; pts.append((O[0] + x / Q, O[1] + y / Q))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    RINGS.append((min(xs), max(xs), min(ys), max(ys), pts))
def on_land(lon, lat):
    inside = False
    for x0, x1, y0, y1, pts in RINGS:
        if lon < x0 or lon > x1 or lat < y0 or lat > y1: continue
        c = False; n = len(pts)
        for i in range(n):
            ax, ay = pts[i - 1]; bx, by = pts[i]
            if (ay > lat) != (by > lat) and lon < ax + (bx - ax) * (lat - ay) / (by - ay): c = not c
        if c: inside = not inside   # 섬 안의 호수 같은 경우는 거의 없으니 단순히 뒤집기
    return inside
KX = math.cos(math.radians(36.6))
def coast_km(lon, lat, lim=0.03):
    """가까운 해안선까지 거리(km, 대략)"""
    best = 9e9
    for x0, x1, y0, y1, pts in RINGS:
        if lon < x0 - lim or lon > x1 + lim or lat < y0 - lim or lat > y1 + lim: continue
        for i in range(len(pts)):
            ax, ay = pts[i - 1]; bx, by = pts[i]
            ax, bx, px = ax * KX, bx * KX, lon * KX
            dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
            t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (lat - ay) * dy) / L2))
            d = math.hypot(px - ax - t * dx, lat - ay - t * dy)
            if d < best: best = d
    return best * 111.32
