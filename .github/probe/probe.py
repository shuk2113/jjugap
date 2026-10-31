"""자료 알아보기 5: 수온 관측소 후보, 최강창낙조 범위, TideBED 속도 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
now = datetime.now(KST); td = now.strftime('%Y%m%d')
B = 'https://apis.data.go.kr/1192136/'
def get(path, params, timeout=25):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    t = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(B + path + q, headers={'Accept': 'application/json'}), timeout=timeout) as r:
            return r.read().decode('utf-8', 'replace').replace(KEY, '***'), time.time() - t
    except Exception as e:
        return f'ERR {type(e).__name__} {str(e)[:120]}', time.time() - t
log = []
# 1) 수온 관측소 후보
for c in ['DT_0065', 'DT_0017', 'DT_0050', 'DT_0037', 'DT_0024', 'DT_0003', 'DT_0093', 'DT_0052', 'DT_0032', 'DT_0044', 'DT_0002',
          'TW_0079', 'TW_0069', 'TW_0072', 'TW_0082', 'TW_0070', 'TW_0076', 'TW_0077', 'KG_0202', 'HF_0070', 'HF_0076']:
    b, dt = get('dtRecent/GetDTRecentApiService', {'type': 'json', 'obsCode': c, 'reqDate': td, 'min': 60, 'pageNo': 1, 'numOfRows': 300})
    try:
        it = json.loads(b)['body']['items']['item']; it = it if isinstance(it, list) else [it]
        last = it[-1]; w = [x.get('wtem') for x in it if x.get('wtem') not in (None, '', '-')]
        log.append(f'obs {c}: n={len(it)} last={ {k: last.get(k) for k in ("obsvtrNm","obsrvnDt","wtem","bscTdlvHgt")} } wtem_n={len(w)} sample={w[-3:]}')
        if c == 'TW_0079': log.append('  keys ' + ','.join(last.keys()))
    except Exception:
        log.append(f'obs {c}: {b[:160]}')
    time.sleep(0.1)
# 2) 최강창낙조 범위와 쪽 나누기
for prm in ({'numOfRows': 1000, 'pageNo': 1}, {'numOfRows': 1000, 'pageNo': 6}, {'numOfRows': 500, 'pageNo': 11}, {'numOfRows': 100, 'pageNo': 57}):
    b, dt = get('crntFcstFldEbb/GetCrntFcstFldEbbApiService', {'type': 'json', 'obsCode': '16LTC03', **prm}, 40)
    try:
        bd = json.loads(b)['body']; it = bd['items']['item']
        log.append(f'fldebb {prm}: total={bd.get("totalCount")} n={len(it)} {it[0]["predcDt"]} .. {it[-1]["predcDt"]} ({dt:.1f}s)')
        if prm['pageNo'] == 11:
            with open(f'{OUT}/fldebb_p11.json', 'w') as f: f.write(b)
    except Exception:
        log.append(f'fldebb {prm}: {b[:200]}')
b, dt = get('crntFcstFldEbb/GetCrntFcstFldEbbApiService', {'type': 'json', 'obsCode': '16LTC03', 'reqDate': td, 'numOfRows': 30, 'pageNo': 1})
log.append(f'fldebb reqDate: {b[:260]}')
# 시계열 견본 (어제·오늘·내일, 10분)
ser = {}
for d in (-1, 0, 1):
    ds = (now + timedelta(days=d)).strftime('%Y%m%d')
    b, dt = get('crntFcstTime/GetCrntFcstTimeApiService', {'type': 'json', 'obsCode': '16LTC03', 'reqDate': ds, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
    try: ser[ds] = [(x['predcDt'], x['crdir'], x['crsp']) for x in json.loads(b)['body']['items']['item']]
    except Exception: log.append(f'series {ds}: {b[:150]}')
with open(f'{OUT}/series_16LTC03.json', 'w') as f: json.dump(ser, f, ensure_ascii=False)
# 3) TideBED 속도·바다 밖/육지
tests = [(36.30, 126.20), (36.00, 125.50), (36.60, 126.80), (36.25, 126.10), (37.10, 126.10), (35.70, 126.20)]
for la, lo in tests:
    b, dt = get('tidebed/GetTidebedApiService', {'type': 'json', 'lat': la, 'lot': lo, 'reqDate': td, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
    try:
        it = json.loads(b)['body']['items']['item']; it = it if isinstance(it, list) else [it]
        x = it[0]; log.append(f'tidebed {la},{lo}: n={len(it)} ref={x["obsvtrNm"]} jogo={float(x["jogo"]):.3f} josi={x["josi"]} msl={x["msl"]:.1f} ({dt:.2f}s)')
    except Exception:
        log.append(f'tidebed {la},{lo}: {b[:200]} ({dt:.2f}s)')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
