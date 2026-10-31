"""조류예보 지점 코드 알아내기 (인증키는 결과에 남기지 않는다)"""
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
    try:
        with urllib.request.urlopen(urllib.request.Request(url + q, headers={'Accept': 'application/json'}), timeout=25) as r:
            return r.status, r.read().decode('utf-8', 'replace').replace(KEY, '***')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300].replace(KEY, '***')
    except Exception as e:
        return -1, f'{type(e).__name__}: {str(e)[:200]}'
log = []
tries = [('없음', {'type': 'json', 'reqDate': td, 'pageNo': 1, 'numOfRows': 50}),
         ('빈값', {'type': 'json', 'obsCode': '', 'reqDate': td, 'pageNo': 1, 'numOfRows': 50}),
         ('ALL', {'type': 'json', 'obsCode': 'ALL', 'reqDate': td, 'pageNo': 1, 'numOfRows': 50})]
for nm, prm in tries:
    for u in (T, F):
        st, body = get(u, prm); log.append(f'{u.split("/")[4]} {nm}: {st} {body[:400]}')
        if nm == '없음':
            with open(f'{OUT}/nocode_{u.split("/")[4]}.json', 'w') as f: f.write(body)
codes = [f'16LTC{n:02d}' for n in range(1, 13)] + [f'07{a}-{n}' for a in ('KS', 'GG', 'YS', 'IC', 'TA', 'GS', 'BR') for n in (1, 2)] + ['01IC-1', 'TC_0001', 'CR_0001', 'PCT_0001', 'DT_0025', 'HF_0069', 'TW_0069']
for c in codes:
    st, body = get(T, {'type': 'json', 'obsCode': c, 'reqDate': td, 'min': 60, 'pageNo': 1, 'numOfRows': 3})
    log.append(f'time {c}: {st} {body[:220]}')
    time.sleep(0.1)
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
