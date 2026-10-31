import json, math, sys
sys.path.insert(0, '.')
from landmask import on_land, KX
PORTS = {'incheon': (37.45, 126.6), 'yeongheung': (37.25, 126.47), 'bangameori': (37.29, 126.57), 'anheung': (36.67, 126.13),
         'ocheon': (36.44, 126.52), 'hongwon': (36.15, 126.5), 'gunsan': (35.98, 126.56), 'gyeokpo': (35.62, 126.47)}
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32
DLAT, DLON = 0.04, 0.05
pts = []
lat = 35.30
while lat <= 37.62:
    lon = 125.70
    while lon <= 126.80:
        p = (round(lat, 3), round(lon, 3))
        if min(km(p, q) for q in PORTS.values()) <= 45 and not on_land(p[1], p[0]): pts.append(p)
        lon += DLON
    lat += DLAT
print(len(pts))
json.dump(pts, open('grid.json', 'w'))
