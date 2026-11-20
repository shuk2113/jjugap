# 국립해양조사원_암초 SHP 확인용 (손으로만). robots.txt 허용일 때만 받음.
import re, json, os, io, zipfile, sys, urllib.request, urllib.parse, urllib.robotparser

UA = 'Mozilla/5.0 (jjugap reef probe)'
BASE = 'https://www.data.go.kr'
OUT = '.github/data/reef'
os.makedirs(OUT, exist_ok=True)
log = []
def L(*a):
    s = ' '.join(str(x) for x in a); print(s); log.append(s)

def get(url, binary=False):
    rq = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(rq, timeout=120) as r:
        b = r.read()
        return b if binary else b.decode('utf-8', 'replace')

rp = urllib.robotparser.RobotFileParser()
try:
    txt = get(BASE + '/robots.txt'); L('--- robots.txt ---'); L(txt[:1500])
    rp.parse(txt.splitlines())
except Exception as e:
    L('robots 읽기 실패', e); rp = None

def ok(url):
    if rp is None: return False
    a = rp.can_fetch(UA, url); L('robots', 'OK' if a else 'NO', url); return a

ds = os.environ.get('DSID', '').strip()
if not ds:
    q = BASE + '/tcs/dss/selectDataSetList.do?' + urllib.parse.urlencode({'keyword': '국립해양조사원_암초', 'dType': 'FILE'})
    if ok(q):
        h = get(q)
        ids = list(dict.fromkeys(re.findall(r'/data/(\d{7,9})/fileData\.do', h)))
        L('검색 결과 id', ids[:10])
        for i in ids[:10]:
            p = get(f'{BASE}/data/{i}/fileData.do')
            t = re.search(r'<title>(.*?)</title>', p, re.S)
            L(i, t.group(1).strip() if t else '?')
            if t and '암초' in t.group(1): ds = i; break
L('dataset', ds)
if not ds:
    open(OUT + '/probe.txt', 'w').write('\n'.join(log)); sys.exit(0)

page_url = f'{BASE}/data/{ds}/fileData.do'
p = get(page_url)
lic = re.findall(r'(공공저작물[^<]{0,40}|이용허락범위[^<]{0,80})', p)[:4]; L('라이선스', lic)
for m in re.finditer(r'(uddi:[0-9a-f\-]+|[Dd]own[A-Za-z]*\([^)]{0,160}\)|fileDetailSn[^,;]{0,40}|selectFileData[A-Za-z]*\.do[^"\']{0,120})', p):
    L('단서', m.group(0))
uddi = list(dict.fromkeys(re.findall(r'uddi:[0-9a-f\-]+', p)))
for u0 in uddi[:3]:
    for path in ['/tcs/dss/selectFileDataDownload.do', '/cmm/cmm/fileDownload.do']:
        u = BASE + path + '?' + urllib.parse.urlencode({'publicDataPk': ds, 'publicDataDetailPk': u0, 'fileDetailSn': '1'})
        if not ok(u): continue
        try:
            rq = urllib.request.Request(u, headers={'User-Agent': UA, 'Referer': page_url})
            with urllib.request.urlopen(rq, timeout=120) as r:
                b = r.read(); L('시도', path, r.status, r.headers.get('Content-Type'), len(b), b[:60])
                if b[:2] == b'PK': cand_bytes = b; raise StopIteration
                try:
                    j = json.loads(b.decode('utf-8','replace'))
                    d = j.get('dataSetFileDetailInfo') or {}
                    L('json키', {k: d[k] for k in d if any(w in k.lower() for w in ('atch','file','sn','nm','ext','size'))})
                    txt0 = b.decode('utf-8','replace')
                    L('최상위키', list(j.keys()))
                    for m in re.finditer(r'"(\w*(?:atch|File|file|url|Url)\w*)":\s*("[^"]{1,200}"|\d+)', txt0):
                        if m.group(2) not in ('""', 'null'): L('  ', m.group(1), m.group(2))
                    af = d.get('atchFileId') or (re.search(r'"atchFileId":"([^"]+)"', txt0) or [None, None])[1]
                    fs = d.get('fileDetailSn') or '1'
                    if af:
                        u2 = BASE + '/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode({'atchFileId': af, 'fileDetailSn': fs, 'dataNm': d.get('dataNm') or 'reef'})
                        if ok(u2):
                            rq2 = urllib.request.Request(u2, headers={'User-Agent': UA, 'Referer': page_url})
                            with urllib.request.urlopen(rq2, timeout=180) as r2:
                                b2 = r2.read(); L('파일', r2.status, r2.headers.get('Content-Type'), len(b2), b2[:4])
                                if b2[:2] == b'PK': cand_bytes = b2; raise StopIteration
                except Exception: pass
        except StopIteration: break
        except Exception as e: L('실패', path, e)
cand = sorted(set(re.findall(r"atchFileId[=\"':\s]+([A-Z0-9_]{10,})", p)))
L('atchFileId', cand)
sn = re.findall(r"fileDetailSn[=\"':\s]+(\d+)", p); L('fileDetailSn', sn[:3])
got = globals().get('cand_bytes')
for a in cand:
    u = f'{BASE}/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode({'atchFileId': a, 'fileDetailSn': (sn[0] if sn else '1'), 'dataNm': 'reef'})
    if not ok(u): continue
    try:
        b = get(u, True); L('받음', len(b), 'bytes', b[:4])
        if b[:2] == b'PK': got = b; break
    except Exception as e:
        L('실패', e)
if not got:
    open(OUT + '/probe.txt', 'w').write('\n'.join(log)); sys.exit(0)

open(OUT + '/reef.zip', 'wb').write(got)
z = zipfile.ZipFile(io.BytesIO(got)); L('zip', z.namelist())
import shapefile  # pyshp
shp = [n for n in z.namelist() if n.lower().endswith('.shp')]
summ = {'dataset': ds, 'files': z.namelist(), 'layers': []}
for s in shp:
    base = s[:-4]
    def f(ext):
        for n in z.namelist():
            if n.lower() == (base + ext).lower(): return io.BytesIO(z.read(n))
    prj = next((z.read(n).decode('utf-8', 'replace') for n in z.namelist() if n.lower() == (base + '.prj').lower()), '')
    r = shapefile.Reader(shp=f('.shp'), dbf=f('.dbf'), shx=f('.shx'), encoding='utf-8', encodingErrors='replace')
    flds = [x[0] for x in r.fields[1:]]
    recs = r.shapeRecords()
    ex = []
    for sr in recs[:8]:
        ex.append({'rec': dict(zip(flds, [str(v) for v in sr.record])), 'pt': sr.shape.points[:1], 'type': sr.shape.shapeTypeName})
    summ['layers'].append({'shp': s, 'n': len(recs), 'fields': flds, 'prj': prj[:300], 'bbox': list(r.bbox), 'sample': ex})
    L(s, len(recs), flds, r.bbox)
json.dump(summ, open(OUT + '/probe.json', 'w'), ensure_ascii=False, indent=1)
open(OUT + '/probe.txt', 'w').write('\n'.join(log))
