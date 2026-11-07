"""남쪽(35.3도 아래) 항·포구 지역 이름을 OSM 행정 경계 결과(pts_region.json, pts.json 순서)로 바꾼다"""
import json, re, math
KX = math.cos(math.radians(36.6))
d = json.load(open('ports_new.json'))
pts = json.load(open('/home/claude/jjugap/.github/probe/pts.json')); R = json.load(open('pts_region.json'))
def reg(r):
    a4, a6, a7 = r
    if not a6: return None
    v = (a6 if a6.endswith('군') else f'{a4[:2]} {a6}') if (a4.endswith('광역시') or a4.endswith('특별시')) else a6
    m = re.match(r'^(경남|경북|전남|전북|충남|충북|강원|경기|제주|전라남도|경상남도) (\S+[시군구])$', v)
    return m.group(2) if m else v
ch = miss = 0
for row in d:
    if row[1] >= 35.3: continue
    best = min(zip(pts, R), key=lambda x: math.hypot((x[0][1] - row[2]) * KX, x[0][0] - row[1]))
    if math.hypot((best[0][1] - row[2]) * KX, best[0][0] - row[1]) * 111 < 1: nr = reg(best[1])
    else: nr = None; miss += 1
    if nr and row[3] != nr: row[3] = nr; ch += 1
json.dump(d, open('ports_new.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('지역 바꿈', ch, '못 찾음', miss, len(d))
