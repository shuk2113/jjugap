"""남해 자료 받기 1: 서남해·남해·제주(+서해 빈 곳) 바다 격자 조석(TideBED)과 조류예보 지점 최강창낙조
- 격자: 해안에서 12km 안은 촘촘히(약 4.5km), 12~60km는 성기게(약 13km). 지금 서해 격자(657곳)와 겹치는 곳은 뺀다
- 육지·해안 거리: 전국 바다 지도(basemap8, 가장 자세한 단계)
- 인증키는 결과·기록에 남기지 않는다. 결과: probe-out/south/
"""
import json, os, re, subprocess, sys, time, math, importlib, site, traceback, urllib.parse, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out/south'; os.makedirs(OUT, exist_ok=True)
log = []; T0 = time.time()
def push_log():   # 진행 상황을 그때그때 가지에 올려, 밖에서 볼 수 있게
    open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
    subprocess.run(f'git config user.name "github-actions[bot]"; git config user.email "41898282+github-actions[bot]@users.noreply.github.com"; '
                   f'git add {OUT}/log.txt && git commit -q -m "진행 [skip ci]" && (git push -q origin HEAD:probe || (git pull -q --rebase origin probe && git push -q origin HEAD:probe))',
                   shell=True, capture_output=True)
def say(m): log.append(f'[{time.time() - T0:.0f}s] {m}'); print(log[-1], flush=True); push_log()
B = 'https://apis.data.go.kr/1192136/'
CODES = collections.Counter()
def get(path, params, tries=3):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + path + q, headers={'Accept': 'application/json'}), timeout=30) as r:
                txt = r.read().decode('utf-8', 'replace')
            d = json.loads(txt); c = d.get('header', {}).get('resultCode')
            CODES[f'{path.split("/")[0]}:{c}'] += 1
            if c == '00': return d['body']
            if c == '10': return None   # 바다 밖·잘못된 값
            if c in ('22', '99'): time.sleep(3)
        except Exception as e:
            CODES[f'{path.split("/")[0]}:{type(e).__name__}'] += 1
        time.sleep(1 + i)
    return 'fail'
try:
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages shapely numpy', shell=True, capture_output=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import numpy as np, shapely, shapely.affinity
    from shapely.geometry import Polygon, Point
    from shapely import STRtree, union_all
    KX = math.cos(math.radians(36.6))
    # ---------- 1) 육지 (전국 바다 지도 가장 자세한 단계)
    bm = json.load(open('probe-out/basemap8/basemap.json')); q = bm['q']; o0, o1 = bm['o']
    polys = []
    for poly in bm['L'][-1]:
        rings = []
        for r in poly:
            x, y = r[0], r[1]; pts = [(o0 + x / q, o1 + y / q)]
            for i in range(2, len(r), 2): x += r[i]; y += r[i + 1]; pts.append((o0 + x / q, o1 + y / q))
            if len(pts) >= 3: rings.append(pts)
        if rings:
            pg = shapely.make_valid(Polygon(rings[0], rings[1:]))
            if not pg.is_empty: polys.append(pg)
    # 거리 계산을 쉽게: 경도에 KX를 곱한 좌표로 (1 = 약 111km)
    land = union_all([shapely.affinity.scale(p, xfact=KX, yfact=1, origin=(0, 0)) for p in polys])
    shapely.prepare(land)
    say(f'육지 조각 {len(polys)}')
    # ---------- 2) 격자 후보
    old = json.load(open('.github/probe/grid_west.json'))   # 지금 서해 격자
    oldT = STRtree([Point(lo * KX, la) for la, lo in old])
    def dist_km(la, lo): return land.distance(Point(lo * KX, la)) * 111.32
    def near_old(la, lo):
        i = oldT.nearest(Point(lo * KX, la)); la2, lo2 = old[int(i)]
        return math.hypot((lo - lo2) * KX, la - la2) * 111.32 < 3.0
    ISL = [(37.95, 124.68), (37.83, 124.70), (37.66, 125.70)]   # 백령·대청·연평
    def keep_box(la, lo):
        if lo > 129.5: return False                       # 동해는 다음 단계
        if la > 35.45 and lo > 127.0: return False        # 내륙
        if la > 37.62:
            if lo >= 126.1: return la <= 37.82            # 강화·교동
            return any(math.hypot((lo - b) * KX, la - a) * 111.32 < 14 for a, b in ISL)
        return True
    cand = []
    lat = 32.90
    while lat <= 38.05:
        lon = 124.50
        while lon <= 129.55:
            la, lo = round(lat, 3), round(lon, 3)
            if keep_box(la, lo) and not land.contains(Point(lo * KX, la)):
                d = dist_km(la, lo)
                fine = d <= 12
                # 성긴 격자: 위도 0.12도·경도 0.15도마다
                coarse = (not fine) and d <= 60 and round((lat - 32.90) / 0.04) % 3 == 0 and round((lon - 124.50) / 0.05) % 3 == 0
                if (fine or coarse) and not near_old(la, lo): cand.append((la, lo, round(d, 1)))
            lon += 0.05
        lat += 0.04
    say(f'격자 후보 {len(cand)} (해안 12km 안 {sum(1 for c in cand if c[2] <= 12)})')
    if len(cand) > 4200: raise RuntimeError(f'격자 후보가 너무 많음 {len(cand)} — 하루 사용 한도를 넘길 수 있어 멈춤')
    # ---------- 3) TideBED: 모든 점은 하루치, 검증용(8곳마다 1곳)은 이틀 더
    now = datetime.now(KST)
    D0 = now.strftime('%Y%m%d'); DV = [(now + timedelta(days=4)).strftime('%Y%m%d'), (now + timedelta(days=11)).strftime('%Y%m%d')]
    def tb(job):
        la, lo, dkm, k = job; res = {'d': dkm}
        for ds in [D0] + (DV if k % 8 == 0 else []):
            b = get('tidebed/GetTidebedApiService', {'type': 'json', 'lat': la, 'lot': lo, 'reqDate': ds, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
            if b is None or b == 'fail': return (la, lo), (b if ds == D0 else res)
            it = b['items']['item']; it = it if isinstance(it, list) else [it]
            x = it[0]
            res.setdefault('ref', x['obsvtrNm']); res.setdefault('rlat', x['lat']); res.setdefault('rlon', x['lot'])
            res.setdefault('jogo', float(x['jogo'])); res.setdefault('josi', x['josi']); res.setdefault('msl', x['msl'])
            res[ds] = {'t0': it[0]['slctdDt'], 'h': [float(y['slctdHgt']) for y in it], 'r0': it[0]['obsrvnDt'], 'rh': [y['obsrvnHgt'] for y in it]}
        return (la, lo), res
    jobs = [(la, lo, d, k) for k, (la, lo, d) in enumerate(cand)]
    tbres = {}; t1 = time.time()
    with ThreadPoolExecutor(6) as ex:
        for n, ((la, lo), r) in enumerate(ex.map(tb, jobs)):
            tbres[f'{la},{lo}'] = r
            if n % 400 == 399: say(f'TideBED {n + 1}/{len(jobs)} · 응답 {dict(CODES)}')
    ok = {k: v for k, v in tbres.items() if isinstance(v, dict)}
    refs = collections.Counter(v['ref'] for v in ok.values())
    say(f'TideBED 끝 {len(ok)}/{len(tbres)} ({time.time() - t1:.0f}s) · 기준 관측소 {len(refs)}곳 {dict(refs.most_common())}')
    json.dump(tbres, open(f'{OUT}/tidebed_grid.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'D0': D0, 'DV': DV}, open(f'{OUT}/days.json', 'w'))
    # ---------- 4) 조류예보 지점 최강창낙조 (서해 33곳 밖의 지점)
    codes = json.load(open('.github/probe/codes_all.json')); west = json.load(open('.github/probe/crnt_west.json'))
    todo = {c: v for c, v in codes.items() if c not in west and v['lon'] <= 129.5 and (v['lat'] < 35.45 or v['lat'] > 37.62)}
    def fe(code):
        rows = []; pg = 1
        while True:
            b = get('crntFcstFldEbb/GetCrntFcstFldEbbApiService', {'type': 'json', 'obsCode': code, 'numOfRows': 100, 'pageNo': pg})
            if b is None or b == 'fail': return code, rows, f'page {pg} {b}'
            total = b.get('totalCount'); it = b['items']['item']; it = it if isinstance(it, list) else [it]
            rows += [(x['predcDt'], float(x['crdir']), float(x['crsp'])) for x in it]
            if len(rows) >= total or not it: break
            pg += 1
        return code, rows, 'ok'
    feres = {}; felog = []
    with ThreadPoolExecutor(4) as ex:
        for code, rows, why in ex.map(fe, list(todo)):
            feres[code] = {'name': todo[code]['name'], 'lat': todo[code]['lat'], 'lon': todo[code]['lon'], 'ev': rows}; felog.append(f'{code} {todo[code]["name"]} {len(rows)} {why}')
    json.dump(feres, open(f'{OUT}/fldebb.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    log.extend(felog)
    say(f'조류 지점 {len(feres)}곳 · 응답 {dict(CODES)}')
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log[-40:]))
