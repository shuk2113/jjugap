"""해양수산부 어항·항포구 목록(공공데이터포털 파일데이터, 로그인 없이 받는 공개 자료) 받기
소규모항 · 마을공동어항 · 지방어항 · 어촌정주어항 · 소형선항만안내 · 어촌어항현황"""
import json, os, re, traceback, urllib.request, urllib.parse, http.cookiejar
log = []
os.makedirs('probe-out/ports', exist_ok=True)
IDS = {'15148635': '소규모항', '15144585': '마을공동어항', '15147449': '지방어항', '15147417': '어촌정주어항', '15148613': '소형선항만안내', '15059868': '어촌어항현황'}
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'), ('Accept-Language', 'ko-KR,ko;q=0.9')]
def get(url, ref=None):
    req = urllib.request.Request(url)
    if ref: req.add_header('Referer', ref)
    with op.open(req, timeout=90) as r: return r.read(), r.headers
for pid, nm in IDS.items():
    try:
        page = f'https://www.data.go.kr/data/{pid}/fileData.do'
        html = get(page)[0].decode('utf-8', 'ignore')
        uddis = sorted(set(re.findall(r'uddi:[0-9a-zA-Z\-_]+', html)))
        log.append(f'== {pid} {nm} uddi={uddis[:4]}')
        for m in re.finditer(r'(fn_\w*[Dd]own\w*\([^)]*\)|selectFileDataDownload[^"\']*|fileDownload\.do[^"\']*|atchFileId[^,;]{0,80})', html):
            log.append('   js: ' + m.group(0)[:200])
        got = False
        for u in uddis:
            for url in (f'https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?recommendDataYn=Y&publicDataPk={pid}&publicDataDetailPk={urllib.parse.quote(u)}',
                        f'https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?publicDataPk={pid}&publicDataDetailPk={urllib.parse.quote(u)}'):
                try:
                    body, hd = get(url, page)
                    txt = body.decode('utf-8', 'ignore')
                    log.append(f'   info {url[-60:]} -> {txt[:300]}')
                    j = json.loads(txt)
                    atch = j.get('atchFileId') or (j.get('fileDataRegistVO') or {}).get('atchFileId')
                    sn = j.get('fileDetailSn') or (j.get('fileDataRegistVO') or {}).get('fileDetailSn') or 1
                    if not atch: continue
                    data, hd2 = get(f'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={atch}&fileDetailSn={sn}', page)
                    ext = 'csv'
                    cd = hd2.get('Content-Disposition', '')
                    if '.xls' in cd: ext = 'xlsx' if '.xlsx' in cd else 'xls'
                    if '.zip' in cd: ext = 'zip'
                    open(f'probe-out/ports/{pid}.{ext}', 'wb').write(data)
                    log.append(f'   saved {pid}.{ext} {len(data)} bytes cd={cd[:120]}')
                    got = True; break
                except Exception as e:
                    log.append(f'   fail {url[-50:]}: {e}')
            if got: break
        if not got:
            i = html.find('다운로드')
            log.append('   page snippet: ' + re.sub(r'\s+', ' ', html[max(0, i - 1500): i + 800])[:2300])
    except Exception:
        log.append(traceback.format_exc())
open('probe-out/log.txt', 'w').write('\n'.join(log))
