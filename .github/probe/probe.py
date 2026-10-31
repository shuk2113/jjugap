"""자료 알아보기 9: ROMS 수치예측모델 사용 가능 여부와 자료 모양 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
def raw(url, params):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    t = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url + q, headers={'Accept': 'application/json'}), timeout=60) as r:
            return r.status, r.read().decode('utf-8', 'replace').replace(KEY, '***'), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:400].replace(KEY, '***'), time.time() - t
    except Exception as e:
        return -1, f'{type(e).__name__} {str(e)[:150]}', time.time() - t
log = []
URLS = ['https://apis.data.go.kr/1192136/roms/GetRomsApiService', 'https://apis.data.go.kr/1192000/service/OceansData/roms/GetRomsApiService']
box = {'ymin': 36.25, 'ymax': 36.35, 'xmin': 126.20, 'xmax': 126.30}
good = None
for u in URLS:
    st, b, dt = raw(u, {'type': 'json', 'pageNo': 1, 'numOfRows': 20, **box})
    log.append(f'{u.split("apis.data.go.kr/")[1]}: {st} {dt:.1f}s {b[:500]}')
    if st == 200 and '"item"' in b and good is None: good = u
if good:
    st, b, dt = raw(good, {'type': 'json', 'pageNo': 1, 'numOfRows': 5000, **box})
    with open(f'{OUT}/roms_box.json', 'w') as f: f.write(b)
    try:
        d = json.loads(b); bd = d.get('body', d); it = bd['items']['item']; it = it if isinstance(it, list) else [it]
        ts = sorted({x['predcDt'] for x in it}); pts = sorted({(x['lat'], x['lot']) for x in it})
        log.append(f'상자 0.1°: total={bd.get("totalCount")} 받은 {len(it)} 시각 {len(ts)}개 {ts[:3]}..{ts[-3:]} 격자점 {len(pts)}개 {pts[:6]} ({dt:.1f}s)')
    except Exception as e:
        log.append(f'parse fail {e} {b[:300]}')
    # 더 큰 상자: 지점 수와 시간
    st, b, dt = raw(good, {'type': 'json', 'pageNo': 1, 'numOfRows': 1, 'ymin': 35.3, 'ymax': 37.6, 'xmin': 125.7, 'xmax': 126.8})
    log.append(f'서해 큰 상자 total: {st} {dt:.1f}s {b[:300]}')
    # 날짜 넣으면?
    st, b, dt = raw(good, {'type': 'json', 'pageNo': 1, 'numOfRows': 3, 'reqDate': (datetime.now(KST) + timedelta(days=1)).strftime('%Y%m%d'), **box})
    log.append(f'reqDate 넣음: {st} {b[:300]}')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
