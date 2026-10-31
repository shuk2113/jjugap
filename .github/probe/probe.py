"""이름으로 위치 찾기 (OSM): 백사장·드르니·시화나래·큰가리섬·방조제 선착장 등"""
import json, os, re, subprocess, sys, time, importlib, site, traceback
log = []
try:
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages osmium', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import osmium
    subprocess.run('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    Q = re.compile(r'백사장|드르니|시화나래|큰가리|작은가리|시화방조제|조력|방조제.*선착|선착.*방조제|오이도|탄도항|전곡항|궁평항|영흥|진두|남항|연안부두|대천항|무창포|홍원|마량|격포|안흥|신진도|마검포|영목|구매항|모항|천리포|만리포|삽시도|원산도|오천')
    class H(osmium.SimpleHandler):
        def __init__(s): super().__init__(); s.out = []
        def take(s, o, lon, lat, typ):
            nm = o.tags.get('name:ko') or o.tags.get('name')
            if nm and Q.search(nm) and 35.1 < lat < 38.1 and 125.3 < lon < 127.4:
                s.out.append([nm, round(lat, 5), round(lon, 5), typ, ';'.join(f'{t.k}={t.v}' for t in o.tags if t.k not in ('name', 'name:ko', 'name:en'))[:80]])
        def node(s, n):
            if n.location.valid(): s.take(n, n.location.lon, n.location.lat, 'n')
        def way(s, w):
            try:
                xs = [nd.lon for nd in w.nodes]; ys = [nd.lat for nd in w.nodes]
                if xs: s.take(w, sum(xs) / len(xs), sum(ys) / len(ys), 'w')
            except osmium.InvalidLocationError: pass
    h = H(); h.apply_file('kr.pbf', locations=True)
    h.out.sort(key=lambda x: x[0])
    json.dump(h.out, open('probe-out/osm/names_found.json', 'w'), ensure_ascii=False)
    log += [' | '.join(map(str, x)) for x in h.out if x[4] and 'highway=bus_stop' not in x[4]]
except Exception:
    log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
