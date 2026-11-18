#!/usr/bin/env python3
"""서해 중부 연안 수심 조각 만들기 (국립해양조사원 BADA2024 격자 수심, 150m 간격).

자료: 공공데이터포털 '해양수산부 국립해양조사원_자연과학용 수심정보 조회' (15142498)
이용조건: 공공저작물 출처표시(공공누리 제1유형) — 앱에 '수심: 국립해양조사원' 표시.
수심 기준은 평균해수면 아래(m). 앱이 그 시각 조위로 '지금 수심'을 계산한다.

인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.

  python3 depth.py --test               # 작은 범위 한 번 불러 응답 모양만 보기
  python3 depth.py OUT_DIR [--only TILE] # 전체(또는 한 조각) 받아 OUT_DIR/depth/ 에 저장
"""
import json, math, os, re, struct, sys, time, urllib.parse, urllib.request, zlib

KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
URL = 'https://apis.data.go.kr/1192136/waterDepth'
# 범위: 인천·경기만 ~ 군산·부안 앞바다 (섬 포함, 해안에서 바깥으로 60~80km)
LAT0, LAT1, LON0, LON1 = 35.50, 37.80, 125.30, 126.95
TILE = 0.10   # 조각 크기(도) — 한 조각 약 11km × 9km


def mask(s):
    return s.replace(KEY, '***') if KEY else s


def call(ymin, ymax, xmin, xmax, page=1, rows=300, tries=4):
    q = {'serviceKey': KEY, 'type': 'json', 'ymin': f'{ymin:.4f}', 'ymax': f'{ymax:.4f}',
         'xmin': f'{xmin:.4f}', 'xmax': f'{xmax:.4f}', 'pageNo': page, 'numOfRows': rows}
    url = URL + '?' + urllib.parse.urlencode(q, safe='%')
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            err = e; time.sleep(2 + 3 * i)
    raise RuntimeError(mask(str(err)))


def items_of(txt):
    d = json.loads(txt)
    body = d.get('body') or d.get('response', {}).get('body') or {}
    it = body.get('items')
    if isinstance(it, dict): it = it.get('item', [])
    if isinstance(it, dict): it = [it]
    total = int(body.get('totalCount') or 0)
    return it or [], total, d


def pick(o, *names):
    for n in names:
        for k in o:
            if k.lower() == n: return o[k]
    return None


def test():
    if not KEY: print('인증키 없음'); return 1
    txt = call(35.95, 35.97, 126.40, 126.43, rows=5)
    print('응답 앞부분:', mask(txt[:900]))
    try:
        it, total, _ = items_of(txt)
        print('총 개수:', total, '· 받은 개수:', len(it))
        if it: print('첫 항목 키:', list(it[0].keys()), '· 값:', it[0])
    except Exception as e:
        print('JSON 읽기 실패:', e)
    return 0


def fetch_tile(la, lo):
    pts, page, total = [], 1, None
    while True:
        it, tot, _ = items_of(call(la, la + TILE, lo, lo + TILE, page=page))
        total = tot if total is None else total
        for o in it:
            y, x, z = pick(o, 'lat', 'latitude', 'y'), pick(o, 'lot', 'lon', 'lng', 'longitude', 'x'), pick(o, 'depth', 'dep', 'wtrdep', 'z', 'val', 'value')
            try: pts.append((float(y), float(x), float(z)))
            except (TypeError, ValueError): pass
        if not it or page * 300 >= (total or 0): break
        page += 1
    return pts, total or 0


def pack(pts, la, lo):
    """점들을 규칙 격자로: 위도 간격 dy, 경도 간격 dx 를 점들에서 알아내 int16(10cm 단위)로."""
    if not pts: return None
    ys = sorted({round(p[0], 5) for p in pts}); xs = sorted({round(p[1], 5) for p in pts})
    def step(v):
        d = [b - a for a, b in zip(v, v[1:]) if b - a > 1e-6]
        d.sort(); return d[len(d) // 2] if d else TILE
    dy, dx = step(ys), step(xs)
    ny, nx = int(round(TILE / dy)) + 1, int(round(TILE / dx)) + 1
    g = [-32768] * (ny * nx)
    for y, x, z in pts:
        i, j = int(round((y - la) / dy)), int(round((x - lo) / dx))
        if 0 <= i < ny and 0 <= j < nx:
            g[i * nx + j] = max(-32767, min(32767, int(round(z * 10))))
    raw = struct.pack('<4d2H', la, lo, dy, dx, ny, nx) + struct.pack(f'<{ny * nx}h', *g)
    return zlib.compress(raw, 9), ny, nx, dy, dx


def main(out, only=None):
    if not KEY: print('인증키 없음'); return 1
    os.makedirs(os.path.join(out, 'depth'), exist_ok=True)
    idx_path = os.path.join(out, 'depth', 'index.json')
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {'tiles': {}}
    idx.update({'src': '국립해양조사원 BADA2024 격자 수심(150m) · 공공누리 제1유형', 'datum': 'msl', 'unit': 'dm', 'tile': TILE,
                'box': [LAT0, LAT1, LON0, LON1], 'fmt': 'zlib(<4d2H header: lat0,lon0,dlat,dlon,ny,nx> + int16[ny*nx], -32768=없음)'})
    n_calls = 0
    la = LAT0
    while la < LAT1 - 1e-9:
        lo = LON0
        while lo < LON1 - 1e-9:
            name = f'{la:.2f}_{lo:.2f}'
            if (only and name != only) or (not only and name in idx['tiles']):
                lo += TILE; continue
            pts, total = fetch_tile(la, lo); n_calls += max(1, math.ceil(total / 300))
            if pts:
                blob, ny, nx, dy, dx = pack(pts, la, lo)
                open(os.path.join(out, 'depth', name + '.bin'), 'wb').write(blob)
                idx['tiles'][name] = {'n': len(pts), 'ny': ny, 'nx': nx}
                print(f'{name}: 점 {len(pts)}개 → {len(blob) // 1024}KB')
            else:
                idx['tiles'][name] = {'n': 0}   # 육지뿐이거나 자료 없음
                print(f'{name}: 자료 없음')
            json.dump(idx, open(idx_path, 'w'), ensure_ascii=False)
            if n_calls > 9000: print('하루 호출 한도 가까움 — 여기까지 저장, 다음에 이어서'); return 0
            lo += TILE
        la += TILE
    print('끝 · 호출', n_calls)
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == '--test': sys.exit(test())
    sys.exit(main(a[0], a[a.index('--only') + 1] if '--only' in a else None))
