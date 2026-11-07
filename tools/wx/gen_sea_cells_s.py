"""지도용 남해 바다 격자(기상청 격자 2칸 = 약 10km 간격) → sea_cells_s.json [격자x, 격자y, 위도, 경도]
해안 5km 안은 10km 간격, 5~30km는 20km 간격 (TideBED 격자 거리로)이고, 지금 서해 격자(sea_cells.json)에 없는 칸"""
import json, math, sys
sys.path.insert(0, '../spots')
KX = math.cos(math.radians(36.6))
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32
def from_grid(x, y):
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0; re = RE / GRID
    s1, s2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5))
    sf = math.tan(math.pi * 0.25 + s1 * 0.5) ** sn * math.cos(s1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    xn = x - XO; yn = ro - y + YO
    ra = math.sqrt(xn * xn + yn * yn)
    if sn < 0: ra = -ra
    alat = 2.0 * math.atan((re * sf / ra) ** (1.0 / sn)) - math.pi * 0.5
    theta = 0.0 if abs(xn) <= 0 else (math.pi * 0.5 * (1 if xn > 0 else -1) if abs(yn) <= 0 else math.atan2(xn, yn))
    return alat / D, (theta / sn + olon) / D
G = json.load(open('../spots/south_in/tidebed_grid.json'))
pts = [(tuple(map(float, k.split(','))), v['d']) for k, v in G.items() if isinstance(v, dict) and 'ref' in v]
west = json.load(open('/home/claude/jjugap-main/.github/scripts/sea_cells.json'))
wset = {(c[0], c[1]) for c in west}
cells = []
for x in range(10, 110, 2):
    for y in range(20, 140, 2):
        if (x, y) in wset: continue
        la, lo = from_grid(x, y)
        if not (32.9 <= la <= 35.5 and 124.9 <= lo <= 129.6): continue
        near = min(pts, key=lambda p: km(p[0], (la, lo)))
        if km(near[0], (la, lo)) > 6: continue
        if near[1] <= 5 or (near[1] <= 30 and x % 4 == 0 and y % 4 == 0): cells.append([x, y, round(la, 4), round(lo, 4)])   # 해안 가까이는 10km, 먼 바다는 20km 간격
json.dump(cells, open('sea_cells_s.json', 'w'))
print('남해 격자', len(cells))
