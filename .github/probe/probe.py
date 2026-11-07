"""남해 자료 받기 3: 조위관측소 수온 목록(이름·위치·수온 있는지) 훑기 + 기상청 중기 해상예보 남해·제주 해역 코드 확인
인증키는 결과·기록에 남기지 않는다. 결과: probe-out/south/obs_list.json, probe-out/south/log3.txt"""
import json, os, re, time, traceback, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out/south'; os.makedirs(OUT, exist_ok=True)
log = []
def raw(url, params):
    q = f'?serviceKey={KEY}&' + urllib.parse.urlencode(params, safe='')
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + q, headers={'Accept': 'application/json'}), timeout=25) as r:
                return r.read().decode('utf-8', 'replace').replace(KEY, '***')
        except Exception as e:
            err = f'ERR {type(e).__name__}'
        time.sleep(1 + i)
    return err
now = datetime.now(KST); td = now.strftime('%Y%m%d')
try:
    OBS = 'https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService'
    def one(code):
        b = raw(OBS, {'type': 'json', 'obsCode': code, 'reqDate': td, 'min': 60, 'pageNo': 1, 'numOfRows': 30})
        try:
            d = json.loads(b); it = d['body']['items']['item']; it = it if isinstance(it, list) else [it]
            last = it[-1]; w = [x.get('wtem') for x in it if x.get('wtem') not in (None, '', '-')]
            return code, {'name': last.get('obsvtrNm'), 'lat': last.get('lat'), 'lon': last.get('lot'), 't': last.get('obsrvnDt'), 'wtem': last.get('wtem'), 'wn': len(w), 'keys': sorted(last.keys()) if code == 'DT_0001' else None}
        except Exception:
            return code, {'err': b[:160]}
    codes = [f'DT_{i:04d}' for i in range(1, 100)] + [f'IE_{i:04d}' for i in range(1, 8)]
    with ThreadPoolExecutor(5) as ex: res = dict(ex.map(one, codes))
    got = {k: v for k, v in res.items() if 'name' in v and v['name']}
    json.dump(got, open(f'{OUT}/obs_list.json', 'w'), ensure_ascii=False, indent=0)
    log.append(f'관측소 {len(got)}곳 (수온 있음 {sum(1 for v in got.values() if v["wn"])})')
    for k, v in got.items(): log.append(f'  {k} {v["name"]} {v["lat"]},{v["lon"]} 수온 {v["wtem"]} ({v["wn"]}) {v["t"]}' + (f' keys {v["keys"]}' if v.get('keys') else ''))
    # 중기 해상예보 해역 코드
    MID = 'https://apis.data.go.kr/1360000/MidFcstInfoService/getMidSeaFcst'
    h = now.hour; tm = now.strftime('%Y%m%d') + ('1800' if h >= 18 else '0600') if h >= 6 else (now - timedelta(days=1)).strftime('%Y%m%d') + '1800'
    for reg in ('12A20000', '12A30000', '12B10000', '12B20000', '12B10500', '12C10000', '12C20000', '12C30000'):
        b = raw(MID, {'pageNo': 1, 'numOfRows': 10, 'dataType': 'JSON', 'regId': reg, 'tmFc': tm})
        log.append(f'중기 {reg}: {b[:220]}')
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log3.txt', 'w').write('\n'.join(log))
print('\n'.join(log))
