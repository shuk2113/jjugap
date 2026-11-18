#!/usr/bin/env python3
"""바다 지도(deploy/data/basemap.json)에 방파제·도류제를 더한다.
OpenStreetMap(© OpenStreetMap 기여자, ODbL)의 man_made=breakwater|groyne 길(선)·면을 GitHub에서 받아 둔
jjugap-main/.github/data/osm_breakwaters.json 에서 읽는다. 육지 자료(해안선)에 들어 있지 않은 바다 위 시설이 지도에 보이게.
  B: { l: [선(1e-5도 정수 차분)], a: [면] }   (앱은 바다 부분에만 육지 색 띠로 그린다)
"""
import json, math, sys
SRC = '/home/claude/jjugap-main/.github/data/osm_breakwaters.json'
BM = '/home/claude/sp/deploy/data/basemap.json'
KX = math.cos(math.radians(36.6))


def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        i, j = st.pop()
        ax, ay = pts[i][0] * KX, pts[i][1]; bx, by = pts[j][0] * KX, pts[j][1]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy); best, bi = -1, -1
        for m in range(i + 1, j):
            px, py = pts[m][0] * KX, pts[m][1]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L > 1e-12 else math.hypot(px - ax, py - ay)
            if d > best: best, bi = d, m
        if best > tol: keep[bi] = True; st += [(i, bi), (bi, j)]
    return [p for p, f in zip(pts, keep) if f]


def length_m(c):
    return sum(math.hypot((b[0] - a[0]) * 111320 * KX, (b[1] - a[1]) * 111320) for a, b in zip(c, c[1:]))


def main():
    d = json.load(open(BM)); o0, o1, q = d['o'][0], d['o'][1], d['q']
    W = json.load(open(SRC))['ways']
    enc = lambda c: (lambda Q: [Q[0][0], Q[0][1]] + [v for a, b in zip(Q, Q[1:]) if a != b for v in (b[0] - a[0], b[1] - a[1])])([(round((x - o0) * q), round((y - o1) * q)) for x, y in c])
    L, A, n = [], [], 0
    for w in W:
        c = w['c']
        if length_m(c) < 30: continue   # 아주 작은 것은 지도에서 안 보여서
        if not all(124.5 < x < 128.5 and 33 < y < 38.7 for x, y in c): continue
        s = dp(c, 0.00003)               # 약 3m 단순화
        if len(s) < 2: continue
        closed = c[0] == c[-1] and len(s) >= 4
        (A if (w['area'] or closed) and len(s) >= 4 else L).append(enc(s)); n += len(s)
    d['B'] = {'l': L, 'a': A}
    d['src'] = d.get('src', '© OpenStreetMap 기여자 (ODbL)')
    js = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
    open(BM, 'w').write(js)
    print('방파제 선', len(L), '면', len(A), '점', n, '· basemap', len(js.encode()) // 1024, 'KB')


if __name__ == '__main__':
    sys.exit(main())
