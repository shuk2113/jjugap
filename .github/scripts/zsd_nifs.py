# 국립수산과학원 정선해양관측(공공데이터포털 15147989, 이용허락범위 제한 없음)에서 서해 정점별 · 달별 투명도(m)만 뽑는다
# 한 번 관측(정점 · 관측일시)마다 투명도는 한 값 → 정점 · 달마다 가운데값과 횟수
import os, re, io, csv, json, time, statistics, urllib.request, urllib.parse, http.cookiejar

PK = '15147989'
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
UA = {'User-Agent': 'Mozilla/5.0 (jjugap data)'}


def get(url, hdr=None):
    with op.open(urllib.request.Request(url, headers=dict(UA, **(hdr or {}))), timeout=180) as r:
        return r.read()


html = get(f'https://www.data.go.kr/data/{PK}/fileData.do').decode('utf-8', 'replace')
u = re.search(r"fileDataDown\('" + PK + r"',\s*'(uddi:[0-9a-fA-F-]+)'", html).group(1)
q = urllib.parse.urlencode({'recommendDataYn': 'Y', 'publicDataPk': PK, 'publicDataDetailPk': u, 'fileDetailSn': '1'})
j = json.loads(get('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?' + q, {'Referer': f'https://www.data.go.kr/data/{PK}/fileData.do', 'X-Requested-With': 'XMLHttpRequest'}).decode('utf-8'))
b = get('https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode({'atchFileId': j['atchFileId'], 'fileDetailSn': j.get('fileDetailSn', '1')}), {'Referer': f'https://www.data.go.kr/data/{PK}/fileData.do'})
txt = b.decode('cp949', 'replace')
rd = csv.DictReader(io.StringIO(txt))
casts = {}
for r in rd:
    try:
        la, lo = float(r['위도']), float(r['경도'])
    except Exception:
        continue
    if not (34.3 <= la <= 38.3 and 124.3 <= lo <= 127.2):
        continue
    z = (r.get('투명도') or '').strip()
    if z in ('', '-', 'NaN'):
        continue
    try:
        z = float(z)
    except Exception:
        continue
    if not (0.1 <= z <= 40):
        continue
    key = (r['정선'], r['정점'], r['관측일시'][:16])
    casts[key] = (la, lo, z, r['관측일시'])
st = {}
for (ln, pt, _), (la, lo, z, t) in casts.items():
    s = st.setdefault((ln, pt), {'line': ln, 'st': pt, 'lat': [], 'lon': [], 'm': {}, 'all': [], 'yr': []})
    s['lat'].append(la); s['lon'].append(lo); s['all'].append(z); s['yr'].append(int(t[:4]))
    s['m'].setdefault(int(t[5:7]), []).append(z)
out = []
for s in st.values():
    out.append({'line': s['line'], 'st': s['st'], 'lat': round(statistics.median(s['lat']), 4), 'lon': round(statistics.median(s['lon']), 4),
                'n': len(s['all']), 'med': round(statistics.median(s['all']), 2), 'yr': [min(s['yr']), max(s['yr'])],
                'm': {str(k): [round(statistics.median(v), 2), len(v)] for k, v in sorted(s['m'].items())}})
out.sort(key=lambda x: (x['line'], int(x['st']) if x['st'].isdigit() else 99))
os.makedirs('.github/data/zsd', exist_ok=True)
json.dump({'src': '국립수산과학원 정선해양관측정보 (공공데이터포털 15147989 · 이용허락범위 제한 없음)', 'when': time.strftime('%Y-%m-%d'), 'casts': len(casts), 'st': out},
          open('.github/data/zsd/nifs_zsd.json', 'w'), ensure_ascii=False, indent=0)
print('관측', len(casts), '정점', len(out))
for s in out:
    print(s['line'], s['st'], s['lat'], s['lon'], 'n', s['n'], 'med', s['med'], s['yr'], {k: v[0] for k, v in s['m'].items()})
