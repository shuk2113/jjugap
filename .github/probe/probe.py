"""몇 곳 위치 찾기 (OSM): 이름에 잠진·오이도·야미·구매·마량·선재·거잠·대천항·남항 이 들어간 모든 것"""
import json, os, subprocess, sys, importlib, site, traceback, re
log = []
try:
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages osmium', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import osmium
    subprocess.run('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf; sudo apt-get -qq install -y osmium-tool > /dev/null; osmium extract -b 125.3,35.1,127.4,38.1 kr.pbf -o box.pbf --overwrite --strategy=smart', shell=True)
    PAT = re.compile(r'(잠진|오이도|야미|구매|마량|거잠|무의대교|대천항|남항|홍원|어은돌)')
    out = []
    def tg(tags): return {k: tags[k] for k in ('place', 'highway', 'amenity', 'harbour', 'man_made', 'leisure', 'public_transport', 'tourism', 'natural', 'building', 'shop', 'seamark:type', 'ferry') if k in tags}
    class H(osmium.SimpleHandler):
        def node(self, n):
            nm = n.tags.get('name:ko') or n.tags.get('name') or ''
            if PAT.search(nm): out.append([nm, round(n.location.lat, 6), round(n.location.lon, 6), tg(n.tags), 'n'])
        def way(self, w):
            nm = w.tags.get('name:ko') or w.tags.get('name') or ''
            if not PAT.search(nm): return
            try:
                pts = [(x.lat, x.lon) for x in w.nodes if x.location.valid()]
            except Exception: return
            if pts: out.append([nm, round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6), tg(w.tags), 'w', [round(pts[0][0], 6), round(pts[0][1], 6)], [round(pts[-1][0], 6), round(pts[-1][1], 6)]])
    H().apply_file('box.pbf', locations=True, idx='flex_mem')
    json.dump(out, open('probe-out/osm/names_find.json', 'w'), ensure_ascii=False)
    log += [json.dumps(o, ensure_ascii=False) for o in out[:400]]
except Exception:
    log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
