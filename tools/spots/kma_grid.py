import math, sys, json
sys.path.insert(0, '.')
from landmask import on_land, KX
from gen_grid import PORTS, km
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
    if abs(xn) <= 0: theta = 0.0
    elif abs(yn) <= 0: theta = math.pi * 0.5 * (1 if xn > 0 else -1)
    else: theta = math.atan2(xn, yn)
    alon = theta / sn + olon
    return alat / D, alon / D
cells = []
for x in range(30, 70):
    for y in range(80, 140):
        if x % 2 or y % 2: continue
        la, lo = from_grid(x, y)
        if min(km((la, lo), q) for q in PORTS.values()) <= 42 and not on_land(lo, la): cells.append((x, y, round(la, 4), round(lo, 4)))
print(len(cells)); json.dump(cells, open('kma_cells.json', 'w'))
