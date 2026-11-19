# 맑은 날(위성 셈 맞추기) 72일과 그 전날의 서해안 기상청 지상관측(ASOS) 시간별 바람 — 바람 방향이 물색에 주는 몫을 확인하려고
#  자료: 기상청_지상(종관, ASOS) 시간자료 조회서비스 (공공데이터포털 15057210 · 공공누리 제1유형 출처표시)
#  인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.
import os, re, json, time, urllib.request, urllib.parse, datetime as dt
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
URL = 'https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
STN = {102: ('백령도', 37.9666, 124.6305), 201: ('강화', 37.7074, 126.4463), 112: ('인천', 37.4776, 126.6244), 129: ('서산', 36.7766, 126.4939),
       235: ('보령', 36.3272, 126.5574), 140: ('군산', 36.0053, 126.7614), 243: ('부안', 35.7295, 126.7166), 172: ('고창', 35.3482, 126.5990)}
days = [d.strip() for d in os.environ['DAYS'].split(',') if d.strip()]
out = {'src': '기상청 지상관측(ASOS) 시간자료 · 공공데이터포털 15057210 · 공공누리 제1유형', 'stn': {k: v for k, v in STN.items()}, 'w': {}, 'err': []}
def get(q):
    u = f'{URL}?serviceKey={KEY}&' + urllib.parse.urlencode(q, safe='')
    for i in range(3):
        try:
            with urllib.request.urlopen(u, timeout=30) as r: return r.read().decode('utf-8', 'replace')
        except Exception as e: err = type(e).__name__; time.sleep(3 + 3 * i)
    return None
for d in days:
    d1 = dt.date.fromisoformat(d); d0 = d1 - dt.timedelta(days=1)
    for s in STN:
        t = get({'pageNo': 1, 'numOfRows': 60, 'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR', 'startDt': d0.strftime('%Y%m%d'), 'startHh': '00', 'endDt': d1.strftime('%Y%m%d'), 'endHh': '23', 'stnIds': s})
        if not t: out['err'].append([d, s, 'net']); continue
        try:
            items = json.loads(t)['response']['body']['items']['item']
        except Exception:
            out['err'].append([d, s, re.sub(r'\s+', ' ', t[:160])]); continue
        W = out['w'].setdefault(str(s), {})
        for it in items:
            ws, wd = it.get('ws'), it.get('wd')
            if ws not in (None, '') and wd not in (None, ''): W[it['tm'].replace('-', '').replace(' ', '').replace(':', '')[:10]] = [float(ws), float(wd)]
        time.sleep(0.3)
    print(d, sum(len(v) for v in out['w'].values()), len(out['err']), flush=True)
    if len(out['err']) > 40 and not out['w']: print('stop: 처음부터 안 됨', out['err'][:2]); break
os.makedirs('.github/data/wind', exist_ok=True)
json.dump(out, open('.github/data/wind/asos72.json', 'w'), ensure_ascii=False)
