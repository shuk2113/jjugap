"""남해 자료 받기 4: 항·포구 자리마다 시·군(광역시는 '부산 사하구'처럼) 이름 — OSM 행정 경계 (Geofabrik 한국)
결과: probe-out/south/pts_region.json  [[시도, 시군구, 구], …] (pts.json 순서대로)"""
import json, os, subprocess, sys, importlib, site, traceback
OUT = 'probe-out/south'; os.makedirs(OUT, exist_ok=True)
log = []
try:
    subprocess.run('sudo apt-get -qq update && sudo apt-get -qq install -y osmium-tool > /dev/null', shell=True)
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages shapely', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import shapely
    from shapely.geometry import shape, Point
    from shapely import STRtree
    subprocess.run('wget -q --timeout=60 --tries=5 https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    subprocess.run('osmium tags-filter kr.pbf r/boundary=administrative -o adm.pbf --overwrite && osmium export adm.pbf -f geojsonseq --geometry-types=polygon -o adm.geojsonseq --overwrite', shell=True)
    polys = {4: [], 6: [], 7: []}
    for l in open('adm.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        f = json.loads(l); p = f['properties']
        try: lv = int(p.get('admin_level', 0))
        except ValueError: continue
        if lv not in polys: continue
        nm = p.get('name:ko') or p.get('name')
        if not nm: continue
        try: g = shape(f['geometry'])
        except Exception: continue
        if not g.is_valid: g = g.buffer(0)
        polys[lv].append((nm, g))
    log.append('경계 ' + str({k: len(v) for k, v in polys.items()}))
    trees = {lv: STRtree([g for _, g in v]) for lv, v in polys.items()}
    pts = json.load(open('.github/probe/pts.json'))
    def name_at(lv, pt, maxd):
        t = trees[lv]; idx = t.query(pt, predicate='within') if False else t.query(pt)
        for i in idx:
            if polys[lv][i][1].contains(pt): return polys[lv][i][0]
        # 바다 위(방파제 끝 등)라 경계 밖이면 가장 가까운 경계 (maxd 도 안)
        j = t.nearest(pt)
        if j is not None and polys[lv][int(j)][1].distance(pt) < maxd: return polys[lv][int(j)][0]
        return ''
    out = []
    for la, lo in pts:
        pt = Point(lo, la)
        out.append([name_at(4, pt, 0.05), name_at(6, pt, 0.05), name_at(7, pt, 0.03)])
    json.dump(out, open(f'{OUT}/pts_region.json', 'w'), ensure_ascii=False)
    log.append(f'점 {len(out)} · 시군구 못 찾음 {sum(1 for o in out if not o[1])}')
    log += [f'{p} {o}' for p, o in list(zip(pts, out))[::60]]
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log4.txt', 'w').write('\n'.join(log))
print('\n'.join(log))
