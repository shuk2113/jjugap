"""전국 바다 지도 자료(basemap.json) 만들기 — 깃허브 작업에서 돌린다 (결과: probe-out/basemap/)
- 육지: OpenStreetMap 육지(osmdata.openstreetmap.de land-polygons-split) — 남한 바다는 자세히, 북한·중국·일본 해안은 거칠게
- 칸(타일)으로 나눠 앱이 화면에 보이는 칸만 그리게 한다. 해안선(K)은 칸 경계선을 빼고 따로 담아, 칸 경계에 선이 생기지 않게
- 두 단계: 멀리 볼 때(0) · 가까이 볼 때(1)
- 방조제 안 호수·저수지·큰 강(W), 섬·만·호수 이름(lab) — Geofabrik 한국 추출본
"""
import json, os, subprocess, sys, time, importlib, site, traceback, math, re, gzip, multiprocessing as mp
OUT = 'probe-out/basemap4'; os.makedirs(OUT, exist_ok=True)
BIG = (118.0, 30.0, 134.0, 44.5)                              # 주변국 해안까지 (멀리 볼 때 지도가 잘려 보이지 않게)
FINE = [(124.0, 33.0, 131.0, 38.75), (130.5, 37.0, 132.0, 37.75)]   # 자세히: 남한 바다 전체 · 울릉도·독도
LON0, LAT0, Q = 118.0, 30.0, 100000
KX = math.cos(math.radians(36.6))
LV = {   # 칸 크기(도), 자세한 곳/거친 곳 단순화(도), 작은 섬 빼기(대각선, 도)
    0: dict(cell=1.0, tol=(0.0006, 0.005), mind=(0.004, 0.02)),
    1: dict(cell=0.25, tol=(0.0001, 0.002), mind=(0.0004, 0.01)),
}
log = []
def sh(c):
    t = time.time(); print(f'$ {c[:140]}', flush=True)
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    log.append(f'$ {c[:140]} → {r.returncode} ({time.time() - t:.0f}s) {(r.stdout + r.stderr)[-400:]}'); print(log[-1], flush=True); push_log(); return r.returncode
def push_log():   # 진행 상황을 그때그때 가지에 올려, 밖에서 볼 수 있게
    open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
    subprocess.run(f'git config user.name "github-actions[bot]"; git config user.email "41898282+github-actions[bot]@users.noreply.github.com"; '
                   f'git add {OUT}/log.txt && git commit -q -m "진행 [skip ci]" && (git push -q origin HEAD:probe || (git pull -q --rebase origin probe && git push -q origin HEAD:probe))',
                   shell=True, capture_output=True)
def say(m): log.append(f'[{time.time() - T0:.0f}s] {m}'); print(log[-1], flush=True); push_log()
in_fine = (lambda x, y: any(a <= x <= c and b <= y <= d for a, b, c, d in FINE))
T0 = time.time()
try:
    sh('sudo apt-get -qq update && sudo apt-get -qq install -y gdal-bin osmium-tool > /dev/null')
    sh(f'{sys.executable} -m pip install -q --user --break-system-packages shapely numpy')
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import numpy as np
    import shapely
    from shapely.geometry import shape, box
    from shapely import STRtree, clip_by_rect, union_all
    from shapely.ops import polylabel
    say(f'shapely {shapely.__version__} · 코어 {os.cpu_count()}')

    # ---------- 1) 육지 조각 받기
    sh('timeout 1800 wget -q --timeout=60 --tries=5 https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip -O land.zip; ls -la land.zip')
    sh('unzip -q -o land.zip')
    shp = subprocess.run('ls land-polygons-split-4326/*.shp', shell=True, capture_output=True, text=True).stdout.strip()
    sh(f'ogr2ogr -f GeoJSONSeq -spat {BIG[0]} {BIG[1]} {BIG[2]} {BIG[3]} land.geojsonseq {shp}')
    say(f'잘라낸 파일 {os.path.getsize("land.geojsonseq") // 1048576} MB')
    pieces = []
    for l in open('land.geojsonseq'):
        l = l.strip().strip('\x1e')
        if l: pieces.append(shape(json.loads(l)['geometry']))
    say('육지 받기 끝'); tree = STRtree(pieces)
    say(f'육지 조각 {len(pieces)}개, 점 {sum(shapely.get_num_coordinates(p) for p in pieces)}')

    # ---------- 2) 칸마다: 조각을 칸으로 자르고 합친 뒤, 칸 경계 점은 고정한 채 단순화
    def dp(xy, tol, fixed):
        """xy: (n,2) numpy, 열린 선. fixed: 꼭 남길 점 번호. 가로(경도)는 KX를 곱해 거리 계산"""
        n = len(xy); keep = np.zeros(n, bool); keep[0] = keep[-1] = True; keep[list(fixed)] = True
        X = xy[:, 0] * KX; Y = xy[:, 1]
        idx = np.flatnonzero(keep); st = list(zip(idx[:-1], idx[1:]))
        while st:
            i, j = st.pop()
            if j - i < 2: continue
            ax, ay, bx, by = X[i], Y[i], X[j], Y[j]; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
            px, py = X[i + 1:j], Y[i + 1:j]
            d = np.abs(dy * px - dx * py + bx * ay - by * ax) / L if L > 1e-12 else np.hypot(px - ax, py - ay)
            m = int(np.argmax(d))
            if d[m] > tol: k = i + 1 + m; keep[k] = True; st += [(i, k), (k, j)]
        return xy[keep]

    def on_side(p, bb, e=1e-9):
        s = 0
        if abs(p[0] - bb[0]) < e: s |= 1
        if abs(p[0] - bb[2]) < e: s |= 2
        if abs(p[1] - bb[1]) < e: s |= 4
        if abs(p[1] - bb[3]) < e: s |= 8
        return s

    def enc(pts):
        q = np.round((pts - [LON0, LAT0]) * Q).astype(np.int64)
        keep = np.ones(len(q), bool); keep[1:] = np.any(q[1:] != q[:-1], axis=1)
        q = q[keep]
        out = [int(q[0, 0]), int(q[0, 1])]
        d = np.diff(q, axis=0)
        out += d.flatten().tolist()
        return out, len(q)

    def sides_of(xy, bb, e=1e-9):
        x, y = xy[:, 0], xy[:, 1]
        return ((np.abs(x - bb[0]) < e) * 1 | (np.abs(x - bb[2]) < e) * 2 | (np.abs(y - bb[1]) < e) * 4 | (np.abs(y - bb[3]) < e) * 8).astype(np.int64)

    def ring_simplify(coords, bb, tol):
        """닫힌 고리 → (단순화한 점들, 각 점의 경계 표시). 칸 경계 위 점은 고정"""
        xy = np.asarray(coords)[:-1, :2]
        fixed = np.flatnonzero(sides_of(xy, bb))
        if len(fixed):   # 경계 점에서 시작하게 돌려서, 고리를 열린 선으로 단순화
            r0 = int(fixed[0]); xy = np.roll(xy, -r0, axis=0)
            fixed = (fixed - r0) % len(xy)
            line = np.vstack([xy, xy[:1]]); s = dp(line, tol, fixed)[:-1]
        else:       # 칸 안에 오롯이 있는 섬: 반으로 나눠 단순화
            h = len(xy) // 2
            if len(xy) < 4: s = xy
            else: s = np.vstack([dp(xy[:h + 1], tol, [])[:-1], dp(np.vstack([xy[h:], xy[:1]]), tol, [])[:-1]])
        return s, sides_of(s, bb).tolist()

    def coast_runs(s, sd):
        """단순화한 고리에서 칸 경계를 따라가는 마디를 빼고 남은 해안선 조각들 (열린 선)"""
        n = len(s)
        if n < 2: return []
        border = [bool(sd[i] & sd[(i + 1) % n]) for i in range(n)]   # i→i+1 마디가 같은 경계 위
        if not any(border): return [np.vstack([s, s[:1]])]          # 칸 안의 섬: 닫힌 선
        runs, cur = [], None
        start = border.index(True) + 1
        for k in range(n):
            i = (start + k) % n
            if border[i]:
                if cur is not None and len(cur) >= 2: runs.append(np.asarray(cur))
                cur = None
            else:
                if cur is None: cur = [s[i]]
                cur.append(s[(i + 1) % n])
        if cur is not None and len(cur) >= 2: runs.append(np.asarray(cur))
        return runs

    def build_col(arg):
        lv, ix = arg
        P = LV[lv]; cs = P['cell']; Lp, Kp, npt = [], [], 0
        ny = int(round((BIG[3] - BIG[1]) / cs))
        if True:
            for iy in range(ny):
                bb = (BIG[0] + ix * cs, BIG[1] + iy * cs, BIG[0] + (ix + 1) * cs, BIG[1] + (iy + 1) * cs)
                hits = tree.query(box(*bb))
                if not len(hits): continue
                parts = [clip_by_rect(pieces[i], *bb) for i in hits]
                parts = [g for g in parts if not g.is_empty]
                if not parts: continue
                u = union_all(parts)
                fine = in_fine((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
                tol, mind = P['tol'][0 if fine else 1], P['mind'][0 if fine else 1]
                polys = list(u.geoms) if hasattr(u, 'geoms') else [u]
                for pg in polys:
                    if pg.geom_type != 'Polygon' or pg.is_empty: continue
                    rings = []
                    for k, ring in enumerate([pg.exterior] + list(pg.interiors)):
                        c = np.asarray(ring.coords)
                        x0, y0 = c[:, 0].min(), c[:, 1].min(); x1, y1 = c[:, 0].max(), c[:, 1].max()
                        touches = bool(sides_of(c, bb).any())
                        if not touches and math.hypot((x1 - x0) * KX, y1 - y0) < mind:
                            if k == 0: break          # 작은 섬은 통째로 뺀다
                            continue                  # 작은 구멍(호수)은 뺀다
                        s, sd = ring_simplify(ring.coords, bb, tol)
                        if len(s) < 3: continue
                        e, m = enc(s); rings.append(e); npt += m
                        for run in coast_runs(s, sd):
                            e2, m2 = enc(run)
                            if m2 >= 2: Kp.append(e2)
                    if rings: Lp.append(rings)
        return Lp, Kp, npt

    L, K = [], []
    NC = os.cpu_count() or 2
    for lv in (0, 1):
        nx = int(round((BIG[2] - BIG[0]) / LV[lv]['cell'])); Lp, Kp, n = [], [], 0
        with mp.get_context('fork').Pool(NC) as pool:
            for j, (a, b, c) in enumerate(pool.imap(build_col, [(lv, ix) for ix in range(nx)])):
                Lp += a; Kp += b; n += c
                if j % 8 == 7: say(f'단계 {lv}: 칸 줄 {j + 1}/{nx}')
        L.append(Lp); K.append(Kp)
        say(f'단계 {lv}: 땅 조각 {len(Lp)} · 해안선 {len(Kp)} · 점 {n} (코어 {NC})')

    # ---------- 3) 한국 OSM: 호수·저수지·큰 강, 섬·만 이름
    sh('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf')
    sh('osmium fileinfo -e kr.pbf | grep -i "timestamp" | head -1 > when.txt')
    when = open('when.txt').read().split('timestamp=')[-1].strip()[:10] if os.path.exists('when.txt') else ''
    sh('osmium tags-filter kr.pbf nwr/natural=water nwr/waterway=riverbank nwr/landuse=reservoir,basin -o water.pbf --overwrite')
    sh('osmium export water.pbf -f geojsonseq -o water.geojsonseq --overwrite --geometry-types=polygon')
    sh('osmium tags-filter kr.pbf nwr/place=island,islet,archipelago nwr/natural=bay -o places.pbf --overwrite')
    sh('osmium export places.pbf -f geojsonseq -o places.geojsonseq --overwrite --attributes=type,id')
    A1 = 1 / (111.32 ** 2 * KX)                     # 1 km² 를 도² 로
    wpolys, wnames = [], []
    for l in open('water.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        f = json.loads(l)
        try: g = shape(f['geometry']).buffer(0)
        except Exception: continue
        if g.is_empty: continue
        c = g.representative_point()
        # 바닷가(서해 안쪽) 물은 작은 것까지, 나머지는 큰 호수·저수지·강만
        if g.area < (0.03 if c.x < 127.05 and c.y > 35.0 else 0.5) * A1: continue
        if not in_fine(c.x, c.y): continue
        wpolys.append(g)
        p = f['properties']; nm = p.get('name:ko') or p.get('name')
        if nm and g.area > 1.5 * A1: wnames.append([nm, round(c.x, 5), round(c.y, 5), g.area, p.get('water') or p.get('natural') or p.get('landuse') or p.get('waterway')])
    # 바다 쪽으로 삐져나온 부분은 빼고 (육지 안의 물만)
    wcut = []
    for g in wpolys:
        near = [pieces[i] for i in tree.query(g, predicate='intersects')]
        if near: wcut.append(g.intersection(union_all(near)))
    wu = union_all([g for g in wcut if not g.is_empty])
    say(f'물 {len(wpolys)}개 → 합침, 이름 {len(wnames)}')

    def level_poly(geom, tol, mind):
        out = []
        for pg in (geom.geoms if hasattr(geom, 'geoms') else [geom]):
            if pg.geom_type != 'Polygon' or pg.is_empty: continue
            rings = []
            for k, ring in enumerate([pg.exterior] + list(pg.interiors)):
                c = np.asarray(ring.coords)
                if math.hypot((c[:, 0].max() - c[:, 0].min()) * KX, c[:, 1].max() - c[:, 1].min()) < mind:
                    if k == 0: break
                    continue
                s, _ = ring_simplify(ring.coords, (1e9, 1e9, -1e9, -1e9), tol)
                if len(s) >= 3: rings.append(enc(s)[0])
            if rings: out.append(rings)
        return out
    W = [level_poly(wu, 0.0008, 0.02), level_poly(wu, 0.0002, 0.003)]

    # 이름표
    HAN = re.compile('[가-힣]')
    def clean(name):
        name = re.sub(r'\s*[\(（].*?[\)）]\s*', '', name or '').strip()
        return name if HAN.search(name) and len(name) <= 8 else None
    def area(r):
        a = 0
        for i in range(len(r)):
            x1, y1 = r[i - 1][:2]; x2, y2 = r[i][:2]; a += (x1 * KX) * y2 - (x2 * KX) * y1
        return abs(a) / 2
    labs = []
    for line in open('places.geojsonseq'):
        line = line.strip().strip('\x1e')
        if not line: continue
        f = json.loads(line); p = f['properties']; g = f['geometry']
        kind = 'bay' if p.get('natural') == 'bay' else 'island' if p.get('place') in ('island', 'islet', 'archipelago') else None
        if not kind: continue
        name = clean(p.get('name:ko') or p.get('name'))
        if not name: continue
        if g['type'] == 'Point':
            x, y = g['coordinates']; a = 0
        else:
            try: sg = shape(g)
            except Exception: continue
            if sg.geom_type == 'LineString':
                if not sg.is_ring:
                    if kind == 'island': continue
                    pt = sg.interpolate(0.5, normalized=True); x, y = pt.x, pt.y; a = 0
                else:
                    sg = shapely.Polygon(sg.coords); a = area(list(sg.exterior.coords))
                    try: pt = polylabel(sg.buffer(0), 1e-4)
                    except Exception: pt = sg.representative_point()
                    x, y = pt.x, pt.y
            else:
                big = max((q for q in (sg.geoms if hasattr(sg, 'geoms') else [sg]) if q.geom_type == 'Polygon'), key=lambda q: q.area, default=None)
                if big is None: continue
                a = area(list(big.exterior.coords))
                try: pt = polylabel(big, 1e-4)
                except Exception: pt = big.representative_point()
                x, y = pt.x, pt.y
            if p.get('place') == 'archipelago': kind = 'group'
        if not in_fine(x, y): continue
        labs.append([name, x, y, a, kind])
    for nm, x, y, a, typ in wnames:
        nm = clean(nm)
        if nm and typ in ('lake', 'reservoir', 'lagoon') and a * KX > 3 * A1 * 0.8: labs.append([nm, x, y, a * KX, 'lake'])
    labs.sort(key=lambda l: -l[3])
    keep = []
    for l in labs:
        if any(k[0] == l[0] and math.hypot((k[1] - l[1]) * KX, k[2] - l[2]) < 0.02 for k in keep): continue
        keep.append(l)
    OVR = {'제주도': 60, '울릉도': 100, '독도': 100, '백령도': 200, '거제도': 200}
    out_l = []
    for name, x, y, a, kind in keep:
        if kind in ('bay', 'lake'): minS = max(600, min(5000, 20 / math.sqrt(max(a, 1e-6))))
        elif kind == 'group': minS = 900
        else: minS = max(250, min(60000, 10 / math.sqrt(a))) if a > 0 else 5000
        if name in OVR and kind == 'island': minS = min(minS, OVR[name])
        out_l.append([name, round(x, 5), round(y, 5), round(minS), {'island': 0, 'bay': 1, 'group': 2, 'lake': 1}[kind]])
    # 바다 이름 (멀리 볼 때만, 앱이 kind 3을 크게 그린다)
    out_l += [['서해', 125.0, 36.15, 60, 3], ['남해', 127.75, 33.95, 60, 3], ['동해', 130.25, 37.95, 60, 3]]
    say(f'이름표 {len(out_l)}')

    js = json.dumps({'src': '© OpenStreetMap 기여자 (ODbL)', 'date': when, 'o': [LON0, LAT0], 'q': Q,
                     'L': L, 'K': K, 'F': [[], []], 'W': W, 'lab': out_l}, ensure_ascii=False, separators=(',', ':'))
    open(f'{OUT}/basemap.json', 'w').write(js)
    gz = len(gzip.compress(js.encode(), 6))
    part = lambda o: len(json.dumps(o, separators=(',', ':')).encode()) // 1024
    say(f'크기 {len(js.encode()) // 1024} KB (압축하면 {gz // 1024} KB) · L0 {part(L[0])} L1 {part(L[1])} K0 {part(K[0])} K1 {part(K[1])} W {part(W)} 이름 {part(out_l)} KB')
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log[-30:]))
