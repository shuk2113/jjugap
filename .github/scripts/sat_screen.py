# 맑은 날 골라내기: 날마다 정오(12:15) 사진 한 장에서 서해 상자 안 바다 칸 중 투명도가 나온 비율
#  자료: 국립해양조사원 국가해양위성센터 OPeNDAP (robots.txt: User-agent * Allow /)
import os, re, sys, json, time, struct, urllib.request, datetime as dt
import numpy as np

UA = {'User-Agent': 'Mozilla/5.0 (jjugap water-clarity calibration; personal app)'}
BASE = 'https://www.nosc.go.kr/opendap/hyrax/GOCI-II/'
R0, R1, C0, C1, ST = 2690, 3860, 3190, 4260, 10   # 2026-11 확인한 서해 상자 (정지궤도 격자는 고정)
T0 = time.time()
OUT = sys.argv[1]


def get(url, tries=3):
    err = ''
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = repr(e)[:150]
        except Exception as e:
            err = repr(e)[:150]
        time.sleep(10 + 10 * i)
    print('FAIL', url[-110:], err, flush=True)
    return None


def dods(url):
    b = get(url)
    if not b:
        return None
    k = b.find(b'\nData:\n')
    if k < 0:
        return None
    dds, data, p, out = b[:k].decode('utf-8', 'replace'), b[k + 7:], 0, {}
    for typ, name, dims in re.findall(r'(Float32|Byte)\s+([^\[\s;]+)((?:\s*\[[^\]]+\])+)\s*;', dds):
        shp = [int(x.split('=')[-1]) for x in re.findall(r'\[([^\]]+)\]', dims)]; n = int(np.prod(shp)); p += 8
        if typ == 'Byte':
            a = np.frombuffer(data[p:p + n], np.uint8); p += n + (-n % 4)
        else:
            a = np.frombuffer(data[p:p + 4 * n], '>f4'); p += 4 * n
        out[name.split('/')[-1]] = a.reshape(shp)
    return out


days = []
a, b, step = os.environ['FROM'], os.environ['TO'], int(os.environ.get('STEP', '3'))
d = dt.date.fromisoformat(a)
while d <= dt.date.fromisoformat(b):
    days.append(d); d += dt.timedelta(days=step)
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
sl = f'%5B{R0}:{ST}:{R1}%5D%5B{C0}:{ST}:{C1}%5D'
navchk = {}
for d in days:
    key = d.isoformat()
    if key in res:
        continue
    ymd = d.strftime('%Y%m%d'); u = None
    for hhmm in ('031530', '031630', '031531'):
        f = f'{BASE}{d.strftime("%Y/%m/%d")}/L2/GK2_GC2_L2_{ymd}_{hhmm}/GK2B_GOCI2_L2_{ymd}_{hhmm}_LA_Zsd.nc'
        w = dods(f + '.dods?/geophysical_data/Zsd' + sl + ',/geophysical_data/flag' + sl)
        if w and 'Zsd' in w:
            u = f; break
    if not u:
        res[key] = None; print(key, 'none', flush=True); continue
    if d.year not in navchk:   # 해마다 한 번: 격자 위치가 같은지
        nv = dods(u + f'.dods?/navigation_data/latitude%5B{R0}:585:{R1}%5D%5B{C0}:535:{C1}%5D,/navigation_data/longitude%5B{R0}:585:{R1}%5D%5B{C0}:535:{C1}%5D')
        navchk[d.year] = [round(float(x), 3) for x in np.concatenate([nv['latitude'].ravel(), nv['longitude'].ravel()])] if nv else None
        print('nav', d.year, navchk[d.year], flush=True)
    z, fl = w['Zsd'], w['flag']
    sea = (fl & 2) == 0
    ok = sea & (z > 0) & (z < 100) & ((fl & 0x47) == 0)
    res[key] = [int(ok.sum()), int(sea.sum())]
    print(key, res[key], f'{100 * ok.sum() / max(1, sea.sum()):.0f}%', f'{time.time() - T0:.0f}s', flush=True)
    json.dump(res, open(OUT, 'w'))
    if time.time() - T0 > float(os.environ.get('TMAX', '19800')):
        print('time up', flush=True); break
json.dump(res, open(OUT, 'w'))
json.dump(navchk, open(OUT.replace('.json', '-nav.json'), 'w'))
