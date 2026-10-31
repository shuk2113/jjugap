"""자료 알아보기 11: ROMS 한 점씩 (조류예보 지점·수온 관측소 옆) — 조류·수온이 공식 값과 얼마나 맞는지"""
import json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
U = 'https://apis.data.go.kr/1192136/roms/GetRomsApiService'
def get(params, tries=3):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode({'type': 'json', **params}, safe='')
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(U + q, headers={'Accept': 'application/json'}), timeout=60) as r:
                d = json.loads(r.read().decode('utf-8', 'replace'))
            if d.get('header', {}).get('resultCode') == '00':
                bd = d['body']; it = bd['items']['item']; return bd.get('totalCount'), (it if isinstance(it, list) else [it])
            if d.get('header', {}).get('resultCode') == '03': return 0, []
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None, None
PTS = {'천수만': (36.37794, 126.46652), '녹도북측': (36.30777, 126.29944), '가의도북동측': (36.69777, 126.08972), '송이도북측': (35.34969, 126.1665),
       '어청도서측': (36.11419, 125.96705), '삽시도북측': (36.36972, 126.35305), '외연도동측': (36.24427, 126.20919), '덕적군도서측': (37.2843, 125.6),
       '어청도(수온)': (36.117, 125.984), '보령(수온)': (36.406, 126.486), '안흥(수온)': (36.674, 126.129), '군산(수온)': (35.975, 126.563), '대산(수온)': (37.007, 126.352), '인천(수온)': (37.451, 126.592)}
def one(kv):
    name, (la, lo) = kv; calls = 0
    for r in (0.016, 0.03, 0.05):
        box = {'ymin': round(la - r, 4), 'ymax': round(la + r, 4), 'xmin': round(lo - r * 1.15, 4), 'xmax': round(lo + r * 1.15, 4)}
        total, it = get({'pageNo': 1, 'numOfRows': 100, **box}); calls += 1
        if total: break
    if not total: return name, {'err': 'none', 'calls': calls}
    rows = list(it); pg = 1
    while len(rows) < total and pg < 80:
        pg += 1; t2, it2 = get({'pageNo': pg, 'numOfRows': 100, **box}); calls += 1
        if not it2: break
        rows += it2
    # 가장 가까운 격자점만
    pts = {}
    for x in rows: pts.setdefault((float(x['lat']), float(x['lot'])), []).append(x)
    near = min(pts, key=lambda p: (p[0] - la) ** 2 + ((p[1] - lo) * 0.8) ** 2)
    return name, {'pt': near, 'npts': len(pts), 'calls': calls, 'rows': [[x['predcDt'][:16], float(x['crdir']), float(x['crsp']), float(x['wtem'])] for x in pts[near]]}
t0 = time.time()
with ThreadPoolExecutor(4) as ex: res = dict(ex.map(one, PTS.items()))
with open(f'{OUT}/roms_points.json', 'w') as f: json.dump(res, f, ensure_ascii=False)
log = [f'{k}: 격자점 {v.get("pt")} (상자 안 {v.get("npts")}점, 호출 {v.get("calls")}회) 시각 {len(v.get("rows", []))}개 첫 {v.get("rows", [[None]])[0]}' for k, v in res.items()]
log.append(f'{time.time()-t0:.0f}s')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
