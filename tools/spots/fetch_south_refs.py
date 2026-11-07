"""남해 자료 받기 2: 새 기준 관측소(TideBED)마다 1년에 걸친 45일치 예측 조위 (조화분석용)
- 관측소마다 그 관측소를 기준으로 쓰는 격자 가운데 관측소에 가장 가까운 점으로 묻는다
- 인증키는 결과·기록에 남기지 않는다. 결과: probe-out/south/ref_series.json
"""
import json, os, re, subprocess, time, math, traceback, urllib.parse, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out/south'; os.makedirs(OUT, exist_ok=True)
log = []; T0 = time.time()
def push_log():
    open(f'{OUT}/log2.txt', 'w').write('\n'.join(log))
    subprocess.run(f'git config user.name "github-actions[bot]"; git config user.email "41898282+github-actions[bot]@users.noreply.github.com"; '
                   f'git add {OUT}/log2.txt && git commit -q -m "진행 [skip ci]" && (git push -q origin HEAD:probe || (git pull -q --rebase origin probe && git push -q origin HEAD:probe))',
                   shell=True, capture_output=True)
def say(m): log.append(f'[{time.time() - T0:.0f}s] {m}'); print(log[-1], flush=True); push_log()
B = 'https://apis.data.go.kr/1192136/'
CODES = collections.Counter()
def get(path, params, tries=4):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + path + q, headers={'Accept': 'application/json'}), timeout=30) as r:
                d = json.loads(r.read().decode('utf-8', 'replace'))
            c = d.get('header', {}).get('resultCode'); CODES[c] += 1
            if c == '00': return d['body']
            if c == '10': return None
        except Exception as e:
            CODES[type(e).__name__] += 1
        time.sleep(1 + i)
    return 'fail'
try:
    G = json.load(open(f'{OUT}/tidebed_grid.json'))
    west = set(json.load(open('probe-out/ref_series.json')))
    KX = math.cos(math.radians(36.6))
    pick = {}
    for k, v in G.items():
        if not isinstance(v, dict) or v['ref'] in west: continue
        la, lo = map(float, k.split(','))
        d = math.hypot((lo - float(v['rlon'])) * KX, la - float(v['rlat']))
        if v['ref'] not in pick or d < pick[v['ref']]['d']: pick[v['ref']] = {'q': k, 'd': d, 'rlat': v['rlat'], 'rlon': v['rlon']}
    say(f'새 기준 관측소 {len(pick)}곳: {", ".join(sorted(pick))}')
    json.dump(pick, open(f'{OUT}/ref_pick.json', 'w'), ensure_ascii=False)
    start = datetime(2026, 11, 1, tzinfo=KST)
    DAYS = [(start + timedelta(days=8 * i)).strftime('%Y%m%d') for i in range(45)]
    jobs = [(r, v['q'], d) for r, v in pick.items() for d in DAYS]
    def job(j):
        r, q, d = j; la, lo = q.split(',')
        b = get('tidebed/GetTidebedApiService', {'type': 'json', 'lat': la, 'lot': lo, 'reqDate': d, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
        if not isinstance(b, dict): return j, None
        it = b['items']['item']; it = it if isinstance(it, list) else [it]
        if it[0]['obsvtrNm'] != r: return j, f'ref changed {it[0]["obsvtrNm"]}'
        return j, {'r0': it[0]['obsrvnDt'], 'rh': [x['obsrvnHgt'] for x in it]}
    res = {}
    with ThreadPoolExecutor(6) as ex:
        for n, ((r, q, d), v) in enumerate(ex.map(job, jobs)):
            res.setdefault(r, {})[d] = v
            if n % 300 == 299: say(f'{n + 1}/{len(jobs)} · 응답 {dict(CODES)}')
    bad = sum(1 for r in res.values() for v in r.values() if not isinstance(v, dict))
    say(f'끝: 관측소 {len(res)} · 날 {len(DAYS)} · 못 받음 {bad} · 응답 {dict(CODES)}')
    json.dump(res, open(f'{OUT}/ref_series.json', 'w'), ensure_ascii=False, separators=(',', ':'))
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log2.txt', 'w').write('\n'.join(log))
print('\n'.join(log[-30:]))
