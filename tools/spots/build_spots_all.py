"""'이 자리' 자료 (서해 + 서남해·남해·제주) → spots_all.json
- 조석: TideBED 기준 관측소 조화상수(69분조, 직접 분석) + 바다 격자마다 조고비·조시차·평균해면
- 조류: 해양조사원 조류예보 지점의 최강창낙조·전류 표(2026)를 분조로 맞춘 흐름 성분
- 검증: 남해 검증용 격자(이틀 더 받은 곳)에서 계산한 물 높이를 TideBED 예측과 비교
입력: (서해) tidebed_grid.json ref_series.json fldebb_all.json refmsl.json · (남해) S/tidebed_grid.json S/ref_series.json S/fldebb.json
"""
import json, sys, math, re
import numpy as np
sys.path.insert(0, '.')
import fit_ref as F
from extra_cons import EXTRA
from fit_crnt import fit as cfit, NAMES as CNAMES
import fit_crnt
S = sys.argv[1] if len(sys.argv) > 1 else 'south_in'
names = {c[0] for c in F.CONS}
DEFS = [c[:4] for c in F.CONS] + [[n, d, c0, rc] for n, d, c0, rc in EXTRA if n not in names and n != '2MK3']
F.CONS = [d + [0, 0] for d in DEFS]
KX = math.cos(math.radians(36.6))
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32
def josi(s):   # '+12분', '-1시간21분', '+23시간46분' → 분 (하루 가까운 시차는 하루를 빼서 가까운 쪽으로)
    m = re.match(r'([+-])(?:(\d+)시간)?(?:(\d+)분)?', s or '')
    if not m or not (m.group(2) or m.group(3)): return 0
    v = (int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) * (1 if m.group(1) == '+' else -1)
    return v   # 하루 가까운 시차도 적힌 그대로 (TideBED가 그렇게 계산한다)

# ---------- 기준 관측소: 서해(기존) + 남해(새)
RS = json.load(open(f'{S}/ref_series.json'))
for r, rec in RS.items():
    good = {d: v for d, v in rec.items() if isinstance(v, dict) and v.get('rh') and all(isinstance(y, (int, float)) for y in v['rh'])}
    if len(good) >= 30 and r not in F.R: F.R[r] = good
    elif r not in F.R: print('기준 관측소 자료 모자람', r, len(good))
G1 = json.load(open('tidebed_grid.json')); G2 = json.load(open(f'{S}/tidebed_grid.json'))
# 평균해면(기준): 서해는 전에 구한 값, 남해는 격자 자료에서 (rh - (h - msl)/조고비 의 가운데값)
refmsl = json.load(open('refmsl.json'))
acc = {}
for k, v in G2.items():
    if not isinstance(v, dict) or v['ref'] in refmsl: continue
    for d, x in v.items():
        if isinstance(x, dict) and 'rh' in x:
            rh = np.array([np.nan if y in (None, '', '-') else float(y) for y in x['rh']]); h = np.array(x['h'])
            acc.setdefault(v['ref'], []).append(np.nanmedian(rh - (h - v['msl']) / v['jogo']))
for r, xs in acc.items(): refmsl[r] = float(np.median(xs))
REFS = sorted(r for r in F.R if r in refmsl)
refs = []
for r in REFS:
    t, y = F.samples(F.R[r], sorted(F.R[r])); c = F.fit(t, y)
    refs.append([r, round(float(c[0]), 2), round(refmsl[r], 2), [round(float(x), 2) for x in c[1:]]])
RI = {r: i for i, r in enumerate(REFS)}
# ---------- 격자
tide = []; miss = 0
for G in (G1, G2):
    for k, v in G.items():
        if not isinstance(v, dict) or 'ref' not in v: continue
        if v['ref'] not in RI: miss += 1; continue
        la, lo = map(float, k.split(','))
        tide.append([la, lo, RI[v['ref']], round(v['jogo'], 4), josi(v['josi']), round(v['msl'], 1)])
print('격자', len(tide), '(기준 관측소 없어 뺀 곳', miss, ')')
# ---------- 검증: 남해 격자에서 앱과 같은 방식(가까운 격자 3곳 거리 가중)으로 계산 → TideBED 예측과 비교
RM = {i: np.array([r[1]] + r[3]) for i, r in enumerate(refs)}
def basisT(t): return np.vstack([np.ones((1, len(t))), F.basis(F.CONS, t)]).T
TA = np.array([[p[0], p[1]] for p in tide])
def point_h(la, lo, t, self_only=False):
    d = np.hypot((TA[:, 1] - lo) * KX, TA[:, 0] - la) * 111.32
    idx = np.argsort(d)[:3]
    near = [(d[i], tide[i]) for i in idx if d[i] <= 8] or [(d[idx[0]], tide[idx[0]])]
    if self_only: near = near[:1]
    w = np.array([1 / max(dd, 0.3) ** 2 for dd, _ in near]); w /= w.sum()
    h = 0
    for wi, (dd, p) in zip(w, near):
        ref = basisT(t - p[4] * 60000) @ RM[p[2]]
        h = h + wi * (p[5] + p[3] * (ref - refs[p[2]][2]))
    return h
def ext(t, h):
    out = []
    for i in range(1, len(h) - 1):
        if (h[i] > h[i - 1] and h[i] >= h[i + 1]) or (h[i] < h[i - 1] and h[i] <= h[i + 1]): out.append((t[i], h[i], 'H' if h[i] > h[i - 1] else 'L'))
    return out
errs, self_errs, terr, herr, worst = [], [], [], [], []
for k, v in G2.items():
    if not isinstance(v, dict) or v.get('ref') not in RI: continue
    days = [d for d, x in v.items() if isinstance(x, dict) and 'h' in x]
    if not days: continue   # 모든 격자의 첫날 + 검증용 격자는 이틀 더
    la, lo = map(float, k.split(','))
    for d in days:
        r = v[d]; t0 = F.ms(r['t0']); t = np.array([t0 + i * 600000 for i in range(len(r['h']))]); obs = np.array(r['h'])
        pr = point_h(la, lo, t); ps = point_h(la, lo, t, True)
        e = pr - obs; errs.append(np.sqrt((e ** 2).mean())); self_errs.append(np.sqrt(((ps - obs) ** 2).mean()))
        eo, ep = ext(t, obs), ext(t, pr)
        for (to, ho, ty) in eo:
            c = [x for x in ep if x[2] == ty and abs(x[0] - to) < 3 * 3600000]
            if c: x = min(c, key=lambda x: abs(x[0] - to)); terr.append(abs(x[0] - to) / 60000); herr.append(abs(x[1] - ho))
        worst.append((errs[-1], k, v['ref'], d, float(obs.max() - obs.min())))
errs = np.array(errs); terr = np.array(terr); herr = np.array(herr)
print(f'검증 {len(errs)}일치: 물 높이 오차(RMS) 가운데 {np.median(errs):.1f}cm · 90% {np.percentile(errs, 90):.1f}cm · 가장 큰 {errs.max():.1f}cm'
      f' (그 격자 하나만 쓰면 가운데 {np.median(self_errs):.1f}cm)')
print(f'  만조·간조 시각 차 가운데 {np.median(terr):.0f}분 · 90% {np.percentile(terr, 90):.0f}분 · 높이 차 가운데 {np.median(herr):.1f}cm · 90% {np.percentile(herr, 90):.1f}cm')
for w in sorted(worst, reverse=True)[:6]: print('  큰 오차', f'{w[0]:.1f}cm', w[1], w[2], w[3], f'조차 {w[4]:.0f}cm')
# ---------- 조류
FE = json.load(open('fldebb_all.json')); FE.update(json.load(open(f'{S}/fldebb.json')))
ci = [i for i, d in enumerate(DEFS) if d[0] in CNAMES]
fit_crnt.CONS = [F.CONS[i] for i in ci]
cur = []; skip = []
for code, rec in sorted(FE.items(), key=lambda x: -x[1]['lat']):
    ev = [e for e in rec['ev'] if e[0] >= '2026']
    if code == '17LTC06':   # 2026 표가 가덕도남측과 똑같이 잘못 올라와 있어 2025 표를 쓴다
        ev = [e for e in rec['ev'] if e[0] < '2026']
    if len(ev) < 400: skip.append(f'{code} {rec["name"]} {len(ev)}'); continue
    th, cu, cv = cfit(ev)
    sp = sorted(e[2] for e in ev if e[2] > 0); mx = sp[int(len(sp) * 0.95)]
    cur.append([rec['name'], rec['lat'], rec['lon'], round(math.degrees(th) % 360, 2), round(mx), [round(float(x), 2) for x in cu], [round(float(x), 2) for x in cv]])
if skip: print('조류 자료 모자라 뺀 곳', skip)
out = {'v': 2, 'src': '국립해양조사원 TideBED 예측조위·조류예보(최강창낙조·전류)를 바탕으로 계산',
       'defs': DEFS, 'refs': refs, 'tide': tide, 'cur': {'ci': ci, 'p': cur}}
js = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open('spots_all.json', 'w').write(js)
import gzip
print('크기', len(js) // 1024, 'KB (압축', len(gzip.compress(js.encode())) // 1024, 'KB) · 분조', len(DEFS), '기준', len(refs), '격자', len(tide), '조류', len(cur))
