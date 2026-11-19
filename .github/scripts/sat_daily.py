# 천리안위성 2B호(GOCI-II) 하루 투명도 지도: 그날 낮 10번 찍은 것 중 구름·육지·실패 칸을 빼고
# 2km 칸(data/water.json과 같은 격자)마다 가운데 값 · 찍힌 시각(칸마다 비트) · 표본 수를 저장한다.
#  자료: 국립해양조사원 국가해양위성센터 OPeNDAP (robots.txt: User-agent * Allow /) · L2 Zsd(세키 깊이, Lee 2015)
#  사용: python3 sat_daily.py 2026-11-18 out.json
import os, re, sys, json, time, base64, struct, urllib.request, datetime as dt
import numpy as np

UA = {'User-Agent': 'Mozilla/5.0 (jjugap water-clarity daily; personal app)'}
BASE = 'https://www.nosc.go.kr/opendap/hyrax/GOCI-II/'
G = dict(lat1=38.3, lon0=124.6, res=0.02, ny=170, nx=140)   # data/water.json 격자와 같게
BOX = (G['lat1'] - G['ny'] * G['res'] - 0.05, G['lat1'] + 0.05, G['lon0'] - 0.05, G['lon0'] + G['nx'] * G['res'] + 0.05)
STEP = 2   # 250m 칸을 2칸마다 (500m)
T0 = time.time()


def get(url, tries=4):
    err = ''
    for i in range(tries):
        try:
            t1 = time.time()
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                b = r.read()
            print(f'{time.time() - T0:7.1f}s {time.time() - t1:5.1f}s {len(b):9d}B {url[-100:]}', flush=True)
            return b
        except Exception as e:
            err = repr(e)[:200]; time.sleep(10 + 10 * i)
    print('FAIL', url[-120:], err, flush=True)
    return None


def dods(f, parts):
    # DAP2 바이너리: [(이름, r0, r1, c0, c1, s)] → {끝이름: ndarray}
    ce = ','.join(f'{v}%5B{r0}:{s}:{r1}%5D%5B{c0}:{s}:{c1}%5D' for v, r0, r1, c0, c1, s in parts)
    b = get(f + '.dods?' + ce)
    if not b:
        return None
    k = b.find(b'\nData:\n')
    if k < 0:
        print('bad dods', b[:300]); return None
    dds, data, p, out = b[:k].decode('utf-8', 'replace'), b[k + 7:], 0, {}
    for typ, name, dims in re.findall(r'(Float32|Float64|Byte|Int16|UInt16|Int32)\s+([^\[\s;]+)((?:\s*\[[^\]]+\])+)\s*;', dds):
        shp = [int(x.split('=')[-1]) for x in re.findall(r'\[([^\]]+)\]', dims)]
        n = int(np.prod(shp)); n1 = struct.unpack('>I', data[p:p + 4])[0]; p += 8
        if typ == 'Byte':
            a = np.frombuffer(data[p:p + n], np.uint8); p += n + (-n % 4)
        else:
            dt_ = {'Float32': '>f4', 'Float64': '>f8', 'Int16': '>i4', 'UInt16': '>u4', 'Int32': '>i4'}[typ]; sz = np.dtype(dt_).itemsize
            a = np.frombuffer(data[p:p + n * sz], dt_); p += n * sz
        out[name.split('/')[-1]] = a.reshape(shp)
    return out


def slots(day):
    d = dt.date.fromisoformat(day); res = []
    for ud in (d - dt.timedelta(days=1), d):
        b = get(BASE + ud.strftime('%Y/%m/%d') + '/L2/contents.html')
        if not b:
            continue
        for x in sorted(set(re.findall(r'GK2_GC2_L2_(\d{8})_(\d{6})', b.decode('utf-8', 'replace')))):
            u = dt.datetime.strptime(x[0] + x[1], '%Y%m%d%H%M%S'); k = u + dt.timedelta(hours=9)
            if k.date() == d:
                res.append((k.strftime('%H:%M'), BASE + ud.strftime('%Y/%m/%d') + f'/L2/GK2_GC2_L2_{x[0]}_{x[1]}/GK2B_GOCI2_L2_{x[0]}_{x[1]}_LA_Zsd.nc'))
    return res


def main(day, outp):
    S = slots(day)
    if not S:
        raise SystemExit('no slots')
    f0 = S[len(S) // 2][1]
    co = dods(f0, [('/navigation_data/latitude', 0, 7999, 0, 10499, 50), ('/navigation_data/longitude', 0, 7999, 0, 10499, 50)])
    la, lo = co['latitude'], co['longitude']
    ii, jj = np.where((la > BOX[0]) & (la < BOX[1]) & (lo > BOX[2]) & (lo < BOX[3]))
    r0, r1 = max(0, ii.min() * 50 - 60), min(7999, ii.max() * 50 + 60)
    c0, c1 = max(0, jj.min() * 50 - 60), min(10499, jj.max() * 50 + 60)
    nav = dods(f0, [('/navigation_data/latitude', r0, r1, c0, c1, STEP), ('/navigation_data/longitude', r0, r1, c0, c1, STEP)])
    LA, LO = nav['latitude'], nav['longitude']
    ci = np.floor((G['lat1'] - LA) / G['res']).astype(int); cj = np.floor((LO - G['lon0']) / G['res']).astype(int)
    inb = (LA > -900) & (ci >= 0) & (ci < G['ny']) & (cj >= 0) & (cj < G['nx'])
    cell = np.where(inb, ci * G['nx'] + cj, -1)
    print('box rows', r0, r1, 'cols', c0, c1, 'shape', LA.shape, 'in grid', int(inb.sum()), flush=True)
    vals, cells, sl = [], [], []
    used = []
    for k, (hm, f) in enumerate(S):
        w = dods(f, [('/geophysical_data/Zsd', r0, r1, c0, c1, STEP), ('/geophysical_data/flag', r0, r1, c0, c1, STEP)])
        if not w or 'Zsd' not in w:
            continue
        z, fl = w['Zsd'], w['flag'].astype(np.uint8)
        ok = inb & (z > 0) & (z < 100) & ((fl & 0x47) == 0)
        n = int(ok.sum()); used.append([hm, n])
        if n:
            vals.append(z[ok].astype(np.float32)); cells.append(cell[ok]); sl.append(np.full(n, k, np.int8))
        time.sleep(2)
    NC = G['ny'] * G['nx']
    zc = np.zeros(NC, np.uint8); mc = np.zeros(NC, np.uint16); nc = np.zeros(NC, np.uint8)
    if vals:
        V, C, K = np.concatenate(vals), np.concatenate(cells), np.concatenate(sl)
        o = np.lexsort((V, C)); V, C, K = V[o], C[o], K[o]
        u, st, cnt = np.unique(C, return_index=True, return_counts=True)
        med = V[st + cnt // 2]
        zc[u] = np.clip(np.round(med / 0.05), 1, 254).astype(np.uint8)
        nc[u] = np.clip(cnt, 0, 255).astype(np.uint8)
        bits = np.zeros(NC, np.uint32); np.bitwise_or.at(bits, C, (1 << K.astype(np.uint32)).astype(np.uint32)); mc[:] = bits.astype(np.uint16)
    b64 = lambda a: base64.b64encode(a.tobytes()).decode()
    out = {'src': '천리안위성 2B호 GOCI-II L2 세키 깊이(Zsd) · 국립해양조사원 국가해양위성센터', 'day': day, 'slots': [s[0] for s in S], 'used': used,
           'g': dict(G, z=b64(zc), m=b64(mc.astype('<u2')), n=b64(nc), zs=0.05), 'cells': int((nc > 0).sum()), 'made': dt.datetime.utcnow().isoformat() + 'Z'}
    json.dump(out, open(outp, 'w'), ensure_ascii=False)
    print('cells with data', out['cells'], 'used', used, flush=True)


if __name__ == '__main__':
    day = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime('%Y-%m-%d')
    main(day, sys.argv[2] if len(sys.argv) > 2 else f'sat-{day}.json')
