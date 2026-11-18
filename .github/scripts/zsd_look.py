# 공공데이터포털 파일데이터를 받아 앞부분·항목·범위만 적어 둔다 (원본 파일은 저장하지 않음)
import os, re, json, io, csv, urllib.request, urllib.parse, http.cookiejar, zipfile

UA = {'User-Agent': 'Mozilla/5.0 (jjugap data check)'}
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(url, data=None, hdr=None):
    h = dict(UA, **(hdr or {}))
    req = urllib.request.Request(url, data=data, headers=h)
    with op.open(req, timeout=120) as r:
        return r.read(), r.headers


def dec(b):
    for e in ('utf-8-sig', 'cp949', 'euc-kr'):
        try:
            return b.decode(e), e
        except UnicodeDecodeError:
            pass
    return b.decode('utf-8', 'replace'), 'utf-8?'


os.makedirs('.github/data/zsd', exist_ok=True)
for pk in [p.strip() for p in os.environ.get('PKS', '15147989').split(',') if p.strip()]:
    log = []
    try:
        page, _ = get(f'https://www.data.go.kr/data/{pk}/fileData.do')
        html = page.decode('utf-8', 'replace')
        uddis = sorted(set(re.findall(r'uddi:[0-9a-fA-F-]{20,}', html)))
        log.append(f'page {len(html)} bytes · uddi {uddis[:5]}')
        for m in re.finditer(r'(fileDataDown|selectFileDataDownload|fileDownload\.do)[^\n]{0,200}', html):
            log.append('js: ' + m.group(0)[:220])
            if len(log) > 12:
                break
        got = None
        for u in uddis[:3]:
            for fsn in ('1',):
                q = urllib.parse.urlencode({'recommendDataYn': 'Y', 'publicDataPk': pk, 'publicDataDetailPk': u, 'fileDetailSn': fsn})
                try:
                    b, h = get('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?' + q, hdr={'Referer': f'https://www.data.go.kr/data/{pk}/fileData.do', 'X-Requested-With': 'XMLHttpRequest'})
                    t = b.decode('utf-8', 'replace')
                    log.append(f'select {u}: {t[:300]}')
                    j = json.loads(t)
                    if j.get('atchFileId'):
                        dl = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode({'atchFileId': j['atchFileId'], 'fileDetailSn': j.get('fileDetailSn', fsn), 'dataNm': j.get('dataNm', '')})
                        b2, h2 = get(dl, hdr={'Referer': f'https://www.data.go.kr/data/{pk}/fileData.do'})
                        got = (b2, h2.get('Content-Disposition', ''), dl)
                        break
                except Exception as e:
                    log.append(f'select {u} 오류: {e}')
            if got:
                break
        if not got:
            log.append('파일을 받지 못함')
        else:
            b2, cd, dl = got
            log.append(f'받음 {len(b2)} bytes · {cd[:200]}')
            if b2[:2] == b'PK':
                z = zipfile.ZipFile(io.BytesIO(b2))
                log.append('zip: ' + ', '.join(z.namelist()[:10]))
                b2 = z.read(z.namelist()[0])
            txt, enc = dec(b2)
            lines = txt.splitlines()
            log.append(f'글자 {enc} · 줄 {len(lines)}')
            log += ['> ' + l[:400] for l in lines[:12]]
            # 서해(위도 34.5~38.2 · 경도 124.5~127) 줄만 세어 보기
            try:
                rd = csv.reader(io.StringIO(txt))
                head = next(rd)
                log.append('항목: ' + ' | '.join(head))
                lat_i = next((i for i, c in enumerate(head) if '위도' in c), None)
                lon_i = next((i for i, c in enumerate(head) if '경도' in c), None)
                zs_i = next((i for i, c in enumerate(head) if '투명' in c), None)
                t_i = next((i for i, c in enumerate(head) if ('일시' in c or '일자' in c or '년' in c)), None)
                n = w = zn = 0; ts = []; st = set()
                for row in rd:
                    n += 1
                    try:
                        la = float(row[lat_i]); lo = float(row[lon_i])
                    except Exception:
                        continue
                    if 34.5 <= la <= 38.2 and 124.5 <= lo <= 127.0:
                        w += 1; st.add((round(la, 3), round(lo, 3)))
                        if zs_i is not None and row[zs_i].strip() not in ('', '-', 'NaN'):
                            zn += 1
                        if t_i is not None:
                            ts.append(row[t_i])
                ts.sort()
                log.append(f'전체 {n} · 서해 {w} · 서해 투명도 있음 {zn} · 서해 정점 {len(st)} · 기간 {ts[:1]} ~ {ts[-1:]}')
            except Exception as e:
                log.append(f'csv 읽기 오류: {e}')
    except Exception as e:
        log.append(f'오류: {e}')
    open(f'.github/data/zsd/look_{pk}.txt', 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print(f'== {pk}'); print('\n'.join(log[:60]))
