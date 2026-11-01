"""해양수산부 어항·항포구 파일들 → 하나의 후보 목록 [이름, 위도, 경도, 종류, 주소]"""
import csv, io, re, json, sys
D = sys.argv[1]
def rows(f):
    raw = open(f'{D}/{f}', 'rb').read()
    for enc in ('utf-8-sig', 'cp949'):
        try: return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError: pass
def ll(a, b):
    a, b = float(a), float(b)
    return (b, a) if a > 90 else (a, b)   # 위도·경도 칸이 뒤바뀐 파일이 있다
def dms(s):
    m = re.match(r'(\d+)-(\d+)-([\d.]+)([NSEW])', s.strip())
    if not m: return None
    v = int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600
    return -v if m[4] in 'SW' else v
out = []
for r in rows('15148635.csv'):
    la, lo = ll(r['소규모항위도'], r['소규모항경도']); out.append([r['소규모항명칭'], la, lo, r['소규모항종류'] or '소규모항', r.get('소규모항주소', '')])
for r in rows('15144585.csv'):
    la, lo = ll(r['어촌정주어항위도'], r['어촌정주어항경도']); out.append([r['어촌정주어항명칭'], la, lo, r['어촌정주어항종류'] or '마을공동어항', ''])
for r in rows('15147417.csv'):
    try: la, lo = ll(r['어촌정주어항위도'], r['어촌정주어항경도'])
    except ValueError: continue
    out.append([r['어촌정주어항명칭'], la, lo, '어촌정주어항', r.get('어촌정주어항주소', '')])
for r in rows('15147449.csv'):
    m = re.search(r'POINT \(([\d.]+) ([\d.]+)\)', r['공간정보'])
    if m: out.append([r['어항명'], float(m[2]), float(m[1]), '지방어항', r['항구지번주소']])
for r in rows('15148613.csv'):
    la, lo = dms(r['소형선항만도분초위도']), dms(r['소형선항만도분초경도'])
    if la is None or lo is None: continue
    kind = '국가어항' if '국가어항' in r['소개설명'] else '연안항' if '연안항' in r['소개설명'] else '무역항' if '무역항' in r['소개설명'] else '지방어항' if '지방어항' in r['소개설명'] else '소형선항만'
    out.append([r['항만명'], la, lo, kind, r['행정구역명']])
box = [o for o in out if 35.1 <= o[1] <= 38.1 and 125.3 <= o[2] <= 127.4]
json.dump(box, open(f'{D}/mof_ports.json', 'w'), ensure_ascii=False)
print('all', len(out), 'box', len(box))
from collections import Counter; print(Counter(o[3] for o in box))
for q in ('남항', '잠진', '영목', '대천', '안흥', '신진', '홍원', '구매', '모항', '마량', '비인', '삽시', '오이도', '을왕', '학암', '만리포', '몽산', '야미', '진두', '영흥', '원산', '격포', '궁평', '무의', '오천', '전곡', '탄도', '방아머리', '마검포', '백사장', '남당', '장고', '무창포', '송공', '영종', '거잠', '삼목', '예단포', '선재', '자월', '덕적', '이작', '승봉'):
    print(q, [f'{o[0]}({o[3]})' for o in box if q in o[0] or q in (o[4] or '')][:6])
