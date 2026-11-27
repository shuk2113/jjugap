"""쭈갑 물때: 지금 날씨 받기 (GitHub Actions에서 매시간)

선상 모드의 '길잡이'와 비 기록이 읽는 data/now.json 을 만든다.
- 기상청 초단기실황(getUltraSrtNcst): 매시 정각 분석값 — 지금 풍속·풍향·강수형태·1시간 강수량  (하루 24번)
- 기상청 초단기예보(getUltraSrtFcst): 매시 30분 발표 — 앞으로 6시간 풍속·풍향·하늘·강수형태  (한국 시각 4~21시만)
- 비 기록: 시간마다 1시간 강수량을 격자별로 쌓아 최근 7일 (rr: 비 온 시간만 · rh: 받은 시간 목록 · rd: 날짜별 합계 mm · rdh: 날짜별 받은 시간 수)
  · 바다 격자에서 '자료 없음'(-998.9)이면 같은 시각 가장 가까운(40km 안) 값 있는 격자로 메움
  · 자동 실행이 늦거나 빠져 빈 시간은 다음 실행 때 지난 6시간 안에서 다시 받아 메움
- 기상특보 현황(기상청_기상특보 조회서비스 getPwnStatus): 지금 발효 중인 특보(t6)와 예비특보(t7) 글을 그대로 받아 wrn 에 넣는다
  · 앱이 출항지의 특보 구역(예: 전북북부앞바다)을 글에서 찾아 '출항 어려움' 신호와 배 위 알림 띠에 쓴다
  · 활용신청 전이거나 서버 오류면 지난 값(6시간 안)을 두고 지나감 — 다른 자료는 그대로 만든다
격자는 단기예보와 같은 동네예보 격자. 앱이 이미 쓰는 예보 지점의 격자(data/wx/*.json 과 weather.json 의 grid)만 받는다.
인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.
출처: 기상청 (공공데이터포털 · 공공누리 1유형)
"""
import glob, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect import KST, get_json, unwrap, log, note   # 같은 호출·키 처리 (키는 로그에 남지 않음)

NCST_URL = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst'
UFCST_URL = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst'
WRN_URL = 'https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus'
SITE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'site'
SKY = {'1': 1, '3': 3, '4': 4}
KEEP_DAYS = 7
BACKFILL_H = 6


def num(v):
    try:
        x = round(float(v), 1)
    except (TypeError, ValueError):
        return None
    return None if x <= -900 else x   # -998.9 같은 '자료 없음' 값


def grids():
    gs = set()
    try:
        w = json.load(open(os.path.join(SITE, 'data', 'weather.json')))
        for st in (w.get('stations') or {}).values():
            if st.get('grid'):
                gs.add(tuple(st['grid']))
    except Exception as e:
        note(f'weather.json 못 읽음: {e}', 'warning')
    for f in glob.glob(os.path.join(SITE, 'data', 'wx', '*.json')):
        try:
            g = json.load(open(f)).get('grid')
            if g:
                gs.add(tuple(g))
        except Exception:
            pass
    return sorted(gs)


def ncst(g, hh):
    """그 시각(YYYYMMDDHH) 실황 → [시각, 풍속, 풍향, 강수형태, 1시간 강수량, 기온] 또는 None"""
    code, msg, items = unwrap(get_json(NCST_URL, {'pageNo': 1, 'numOfRows': 60, 'dataType': 'JSON', 'base_date': hh[:8], 'base_time': hh[8:] + '00', 'nx': g[0], 'ny': g[1]}))
    if code in ('00', '0') and items:
        c = {it['category']: it.get('obsrValue') for it in items}
        pty = num(c.get('PTY'))
        return [hh, num(c.get('WSD')), num(c.get('VEC')), None if pty is None else int(pty), num(c.get('RN1')), num(c.get('T1H'))]
    return None


def ufcst(g, base):
    d, t = base
    for _ in range(2):
        code, msg, items = unwrap(get_json(UFCST_URL, {'pageNo': 1, 'numOfRows': 100, 'dataType': 'JSON', 'base_date': d, 'base_time': t, 'nx': g[0], 'ny': g[1]}))
        if code in ('00', '0') and items:
            by = {}
            for it in items:
                by.setdefault(it['fcstDate'] + it['fcstTime'][:2], {})[it['category']] = it.get('fcstValue')
            return {k: [num(c.get('WSD')), num(c.get('VEC')), SKY.get(str(c.get('SKY', '')), None), int(num(c.get('PTY')) or 0)] for k, c in sorted(by.items())}
        b = datetime.strptime(d + t, '%Y%m%d%H%M') - timedelta(hours=1)
        d, t = b.strftime('%Y%m%d'), b.strftime('%H30')
    return None


def fill_near(vals, gs):
    """같은 시각 '자료 없음' 격자는 가장 가까운(40km 안) 값 있는 격자로 (격자 1칸 = 5km)"""
    ok = [g for g in gs if vals.get(g) is not None]
    out = dict(vals)
    for g in gs:
        if out.get(g) is None and ok:
            n = min(ok, key=lambda q: (q[0] - g[0]) ** 2 + (q[1] - g[1]) ** 2)
            if (n[0] - g[0]) ** 2 + (n[1] - g[1]) ** 2 <= 8 ** 2:
                out[g] = vals[n]
    return out


def warnings(prev, now):
    """기상특보 현황: {'at': 받은 시각, 'tm': 발표시각, 'on': 발효 중 글(t6), 'pre': 예비특보 글(t7)}. 못 받으면 지난 값(6시간 안) 또는 None"""
    try:
        raw = get_json(WRN_URL, {'pageNo': 1, 'numOfRows': 10, 'dataType': 'JSON'}, tries=2, timeout=15)
        c, msg, items = unwrap(raw)
        if c not in ('00', '') or not items:
            raise RuntimeError(f'결과코드 {c} {msg}')
        it = sorted(items, key=lambda x: str(x.get('tmFc', '')))[-1]
        clean = lambda t: '\n'.join(l.rstrip() for l in str(t or '').replace('\r', '').split('\n')).strip()[:3000]
        w = {'at': now.isoformat(timespec='minutes'), 'tm': str(it.get('tmFc', '')), 'on': clean(it.get('t6')), 'pre': clean(it.get('t7'))}
        note(f'기상특보: {w["tm"]} 발표 · 발효 {len(w["on"])}자 · 예비 {len(w["pre"])}자')
        log('기상특보 항목:', sorted(it.keys()))   # 항목 이름 확인용
        return w
    except Exception as e:
        note(f'기상특보 못 받음: {str(e)[-160:]} (활용신청 전이면 정상)', 'warning')
        pw = prev.get('wrn')
        try:
            if pw and now - datetime.fromisoformat(pw['at']) < timedelta(hours=6):
                return pw
        except Exception:
            pass
        return None


def main():
    now = datetime.now(KST)
    cur = (now - timedelta(minutes=42)).strftime('%Y%m%d%H')          # 실황: 매시 40분쯤부터
    fb = now - timedelta(minutes=47)                                   # 초단기예보: 매시 45분쯤부터
    if fb.minute < 30:
        fb -= timedelta(hours=1)
    fbase = (fb.strftime('%Y%m%d'), fb.strftime('%H30'))
    do_fc = 4 <= now.hour <= 21
    gs = grids()
    p = os.path.join(SITE, 'data', 'now.json')
    try:
        prev = json.load(open(p))
    except Exception:
        prev = {}
    keep = (now - timedelta(days=KEEP_DAYS)).strftime('%Y%m%d%H')
    rh = sorted(h for h in set(prev.get('rh') or []) if h >= keep)
    rr = {gk: {h: v for h, v in hs.items() if h >= keep} for gk, hs in (prev.get('rr') or {}).items()}
    # 바람 기록 (센 바람 뒤 남는 흙탕 셈용 · 사용자 2026-11-28): 3시간 칸마다 가장 센 실황 바람 [풍속×10, 풍향] · 최근 KEEP_DAYS일
    blk = lambda h: h[:8] + '%02d' % (int(h[8:]) // 3 * 3)
    pw = prev.get('rw') or {}
    rw = {}
    if pw.get('b0'):
        b0 = datetime.strptime(pw['b0'], '%Y%m%d%H')
        for gk, arr in (pw.get('g') or {}).items():
            for i, v in enumerate(arr):
                b = (b0 + timedelta(hours=3 * i)).strftime('%Y%m%d%H')
                if v and b >= keep[:8] + '00':
                    rw.setdefault(gk, {})[b] = v
    want = [(datetime.strptime(cur, '%Y%m%d%H') - timedelta(hours=i)).strftime('%Y%m%d%H') for i in range(BACKFILL_H, -1, -1)]
    todo = [h for h in want if h == cur or h not in rh]
    log(f'격자 {len(gs)}곳 · 실황 {todo} · 초단기예보 {fbase if do_fc else "밤이라 안 받음"}')
    latest = {}
    for hh in todo:
        def one(g):
            try:
                return g, ncst(g, hh)
            except RuntimeError as e:
                log(f'  {g} {hh} 실황 오류 {str(e)[:100]}')
                return g, None
        with ThreadPoolExecutor(4) as ex:
            res = dict(ex.map(one, gs))
        got = sum(1 for v in res.values() if v)
        if got < len(gs) * 0.5:
            log(f'  {hh}: {got}/{len(gs)}곳만 받아 비 기록에 안 씀')
            continue
        rain = fill_near({g: (None if not v or v[4] is None else v[4]) for g, v in res.items()}, gs)
        pty = fill_near({g: (None if not v or v[3] is None else v[3]) for g, v in res.items()}, gs)
        for g in gs:
            mm = rain.get(g)
            if not mm and pty.get(g):
                mm = 0.1   # 강수형태는 있는데 양이 비면 흔적
            gk = f'{g[0]},{g[1]}'
            if mm and mm > 0:
                rr.setdefault(gk, {})[hh] = mm
            elif gk in rr:
                rr[gk].pop(hh, None)
        wsa = fill_near({g: (v[1] if v else None) for g, v in res.items()}, gs)
        wda = fill_near({g: (v[2] if v else None) for g, v in res.items()}, gs)
        for g in gs:
            w, d = wsa.get(g), wda.get(g)
            if w is None or w < 0 or w > 80:
                continue
            gk = f'{g[0]},{g[1]}'; b = blk(hh); old = rw.setdefault(gk, {}).get(b)
            if not old or round(w * 10) > old[0]:
                rw[gk][b] = [round(w * 10), int(d) if d is not None and 0 <= d <= 360 else -1]
        if hh not in rh:
            rh.append(hh)
        if hh == cur:
            wsd = fill_near({g: (v[1] if v else None) for g, v in res.items()}, gs)
            vec = fill_near({g: (v[2] if v else None) for g, v in res.items()}, gs)
            for g in gs:
                latest[g] = [hh, wsd.get(g), vec.get(g), pty.get(g), rain.get(g), (res.get(g) or [None] * 6)[5]]
    rh = sorted(set(rh))
    rr = {gk: dict(sorted(hs.items())) for gk, hs in rr.items() if hs}
    out = {'generated': now.isoformat(timespec='minutes'), 'src': '기상청 초단기실황·초단기예보', 'g': {}, 'rr': rr, 'rh': rh}
    days = {}
    for h in rh:
        days[h[:8]] = days.get(h[:8], 0) + 1
    out['rdh'] = days
    bs = sorted({b for hs in rw.values() for b in hs})
    if bs:
        b0 = datetime.strptime(bs[0], '%Y%m%d%H'); nb = int((datetime.strptime(bs[-1], '%Y%m%d%H') - b0).total_seconds() // 10800) + 1
        out['rw'] = {'b0': bs[0], 'g': {gk: [hs.get((b0 + timedelta(hours=3 * i)).strftime('%Y%m%d%H')) or 0 for i in range(nb)] for gk, hs in sorted(rw.items())}}
    out['rd'] = {}
    for gk, hs in rr.items():
        dd = out['rd'].setdefault(gk, {})
        for h, v in hs.items():
            dd[h[:8]] = round(dd.get(h[:8], 0) + v, 1)
    pg = prev.get('g') or {}
    fcs = {}
    if do_fc:
        def onef(g):
            try:
                return g, ufcst(g, fbase)
            except RuntimeError as e:
                log(f'  {g} 초단기예보 오류 {str(e)[:100]}')
                return g, None
        with ThreadPoolExecutor(4) as ex:
            fcs = dict(ex.map(onef, gs))
    ok_n = ok_f = 0
    for g in gs:
        gk = f'{g[0]},{g[1]}'
        e = {}
        o = latest.get(g) or (pg.get(gk) or {}).get('o')
        if o:
            e['o'] = o
            ok_n += 1 if g in latest else 0
        f = fcs.get(g) or (pg.get(gk) or {}).get('f')
        if f:
            e['f'] = f
            ok_f += 1 if fcs.get(g) else 0
        if e:
            out['g'][gk] = e
    note(f'지금 날씨: 실황 {ok_n}/{len(gs)}곳, 초단기예보 {ok_f}/{len(gs)}곳, 비 기록 {len(rh)}시간(최근 {KEEP_DAYS}일), 비 온 격자 {len(rr)}곳, 바람 기록 {len(bs)}칸(3시간)')
    wrn = warnings(prev, now)
    if wrn:
        out['wrn'] = wrn
    if not out['g']:
        sys.exit('하나도 받지 못했어요')
    with open(p, 'w') as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main()
