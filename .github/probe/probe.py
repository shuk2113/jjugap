"""주차 팁 주소 → 자리 찾기 (OSM: addr:street/housenumber, 이름)
결과: probe-out/port/geo.json"""
import json, os, subprocess, sys, traceback
OUT = 'probe-out/port'; os.makedirs(OUT, exist_ok=True)
log = []
def L(*a):
    s = ' '.join(str(x) for x in a); log.append(s); print(s, flush=True)
Q_ADDR = [['소성안길', '33'], ['연안부두로', '36'], ['궁평항로', '1049'], ['잠진도길', '11'], ['요포길', '98-12'], ['홍원길', '2'], ['축항대로85번길', '15'], ['축항대로166번길', '18']]
Q_NAME = ['오감센터', '충청수영', '염부두', '화미', '해양광장', '신진도', '잠진도', '거잠포', '비응', '낚시터미널', '시화나래', '궁평항', '홍원항', '무창포', '오천', '백사장', '영목', '마검포', '격포', '전곡', '대천항']
try:
    subprocess.run('sudo apt-get -qq update && sudo apt-get -qq install -y osmium-tool > /dev/null', shell=True)
    subprocess.run('wget -q --timeout=60 --tries=5 https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    streets = ','.join(sorted({a for a, _ in Q_ADDR}))
    subprocess.run(f'osmium tags-filter kr.pbf nwr/addr:street={streets} -o addr.pbf --overwrite', shell=True)
    subprocess.run('osmium export addr.pbf -f geojsonseq -o addr.geojsonseq --overwrite', shell=True)
    subprocess.run('osmium tags-filter kr.pbf nwr/name nwr/name:ko -o nm.pbf --overwrite', shell=True)
    subprocess.run('osmium export nm.pbf -f geojsonseq -o nm.geojsonseq --overwrite', shell=True)
    def center(g):
        t = g['type']; c = g['coordinates']
        if t == 'Point': return c
        pts = []
        def walk(x):
            if isinstance(x[0], (int, float)): pts.append(x)
            else:
                for y in x: walk(y)
        walk(c); return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
    out = {'addr': {}, 'name': {}}
    for line in open('addr.geojsonseq'):
        line = line.strip().strip('\x1e')
        if not line: continue
        f = json.loads(line); p = f['properties']
        for a, n in Q_ADDR:
            if p.get('addr:street') == a and p.get('addr:housenumber') == n:
                out['addr'].setdefault(f'{a} {n}', []).append([center(f['geometry']), {k: p[k] for k in p if k in ('name', 'building', 'amenity')}])
    for line in open('nm.geojsonseq'):
        line = line.strip().strip('\x1e')
        if not line: continue
        f = json.loads(line); p = f['properties']; nm = p.get('name:ko') or p.get('name') or ''
        if not (33.0 < center(f['geometry'])[1] < 38.7): continue
        for q in Q_NAME:
            if q in nm and (p.get('amenity') == 'parking' or '주차' in nm or q in ('오감센터', '충청수영', '낚시터미널', '시화나래', '해양광장', '염부두', '화미')):
                out['name'].setdefault(q, []).append([center(f['geometry']), nm, {k: p[k] for k in p if k in ('amenity', 'fee', 'capacity', 'building')}])
    json.dump(out, open(f'{OUT}/geo.json', 'w'), ensure_ascii=False, indent=1)
    L('주소', {k: len(v) for k, v in out['addr'].items()}); L('이름', {k: len(v) for k, v in out['name'].items()})
except Exception:
    L(traceback.format_exc())
open(f'{OUT}/geo_log.txt', 'w').write('\n'.join(log))
