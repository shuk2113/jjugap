"""지도 자료 더하기: 방조제 안쪽 호수·저수지·큰 강 (OSM 육지 자료에는 땅으로 들어가 있음)"""
import json, os, subprocess, sys, time, importlib, site, traceback
OUT = 'probe-out/osm'; os.makedirs(OUT, exist_ok=True)
BB = (125.3, 35.1, 127.4, 38.1)
log = []
def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True); log.append(f'$ {c[:120]} → {r.returncode} {(r.stdout + r.stderr)[-300:]}'); return r.returncode
try:
    t = time.time()
    sh('sudo apt-get -qq update && sudo apt-get -qq install -y osmium-tool > /dev/null')
    sh(f'{sys.executable} -m pip install -q --user --break-system-packages shapely')
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    from shapely import set_precision
    sh('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf')
    sh(f'osmium extract -b {BB[0]},{BB[1]},{BB[2]},{BB[3]} kr.pbf -o box.pbf --overwrite')
    sh('osmium tags-filter box.pbf nwr/natural=water nwr/waterway=riverbank nwr/landuse=reservoir,basin -o water.pbf --overwrite')
    sh('osmium export water.pbf -f geojsonseq -o water.geojsonseq --overwrite --geometry-types=polygon')
    land = shape(json.load(open(f'{OUT}/land_union.geojson'))['geometry'])
    KX = 0.80
    MIN = 0.03 / (111.32 ** 2 * KX)          # 0.03 km² 보다 작은 연못은 뺀다
    polys, names = [], []
    for l in open('water.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        f = json.loads(l); g = shape(f['geometry']).buffer(0)
        if g.is_empty or g.area < MIN: continue
        polys.append(g)
        p = f['properties']; nm = p.get('name:ko') or p.get('name')
        if nm and g.area > 1.5 / (111.32 ** 2 * KX):      # 1.5 km² 넘는 이름 있는 물
            c = g.representative_point(); names.append([nm, round(c.x, 5), round(c.y, 5), g.area, p.get('water') or p.get('natural') or p.get('landuse') or p.get('waterway')])
    log.append(f'물 다각형 {len(polys)}개, 이름 {len(names)}')
    wu = unary_union(polys).intersection(land.buffer(0))
    json.dump({'type': 'Feature', 'properties': {}, 'geometry': mapping(set_precision(wu, 1e-6))}, open(f'{OUT}/water_union.geojson', 'w'))
    json.dump(names, open(f'{OUT}/water_names.json', 'w'), ensure_ascii=False)
    log.append(f'water_union {os.path.getsize(f"{OUT}/water_union.geojson") // 1024} KB, {time.time()-t:.0f}s')
except Exception:
    log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log))
