"""조류예보·TideBED 자료 형식 알아보기 (인증키는 비밀값에서만 읽고 결과에는 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
now = datetime.now(KST); td = now.strftime('%Y%m%d')
def get(url, params=None, data=None, timeout=25):
    q = ('?' + (f'serviceKey={KEY}&' if 'apis.data.go.kr' in url else '') + urllib.parse.urlencode(params or {}, safe='')) if params is not None else ''
    req = urllib.request.Request(url + q, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*', 'X-Requested-With': 'XMLHttpRequest'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace').replace(KEY, '***')
    except Exception as e:
        return -1, f'{type(e).__name__}: {str(e)[:300]}'.replace(KEY, '***')
def save(name, obj):
    with open(f'{OUT}/{name}', 'w') as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1))
log = []
# 1) 해양조사원 누리집: 조류예보 지점 목록
for sid in ('SV_AP_04_008', 'SV_AP_04_009', 'SV_AP_04_010'):
    st, body = get('https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do', data={'id': sid})
    log.append(f'portal {sid}: {st} {len(body)}자')
    save(f'portal_{sid}.json', body)
# 2) 서해 쪽 조류예보 지점 고르기
pts = []
try:
    rows = json.loads(open(f'{OUT}/portal_SV_AP_04_008.json').read()).get('observatoryList') or []
    for r in rows:
        lat = float(r.get('lat') or r.get('obsLat') or r.get('latitude') or 0); lon = float(r.get('lon') or r.get('lot') or r.get('obsLon') or r.get('longitude') or 0)
        if 35.2 <= lat <= 38.0 and 125.3 <= lon <= 127.2:
            pts.append(r)
    log.append(f'서해 조류예보 지점 {len(pts)}곳 (전체 {len(rows)})')
    save('crnt_points_west.json', pts)
    if rows: save('crnt_point_sample.json', rows[:3])
except Exception as e:
    log.append(f'지점 목록 해석 실패: {e}')
# 3) 조류예보 시계열·최강창낙조: 앞의 두 지점
def code_of(r):
    for k in ('obsCode', 'obs_post_id', 'obsPostId', 'code', 'id', 'obsId'):
        if r.get(k): return r[k]
    return None
for r in pts[:2]:
    c = code_of(r)
    for name, url, prm in (('time', 'https://apis.data.go.kr/1192136/crntFcstTime/GetCrntFcstTimeApiService', {'type': 'json', 'obsCode': c, 'reqDate': td, 'min': 10, 'pageNo': 1, 'numOfRows': 300}),
                           ('fldebb', 'https://apis.data.go.kr/1192136/crntFcstFldEbb/GetCrntFcstFldEbbApiService', {'type': 'json', 'obsCode': c, 'reqDate': td, 'pageNo': 1, 'numOfRows': 50})):
        st, body = get(url, prm)
        log.append(f'{name} {c}: {st} {body[:160]}')
        save(f'crnt_{name}_{c}.json', body)
# 4) TideBED 한 지점(오천항 앞바다) 원문
st, body = get('https://apis.data.go.kr/1192136/tidebed/GetTidebedApiService', {'type': 'json', 'lat': 36.37, 'lot': 126.33, 'reqDate': td, 'min': 10, 'pageNo': 1, 'numOfRows': 300})
log.append(f'tidebed: {st} {body[:200]}'); save('tidebed_sample.json', body)
save('log.txt', '\n'.join(log)); print('\n'.join(log))
