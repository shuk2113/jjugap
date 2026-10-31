"""자료 받기 7: 바다 격자 조석(TideBED) 이틀 더, 기상청 바다 격자 시험 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
now = datetime.now(KST)
DAYS = ['20261103', '20261114']
B = 'https://apis.data.go.kr/1192136/'
def get(path, params, tries=3):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + path + q, headers={'Accept': 'application/json'}), timeout=30) as r:
                d = json.loads(r.read().decode('utf-8', 'replace'))
            if d.get('header', {}).get('resultCode') == '00': return d['body']
            if d.get('header', {}).get('resultCode') == '10': return None   # 바다 밖·잘못된 값
        except Exception:
            pass
        time.sleep(1 + i)
    return 'fail'
def tb(p):
    la, lo = p; res = {}
    for ds in DAYS:
        b = get('tidebed/GetTidebedApiService', {'type': 'json', 'lat': la, 'lot': lo, 'reqDate': ds, 'min': 10, 'pageNo': 1, 'numOfRows': 200})
        if b is None or b == 'fail': return p, b
        it = b['items']['item']; it = it if isinstance(it, list) else [it]
        x = it[0]
        res.setdefault('ref', x['obsvtrNm']); res.setdefault('rlat', x['lat']); res.setdefault('rlon', x['lot'])
        res.setdefault('jogo', float(x['jogo'])); res.setdefault('josi', x['josi']); res.setdefault('msl', x['msl'])
        res.setdefault('c', [x[k] for k in ('m2TconstAmp', 'm2TconstTlag', 's2TconstAmp', 's2TconstTlag', 'k1TconstAmp', 'k1TconstTlag', 'o1TconstAmp', 'o1TconstTlag')])
        res.setdefault('rc', [x[k] for k in ('m2TdlvAmp', 'm2TdlvTlag', 's2TdlvAmp', 's2TdlvTlag', 'k1TdlvAmp', 'k1TdlvTlag', 'o1TdlvAmp', 'o1TdlvTlag')])
        res[ds] = {'t0': it[0]['slctdDt'], 'h': [float(y['slctdHgt']) for y in it], 'r0': it[0]['obsrvnDt'], 'rh': [y['obsrvnHgt'] for y in it]}
    return p, res
def fe(code):
    rows = []; pg = 1; total = None
    while True:
        b = get('crntFcstFldEbb/GetCrntFcstFldEbbApiService', {'type': 'json', 'obsCode': code, 'numOfRows': 100, 'pageNo': pg})
        if b is None or b == 'fail': return code, rows, f'page {pg} {b}'
        total = b.get('totalCount'); it = b['items']['item']; it = it if isinstance(it, list) else [it]
        rows += [(x['predcDt'], float(x['crdir']), float(x['crsp'])) for x in it]
        if len(rows) >= total or not it: break
        pg += 1
    return code, rows, 'ok'
t0 = time.time()
prev = json.load(open('probe-out/tidebed_grid.json'))
grid = [tuple(map(float, k.split(','))) for k, v in prev.items() if isinstance(v, dict)]
with ThreadPoolExecutor(6) as ex:
    tbres = {f'{p[0]},{p[1]}': r for p, r in ex.map(tb, grid)}
with open(f'{OUT}/tidebed_grid2.json', 'w') as f: json.dump(tbres, f, ensure_ascii=False, separators=(',', ':'))
ok = sum(1 for v in tbres.values() if isinstance(v, dict))
log = [f'days {DAYS}', f'tidebed ok {ok} / {len(tbres)}']
# 기상청 바다 격자: 파고가 나오는지
KMA = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'
c = now - timedelta(minutes=12); hs = [h for h in (2, 5, 8, 11, 14, 17, 20, 23) if h <= c.hour]
bd, bt = (c.strftime('%Y%m%d'), f'{max(hs):02d}00') if hs else ((c - timedelta(days=1)).strftime('%Y%m%d'), '2300')
cells = json.load(open('.github/probe/kma_cells.json'))
def kma(cell):
    x, y, la, lo = cell
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode({'pageNo': 1, 'numOfRows': 1500, 'dataType': 'JSON', 'base_date': bd, 'base_time': bt, 'nx': x, 'ny': y})
    t = time.time()
    try:
        with urllib.request.urlopen(KMA + q, timeout=30) as r: d = json.loads(r.read().decode())
        it = d['response']['body']['items']['item']
        w = [i for i in it if i['category'] == 'WAV']; ws = [i for i in it if i['category'] == 'WSD']
        return f'{x},{y} ({la},{lo}) n={len(it)} wav={len(w)} {[i["fcstValue"] for i in w[:4]]} wsd={[i["fcstValue"] for i in ws[:4]]} {time.time()-t:.1f}s'
    except Exception as e:
        return f'{x},{y} ERR {type(e).__name__} {time.time()-t:.1f}s'
t1 = time.time()
with ThreadPoolExecutor(4) as ex: log += list(ex.map(kma, cells))
log.append(f'kma {len(cells)} cells {time.time()-t1:.0f}s')
log.append(f'{time.time()-t0:.0f}s')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
