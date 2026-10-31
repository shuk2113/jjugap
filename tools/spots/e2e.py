import json, sys, math, re
import numpy as np
sys.path.insert(0, '.')
import fit_ref as F
from extra_cons import EXTRA
names = {c[0] for c in F.CONS}
F.CONS = F.CONS + [[n, d, c0, rc, 0, 0] for n, d, c0, rc in EXTRA if n not in names and n != '2MK3']
D1 = json.load(open('tidebed_grid.json')); D2 = json.load(open('tidebed_grid2.json'))
models, refmsl = {}, {}
for r, rec in F.R.items():
    t, y = F.samples(rec, sorted(rec)); models[r] = F.fit(t, y)
def josi(s):
    m = re.match(r'([+-])(\d+)', s.replace('분', '')) if s not in ('+', '-') else None
    return 0 if not m else (int(m.group(2)) * (1 if m.group(1) == '+' else -1))
# 기준 MSL: 격자 자료에서 구한다 (rh - (h-msl)/jogo 의 가운데값)
for k, v in D1.items():
    if not isinstance(v, dict): continue
    d = v['20261031']; refmsl.setdefault(v['ref'], []).append(np.median(np.array(d['rh']) - (np.array(d['h']) - v['msl']) / v['jogo']))
refmsl = {r: float(np.median(x)) for r, x in refmsl.items()}
errs, mx, refe = [], [], []
for k, v in D1.items():
    if not isinstance(v, dict) or not isinstance(D2.get(k), dict): continue
    for src, d in ((D1, '20261031'), (D1, '20261107'), (D2, '20261103'), (D2, '20261114')):
        r = src[k][d]; t0 = F.ms(r['t0']); t = np.array([t0 + i * 600000 for i in range(len(r['h']))])
        js = josi(v['josi'])
        ref = F.pred(models[v['ref']], t - js * 60000)
        p = v['msl'] + v['jogo'] * (ref - refmsl[v['ref']])
        e = p - np.array(r['h']); errs.append(math.sqrt((e ** 2).mean())); mx.append(np.abs(e).max())
        tr0 = F.ms(r['r0']); tr = np.array([tr0 + i * 600000 for i in range(len(r['rh']))])
        refe.append(math.sqrt(((F.pred(models[v['ref']], tr) - np.array(r['rh'])) ** 2).mean()))
print('점 물높이 오차(TideBED 대비): RMS 중앙 %.1f 90%% %.1f · 최대오차 중앙 %.1f 90%% %.1f cm' % (np.median(errs), np.percentile(errs, 90), np.median(mx), np.percentile(mx, 90)))
print('기준 관측소 재현 오차 RMS 중앙 %.1f 90%% %.1f' % (np.median(refe), np.percentile(refe, 90)))
json.dump(refmsl, open('refmsl.json', 'w'), ensure_ascii=False)
