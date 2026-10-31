"""자료 받기 6: 바다 격자 조석(TideBED) 2일치, 조류 지점 최강창낙조 전체 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
now = datetime.now(KST)
DAYS = [now.strftime('%Y%m%d'), (now + timedelta(days=7)).strftime('%Y%m%d')]
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
grid = [tuple(p) for p in json.load(open('.github/probe/grid.json'))]
ports = [(37.45, 126.6), (37.25, 126.47), (37.29, 126.57), (36.67, 126.13), (36.44, 126.52), (36.15, 126.5), (35.98, 126.56), (35.62, 126.47),
         (36.406, 126.486), (36.674, 126.129), (35.975, 126.563), (37.238, 126.428), (36.128, 126.495), (35.618, 126.301), (37.451, 126.592)]
crnt = json.load(open('.github/probe/crnt_west.json'))
with ThreadPoolExecutor(6) as ex:
    fut_tb = ex.map(tb, ports + grid)
    fut_fe = ex.map(fe, list(crnt))
    tbres = {f'{p[0]},{p[1]}': r for p, r in fut_tb}
    feres = {}; felog = []
    for code, rows, why in fut_fe:
        feres[code] = {'name': crnt[code]['name'], 'lat': crnt[code]['lat'], 'lon': crnt[code]['lon'], 'ev': rows}; felog.append(f'{code} {len(rows)} {why}')
with open(f'{OUT}/tidebed_grid.json', 'w') as f: json.dump(tbres, f, ensure_ascii=False, separators=(',', ':'))
with open(f'{OUT}/fldebb_all.json', 'w') as f: json.dump(feres, f, ensure_ascii=False, separators=(',', ':'))
ok = sum(1 for v in tbres.values() if isinstance(v, dict)); bad = [k for k, v in tbres.items() if not isinstance(v, dict)]
log = [f'days {DAYS}', f'tidebed ok {ok} / {len(tbres)}  none/fail {len(bad)} {bad[:20]}', *felog, f'{time.time()-t0:.0f}s']
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log))
