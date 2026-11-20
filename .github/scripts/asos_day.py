# 하루치 서해안 기상청 지상관측(ASOS) 시간자료 — 일사·일조·구름·비·바람 (출조한 날을 실제 빛으로 다시 셈하려고)
#  자료: 기상청_지상(종관, ASOS) 시간자료 조회서비스 (공공데이터포털 15057210 · 공공누리 제1유형 출처표시)
#  인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.
import os, re, json, time, urllib.request, urllib.parse, urllib.error
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
URL = 'https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
DAY = os.environ['DAY'].replace('-', '')
STNS = [int(s) for s in os.environ.get('STNS', '140,243,235').split(',')]
F = ['ta', 'rn', 'ws', 'wd', 'ss', 'icsr', 'dc10Tca', 'dc10LmcsCa', 'vs']
out = {'src': '기상청 지상관측(ASOS) 시간자료 · 공공데이터포털 15057210 · 공공누리 제1유형', 'day': DAY, 'stn': {}}
for s in STNS:
    u = f'{URL}?serviceKey={KEY}&' + urllib.parse.urlencode({'pageNo': 1, 'numOfRows': 30, 'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR', 'startDt': DAY, 'startHh': '00', 'endDt': DAY, 'endHh': '23', 'stnIds': s}, safe='')
    t = None
    for i in range(3):
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                t = r.read().decode('utf-8', 'replace'); break
        except Exception as e:
            print('err', s, type(e).__name__); time.sleep(3)
    try:
        items = json.loads(t)['response']['body']['items']['item']
    except Exception:
        print('bad', s, re.sub(r'\s+', ' ', (t or '')[:160])); continue
    rows = []
    for it in items:
        rows.append([it['tm'][11:13]] + [it.get(k, '') for k in F])
    out['stn'][str(s)] = {'nm': items[0].get('stnNm', ''), 'rows': rows}
    print('== ', s, items[0].get('stnNm', ''), '시각', F)
    for r in rows:
        print(' ', r)
os.makedirs('.github/data/wind', exist_ok=True)
json.dump(out, open(f'.github/data/wind/asos_{DAY}.json', 'w'), ensure_ascii=False)
