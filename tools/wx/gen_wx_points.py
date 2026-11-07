"""바다 날씨 예보 지점 만들기 → wx_points.json (수집 프로그램이 읽는다)
- 항·포구(서해+남해+제주)를 R km 안으로 묶어, 묶음마다 예보 지점 하나 (예전 기본 출항지 8곳은 그대로 따로 있음)
- 지점마다: 이름(가운데 항·포구), 위치, 예보 받을 앞바다 점 2곳(바다 격자 가운데 항·포구에서 2~12km), 수온 관측소(가까운 순 3곳), 중기 해상예보 해역"""
import json, math, sys
KX = math.cos(math.radians(36.6))
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32
R = float(sys.argv[1]) if len(sys.argv) > 1 else 14
ports = json.load(open('../ports_new.json'))
grid = json.load(open('../grid_all.json'))
obs = json.load(open('../obs_list.json'))
OBS = {k: (float(v['lat']), float(v['lon']), v['name'], v['wn'] > 0) for k, v in obs.items() if v.get('lat')}
OBS['DT_0025'] = (36.406, 126.486, '보령', True)   # 오늘 응답이 없어 목록에 빠진 곳
BASE = {'incheon': (37.45, 126.6), 'bangameori': (37.29, 126.57), 'yeongheung': (37.25, 126.47), 'anheung': (36.67, 126.13),
        'ocheon': (36.44, 126.52), 'hongwon': (36.15, 126.5), 'gunsan': (35.98, 126.56), 'gyeokpo': (35.62, 126.47)}
def mid_of(la, lo):
    if la < 34.05 and not (la > 33.9 and lo > 126.9): return '12B10500'          # 제주도 (추자도 포함)
    if la < 34.85 and lo >= 127.6: return '12B20000'                            # 남해동부 (경남·부산, 광양만 동쪽)
    if la < 35.2 and lo >= 127.6: return '12B20000'
    if la < 34.62 and lo > 126.15: return '12B10000'                            # 남해서부 (해남·완도·고흥·여수)
    if la < 34.85 and lo > 127.0: return '12B10000'
    return '12A30000' if la < 36.05 else '12A20000'                             # 서해남부 · 서해중부
# 큰 항(종류 0)부터, 이미 지점(또는 기본 출항지)에서 R km 안이면 넘어간다
order = sorted(ports, key=lambda r: (r[4], -r[1]))
pts = []
for r in order:
    p = (r[1], r[2])
    if any(km(p, b) <= R for b in BASE.values()) or any(km(p, (q['lat'], q['lon'])) <= R for q in pts): continue
    pts.append({'name': r[0], 'lat': r[1], 'lon': r[2]})
out = {}
for i, q in enumerate(sorted(pts, key=lambda q: (-q['lat'], q['lon']))):
    p = (q['lat'], q['lon'])
    sea = sorted((g for g in grid if 2 <= km(p, g) <= 12), key=lambda g: km(p, g))[:2] or sorted(grid, key=lambda g: km(p, g))[:2]
    ob = sorted((k for k, v in OBS.items() if km(p, v[:2]) <= 70), key=lambda k: (not OBS[k][3], km(p, OBS[k][:2])))[:3]
    if not any(OBS[k][3] for k in ob):   # 70km 안에 수온 나오는 곳이 없으면 120km 안의 가장 가까운 곳을 더한다
        far = sorted((k for k, v in OBS.items() if v[3] and km(p, v[:2]) <= 120), key=lambda k: km(p, OBS[k][:2]))[:1]
        ob = (ob + far)[:4]
    out[f'w{i:03d}'] = {'name': q['name'], 'pos': [round(q['lat'], 4), round(q['lon'], 4)], 'sea': [[round(g[0], 3), round(g[1], 3)] for g in sea], 'obs': ob, 'mid': mid_of(*p)}
json.dump(out, open('wx_points.json', 'w'), ensure_ascii=False, indent=0)
json.dump({k: [v[0], v[1]] for k, v in OBS.items()}, open('obs_pos.json', 'w'))
import collections
print('R', R, '지점', len(out), '해역', collections.Counter(v['mid'] for v in out.values()), '관측소 없음', [k for k, v in out.items() if not v['obs']])
