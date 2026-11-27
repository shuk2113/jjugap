# 셈 바로잡기용: 고른 맑은 날들의 시각별 위성 투명도 지도(2km 칸, 시각마다 칸 가운데 값)를 만들어
# 실행 기록에만 압축해 남긴다 (저장소·앱 칸에는 남기지 않음 · 받은 뒤 기록은 지움)
#  자료: 국립해양조사원 국가해양위성센터 OPeNDAP (robots.txt: User-agent * Allow /) · GOCI-II L2 Zsd
import os, sys, json, time, base64, gzip
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sat_daily import dods, slots, G, STEP

R0, R1, C0, C1 = 2690, 3860, 3190, 4260   # 2026-11 확인한 서해 상자
T0 = time.time()
days = [d.strip() for d in os.environ['DAYS'].split(',') if d.strip()]
nav = None
for day in days:
    S = slots(day)
    if not S:
        print('ARCHX', day, 'noslots', flush=True); continue
    if nav is None:
        nv = None
        for _, f in S[len(S) // 2:] + S[:len(S) // 2]:   # 한 파일이 안 되면 다른 시각 파일로 (위치 격자는 같음)
            nv = dods(f, [('/navigation_data/latitude', R0, R1, C0, C1, STEP), ('/navigation_data/longitude', R0, R1, C0, C1, STEP)])
            if nv: break
        if not nv:
            print('ARCHX', day, 'nonav', flush=True); continue
        LA, LO = nv['latitude'], nv['longitude']
        ci = np.floor((G['lat1'] - LA) / G['res']).astype(int); cj = np.floor((LO - G['lon0']) / G['res']).astype(int)
        inb = (LA > -900) & (ci >= 0) & (ci < G['ny']) & (cj >= 0) & (cj < G['nx'])
        cell = np.where(inb, ci * G['nx'] + cj, -1); nav = 1
    NC = G['ny'] * G['nx']; rows = []
    for hm, f in S:
        if hm >= '16:00':   # 해가 낮아 산출물 없음
            continue
        if os.environ.get('HMS') and hm[:2] not in os.environ['HMS'].split(','):   # 고른 시(時)만 (빨리 모으기)
            continue
        w = dods(f, [('/geophysical_data/Zsd', R0, R1, C0, C1, STEP), ('/geophysical_data/flag', R0, R1, C0, C1, STEP)])
        if not w or 'Zsd' not in w:
            continue
        z, fl = w['Zsd'], w['flag'].astype(np.uint8)
        ok = inb & (z > 0) & (z < 100) & ((fl & 0x47) == 0)
        zc = np.zeros(NC, np.uint8)
        if ok.sum():
            V, C = z[ok].astype(np.float32), cell[ok]; o = np.lexsort((V, C)); V, C = V[o], C[o]
            u, st, cnt = np.unique(C, return_index=True, return_counts=True); keep = cnt >= 3
            zc[u[keep]] = np.clip(np.round(V[st + cnt // 2][keep] / 0.05), 1, 254).astype(np.uint8)
        rows.append((hm, zc)); print(day, hm, int((zc > 0).sum()), f'{time.time() - T0:.0f}s', flush=True)
        time.sleep(2)
    if rows:
        blob = base64.b64encode(gzip.compress(np.stack([r[1] for r in rows]).tobytes(), 9)).decode()
        meta = json.dumps({'day': day, 'slots': [r[0] for r in rows]}, separators=(',', ':'))
        for i in range(0, len(blob), 60000):
            print(f'ARCH {day} {i // 60000} {meta if i == 0 else "-"} {blob[i:i + 60000]}', flush=True)
        print('ARCHEND', day, len(blob), flush=True)
    if time.time() - T0 > float(os.environ.get('TMAX', '19800')):
        print('time up', flush=True); break
