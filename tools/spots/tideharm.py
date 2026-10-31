"""앱의 TideHarm 계산을 파이썬으로 옮긴 것 (같은 결과가 나와야 한다)"""
import json, math
import numpy as np
D2R = math.pi / 180; DAY = 86400000
SPEED = np.array([14.4920521, 0.5490165, 0.0410686, 0.0046418, 0.0022064, 0.0000020])
ST = json.load(open('/tmp/claude-0/-home-claude/9ec8b963-99f7-50b6-9d59-55e76d707139/scratchpad/spots/stations.json'))
def astro(jd):
    T = (jd - 2451545.0) / 36525
    s = 218.3164477 + 481267.88123421 * T; h = 280.46646 + 36000.76983 * T
    p = 83.3532465 + 4069.0137287 * T; N = 125.04452 - 1934.136261 * T; p1 = 282.93735 + 1.71946 * T
    ut = ((jd + 0.5) % 1 + 1) % 1
    return np.stack([360 * ut + 180 + h - s, s, h, p, -N, p1]), N
def groups(N):
    n = N * D2R; c = np.cos; s = np.sin
    return {'1': (1 + 0 * n, 0 * n),
            'M2': (1.0004 - 0.0373 * c(n) + 0.0002 * c(2 * n), -2.14 * s(n)),
            'K1': (1.0060 + 0.1150 * c(n) - 0.0088 * c(2 * n) + 0.0006 * c(3 * n), -8.86 * s(n) + 0.68 * s(2 * n) - 0.07 * s(3 * n)),
            'O1': (1.0089 + 0.1871 * c(n) - 0.0147 * c(2 * n) + 0.0014 * c(3 * n), 10.80 * s(n) - 1.34 * s(2 * n) + 0.19 * s(3 * n)),
            'K2': (1.0241 + 0.2863 * c(n) + 0.0083 * c(2 * n) - 0.0015 * c(3 * n), -17.74 * s(n) + 0.68 * s(2 * n) - 0.04 * s(3 * n)),
            'MM': (1.0 - 0.1300 * c(n) + 0.0013 * c(2 * n), 0 * n)}
def gf(G, k):
    if k == 'OO1': return G['O1'][0] ** 2, -G['O1'][1]
    if k == 'MSF': return G['M2'][0], -G['M2'][1]
    return G[k]
def basis(cons, ms):
    """각 분조의 (f·cos, f·sin) 기저 — 계수 a,b 곱하면 물 높이"""
    ms = np.asarray(ms, dtype=float); jd = ms / DAY + 2440587.5
    args, N = astro(jd); G = groups(N); out = []
    for name, d, c0, recipe, *_ in cons:
        V = c0 + sum(d[i] * args[i] for i in range(6))
        f = 1; u = 0
        for k, m in recipe:
            fk, uk = gf(G, k); f = f * fk ** abs(m); u = u + m * uk
        ph = (V + u) * D2R
        out.append(f * np.cos(ph)); out.append(f * np.sin(ph))
    return np.stack(out)
def height(key, ms):
    st = ST[key]; B = basis(st['cons'], ms)
    coef = np.array([v for c in st['cons'] for v in (c[4], c[5])])
    return st['z0'] + coef @ B
