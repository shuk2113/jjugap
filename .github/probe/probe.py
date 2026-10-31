"""출항지 목록의 행정구역(시·군·구) 이름 붙이기 (OSM 행정경계)"""
import json, os, subprocess, sys, importlib, site, traceback
log = []
try:
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages shapely', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    from shapely.geometry import shape, Point
    subprocess.run('sudo apt-get -qq install -y osmium-tool > /dev/null; wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    subprocess.run('osmium extract -b 125.3,35.1,127.4,38.1 kr.pbf -o box.pbf --overwrite --strategy=smart', shell=True)
    subprocess.run('osmium tags-filter box.pbf r/boundary=administrative -o adm.pbf --overwrite && osmium export adm.pbf -f geojsonseq -o adm.geojsonseq --overwrite --geometry-types=polygon', shell=True)
    lv = {4: [], 6: [], 7: []}
    for l in open('adm.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        f = json.loads(l); p = f['properties']
        try: a = int(p.get('admin_level', 0))
        except ValueError: continue
        if a in lv: lv[a].append((p.get('name:ko') or p.get('name'), shape(f['geometry'])))
    log.append({k: len(v) for k, v in lv.items()}.__repr__())
    ports = json.load(open('.github/probe/ports_pre.json'))
    out = []
    for n, la, lo, _ in ports:
        pt = Point(lo, la)
        def find(level):
            for nm, g in lv[level]:
                if g.contains(pt): return nm
            # 바다 쪽 점이면 가장 가까운 경계
            best = min(lv[level], key=lambda x: x[1].distance(pt)) if lv[level] else (None, None)
            return best[0] if best[1] is not None and best[1].distance(pt) < 0.03 else None
        out.append([n, la, lo, find(4), find(6), find(7)])
    json.dump(out, open('probe-out/osm/ports_adm.json', 'w'), ensure_ascii=False)
    log += [str(x) for x in out[:400]]
except Exception:
    log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
