# 센 바람 뒤 흙탕이 얼마나 남는지 맞추기용: 서해안 기상청 지상관측(ASOS) 시간별 바람 긴 기록 → 실행 기록에만 압축해 남김 (저장소에 안 남김)
#  자료: 기상청_지상(종관, ASOS) 시간자료 조회서비스 (공공데이터포털 15057210 · 공공누리 제1유형 출처표시)
#  인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.
import os, re, json, time, gzip, base64, urllib.request, urllib.parse, urllib.error, datetime as dt
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
URL = 'https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
STN = [112, 129, 235, 140]
d0, d1 = dt.date.fromisoformat(os.environ.get('D0', '2023-09-01')), dt.date.fromisoformat(os.environ.get('D1', '2026-11-26'))
def get(q):
    u = f'{URL}?serviceKey={KEY}&' + urllib.parse.urlencode(q, safe='')
    for i in range(4):
        try:
            with urllib.request.urlopen(u, timeout=60) as r: return json.loads(r.read().decode('utf-8', 'replace'))['response']['body']['items']['item']
        except urllib.error.HTTPError as e: print('HTTP', e.code, flush=True); time.sleep(5 + 5 * i)
        except Exception as e: print('ERR', type(e).__name__, flush=True); time.sleep(5 + 5 * i)
    return []
out = {}
for s in STN:
    W = out.setdefault(str(s), {}); a = d0
    while a <= d1:
        b = min(d1, a + dt.timedelta(days=40))
        for it in get({'pageNo': 1, 'numOfRows': 999, 'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR', 'startDt': a.strftime('%Y%m%d'), 'startHh': '00', 'endDt': b.strftime('%Y%m%d'), 'endHh': '23', 'stnIds': s}):
            ws, wd = it.get('ws'), it.get('wd')
            if ws not in (None, ''): W[it['tm'].replace('-', '').replace(' ', '').replace(':', '')[:10]] = [float(ws), float(wd) if wd not in (None, '') else -1]
        print(s, a, len(W), flush=True); a = b + dt.timedelta(days=1); time.sleep(0.5)
blob = base64.b64encode(gzip.compress(json.dumps(out, separators=(',', ':')).encode(), 9)).decode()
for i in range(0, len(blob), 60000): print(f'SER {i // 60000} {blob[i:i + 60000]}', flush=True)
print('SEREND', len(blob))
