#!/usr/bin/env python3
"""서해 중부 연안 수심 조각 만들기 (국립해양조사원 BADA2024 격자 수심, 150m 간격).

자료: 공공데이터포털 '해양수산부 국립해양조사원_자연과학용 수심정보 조회' (15142498)
이용조건: 공공저작물 출처표시(공공누리 제1유형) — 앱에 '수심: 국립해양조사원' 표시.
수심 기준은 평균해수면 아래(m). 앱이 그 시각 조위로 '지금 수심'을 계산한다.

인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.

  python3 depth.py --test               # 작은 범위 한 번 불러 응답 모양만 보기
  python3 depth.py OUT_DIR [--only TILE] # 전체(또는 한 조각) 받아 OUT_DIR/depth/ 에 저장
"""
import json, math, os, re, struct, sys, time, urllib.error, urllib.parse, urllib.request, zlib

KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
URL = 'https://apis.data.go.kr/1192136/waterDepth/GetWaterDepthApiService'
# 범위: 인천·경기만 ~ 군산·부안 앞바다 (섬 포함, 해안에서 바깥으로 60~80km)
LAT0, LAT1, LON0, LON1 = 35.50, 37.80, 125.30, 126.95
TILE = 0.10   # 조각 크기(도) — 한 조각 약 11km × 9km


def mask(s):
    return s.replace(KEY, '***') if KEY else s


def call(ymin, ymax, xmin, xmax, page=1, rows=300, tries=4):
    q = {'type': 'json', 'ymin': f'{ymin:.4f}', 'ymax': f'{ymax:.4f}',
         'xmin': f'{xmin:.4f}', 'xmax': f'{xmax:.4f}', 'pageNo': page, 'numOfRows': rows}
    url = f'{URL}?serviceKey={KEY}&' + urllib.parse.urlencode(q, safe='')   # 다른 수집과 같은 방식(키는 그대로)
    err = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:400]
            err = f'HTTP {e.code} · {body}'
            if e.code in (400, 401, 403): break
            time.sleep(2 + 3 * i)
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
    try:
        txt = call(35.95, 35.97, 126.40, 126.43, rows=12, tries=1)
    except Exception as e:
        print('실패:', str(e)[:400].replace('\n', ' ')); return 1
    print('응답 앞부분:', mask(txt[:900]))
    try:
        it, total, _ = items_of(txt)
        print('총 개수:', total, '· 받은 개수:', len(it))
        if it: print('첫 항목 키:', list(it[0].keys()), '· 값:', it[0])
        for o in it[1:5]: print('  ', o)
    except Exception as e:
        print('JSON 읽기 실패:', e)
    return 0


DY, DX = 1 / 720, 1 / 600        # 앱 격자: 위도 5초(약 154m) · 경도 6초(약 150m)
NY, NX = round(TILE / DY), round(TILE / DX)   # 한 조각 72 × 60 칸
NONE = -32768


def tname(ti, tj):
    return f'{round((LAT0 + ti * TILE) * 10)}_{round((LON0 + tj * TILE) * 10)}'


def fetch_tile(ti, tj):
    la, lo = LAT0 + ti * TILE, LON0 + tj * TILE
    pts, page, total = [], 1, None
    while True:
        it, tot, _ = items_of(call(la, la + TILE, lo, lo + TILE, page=page))
        total = tot if total is None else total
        for o in it:
            y = pick(o, 'lat', 'latitude', 'y')
            x = pick(o, 'lot', 'lon', 'lng', 'longitude', 'x')
            z = pick(o, 'depth', 'dep', 'wtrdep', 'wdepth', 'dpth', 'z', 'val', 'value')
            try: pts.append((float(y), float(x), float(z)))
            except (TypeError, ValueError): pass
        if not it or page * 300 >= (total or 0): break
        page += 1
    return pts, total or 0


def pack(pts, ti, tj):
    """점들을 앱 격자 칸에 평균으로 담고(조각 밖 점은 버림), 빈 칸은 이웃 3칸 이상이 있으면 이웃 평균으로 메운다.
    저장: int16(10cm 단위, 평균해수면 아래 +) NY×NX, 없음 = -32768, zlib."""
    sm = [0.0] * (NY * NX); cn = [0] * (NY * NX)
    y0, x0 = LAT0 + ti * TILE, LON0 + tj * TILE
    for y, x, z in pts:
        i, j = int((y - y0) / DY + 0.5), int((x - x0) / DX + 0.5)
        if 0 <= i < NY and 0 <= j < NX and -100 < z < 12000:
            sm[i * NX + j] += z; cn[i * NX + j] += 1
    g = [round(sm[k] / cn[k] * 10) if cn[k] else NONE for k in range(NY * NX)]
    fill = []
    for i in range(NY):
        for j in range(NX):
            if g[i * NX + j] != NONE: continue
            nb = [g[a * NX + b] for a in (i - 1, i, i + 1) for b in (j - 1, j, j + 1)
                  if 0 <= a < NY and 0 <= b < NX and (a, b) != (i, j) and g[a * NX + b] != NONE]
            if len(nb) >= 3: fill.append((i * NX + j, round(sum(nb) / len(nb))))
    for k, v in fill: g[k] = v
    g = [max(-32767, min(32767, v)) if v != NONE else NONE for v in g]
    n = sum(1 for v in g if v != NONE)
    return zlib.compress(struct.pack(f'<{NY * NX}h', *g), 9), n


def main(out, only=None):
    if not KEY: print('인증키 없음'); return 1
    d = os.path.join(out, 'depth'); os.makedirs(d, exist_ok=True)
    idx_path = os.path.join(d, 'index.json')
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    idx.setdefault('tiles', {}); idx.setdefault('none', [])
    idx.update({'src': '국립해양조사원 BADA2024 격자 수심(150m) · 공공누리 제1유형', 'datum': '평균해수면', 'unit': 'dm',
                'lat0': LAT0, 'lon0': LON0, 'tile': TILE, 'ny': NY, 'nx': NX, 'nt': [round((LAT1 - LAT0) / TILE), round((LON1 - LON0) / TILE)]})
    n_calls = 0
    for ti in range(idx['nt'][0]):
        for tj in range(idx['nt'][1]):
            name = tname(ti, tj)
            if only and name != only: continue
            if not only and (name in idx['tiles'] or name in idx['none']): continue
            pts, total = fetch_tile(ti, tj); n_calls += max(1, math.ceil(total / 300))
            blob, n = pack(pts, ti, tj) if pts else (None, 0)
            if n:
                open(os.path.join(d, name + '.bin'), 'wb').write(blob)
                idx['tiles'][name] = n
                print(f'{name}: 점 {len(pts)}개 → 칸 {n}개 · {len(blob) // 1024}KB')
            else:
                if name not in idx['none']: idx['none'].append(name)
                print(f'{name}: 바다 자료 없음')
            idx['v'] = int(time.time())
            json.dump(idx, open(idx_path, 'w'), ensure_ascii=False, separators=(',', ':'))
            if n_calls > 9000: print('하루 호출 한도 가까움 — 여기까지 저장, 다음에 이어서'); return 0
    left = idx['nt'][0] * idx['nt'][1] - len(idx['tiles']) - len(idx['none'])
    print('끝 · 호출', n_calls, '· 남은 조각', left)
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == '--test': sys.exit(test())
    sys.exit(main(a[0], a[a.index('--only') + 1] if '--only' in a else None))
