# 위성 물색 자료 살펴보기 (형식·이용조건·받기 가능 여부만 적어 둠 · 원본은 저장하지 않음)
import os, re, json, urllib.request, http.cookiejar, datetime as dt

UA = {'User-Agent': 'Mozilla/5.0 (jjugap data check)'}
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
out = {'when': dt.datetime.utcnow().isoformat() + 'Z'}


def get(url, n=None, timeout=60):
    if not url.endswith('/robots.txt') and not allowed(url):
        return {'ok': False, 'err': 'robots 금지 · 안 읽음'}, b''
    return get0(url, n, timeout)


def get0(url, n=None, timeout=60):
    try:
        req = urllib.request.Request(url, headers=UA)
        with op.open(req, timeout=timeout) as r:
            b = r.read(n) if n else r.read()
            return {'ok': True, 'code': r.status, 'url': r.geturl(), 'len': len(b), 'ct': r.headers.get('Content-Type', ''), 'cl': r.headers.get('Content-Length', '')}, b
    except Exception as e:
        return {'ok': False, 'err': repr(e)[:300]}, b''


import urllib.robotparser
RP = {}


def allowed(url):
    from urllib.parse import urlparse
    h = urlparse(url); key = h.scheme + '://' + h.netloc
    if key not in RP:
        rp = urllib.robotparser.RobotFileParser(); m, b = get0(key + '/robots.txt')
        if m.get('ok') and m.get('code') == 200:
            rp.parse(txt(b).splitlines())
        else:
            rp.parse([])   # 없으면 막는 규칙 없음
        RP[key] = rp
    return RP[key].can_fetch('*', url)


def txt(b):
    return b.decode('utf-8', 'replace')


def snips(t, pats, w=200, k=8):
    res = []
    for p in pats:
        for m in re.finditer(p, t):
            s = max(0, m.start() - w); res.append(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t[s:m.end() + w])))
            if len(res) >= k:
                return res
    return res


# 1) 로봇 규칙
for host in ['https://www.nosc.go.kr', 'https://nosc.go.kr', 'https://coastwatch.noaa.gov', 'https://coastwatch.pfeg.noaa.gov']:
    m, b = get(host + '/robots.txt')
    out['robots ' + host] = dict(m, body=txt(b)[:3000])

# 2) 천리안 누리집: 저작권·이용조건 문구 찾기
m, b = get('https://www.nosc.go.kr/main.do')
t = txt(b); out['nosc main'] = m
links = sorted(set(re.findall(r'href="([^"]+)"', t)))
out['nosc links'] = [l for l in links if re.search(r'copy|policy|저작|약관|terms|privacy|Cons00|download|opendap|wd/', l, re.I)][:80]
out['nosc main snips'] = snips(t, [r'공공누리', r'저작권', r'이용약관', r'출처'])
for path in ['/boardContents/actionBoardContentsCons0008.do', '/boardContents/actionBoardContentsCons0030.do', '/boardContents/actionBoardContentsCons0031.do',
             '/boardContents/actionBoardContentsCons0032.do', '/boardContents/actionBoardContentsCons0033.do', '/boardContents/actionBoardContentsCons0034.do',
             '/boardContents/actionBoardContentsCons0035.do', '/boardContents/actionBoardContentsCons0036.do', '/boardContents/actionBoardContentsCons0037.do',
             '/program/actionGociDownload.do', '/wd/zTreeView.do', '/opendap/']:
    m, b = get('https://www.nosc.go.kr' + path)
    t = txt(b)
    ti = re.search(r'<title>(.*?)</title>', t, re.S)
    h = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', t, re.S)
    out['page ' + path] = dict(m, title=(ti.group(1).strip() if ti else ''), heads=[re.sub(r'<[^>]+>|\s+', ' ', x).strip() for x in h][:12],
                               snips=snips(t, [r'공공누리', r'저작권', r'이용\s*조건', r'이용약관', r'출처\s*표시', r'상업', r'라이선스|license'], k=10))
for l in out['nosc links']:
    if re.search(r'copy|저작|약관|policy', l, re.I):
        u = l if l.startswith('http') else 'https://www.nosc.go.kr' + (l if l.startswith('/') else '/' + l)
        m, b = get(u); t = txt(b)
        out['link ' + l] = dict(m, snips=snips(t, [r'공공누리', r'저작권', r'출처', r'상업', r'변경', r'위성자료'], k=14))

# 3) OPeNDAP 목록과 투명도(Zsd) 파일 머리 정보
day = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime('%Y/%m/%d')
for base in ['https://www.nosc.go.kr/opendap/hyrax/GOCI-II/', 'https://nosc.go.kr/opendap/hyrax/GOCI-II/', 'https://nosc.go.kr/opendap/GOCI-II/']:
    u = base + day + '/L2/contents.html'
    m, b = get(u); t = txt(b)
    dirs = sorted(set(re.findall(r'(GK2_GC2_L2_\d{8}_\d{6})', t)))
    out['opendap ' + u] = dict(m, dirs=dirs, head=t[:600] if not dirs else '')
    if dirs:
        d0 = dirs[len(dirs) // 2]
        u2 = base + day + '/L2/' + d0 + '/contents.html'
        m2, b2 = get(u2); t2 = txt(b2)
        files = sorted(set(re.findall(r'(GK2B_GOCI2_L2_[\w]+?\.nc)', t2)))
        sizes = re.findall(r'(GK2B_GOCI2_L2_[\w]+?_(?:Zsd|Kd|TSS)\.nc)[\s\S]{0,400}?(\d[\d.]*\s*[KMG]B?)', t2)
        out['dir ' + d0] = dict(m2, n=len(files), zsd=[f for f in files if 'Zsd' in f or 'ZSD' in f], kd=[f for f in files if '_Kd' in f][:4], tss=[f for f in files if 'TSS' in f][:4], sizes=sizes[:20], sample=files[:30])
        zf = [f for f in files if re.search(r'Zsd', f, re.I)]
        if zf:
            f0 = next((f for f in zf if '_LA_Zsd' in f or 'LA_S' not in f), zf[0])
            for ext in ['.das', '.dds']:
                m3, b3 = get(base + day + '/L2/' + d0 + '/' + f0 + ext)
                out[ext + ' ' + f0] = dict(m3, body=txt(b3)[:6000])
        break

# 4) NOAA ERDDAP: 우리 바다를 덮는 Kd490 목록과 마지막 날짜
for srv in ['https://coastwatch.noaa.gov/erddap', 'https://coastwatch.pfeg.noaa.gov/erddap']:
    u = srv + '/search/advanced.json?searchFor=kd490&minLat=34&maxLat=38&minLon=124&maxLon=127&itemsPerPage=60'
    m, b = get(u)
    rows = []
    try:
        j = json.loads(b); cols = j['table']['columnNames']
        for r in j['table']['rows']:
            d = dict(zip(cols, r)); rows.append([d.get('Dataset ID'), d.get('Title'), d.get('maxTime') or d.get('Max Time') or ''])
    except Exception as e:
        rows = [repr(e)[:200], txt(b)[:300]]
    out['erddap ' + srv] = dict(m, rows=rows)
    for r in rows:
        if isinstance(r, list) and r[0]:
            m2, b2 = get(srv + '/info/' + r[0] + '/index.json')
            try:
                jj = json.loads(b2); a = {x[2]: x[4] for x in jj['table']['rows'] if x[0] == 'attribute' and x[1] == 'NC_GLOBAL' and x[2] in ('time_coverage_end', 'geospatial_lat_resolution', 'license', 'title')}
                r.append(a)
            except Exception:
                pass

os.makedirs('.github/data/sat', exist_ok=True)
json.dump(out, open('.github/data/sat/look.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:3000])
