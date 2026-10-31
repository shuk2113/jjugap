"""TideBED 기준 관측소 42곳 조화분석 (1년에 걸친 45일 × 10분 예측 조위)"""
import json, sys, math
import numpy as np
sys.path.insert(0, '.')
from tideharm import basis, ST
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
def ms(s): return datetime.strptime(s, '%Y-%m-%d %H:%M').replace(tzinfo=KST).timestamp() * 1000
CONS = ST['ocheon']['cons']          # 44개 분조 정의를 그대로 쓴다
NAMES = [c[0] for c in CONS]
R = json.load(open('ref_series.json'))
def samples(rec, days):
    t, y = [], []
    for d in days:
        v = rec[d]; t0 = ms(v['r0'])
        t += [t0 + i * 600000 for i in range(len(v['rh']))]; y += v['rh']
    return np.array(t), np.array(y, dtype=float)
def fit(t, y, lam=0.0):
    A = np.vstack([np.ones((1, len(t))), basis(CONS, t)]).T
    c = np.linalg.lstsq(A, y, rcond=None)[0]
    return c
def pred(c, t): return np.vstack([np.ones((1, len(t))), basis(CONS, t)]).T @ c
if __name__ == '__main__':
    models = {}; rep = []
    for r, rec in R.items():
        days = sorted(rec)
        te = days[3::9]; tr = [d for d in days if d not in te]
        t, y = samples(rec, tr); c = fit(t, y)
        t2, y2 = samples(rec, te); e = pred(c, t2) - y2
        e_in = pred(c, t) - y
        t3, y3 = samples(rec, days); cf = fit(t3, y3)
        models[r] = cf
        rep.append((r, math.sqrt((e_in ** 2).mean()), math.sqrt((e ** 2).mean()), np.abs(e).max()))
    rep.sort(key=lambda x: -x[2])
    for x in rep[:8]: print('%-8s 맞춘 날 %.2f · 확인 날 RMS %.2f 최대 %.1f cm' % x)
    print('확인 날 RMS 중앙 %.2f cm' % np.median([x[2] for x in rep]))
    np.save('ref_models.npy', {r: c.tolist() for r, c in models.items()}, allow_pickle=True)
    json.dump({r: [round(float(v), 3) for v in c] for r, c in models.items()}, open('ref_models.json', 'w'), ensure_ascii=False)
