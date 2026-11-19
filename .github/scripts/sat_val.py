# 천리안위성 2B호(GOCI-II) 투명도(Zsd)를 몇 자리·며칠만 뽑아 본다 (검증용 · 원본 파일은 저장하지 않음)
#  자료: 국립해양조사원 국가해양위성센터 OPeNDAP (robots.txt: User-agent * Allow /)
import os, re, json, time, math, urllib.request, urllib.parse, datetime as dt

UA = {'User-Agent': 'Mozilla/5.0 (jjugap water-clarity check; personal app)'}
BASE = 'https://www.nosc.go.kr/opendap/hyrax/GOCI-II/'
PTS = json.loads(os.environ.get('PTS', '[["11/5 대천항 앞",36.330,126.4985],["11/17 비응항 앞",35.968,126.503]]'))
DAYS = [x.strip() for x in os.environ.get('DAYS', '2026-11-03,2026-11-04,2026-11-05,2026-11-15,2026-11-16,2026-11-17,2026-11-18').split(',') if x.strip()]
log = []


T0 = time.time()


def save():
    os.makedirs('.github/data/sat', exist_ok=True)
    json.dump(out, open('.github/data/sat/val.json', 'w'), ensure_ascii=False, indent=1)


def get(url, tries=3):
    for i in range(tries):
        try:
            t1 = time.time()
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                b = r.read().decode('utf-8', 'replace')
            print(f'{time.time() - T0:7.1f}s get {time.time() - t1:5.1f}s {len(b):8d}B {url[-90:]}', flush=True)
            return b
        except Exception as e:
            err = repr(e)[:200]; time.sleep(3 + 3 * i)
    log.append('fail ' + url[-160:] + ' ' + err)
    return None


VN = {}


def ascii(f, parts):
    # parts: [(var, r0, r1, c0, c1, step)] → {var: 2D list}
    for style in ([VN['style']] if 'style' in VN else ['enc', 'raw', 'flat']):
        def nm(v):
            return urllib.parse.quote(v, safe='') if style == 'enc' else v if style == 'raw' else v.strip('/').replace('/', '_')
        ce = ','.join(f'{nm(v)}%5B{r0}:{s}:{r1}%5D%5B{c0}:{s}:{c1}%5D' for v, r0, r1, c0, c1, s in parts)
        t = get(f + '.ascii?' + ce, tries=1 if 'style' not in VN else 3)
        if not t or 'Error' in t[:300]:
            continue
        VN['style'] = style
        out, cur = {}, None
        for line in t.splitlines():
            m = re.match(r'^\s*([^\[,]+?)\[(\d+)\](?:\[\d+\])?,\s*(.*)$', line)
            if m:
                key = m.group(1).strip(); cur = out.setdefault(key, [])
                cur.append([float(x) for x in m.group(3).split(',') if x.strip()])
        res = {}
        for v, *_ in parts:
            k = next((k for k in out if k.endswith(v.split('/')[-1])), None)
            res[v] = out.get(k)
        return res
    return None


def dirs_for(kst_day):
    d = dt.date.fromisoformat(kst_day); res = []
    for ud in (d - dt.timedelta(days=1), d):
        t = get(BASE + ud.strftime('%Y/%m/%d') + '/L2/contents.html')
        if not t:
            continue
        for x in sorted(set(re.findall(r'GK2_GC2_L2_(\d{8})_(\d{6})', t))):
            u = dt.datetime.strptime(x[0] + x[1], '%Y%m%d%H%M%S'); k = u + dt.timedelta(hours=9)
            if k.date() == d:
                res.append((u, k, BASE + ud.strftime('%Y/%m/%d') + f'/L2/GK2_GC2_L2_{x[0]}_{x[1]}/GK2B_GOCI2_L2_{x[0]}_{x[1]}_LA_Zsd.nc'))
        time.sleep(1)
    return res


def km(a, b, c, d):
    return math.hypot((a - c) * 111.2, (b - d) * 111.2 * math.cos(math.radians(a)))


out = {'src': '국립해양조사원 국가해양위성센터 GOCI-II L2 Zsd (LA mosaic)', 'pts': {}, 'log': log}
D0 = dirs_for(DAYS[-1])
if not D0:
    raise SystemExit('no dirs')
f0 = D0[len(D0) // 2][2]
S = 50
co = ascii(f0, [('/navigation_data/latitude', 0, 7999, 0, 10499, S), ('/navigation_data/longitude', 0, 7999, 0, 10499, S)])
LA, LO = co['/navigation_data/latitude'], co['/navigation_data/longitude']
log.append(f'coarse {len(LA)}x{len(LA[0])} style {VN.get("style")}')
win = {}
for nm_, la, lo in PTS:
    best = min(((km(LA[i][j], LO[i][j], la, lo), i, j) for i in range(len(LA)) for j in range(len(LA[0])) if LA[i][j] > -900), key=lambda x: x[0])
    r, c = best[1] * S, best[2] * S
    fw = ascii(f0, [('/navigation_data/latitude', r - 30, r + 30, c - 30, c + 30, 1), ('/navigation_data/longitude', r - 30, r + 30, c - 30, c + 30, 1)])
    a, b = fw['/navigation_data/latitude'], fw['/navigation_data/longitude']
    d2, i2, j2 = min(((km(a[i][j], b[i][j], la, lo), i, j) for i in range(len(a)) for j in range(len(a[0]))), key=lambda x: x[0])
    R, C = r - 30 + i2, c - 30 + j2
    win[nm_] = (R, C)
    out['pts'][nm_] = {'lat': la, 'lon': lo, 'pix': [R, C], 'pix_km': round(d2, 3), 'obs': []}; save()
    time.sleep(1)
H = 8   # 17 x 17 칸 (약 4km)
for day in DAYS:
    for u, k, f in dirs_for(day):
        for nm_, (R, C) in win.items():
            w = ascii(f, [('/geophysical_data/Zsd', R - H, R + H, C - H, C + H, 1), ('/geophysical_data/flag', R - H, R + H, C - H, C + H, 1)])
            if not w or not w.get('/geophysical_data/Zsd'):
                out['pts'][nm_]['obs'].append({'kst': k.strftime('%m-%d %H:%M'), 'err': 1}); continue
            z, fl = w['/geophysical_data/Zsd'], w['/geophysical_data/flag']
            v1, v2, cl = [], [], 0
            for i in range(2 * H + 1):
                for j in range(2 * H + 1):
                    dd = math.hypot(i - H, j - H) * 0.25
                    if dd > 2.0:
                        continue
                    fg = int(fl[i][j]) if fl else 0
                    if fg & 1:
                        cl += 1
                    if z[i][j] > 0 and z[i][j] < 100 and not (fg & 0x47):
                        (v1 if dd <= 1.0 else v2).append(z[i][j])
            med = lambda v: sorted(v)[len(v) // 2] if v else None
            out['pts'][nm_]['obs'].append({'kst': k.strftime('%m-%d %H:%M'), 'n1': len(v1), 'z1': med(v1), 'n2': len(v2) + len(v1), 'z2': med(v1 + v2),
                                           'lo': round(min(v1 + v2), 2) if v1 + v2 else None, 'hi': round(max(v1 + v2), 2) if v1 + v2 else None, 'cloud': cl})
            time.sleep(0.5)
        save()
    if time.time() - T0 > 3600:
        log.append('time up'); break
save()
print(json.dumps(out, ensure_ascii=False)[:2500])
