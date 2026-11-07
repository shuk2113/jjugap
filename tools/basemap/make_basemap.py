"""전국 바다 지도 자료(basemap.json) 만들기 — 깃허브 작업에서 돌린다 (결과: probe-out/basemap/)
- 육지: 남한 바다는 OpenStreetMap 해안선(Geofabrik 남·북한 추출본)으로 자세히, 북한 북쪽·중국·일본은 Natural Earth 1:10m로 거칠게
- 칸(타일)으로 나눠 앱이 화면에 보이는 칸만 그리게 한다. 해안선(K)은 칸 경계선을 빼고 따로 담아, 칸 경계에 선이 생기지 않게
- 두 단계: 멀리 볼 때(0) · 가까이 볼 때(1)
- 방조제 안 호수·저수지·큰 강(W), 섬·만·호수 이름(lab) — Geofabrik 한국 추출본
"""
import json, os, subprocess, sys, time, importlib, site, traceback, math, re, gzip, multiprocessing as mp
OUT = 'probe-out/basemap8'; os.makedirs(OUT, exist_ok=True)
BIG = (118.0, 30.0, 134.0, 44.5)                              # 주변국 해안까지 (멀리 볼 때 지도가 잘려 보이지 않게)
FINE = [(124.0, 33.0, 131.0, 38.75), (130.5, 37.0, 132.0, 37.75)]   # 자세히: 남한 바다 전체 · 울릉도·독도
LON0, LAT0, Q = 118.0, 30.0, 100000
KX = math.cos(math.radians(36.6))
# 네 단계: 멀리 볼수록 거칠게 (각 단계를 쓰는 가장 큰 배율에서 단순화 오차가 1점 안, 3점보다 작은 섬은 뺀다)
# 앱은 배율(1도에 몇 점) TH 경계에서 단계를 바꾼다
TH = [240, 900, 2800]
LV = {   # 칸 크기(도), 자세한 곳/거친 곳 단순화(도), 작은 섬 빼기(대각선, 도), 물(단순화, 작은 것 빼기)
    0: dict(cell=2.0, tol=(0.0035, 0.008), mind=(0.014, 0.04), w=(0.003, 0.03)),
    1: dict(cell=1.0, tol=(0.001, 0.004), mind=(0.004, 0.02), w=(0.001, 0.012)),
    2: dict(cell=0.5, tol=(0.0004, 0.002), mind=(0.0015, 0.01), w=(0.0005, 0.006)),
    3: dict(cell=0.25, tol=(0.00012, 0.002), mind=(0.0004, 0.01), w=(0.00025, 0.003)),
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

    # ---------- 1) 육지 만들기
    # 남한 바다(FINE, 일본 쪽 빼고)는 OSM 해안선(Geofabrik 남·북한 추출본, 매일 갱신)으로 직접 만들고,
    # 그 밖(북한 북쪽·중국·러시아)과 일본 쪽은 Natural Earth 1:10m(ne_big.json, 멀리 볼 때만 쓰는 거친 해안)
    from shapely.geometry import Polygon, LineString, Point
    W1 = 'wget -q --timeout=60 --tries=5'
    sh(f'{W1} https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf; {W1} https://download.geofabrik.de/asia/north-korea-latest.osm.pbf -O nk.pbf; ls -la kr.pbf nk.pbf')
    open('lin.json', 'w').write('{"linear_tags": true, "area_tags": false}')   # 닫힌 길도 선으로 (방향 그대로)
    sh('osmium tags-filter kr.pbf w/natural=coastline -o c1.pbf --overwrite && osmium tags-filter nk.pbf w/natural=coastline -o c2.pbf --overwrite '
       '&& osmium merge c1.pbf c2.pbf -o coast.pbf --overwrite && osmium export coast.pbf -c lin.json -f geojsonseq --geometry-types=linestring -o coast.geojsonseq --overwrite')
    lines = []
    for l in open('coast.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        g = json.loads(l)['geometry']
        if g['type'] == 'LineString' and len(g['coordinates']) >= 2: lines.append(LineString(g['coordinates']))
    say(f'해안선 길 {len(lines)}개')
    mg = shapely.line_merge(shapely.MultiLineString(lines), directed=True)
    parts = [list(g.coords) for g in (mg.geoms if hasattr(mg, 'geoms') else [mg])]
    rings = [c for c in parts if len(c) >= 4 and c[0] == c[-1]]
    opens = [c for c in parts if not (len(c) >= 4 and c[0] == c[-1])]
    # 끊긴 곳 잇기 (1km 안, 방향이 거꾸로 된 길도) — 한 번 돌 때 여러 곳을 잇고, 더 이을 게 없을 때까지
    def dd(p, q): return math.hypot((p[0] - q[0]) * KX, p[1] - q[1])
    GAP = 0.01; gaps = []
    while opens:
        n = len(opens); S = np.array([c[0][:2] for c in opens], float); E = np.array([c[-1][:2] for c in opens], float)
        used = np.zeros(n, bool); joined = 0
        for i in sorted(range(n), key=lambda k: -len(opens[k])):
            if used[i]: continue
            a = opens[i]
            if len(a) >= 4 and dd(a[-1], a[0]) < GAP:
                gaps.append(round(dd(a[-1], a[0]) * 111000)); rings.append(a + [a[0]]); used[i] = True; joined += 1; continue
            ex, ey = a[-1][0], a[-1][1]
            ds = np.hypot((S[:, 0] - ex) * KX, S[:, 1] - ey); de = np.hypot((E[:, 0] - ex) * KX, E[:, 1] - ey)
            ds[used] = 9; de[used] = 9; ds[i] = 9; de[i] = 9
            j1, j2 = int(np.argmin(ds)), int(np.argmin(de))
            if min(ds[j1], de[j2]) >= GAP: continue
            if ds[j1] <= de[j2]: j, b = j1, opens[j1]; d = ds[j1]
            else: j, b = j2, opens[j2][::-1]; d = de[j2]
            gaps.append(round(d * 111000)); opens[i] = a + b; used[j] = True; E[i] = b[-1][:2]; joined += 1
        opens = [opens[k] for k in range(n) if not used[k]]
        if not joined: break
    opens.sort(key=len, reverse=True)
    main = opens[0]
    say(f'섬 고리 {len(rings)} · 열린 선 {len(opens)} · 이은 틈(m) {sorted(gaps)[-8:]} · 본토 {len(main)}점 {main[0]} → {main[-1]}')
    for o in opens[1:12]: log.append(f'  남은 열린 선 {len(o)}점 {o[0]} → {o[-1]}')
    ok_ends = main[0][1] > 38.8 and main[-1][1] > 38.8 and main[0][0] < 127 and main[-1][0] > 127
    if not ok_ends:   # 방향이 반대로 잡혔으면 뒤집어 본다
        r = main[::-1]
        if r[0][1] > 38.8 and r[-1][1] > 38.8 and r[0][0] < 127 and r[-1][0] > 127: main = r; ok_ends = True
    if not ok_ends: raise RuntimeError('본토 해안선이 북한 북쪽까지 이어지지 않음')
    # 본토: 해안선 끝(두만강 쪽)에서 내륙(중국)을 돌아 시작(압록강 쪽)으로 닫는다 — 모두 북위 38.8도 위라 남한 바다에는 영향 없음
    close = [(130.0, 43.6), (126.0, 43.6), (123.4, 41.6)]
    mpoly = shapely.make_valid(Polygon(main + close + [main[0]]))
    mpoly = union_all([g for g in (mpoly.geoms if hasattr(mpoly, 'geoms') else [mpoly]) if g.geom_type in ('Polygon', 'MultiPolygon')])
    shapely.prepare(mpoly)
    isl, holes = [], []
    for c in rings:
        pg = shapely.make_valid(Polygon(c))
        if pg.is_empty: continue
        if not shapely.LinearRing(c).is_ccw and mpoly.contains(pg.representative_point()): holes.append(pg)   # 땅 안의 바닷물(석호)
        else: isl.append(pg)
    osm = union_all([mpoly] + isl)
    if holes: osm = osm.difference(union_all(holes))
    chk = {'서울': (126.98, 37.57, True), '대전': (127.38, 36.35, True), '부산': (129.05, 35.2, True), '목포': (126.4, 34.8, True),
           '제주': (126.55, 33.4, True), '울릉': (130.87, 37.5, True), '서해': (125.5, 36.5, False), '동해': (130.0, 37.5, False), '남해': (127.5, 34.0, False)}
    shapely.prepare(osm)
    bad = [k for k, (x, y, want) in chk.items() if osm.contains(Point(x, y)) != want]
    say(f'남북한 OSM 육지 점 {shapely.get_num_coordinates(osm)} · 확인 틀린 곳 {bad}')
    if bad: raise RuntimeError(f'육지 확인 실패 {bad}')
    JP = union_all([box(128.7, 32.5, 132.5, 34.0), box(129.0, 32.5, 132.5, 34.8)])     # 대마도·이키·규슈·혼슈 끝 (일본 쪽)
    KF = union_all([box(*f) for f in FINE]).difference(JP)
    nep = []
    for rs in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ne_big.json'))):
        try: pg = shapely.make_valid(Polygon(rs[0], rs[1:]))
        except Exception: continue
        if not pg.is_empty: nep.append(pg)
    ne_land = union_all(nep).difference(KF)
    osm_k = osm.intersection(KF)
    def polys_of(g):
        for q in shapely.get_parts(g):
            if q.geom_type == 'Polygon':
                if not q.is_empty: yield q
            elif q.geom_type in ('MultiPolygon', 'GeometryCollection'): yield from polys_of(q)
    srcs = list(polys_of(osm_k)) + list(polys_of(ne_land)); st = STRtree(srcs)
    pieces = []
    for ix in range(int(BIG[2] - BIG[0])):
        for iy in range(int(math.ceil(BIG[3] - BIG[1]))):
            bb = (BIG[0] + ix, BIG[1] + iy, BIG[0] + ix + 1, BIG[1] + iy + 1)
            for k in st.query(box(*bb)):
                pieces += list(polys_of(clip_by_rect(srcs[k], *bb)))
    tree = STRtree(pieces)
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
        ny = int(math.ceil((BIG[3] - BIG[1]) / cs - 1e-9))
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
    for lv in LV:
        nx = int(math.ceil((BIG[2] - BIG[0]) / LV[lv]['cell'] - 1e-9)); Lp, Kp, n = [], [], 0
        with mp.get_context('fork').Pool(NC) as pool:
            for j, (a, b, c) in enumerate(pool.imap(build_col, [(lv, ix) for ix in range(nx)])):
                Lp += a; Kp += b; n += c
                if j % 8 == 7: say(f'단계 {lv}: 칸 줄 {j + 1}/{nx}')
        L.append(Lp); K.append(Kp)
        say(f'단계 {lv}: 땅 조각 {len(Lp)} · 해안선 {len(Kp)} · 점 {n} (코어 {NC})')

    # ---------- 3) 한국 OSM: 호수·저수지·큰 강, 섬·만 이름
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
        if g.area < (0.03 if c.x < 127.05 and c.y > 35.0 else 2.0) * A1: continue
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
    W = [level_poly(wu, *LV[lv]['w']) for lv in LV]

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
    OVR = {'제주도': (126.55, 33.38, 45), '울릉도': (130.87, 37.5, 50), '독도': (131.87, 37.24, 50), '백령도': (124.68, 37.95, 200), '거제도': (128.65, 34.86, 200)}   # 같은 이름의 작은 섬은 빼고 그 섬만
    out_l = []
    for name, x, y, a, kind in keep:
        if kind in ('bay', 'lake'): minS = max(600, min(5000, 20 / math.sqrt(max(a, 1e-6))))
        elif kind == 'group': minS = 900
        else: minS = max(250, min(60000, 10 / math.sqrt(a))) if a > 0 else 5000
        if name in OVR and math.hypot(x - OVR[name][0], y - OVR[name][1]) < 0.3: minS = min(minS, OVR[name][2]); kind = 'island'
        out_l.append([name, round(x, 5), round(y, 5), round(minS), {'island': 0, 'bay': 1, 'group': 2, 'lake': 1}[kind]])
    # 바다 이름 (멀리 볼 때만, 앱이 kind 3을 크게 그린다)
    out_l += [['서해', 125.0, 36.15, 40, 3], ['남해', 127.75, 33.95, 40, 3], ['동해', 130.25, 37.95, 40, 3]]   # 가장 멀리(배율 50)에서도 보이게
    say(f'이름표 {len(out_l)}')

    js = json.dumps({'src': '© OpenStreetMap 기여자 (ODbL)', 'date': when, 'o': [LON0, LAT0], 'q': Q,
                     'L': L, 'kc': [round(LV[lv]['cell'] * Q) for lv in LV], 'lv': TH, 'F': [[] for _ in LV], 'W': W, 'lab': out_l}, ensure_ascii=False, separators=(',', ':'))
    open(f'{OUT}/basemap.json', 'w').write(js)
    gz = len(gzip.compress(js.encode(), 6))
    part = lambda o: len(json.dumps(o, separators=(',', ':')).encode()) // 1024
    say(f'크기 {len(js.encode()) // 1024} KB (압축하면 {gz // 1024} KB) · 땅 {[part(x) for x in L]} · 물 {[part(x) for x in W]} · 이름 {part(out_l)} KB')
except Exception:
    log.append(traceback.format_exc())
open(f'{OUT}/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log[-30:]))
