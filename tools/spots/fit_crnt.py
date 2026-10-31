"""조류 조화 맞춤: 최강창낙조(크기·방향)와 전류(0) 표에서 흐름 성분 u(주축)·v(옆)를 분조로 맞춘다"""
import json, sys, math
import numpy as np
sys.path.insert(0, '.')
from tideharm import basis, ST, D2R
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
def ms(s): return datetime.strptime(s, '%Y-%m-%d %H:%M').replace(tzinfo=KST).timestamp() * 1000
NAMES = ['M2', 'S2', 'N2', 'K2', 'K1', 'O1', 'P1', 'Q1', 'M4', 'MS4', 'MN4', 'M6', '2MS6', 'MK3', 'MO3', '2N2', 'MU2', 'NU2', 'L2', '2SM2', 'MSF', 'MK4', 'S4', '2MN6', 'MSN6', 'M8', 'J1', 'OO1', 'T2', 'MNS2', '2MS2', 'SN4']
CONS = [c for c in ST['ocheon']['cons'] if c[0] in NAMES]
SPD = {}
for c in CONS:
    w = sum(c[1][i] * s for i, s in enumerate([14.4920521, 0.5490165, 0.0410686, 0.0046418, 0.0022064, 0.0000020]))
    SPD[c[0]] = w
def design(tms, deriv=False):
    B = basis(CONS, tms)              # 2N × T  (f cos, f sin)
    if not deriv:
        return np.vstack([np.ones((1, B.shape[1])), B]).T
    # 시간 미분(시당): d/dt [f cos φ] = -f w sin φ, d/dt [f sin φ] = f w cos φ
    rows = [np.zeros(B.shape[1])]
    for j, c in enumerate(CONS):
        w = SPD[c[0]] * D2R
        rows.append(-w * B[2 * j + 1]); rows.append(w * B[2 * j])
    return np.vstack(rows).T
def fit(ev, lam=0.3):
    t = np.array([ms(e[0]) for e in ev]); ph = np.array([e[1] for e in ev]) * D2R; sp = np.array([e[2] for e in ev])
    mx = sp > 0
    z = (sp[mx] * np.exp(2j * ph[mx])).sum(); th = np.angle(z) / 2       # 주축 방향 (도착 방향 기준, 북=0 시계방향)
    u = sp * np.cos(ph - th); v = sp * np.sin(ph - th)
    A = design(t); Ad = design(t[mx], True)
    M = np.vstack([A, lam * Ad]); yu = np.concatenate([u, np.zeros(mx.sum())]); yv = np.concatenate([v, np.zeros(mx.sum())])
    # 약한 능선 정규화로 사이 값이 출렁이지 않게
    R = 0.02 * np.eye(M.shape[1]); R[0, 0] = 0
    cu = np.linalg.lstsq(np.vstack([M, R]), np.concatenate([yu, np.zeros(M.shape[1])]), rcond=None)[0]
    cv = np.linalg.lstsq(np.vstack([M, R]), np.concatenate([yv, np.zeros(M.shape[1])]), rcond=None)[0]
    return th, cu, cv
def predict(th, cu, cv, tms):
    A = design(tms); u = A @ cu; v = A @ cv
    return u, v
if __name__ == '__main__':
    D = json.load(open('fldebb_all.json'))
    # 1) 2025로 맞추고 2026 표로 검증 (전류 시각·최강 크기)
    for code in ['16LTC03', '20LTC07', '15LTC02', '17LTC06', '19LTC02', '15LTC03']:
        ev = D[code]['ev']; tr = [e for e in ev if e[0] < '2026']; te = [e for e in ev if e[0] >= '2026']
        if not tr: tr, te = ev[:len(ev) // 2], ev[len(ev) // 2:]
        th, cu, cv = fit(tr)
        tt = np.array([ms(e[0]) for e in te]); sp = np.array([e[2] for e in te]); ph = np.array([e[1] for e in te]) * D2R
        u, v = predict(th, cu, cv, tt)
        mx = sp > 0
        e_max = np.hypot(u, v)[mx] - sp[mx]
        # 전류 시각 오차: 0 사건 근처 ±90분에서 |흐름| 최소 시각
        errs = []
        for t0 in tt[~mx][:600]:
            g = t0 + np.arange(-90, 91, 2) * 60000; uu, vv = predict(th, cu, cv, g)
            errs.append(abs((g[np.argmin(np.hypot(uu, vv))] - t0) / 60000))
        print(f"{code} {D[code]['name']}: 최강 크기 오차 RMS {math.sqrt((e_max**2).mean()):.1f} cm/s (평균 {sp[mx].mean():.0f}) · 전류 시각 오차 중앙 {np.median(errs):.0f}분 90% {np.percentile(errs,90):.0f}분 · 전류 때 |흐름| {np.median(np.hypot(*predict(th,cu,cv,tt[~mx]))):.1f}")
    # 2) 10분 시계열(10/30~11/01)과 비교: 천수만
    S = json.load(open('series_16LTC03.json'))
    DIRS = ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동', '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서']
    th, cu, cv = fit(D['16LTC03']['ev'])
    rows = [r for d in sorted(S) for r in S[d]]
    tt = np.array([ms(r[0]) for r in rows]); obs = np.array([r[2] for r in rows]); od = np.array([DIRS.index(r[1]) * 22.5 for r in rows])
    u, v = predict(th, cu, cv, tt); pr = np.hypot(u, v)
    pd = (np.degrees(th + np.arctan2(v, u))) % 360
    dd = np.abs((pd - od + 180) % 360 - 180)
    print('천수만 10분 시계열: 속도 RMS %.1f cm/s (관측 평균 %.0f, 최대 %.0f), 방향 차 중앙 %.0f° (속도>30일 때 %.0f°)' % (
        math.sqrt(((pr - obs) ** 2).mean()), obs.mean(), obs.max(), np.median(dd), np.median(dd[obs > 30])))
    for i in range(0, 144, 9): print(rows[i][0], rows[i][1], rows[i][2], '→ %.0f %.0f°' % (pr[i], pd[i]))
