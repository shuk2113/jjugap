"""누리집 상세 번호별 관측소 목록 훑기 + ROMS 수치모델 시험 (인증키는 결과에 남기지 않는다)"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = 'probe-out'; os.makedirs(OUT, exist_ok=True)
now = datetime.now(KST); td = now.strftime('%Y%m%d')
def get(url, params=None, data=None, headers=None, timeout=25):
    q = ('?' + (f'serviceKey={KEY}&' if 'apis.data.go.kr' in url else '') + urllib.parse.urlencode(params or {}, safe='')) if params is not None else ''
    h = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*'}; h.update(headers or {})
    req = urllib.request.Request(url + q, data=urllib.parse.urlencode(data).encode() if data else None, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace').replace(KEY, '***')
    except Exception as e:
        return -1, f'{type(e).__name__}: {str(e)[:300]}'.replace(KEY, '***')
log, found = [], {}
for i in range(1, 121):
    st, body = get('https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do', data={'id': str(i)},
                   headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': f'https://www.khoa.go.kr/oceandata/openapi/openApiDetail.do?id={i}'})
    try:
        d = json.loads(body)
    except Exception:
        log.append(f'{i}: {st} JSON 아님 {body[:80]}'); continue
    rows = d.get('observatoryList') or []
    det = d.get('openapiinfoDetail') or {}
    title = det.get('title') or det.get('apiNm') or det.get('openapiNm') or det.get('dataNm') or ''
    if not title and isinstance(det, dict):
        title = next((str(v) for k, v in det.items() if isinstance(v, str) and 2 < len(v) < 40 and re.search('[가-힣]', v)), '')
    log.append(f'{i}: 관측소 {len(rows)} · {title}')
    if rows:
        found[i] = {'title': title, 'n': len(rows), 'sample': rows[:2], 'keys': list(det.keys())[:30] if isinstance(det, dict) else []}
        with open(f'{OUT}/portal_{i}.json', 'w') as f: json.dump(d, f, ensure_ascii=False)
    time.sleep(0.15)
with open(f'{OUT}/portal_found.json', 'w') as f: json.dump(found, f, ensure_ascii=False, indent=1)
# ROMS 수치모델 (오천항 앞바다 작은 네모)
for path in ('https://apis.data.go.kr/1192136/roms/GetRomsApiService', 'https://apis.data.go.kr/1192000/service/OceansData/roms/GetRomsApiService'):
    st, body = get(path, {'type': 'json', 'ymin': 36.30, 'ymax': 36.40, 'xmin': 126.30, 'xmax': 126.40, 'pageNo': 1, 'numOfRows': 20})
    log.append(f'ROMS {path.split("/")[3]}: {st} {body[:300]}')
with open(f'{OUT}/log.txt', 'w') as f: f.write('\n'.join(log))
print('\n'.join(log[-30:]))
