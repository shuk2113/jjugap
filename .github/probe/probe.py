"""자료 알아보기 10: ROMS 한 번에 받을 수 있는 양, 격자 간격, 예측 기간"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
U = 'https://apis.data.go.kr/1192136/roms/GetRomsApiService'
def get(params):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode({'type': 'json', **params}, safe='')
    t = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(U + q, headers={'Accept': 'application/json'}), timeout=90) as r:
            b = r.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, f'{type(e).__name__}', time.time() - t
    try:
        d = json.loads(b)
        if d.get('header', {}).get('resultCode') != '00': return None, b[:160], time.time() - t
        bd = d['body']; it = bd['items']['item']; it = it if isinstance(it, list) else [it]
        return (bd, it), '', time.time() - t
    except Exception as e:
        return None, b[:160], time.time() - t
log = []
box = {'ymin': 36.25, 'ymax': 36.35, 'xmin': 126.20, 'xmax': 126.30}
for n in (100, 300, 500, 999, 1000, 2000):
    r, err, dt = get({'pageNo': 1, 'numOfRows': n, **box})
    log.append(f'numOfRows {n}: ' + (f'total {r[0].get("totalCount")} 받은 {len(r[1])} ({dt:.1f}s)' if r else f'실패 {err}'))
# 상자 전체를 쪽 넘기며
allit = []; pg = 1; best = None
for n in (1000, 500, 300, 100):
    r, err, dt = get({'pageNo': 1, 'numOfRows': n, **box})
    if r: best = n; break
total = r[0].get('totalCount') if r else 0
while r and len(allit) < total and pg < 200:
    allit += r[1]; pg += 1
    if len(allit) >= total: break
    r, err, dt = get({'pageNo': pg, 'numOfRows': best, **box})
ts = sorted({x['predcDt'] for x in allit}); pts = sorted({(x['lat'], x['lot']) for x in allit})
log.append(f'상자 0.1°x0.1°: {len(allit)}/{total}행, 시각 {len(ts)}개 {ts[:2]} .. {ts[-2:]}, 격자점 {len(pts)}개')
lats = sorted({p[0] for p in pts}); lons = sorted({p[1] for p in pts})
log.append(f'  위도 {lats[:8]}  경도 {lons[:8]}')
with open(f'{OUT}/roms_box.json', 'w') as f: json.dump(allit, f)
# 상자 크기 한도
for s in (0.2, 0.3, 0.5, 1.0, 2.0):
    r, err, dt = get({'pageNo': 1, 'numOfRows': 10, 'ymin': 36.0, 'ymax': 36.0 + s, 'xmin': 126.0, 'xmax': 126.0 + s})
    log.append(f'상자 {s}°: ' + (f'total {r[0].get("totalCount")} ({dt:.1f}s)' if r else f'실패 {err} ({dt:.1f}s)'))
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
