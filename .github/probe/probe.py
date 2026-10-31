"""자료 받기 8: TideBED 기준 관측소 42곳의 예측 조위를 1년에 걸쳐 45일치 (조화분석용) + 다른 서비스 사용 가능 여부"""
import json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
B = 'https://apis.data.go.kr/1192136/'
def raw(path, params):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    try:
        with urllib.request.urlopen(urllib.request.Request(B + path + q, headers={'Accept': 'application/json'}), timeout=30) as r:
            return r.read().decode('utf-8', 'replace').replace(KEY, '***')
    except urllib.error.HTTPError as e:
        return f'HTTP {e.code} {e.read().decode("utf-8", "replace")[:150]}'
    except Exception as e:
        return f'ERR {type(e).__name__}'
def get(path, params, tries=3):
    for i in range(tries):
        b = raw(path, params)
        try:
            d = json.loads(b)
            c = d.get('header', {}).get('resultCode')
            if c == '00': return d['body']
            if c == '10': return None
        except Exception:
            pass
        time.sleep(1 + i)
    return 'fail'
log = []
td = datetime.now(KST).strftime('%Y%m%d')
for nm, path, prm in (('조석예보 시계열', 'tideFcstTime/GetTideFcstTimeApiService', {'obsCode': 'DT_0025', 'reqDate': td, 'min': 60}),
                      ('조석예보 고저조', 'tideFcstHghLw/GetTideFcstHghLwApiService', {'obsCode': 'DT_0025', 'reqDate': td}),
                      ('부이 최신', 'twRecent/GetTWRecentApiService', {'obsCode': 'TW_0079', 'reqDate': td, 'min': 60}),
                      ('1시간 조위', 'hourlyTide/GetHourlyTideApiService', {'obsCode': 'DT_0025', 'reqDate': td})):
    log.append(f'{nm}: {raw(path, {"type": "json", "pageNo": 1, "numOfRows": 5, **prm})[:260]}')
pick = json.load(open('.github/probe/ref_pick.json'))
start = datetime(2026, 11, 1, tzinfo=KST)
DAYS = [(start + timedelta(days=8 * i)).strftime('%Y%m%d') for i in range(45)]
jobs = [(r, v['q'], d) for r, v in pick.items() for d in DAYS]
def job(j):
    r, q, d = j; la, lo = q.split(',')
    b = get('tidebed/GetTidebedApiService', {'type': 'json', 'lat': la, 'lot': lo, 'reqDate': d, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
    if not isinstance(b, dict): return j, None
    it = b['items']['item']; it = it if isinstance(it, list) else [it]
    if it[0]['obsvtrNm'] != r: return j, f'ref changed {it[0]["obsvtrNm"]}'
    return j, {'r0': it[0]['obsrvnDt'], 'rh': [x['obsrvnHgt'] for x in it], 'rc': [it[0][k] for k in ('m2TdlvAmp', 'm2TdlvTlag', 's2TdlvAmp', 's2TdlvTlag', 'k1TdlvAmp', 'k1TdlvTlag', 'o1TdlvAmp', 'o1TdlvTlag')]}
t0 = time.time()
res = {}
with ThreadPoolExecutor(6) as ex:
    for (r, q, d), v in ex.map(job, jobs):
        res.setdefault(r, {})[d] = v
bad = sum(1 for r in res.values() for v in r.values() if not isinstance(v, dict))
log.append(f'refs {len(res)} days {len(DAYS)} bad {bad} {time.time()-t0:.0f}s')
with open(f'{OUT}/ref_series.json', 'w') as f: json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
