"""지도 화면용 '이 자리' 자료 만들기 → deploy/data/spots.json
- 조석: TideBED 기준 관측소 42곳 조화상수(69분조, 직접 분석) + 바다 격자 657곳의 조고비·조시차·평균해면
- 조류: 해양조사원 조류예보 지점 33곳의 최강창낙조·전류 표(2026)를 분조로 맞춘 흐름 성분"""
import json, sys, math, re
import numpy as np
sys.path.insert(0, '.')
import fit_ref as F
from extra_cons import EXTRA
from fit_crnt import fit as cfit, NAMES as CNAMES
import fit_crnt
from gen_grid import km
names = {c[0] for c in F.CONS}
DEFS = [c[:4] for c in F.CONS] + [[n, d, c0, rc] for n, d, c0, rc in EXTRA if n not in names and n != '2MK3']
F.CONS = [d + [0, 0] for d in DEFS]
D1 = json.load(open('tidebed_grid.json'))
refmsl = json.load(open('refmsl.json'))
REFS = sorted(F.R)
refs = []
for r in REFS:
    t, y = F.samples(F.R[r], sorted(F.R[r])); c = F.fit(t, y)
    refs.append([r, round(float(c[0]), 2), round(refmsl[r], 2), [round(float(x), 2) for x in c[1:]]])
def josi(s):
    m = re.match(r'([+-])(\d+)', s.replace('분', '')) if s not in ('+', '-') else None
    return 0 if not m else (int(m.group(2)) * (1 if m.group(1) == '+' else -1))
tide = []
for k, v in D1.items():
    if not isinstance(v, dict): continue
    la, lo = map(float, k.split(','))
    tide.append([la, lo, REFS.index(v['ref']), round(v['jogo'], 4), josi(v['josi']), round(v['msl'], 1)])
# 이 자리 물 높이 (앱과 같은 방식: 가까운 격자 3곳 거리 가중)
RM = {i: np.array([r[1]] + r[3]) for i, r in enumerate(refs)}
def basisT(t): return np.vstack([np.ones((1, len(t))), F.basis(F.CONS, t)]).T
def point_h(la, lo, t):
    near = sorted(((km((la, lo), (p[0], p[1])), p) for p in tide), key=lambda x: x[0])[:3]
    near = [x for x in near if x[0] <= 8] or near[:1]
    w = np.array([1 / max(d, 0.3) ** 2 for d, _ in near]); w /= w.sum()
    h = 0
    for wi, (d, p) in zip(w, near):
        ref = basisT(t - p[4] * 60000) @ RM[p[2]]
        h = h + wi * (p[5] + p[3] * (ref - refs[p[2]][2]))
    return h
# 조류
FE = json.load(open('fldebb_all.json'))
ci = [i for i, d in enumerate(DEFS) if d[0] in CNAMES]
fit_crnt.CONS = [F.CONS[i] for i in ci]
cur = []
for code, rec in sorted(FE.items(), key=lambda x: -x[1]['lat']):
    ev = [e for e in rec['ev'] if e[0] >= '2026']
    if code == '17LTC06':   # 2026 표가 가덕도남측과 똑같이 잘못 올라와 있어 2025 표를 쓴다
        ev = [e for e in rec['ev'] if e[0] < '2026']
    th, cu, cv = cfit(ev)
    sp = sorted(e[2] for e in ev if e[2] > 0); mx = sp[int(len(sp) * 0.95)]
    cur.append([rec['name'], rec['lat'], rec['lon'], round(math.degrees(th) % 360, 2), round(mx), [round(float(x), 2) for x in cu], [round(float(x), 2) for x in cv]])
out = {'v': 1, 'src': '국립해양조사원 TideBED 예측조위·조류예보(최강창낙조·전류)를 바탕으로 계산',
       'defs': DEFS, 'refs': refs, 'tide': tide, 'cur': {'ci': ci, 'p': cur}}
js = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open('../deploy/data/spots.json', 'w').write(js)
print('크기', len(js) // 1024, 'KB', '분조', len(DEFS), '기준', len(refs), '격자', len(tide), '조류', len(cur))
