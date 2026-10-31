"""출항지 검색용 목록: 서해 중부 해안의 항·포구·선착장·부두·마리나 이름과 위치 (OSM), 가까운 시·군 이름"""
import json, os, re, subprocess, sys, time, importlib, site, traceback, math
OUT = 'probe-out/osm'; os.makedirs(OUT, exist_ok=True)
BB = (125.3, 35.1, 127.4, 38.1)
log = []
def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True); log.append(f'$ {c[:100]} → {r.returncode} {(r.stdout + r.stderr)[-300:]}'); return r.returncode
try:
    t0 = time.time()
    sh(f'{sys.executable} -m pip install -q --user --break-system-packages shapely osmium')
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import osmium
    from shapely.geometry import shape, Point
    from shapely.strtree import STRtree
    sh('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf')
    sh('sudo apt-get -qq install -y osmium-tool > /dev/null; osmium extract -b %s,%s,%s,%s kr.pbf -o box.pbf --overwrite' % BB)
    PORT = re.compile(r'(항|항구|포구|선착장|부두|나루|나루터|마리나|어항|물양장|선창|포)$|선착장|부두|마리나|요트')
    BAD = re.compile(r'공항|정류장|정류소|버스|주차장|식당|횟집|모텔|펜션|마트|은행|교회|학교|병원|아파트|빌라|편의점|카페|약국|사거리|삼거리|IC|JC|휴게소|역$|주유소|수산|상회|호텔|낚시$|낚시점|마을회관|경로당|입구')
    PORT_TAGS = {('harbour', None), ('leisure', 'marina'), ('landuse', 'harbour'), ('industrial', 'port'), ('man_made', 'pier'), ('man_made', 'quay'),
                 ('amenity', 'ferry_terminal'), ('seamark:type', 'harbour'), ('waterway', 'dock'), ('man_made', 'breakwater'), ('mooring', None)}
    class H(osmium.SimpleHandler):
        def __init__(s):
            super().__init__(); s.out = []; s.places = []
        def take(s, o, lon, lat):
            tg = o.tags; nm = tg.get('name:ko') or tg.get('name')
            if not nm: return
            pl = tg.get('place')
            if pl in ('city', 'county', 'town', 'borough') and o.__class__.__name__ == 'Node':
                s.places.append([nm, lat, lon, pl]); return
            portish = any((k in tg) if v is None else (tg.get(k) == v) for k, v in PORT_TAGS)
            if (PORT.search(nm) or portish) and not BAD.search(nm):
                kind = 'harbour' if portish else ('bus' if tg.get('highway') == 'bus_stop' else (tg.get('place') or tg.get('amenity') or tg.get('natural') or 'name'))
                s.out.append([nm, lat, lon, kind])
        def node(s, n):
            if n.location.valid(): s.take(n, n.location.lon, n.location.lat)
        def way(s, w):
            try:
                xs = [nd.lon for nd in w.nodes]; ys = [nd.lat for nd in w.nodes]
                if xs: s.take(w, sum(xs) / len(xs), sum(ys) / len(ys))
            except osmium.InvalidLocationError:
                pass
    h = H(); h.apply_file('box.pbf', locations=True)
    log.append(f'후보 {len(h.out)}, 시군 {len(h.places)}  {time.time()-t0:.0f}s')
    # 해안선에서 1.5km 안
    land = shape(json.load(open(f'{OUT}/land_union.geojson'))['geometry'])
    edges = []
    for poly in (land.geoms if hasattr(land, 'geoms') else [land]):
        b = poly.exterior.coords
        for i in range(0, len(b) - 1, 1):
            edges.append(((b[i][0], b[i][1]), (b[i + 1][0], b[i + 1][1])))
    from shapely.geometry import LineString
    lines = [LineString(e) for e in edges]; tree = STRtree(lines)
    KX = math.cos(math.radians(36.6))
    def coast_km(lon, lat):
        p = Point(lon, lat); i = tree.nearest(p); ln = lines[i]
        q = ln.interpolate(ln.project(p)); return math.hypot((q.x - lon) * KX, q.y - lat) * 111.32
    keep = []
    for nm, lat, lon, kind in h.out:
        d = coast_km(lon, lat)
        if d <= 1.5: keep.append([nm, round(lat, 5), round(lon, 5), kind, round(d, 2)])
    log.append(f'해안 1.5km 안 {len(keep)}')
    json.dump({'ports': keep, 'places': h.places}, open(f'{OUT}/ports_raw.json', 'w'), ensure_ascii=False)
    for q in ('남항', '대천항', '백사장', '시화', '방아머리', '오천항', '선착장'):
        log.append(q + ': ' + ', '.join(f'{x[0]}({x[3]},{x[1]:.3f},{x[2]:.3f})' for x in keep if q in x[0])[:600])
except Exception:
    log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log))
