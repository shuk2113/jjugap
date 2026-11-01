"""출항지 목록 넓히기 → deploy/data/ports.json  [[이름, 위도, 경도, 지역, 종류(0 큰 항·1 선착장·2 작은 곳), 다른 이름(검색용)], …]
- 기존 목록(OSM 항·포구·선착장 151곳)
- 해양수산부 공개 자료(공공데이터포털 파일데이터): 국가어항·지방어항·연안항·소규모항·어촌정주어항·마을공동어항·소형선항만안내
- OSM에서 이름·항구 태그로 넓게 모은 후보
- OSM에도 공개 자료에도 없는 곳 몇 곳(가까운 길·정류장 기준 위치)
해안에서 먼 내륙 점, 물때 계산 범위 밖, 화물 부두 등은 빼고, 같은 곳은 하나로 합친다"""
import json, math, re
from collections import defaultdict
P = 'ports2/'
KX = math.cos(math.radians(36.6))
def km(a, b): return math.hypot((a[1] - b[1]) * KX, a[0] - b[0]) * 111.32

old = json.load(open(P + 'ports_old.json'))
mof = json.load(open(P + 'mof_ports.json'))
osm2 = json.load(open(P + 'ports_raw2.json'))
grid = [(t[0], t[1]) for t in json.load(open('deploy/data/spots.json'))['tide']]

# ---------- 해안선 (바다 지도 자세한 단계) : 점이 육지 안인지, 해안까지 거리
bm = json.load(open('deploy/data/basemap.json'))
o0, o1, q = bm['o'][0], bm['o'][1], bm['q']
rings = []
for poly in bm['L'][1]:
    for r in poly:
        x, y = r[0], r[1]; pts = [(o0 + x / q, o1 + y / q)]
        for i in range(2, len(r), 2): x += r[i]; y += r[i + 1]; pts.append((o0 + x / q, o1 + y / q))
        rings.append(pts)
G = 0.02
cells = defaultdict(list)
for ri, pts in enumerate(rings):
    for i in range(len(pts)):
        a, b = pts[i - 1], pts[i]
        for cx in range(int(min(a[0], b[0]) // G), int(max(a[0], b[0]) // G) + 1):
            for cy in range(int(min(a[1], b[1]) // G), int(max(a[1], b[1]) // G) + 1):
                cells[(cx, cy)].append((a, b))
def coast_km(la, lo):
    best = 9e9; cx, cy = int(lo // G), int(la // G)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for a, b in cells.get((cx + dx, cy + dy), ()):
                ax, ay, bx, by, px = a[0] * KX, a[1], b[0] * KX, b[1], lo * KX
                ddx, ddy = bx - ax, by - ay; L2 = ddx * ddx + ddy * ddy
                t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * ddx + (la - ay) * ddy) / L2))
                best = min(best, math.hypot(px - ax - t * ddx, la - ay - t * ddy))
    return best * 111.32
def on_land(la, lo):
    inside = False
    for pts in rings:
        n = len(pts)
        for i in range(n):
            (ax, ay), (bx, by) = pts[i - 1], pts[i]
            if (ay > la) != (by > la) and lo < ax + (bx - ax) * (la - ay) / (by - ay): inside = not inside
    return inside

# ---------- 후보 모으기: [이름, 위도, 경도, 출처순위, 종류, 지역후보]
# 종류: 0 큰 항(국가·지방·연안·무역항, '…항') · 1 선착장·여객터미널·마리나 · 2 작은 곳(소규모항·포구·부두·나루)
def kind_of(n, typ=''):
    if typ in ('국가어항', '연안항', '무역항', '지방어항') or re.search(r'항(\(.*\))?$', n) and not re.search(r'(소규모|정주)', typ): return 0
    if re.search(r'(선착장|여객선?터미널|마리나|도선장)', n): return 1
    return 2
BAD = re.compile(r'(사령부|국제여객|유람선|컨테이너|다목적|부두운영|화물|석탄|시멘트|유류|LNG|가스|발전|제철|자동차|해양경찰|해경|해군|조선소|크루즈|항만공사|공항|항공|잔교$|^\d+부두|부두로|부두길|휴게소|정류장)')
PORTISH = re.compile(r'(항|항구|포구|포|선착장|부두|나루|나루터|마리나|어항|여객터미널|여객선터미널|물양장|선창|도선장|부잔교)(\s*\(.*\))?$')
C = []
for n, la, lo, reg in old: C.append([n, la, lo, 1, kind_of(n), reg, reg])
rank = {'국가어항': 0, '연안항': 0, '무역항': 0, '지방어항': 0, '소형선항만': 1, '어촌정주어항': 2, '마을공동어항': 2, '소규모어항': 2, '소규모항': 2}
# 연안항·무역항 위치는 항만 구역 한가운데(바다 쪽)라서, 같은 이름의 OSM·기존 위치가 5km 안에 있으면 그쪽을 쓴다
osm_pos = [(o[0], o[1], o[2]) for o in old] + [(r[0].strip(), r[1], r[2]) for r in osm2]
for n, la, lo, typ, addr in mof:
    n = n.strip()
    if not n or BAD.search(n): continue
    if typ in ('연안항', '무역항'):
        same = [p for p in osm_pos if p[0].replace(' ', '') == n.replace(' ', '') and km((p[1], p[2]), (la, lo)) < 5]
        if same:
            p = min(same, key=lambda p: km((p[1], p[2]), (la, lo))); la, lo = p[1], p[2]
    C.append([n, la, lo, rank.get(typ, 2), kind_of(n, typ), addr, None])
for n, la, lo, tags, _t, harb in osm2:
    n = n.strip()
    if BAD.search(n) or not PORTISH.search(n): continue
    if 'highway' in tags and tags.get('highway') != 'bus_stop': continue
    if re.search(r'포$', n) and not harb: continue        # '…포' 마을 이름은 항구 표시가 있을 때만
    C.append([n, la, lo, 4 if tags.get('highway') == 'bus_stop' else 3, kind_of(n), '', None])
# OSM·공개 자료 모두에 없는 곳 (가까운 길·정류장·등대 기준)
EXTRA = [['잠진도선착장', 37.4168, 126.4150, 1, 1, '', '인천 영종구'],     # 잠진도길 남쪽 끝 (무의도 가는 옛 뱃길)
         ['오이도선착장', 37.3451, 126.6867, 1, 1, '', '시흥시']]           # 오이도 빨간등대 옆
C += EXTRA

# ---------- 거르기: 이름 길이, 물때 계산 범위, 해안 가까이
def base(n):
    n = re.sub(r'\s+', '', n)
    if '(' in n: return n   # 인천항(남항)·인천항(내항)처럼 괄호로 나뉜 곳은 따로
    sfx = r'(연안여객선터미널|연안여객터미널|여객선터미널|여객터미널|선착장|항구|어항|항|포구|부두|마리나|방파제|물양장|정류장|입구)$'
    return re.sub(sfx, '', re.sub(sfx, '', n)) or n   # '대천항선착장' → '대천'
keep = []
drop = defaultdict(int)
for c in C:
    n, la, lo = c[0], c[1], c[2]
    if len(n) < 2 or len(n) > 18: drop['길이'] += 1; continue
    if min(km((la, lo), g) for g in grid) > 10: drop['범위밖'] += 1; continue
    d = coast_km(la, lo)
    if d > 1.5 and on_land(la, lo): drop['내륙'] += 1; continue
    if d > 4: drop['먼바다'] += 1; continue
    keep.append(c)
print('후보', len(C), '남음', len(keep), dict(drop))

# ---------- 같은 곳 합치기: 같은 기본 이름이 2.5km 안 → 출처 순위가 높은 이름 하나 (나머지 이름은 검색용 다른 이름으로)
keep.sort(key=lambda c: (c[3], c[4], len(c[0])))
out = []
for c in keep:
    b = base(c[0])
    hit = next((o for o in out if base(o[0]) == b and km((o[1], o[2]), (c[1], c[2])) < 2.5), None)
    if hit:
        if c[0] not in hit[6] and c[0] != hit[0]: hit[6].append(c[0])
        if not hit[5] and c[5]: hit[5] = c[5]
        if not hit[7] and c[6]: hit[7] = c[6]
        continue
    # 정류장 이름은 근처(400m)에 이미 항구가 있으면 버린다
    if c[3] == 4 and any(km((o[1], o[2]), (c[1], c[2])) < 0.4 for o in out): continue
    out.append([c[0], c[1], c[2], c[3], c[4], c[5], [], c[6]])

# ---------- '인천항'처럼 뭉뚱그린 이름은 가까운 '인천항(내항)' 같은 갈래 이름의 다른 이름으로
for o in list(out):
    if '(' in o[0]: continue
    sib = [p for p in out if p[0].startswith(o[0] + '(') and km((p[1], p[2]), (o[1], o[2])) < 6]
    if sib:
        p = min(sib, key=lambda p: km((p[1], p[2]), (o[1], o[2])))
        p[6] += [o[0]] + o[6]; out.remove(o)
# ---------- 기본 출항지(물때 기준점)와 같은 곳은 뺀다 (검색·지도에 두 번 나오지 않게)
STATIONS = [('인천 연안부두', 37.45, 126.6), ('영흥도', 37.25, 126.47), ('대부도 방아머리', 37.29, 126.57), ('태안 안흥항', 36.67, 126.13),
            ('보령 오천항', 36.44, 126.52), ('서천 홍원항', 36.15, 126.5), ('군산외항', 35.98, 126.56), ('부안 격포항', 35.62, 126.47)]
for o in list(out):
    b = base(o[0])
    st = next((s for s in STATIONS if b in s[0].replace(' ', '') and km((s[1], s[2]), (o[1], o[2])) < 3), None)
    if st: print('기본 출항지와 같음', o[0], '→', st[0]); out.remove(o)

# ---------- 지역 이름: 기존 목록에서 가장 가까운 곳의 지역(10km 안) → 아니면 주소의 시·군
def region(o):
    if o[7]: return o[7]   # 기존 목록·직접 넣은 곳의 지역
    a = o[5] or ''
    m = re.search(r'(\S+[시군])\s', a + ' ')
    if m and not m.group(1).endswith('광역시') and '인천' not in a: return m.group(1)
    near = min(old, key=lambda r: km((r[1], r[2]), (o[1], o[2])))
    if km((near[1], near[2]), (o[1], o[2])) < 10: return near[3]
    a = o[5] or ''
    m = re.search(r'(\S+[시군])\s', a + ' ')
    if m and not m.group(1).endswith('광역시'): return m.group(1)
    if '인천' in a: return '인천'
    return near[3]
# 검색용 다른 이름 (흔히 부르는 이름)
ALIAS = {'비인항': '마량 마량포구', '안흥항(외항)': '신진도 신진항', '안흥항(내항)': '신진도', '진두항': '영흥도 진두선착장', '인천항(남항)': '인천 남항',
         '잠진도선착장': '잠진포 무의도', '거잠포 선착장': '거잠포선착장 영종도', '오이도선착장': '오이도항 오이도 빨간등대', '대천항': '보령 대천',
         '시화방조제 중간선착장': '시화 방조제 중간 오이도', '남항유어선부두': '인천 남항 유어선', '삽시도항': '삽시도', '원산도항': '원산도'}
res = []
for o in out:
    al = ' '.join(dict.fromkeys(o[6] + ([ALIAS[o[0]]] if o[0] in ALIAS else [])))
    row = [o[0], round(o[1], 5), round(o[2], 5), region(o), o[4]]
    if al: row.append(al[:60])
    res.append(row)
res.sort(key=lambda r: -r[1])
json.dump(res, open('deploy/data/ports.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('출항지', len(res), len(json.dumps(res, ensure_ascii=False).encode()) // 1024, 'KB', '종류', {k: sum(1 for r in res if r[4] == k) for k in (0, 1, 2)})
for qq in ('남항', '시화', '잠진', '거잠', '영목', '대천', '안흥', '홍원', '비인', '모항', '삽시', '오이도', '학암', '만리포', '몽산', '진두', '원산', '격포', '궁평', '무의', '오천', '전곡', '탄도', '방아머리', '마검포', '백사장', '남당', '장고', '무창포'):
    print(qq, [f'{r[0]}·{r[3]}·{r[4]}' for r in res if qq in r[0] or (len(r) > 5 and qq in r[5])][:5])
