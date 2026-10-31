"""조류예보 지점 코드 훑기 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
td = datetime.now(KST).strftime('%Y%m%d')
T = 'https://apis.data.go.kr/1192136/crntFcstTime/GetCrntFcstTimeApiService'
F = 'https://apis.data.go.kr/1192136/crntFcstFldEbb/GetCrntFcstFldEbbApiService'
def get(url, params):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    for i in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + q, headers={'Accept': 'application/json'}), timeout=20) as r:
                return r.read().decode('utf-8', 'replace').replace(KEY, '***')
        except Exception as e:
            err = f'{type(e).__name__}'
    return err
def first(code):
    b = get(T, {'type': 'json', 'obsCode': code, 'reqDate': td, 'min': 60, 'pageNo': 1, 'numOfRows': 1})
    try:
        it = json.loads(b)['body']['items']['item']
        it = it[0] if isinstance(it, list) else it
        return {'name': it['obsvtrNm'], 'lat': float(it['lat']), 'lon': float(it['lot'])}
    except Exception:
        return None
found = {}; log = []
t0 = time.time()
# 1) 앞자리(연도로 보이는) 어떤 것이 있는지
prefixes = []
for yy in range(0, 27):
    for typ in ('LTC', 'STC', 'PTC', 'TC'):
        c = f'{yy:02d}{typ}01'
        r = first(c)
        if r:
            prefixes.append((yy, typ)); found[c] = r
log.append(f'prefixes {prefixes}  ({time.time()-t0:.0f}s)')
# 2) 있는 앞자리마다 번호 훑기 (연속 10개 없으면 멈춤)
for yy, typ in prefixes:
    miss = 0; n = 1
    while miss < 10 and n < 150 and time.time() - t0 < 1500:
        n += 1; c = f'{yy:02d}{typ}{n:02d}'
        r = first(c)
        if r: found[c] = r; miss = 0
        else: miss += 1
    log.append(f'{yy:02d}{typ}: up to {n}  ({time.time()-t0:.0f}s)')
with open(f'{OUT}/codes.json', 'w') as f: json.dump(found, f, ensure_ascii=False, indent=0)
# 3) 응답 모양 견본: 천수만
for nm, u, prm in (('time10', T, {'min': 10, 'numOfRows': 300}), ('time30', T, {'min': 30, 'numOfRows': 100}), ('fldebb', F, {'numOfRows': 50})):
    b = get(u, {'type': 'json', 'obsCode': '16LTC03', 'reqDate': td, 'pageNo': 1, **prm})
    with open(f'{OUT}/sample_{nm}.json', 'w') as f: f.write(b)
    log.append(f'{nm}: {b[:300]}')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log)); print(len(found), 'codes')
