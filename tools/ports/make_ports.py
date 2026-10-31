"""출항지 검색 목록 → deploy/data/ports.json  [[이름, 위도, 경도, 지역], …]
OSM(© OpenStreetMap 기여자) 해안 1.5km 안의 항·포구·선착장·부두·마리나 + OSM에 없는 자주 쓰는 출항지 몇 곳(가까운 OSM 지형지물로 위치를 잡음)"""
import json, math, re
KX = math.cos(math.radians(36.6))
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32
R = json.load(open('osm/ports_raw.json')); spots = json.load(open('deploy/data/spots.json'))
grid = [(t[0], t[1]) for t in spots['tide']]
# OSM에 없는 곳: 근처 지형지물 기준 (백사장 어시장·백사장1길 36.585,126.318 / 시화나래 휴게소 37.311,126.606)
EXTRA = [['백사장항', 36.5857, 126.3160, 'harbour'], ['시화방조제 중간선착장', 37.3120, 126.6052, 'harbour']]
cands = [[n, la, lo, k] for n, la, lo, k, d in R['ports']] + EXTRA
pri = {'harbour': 0, 'name': 1, 'bus': 3}
cands.sort(key=lambda c: pri.get(c[3], 2))
def base(n): return re.sub(r'\s+|\(.*?\)|여객터미널|선착장$|정류장', '', n)
out = []
for n, la, lo, k in cands:
    n = n.strip()
    if len(n) < 2 or len(n) > 16: continue
    if any(base(o[0]) == base(n) and km((o[1], o[2]), (la, lo)) < 1.5 for o in out): continue
    if k == 'bus' and any(km((o[1], o[2]), (la, lo)) < 0.3 for o in out): continue
    if min(km((la, lo), g) for g in grid) > 10: continue   # 이 자리 물때 계산 범위 밖
    out.append([n, la, lo, k])
# 지역 이름: 가장 가까운 시·군 (없으면 읍·면)
pl = [p for p in R['places'] if p[3] in ('city', 'county')]
def region(la, lo):
    best = min(pl, key=lambda p: km((p[1], p[2]), (la, lo)))
    nm = best[0]
    return re.sub(r'광역시$|특별시$', '', nm)
res = [[n, round(la, 5), round(lo, 5), region(la, lo)] for n, la, lo, k in out]
res.sort(key=lambda r: -r[1])
json.dump(res, open('deploy/data/ports.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(res), len(json.dumps(res, ensure_ascii=False)) // 1024, 'KB')
for q in ('남항', '대천', '백사장', '시화', '방아머리', '오천', '홍원', '격포', '안흥', '마검포', '영목', '궁평', '전곡', '진두', '삽시'):
    print(q, [r for r in res if q in r[0]][:4])
print(sorted({r[3] for r in res}))
