"""항구 주변 자료 만들기 (항구 정보 · 주차 1단계)
- 공공데이터 '전국주차장정보표준데이터' (DATA_GO_KR_KEY, 키는 로그·파일에 남기지 않는다)
- OSM(Geofabrik 한국, © OpenStreetMap 기여자 ODbL): 도로·건물·주차장 구역·편의시설·방파제
결과: probe-out/port/p{번호}.json (번호 = 앱 항구 목록 ports_app.json 순서) · log.txt · stats.json
좌표: 항구 자리(c)에서 떨어진 정도를 1e-5도 정수로, 선은 [x0,y0,dx1,dy1,...] 차분
"""
import json, os, subprocess, sys, importlib, site, traceback, math, time, re, urllib.parse, urllib.request
OUT = 'probe-out/port'; os.makedirs(OUT, exist_ok=True)
log = []
def L(*a):
    s = ' '.join(str(x) for x in a); log.append(s); print(s, flush=True)
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
def mask(s): return s.replace(KEY, '***') if KEY else s

R_ROAD, R_BLD, R_MISC, R_PK = 1500, 800, 1500, 2000   # m
Q = 1e5

try:
    ports = json.load(open('.github/probe/ports_app.json'))
    L('항구', len(ports))

    # ---------- 1) 공공데이터 주차장
    parking = []; total = None
    url = 'https://api.data.go.kr/openapi/tn_pubr_prkplce_info_api'
    page = 1
    while True:
        q = urllib.parse.urlencode({'pageNo': page, 'numOfRows': 1000, 'type': 'json'})
        raw = ''
        for t in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(f'{url}?serviceKey={KEY}&{q}', headers={'Accept': 'application/json'}), timeout=90) as r:
                    raw = r.read().decode('utf-8', 'replace'); break
            except Exception as e:
                L('주차장 API 다시', page, t, mask(repr(e))[:200]); time.sleep(3 + 5 * t)
        if not raw: L('주차장 API 실패', page); break
        try: j = json.loads(raw)
        except Exception:
            L('주차장 API 응답(JSON 아님)', mask(raw[:400]).replace('\n', ' ')); break
        head = j.get('response', {}).get('header', {}); body = j.get('response', {}).get('body', {})
        if str(head.get('resultCode', '00')) not in ('00', '0'):
            L('주차장 API 머리', head); break
        items = body.get('items') or []
        if isinstance(items, dict): items = items.get('item', []) or []
        if isinstance(items, dict): items = [items]
        total = int(body.get('totalCount', 0) or 0)
        parking += items
        if page == 1 and items: L('주차장 항목 이름', sorted(items[0].keys()))
        if not items or page * 1000 >= total: break
        page += 1; time.sleep(0.15)
    L('주차장 받음', len(parking), '/', total)
    if not parking:   # 아직 허락 전이면 OSM은 다시 만들지 않고 끝 (지난 결과 그대로)
        raise SystemExit('주차장 자료 없음 — OSM 다시 만들기는 건너뜀')

    # ---------- 2) OSM
    subprocess.run('sudo apt-get -qq update && sudo apt-get -qq install -y osmium-tool > /dev/null', shell=True)
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages shapely', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    from shapely.geometry import shape, box, mapping, LineString, Polygon, MultiPolygon, MultiLineString, Point
    from shapely.ops import unary_union
    from shapely import STRtree
    subprocess.run('wget -q --timeout=60 --tries=5 https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    L('pbf', os.path.getsize('kr.pbf') if os.path.exists('kr.pbf') else 0)
    def bb(la, lo, m):
        dla = m / 111320; dlo = m / (111320 * math.cos(math.radians(la))); return (lo - dlo, la - dla, lo + dlo, la + dla)
    near = unary_union([box(*bb(p[1], p[2], R_PK + 200)) for p in ports])
    json.dump({'type': 'Feature', 'properties': {}, 'geometry': mapping(near)}, open('near.geojson', 'w'))
    subprocess.run('osmium extract -p near.geojson kr.pbf -o near.pbf --overwrite -s smart', shell=True)
    L('near.pbf', os.path.getsize('near.pbf'))
    flt = ('w/highway wr/building nwr/amenity=parking,toilets,fuel,marketplace,ferry_terminal,police '
           'nwr/shop=convenience,supermarket,fishing,seafood nwr/man_made=pier,breakwater nwr/leisure=marina,slipway nwr/name')
    subprocess.run(f'osmium tags-filter near.pbf {flt} -o sel.pbf --overwrite', shell=True)
    subprocess.run('osmium export sel.pbf -f geojsonseq -o sel.geojsonseq --overwrite', shell=True)
    K = {k: [] for k in ('road', 'bld', 'park', 'poi', 'pier')}
    RC = {'motorway': 0, 'trunk': 0, 'primary': 0, 'secondary': 0, 'motorway_link': 0, 'trunk_link': 0, 'primary_link': 0, 'secondary_link': 0,
          'tertiary': 1, 'tertiary_link': 1, 'unclassified': 1, 'residential': 1, 'living_street': 1, 'road': 1, 'service': 2, 'track': 2}
    def poi_kind(p):
        a, s, n = p.get('amenity'), p.get('shop'), (p.get('name:ko') or p.get('name') or '')
        if s in ('convenience', 'supermarket'): return 'cvs'
        if a == 'toilets': return 'wc'
        if s == 'fishing' or '낚시' in n: return 'fish'
        if a == 'marketplace' or s == 'seafood' or re.search('위판장|어시장|수산시장|활어', n): return 'mkt'
        if '수협' in n: return 'sh'
        if a == 'fuel': return 'fuel'
        if a == 'ferry_terminal' or '여객터미널' in n: return 'ferry'
        if a == 'police' or '파출소' in n or '해양경찰' in n: return 'pol'
        if p.get('leisure') in ('marina',): return 'marina'
        return None
    n = 0
    for line in open('sel.geojsonseq'):
        line = line.strip().strip('\x1e')
        if not line: continue
        try: f = json.loads(line)
        except Exception: continue
        p = f.get('properties') or {}
        try: g = shape(f['geometry'])
        except Exception: continue
        if g.is_empty: continue
        n += 1
        hw = p.get('highway')
        if hw in RC and g.geom_type in ('LineString', 'MultiLineString'):
            K['road'].append((g, RC[hw], p.get('name:ko') or p.get('name') or '')); continue
        if p.get('amenity') == 'parking':
            K['park'].append((g, p)); continue
        if p.get('man_made') in ('pier', 'breakwater'):
            K['pier'].append((g, p.get('man_made'))); continue
        pk = poi_kind(p)
        if pk:
            K['poi'].append((g.representative_point() if g.geom_type != 'Point' else g, pk, p.get('name:ko') or p.get('name') or ''))
        if p.get('building') and g.geom_type in ('Polygon', 'MultiPolygon'):
            K['bld'].append((g, p.get('name:ko') or p.get('name') or ''))
    L('OSM', n, {k: len(v) for k, v in K.items()})
    T = {k: STRtree([x[0] for x in v]) for k, v in K.items() if v}

    def enc_line(coords, cla, clo):
        out = []; px = py = 0; first = True
        for lo, la in coords:
            x = round((lo - clo) * Q); y = round((la - cla) * Q)
            if first: out += [x, y]; first = False
            else:
                if x == px and y == py: continue
                out += [x - px, y - py]
            px, py = x, y
        return out
    def parts(g):
        if g.is_empty: return []
        if g.geom_type in ('LineString', 'Polygon', 'Point'): return [g]
        if hasattr(g, 'geoms'): return [h for x in g.geoms for h in parts(x)]
        return []

    # 공공데이터 주차장 → 자리 있는 것만
    PK = []
    for it in parking:
        try: la, lo = float(it.get('latitude') or 0), float(it.get('longitude') or 0)
        except Exception: continue
        if not (33 < la < 39 and 124 < lo < 132): continue
        PK.append((Point(lo, la), it))
    TPK = STRtree([x[0] for x in PK]) if PK else None
    def dist_m(la1, lo1, la2, lo2):
        kx = math.cos(math.radians((la1 + la2) / 2)); return math.hypot((lo2 - lo1) * kx, la2 - la1) * 111320
    KEEP = ['prkplceNm', 'prkplceSe', 'prkplceType', 'rdnmadr', 'lnmadr', 'prkcmprt', 'operDay', 'weekdayOperOpenHhmm', 'weekdayOperColseHhmm',
            'satOperOperOpenHhmm', 'satOperCloseHhmm', 'holidayOperOpenHhmm', 'holidayCloseOpenHhmm', 'parkingchrgeInfo', 'basicTime', 'basicCharge',
            'addUnitTime', 'addUnitCharge', 'dayCmmtktAdjTime', 'dayCmmtkt', 'metpay', 'spcmnt', 'institutionNm', 'phoneNumber', 'referenceDate']

    sizes = []; bigs = []
    for i, pt in enumerate(ports):
        nm, cla, clo = pt[0], pt[1], pt[2]
        o = {'n': nm, 'c': [cla, clo], 'v': time.strftime('%Y%m%d')}
        rb = box(*bb(cla, clo, R_ROAD)); bbx = box(*bb(cla, clo, R_BLD)); mb = box(*bb(cla, clo, R_MISC))
        tol = lambda m: m / 111320
        # 도로
        roads = []; names = []
        if 'road' in T:
            for j in T['road'].query(rb):
                g, c, rn = K['road'][j]
                h = g.intersection(rb).simplify(tol(2.5 if c < 2 else 3.5))
                for q in parts(h):
                    if q.geom_type != 'LineString' or q.length < tol(8): continue
                    ni = -1
                    if rn:
                        if rn not in names: names.append(rn)
                        ni = names.index(rn)
                    roads.append([c, ni] + enc_line(q.coords, cla, clo))
        o['r'] = roads; o['rn'] = names
        # 건물 (작은 것 빼고)
        blds = []
        if 'bld' in T:
            for j in T['bld'].query(bbx):
                g, bn = K['bld'][j]
                h = g.intersection(bbx)
                for q in parts(h):
                    if q.geom_type != 'Polygon': continue
                    if q.area * 111320 * 111320 * math.cos(math.radians(cla)) < 25: continue
                    q = q.simplify(tol(1.2))
                    if q.is_empty or q.geom_type != 'Polygon': continue
                    blds.append(enc_line(list(q.exterior.coords)[:-1], cla, clo))
        o['b'] = blds
        # 주차장 구역 (OSM)
        pa = []
        if 'park' in T:
            for j in T['park'].query(mb):
                g, p = K['park'][j]
                info = {k: p[k] for k in ('name', 'fee', 'access', 'capacity', 'parking', 'operator') if p.get(k)}
                if g.geom_type == 'Point':
                    info['p'] = enc_line([g.coords[0]], cla, clo)
                else:
                    h = g.intersection(mb)
                    rings = [enc_line(list(q.exterior.coords)[:-1], cla, clo) for q in parts(h.simplify(tol(1.5))) if q.geom_type == 'Polygon']
                    if not rings: continue
                    info['g'] = rings
                    c = g.representative_point(); info['p'] = enc_line([c.coords[0]], cla, clo)
                    info['a'] = round(g.area * 111320 * 111320 * math.cos(math.radians(cla)))
                pa.append(info)
        o['pa'] = pa
        # 방파제·부두
        pr = []
        if 'pier' in T:
            for j in T['pier'].query(mb):
                g, kind = K['pier'][j]
                h = g.intersection(mb).simplify(tol(1.5))
                for q in parts(h):
                    if q.geom_type == 'LineString': pr.append([0] + enc_line(q.coords, cla, clo))
                    elif q.geom_type == 'Polygon': pr.append([1] + enc_line(list(q.exterior.coords)[:-1], cla, clo))
        o['pr'] = pr
        # 기준 건물·편의시설
        po = []
        if 'poi' in T:
            for j in T['poi'].query(mb):
                g, pk, pn = K['poi'][j]
                if not mb.contains(g): continue
                po.append([pk, pn] + enc_line([g.coords[0]], cla, clo))
        o['po'] = po
        # 공공데이터 주차장 (2km 안 가까운 순 12곳)
        pl = []
        if TPK is not None:
            for j in TPK.query(box(*bb(cla, clo, R_PK))):
                g, it = PK[j]; d = dist_m(cla, clo, g.y, g.x)
                if d > R_PK: continue
                rec = {k: it.get(k) for k in KEEP if it.get(k) not in (None, '')}
                rec['d'] = round(d); rec['p'] = enc_line([g.coords[0]], cla, clo)
                pl.append(rec)
        pl.sort(key=lambda r: r['d']); o['pk'] = pl[:12]
        s = json.dumps(o, ensure_ascii=False, separators=(',', ':'))
        open(f'{OUT}/p{i}.json', 'w').write(s)
        sizes.append(len(s.encode()))
        if len(s.encode()) > 150000: bigs.append((i, nm, len(s.encode())))
    sizes_s = sorted(sizes)
    st = {'n': len(sizes), 'total': sum(sizes), 'median': sizes_s[len(sizes_s) // 2], 'p90': sizes_s[int(len(sizes_s) * .9)], 'max': sizes_s[-1], 'bigs': bigs[:40],
          'withPK': sum(1 for i in range(len(ports)) if json.load(open(f'{OUT}/p{i}.json'))['pk'])}
    json.dump(st, open(f'{OUT}/stats.json', 'w'), ensure_ascii=False, indent=1)
    L('크기', st)
    for i in (44, 45, 46, 47, 48, 59, 82, 87, 121, 122, 125, 130, 135, 143, 152, 157, 159, 178, 195):
        o = json.load(open(f'{OUT}/p{i}.json'))
        L(i, o['n'], '도로', len(o['r']), '이름', len(o['rn']), '건물', len(o['b']), 'OSM주차', len(o['pa']), '공공주차', len(o['pk']), '부두', len(o['pr']), '시설', len(o['po']),
          [p.get('prkplceNm') for p in o['pk'][:4]], [x[0] + ':' + x[1] for x in o['po'][:6]])
except SystemExit as e:
    L(str(e))
except Exception:
    L(mask(traceback.format_exc()))
open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
