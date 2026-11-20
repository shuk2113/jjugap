"""쭈갑 물때: 지금 날씨 받기 (GitHub Actions에서 매시간 · 한국 시각 새벽 4시~밤 9시)

선상 모드의 '길잡이'가 10분마다 읽는 data/now.json 을 만든다.
- 기상청 초단기실황(getUltraSrtNcst): 매시 정각 분석값 — 지금 풍속·풍향·강수
- 기상청 초단기예보(getUltraSrtFcst): 매시 30분 발표 — 앞으로 6시간 1시간 간격 풍속·풍향·하늘·강수
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
SITE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'site'
SKY = {'1': 1, '3': 3, '4': 4}


def num(v):
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


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


def ncst(g, base):
    d, t = base
    for _ in range(2):   # 막 나온 직후 비어 있으면 한 시간 전
        code, msg, items = unwrap(get_json(NCST_URL, {'pageNo': 1, 'numOfRows': 60, 'dataType': 'JSON', 'base_date': d, 'base_time': t, 'nx': g[0], 'ny': g[1]}))
        if code in ('00', '0') and items:
            c = {it['category']: it.get('obsrValue') for it in items}
            return [d + t[:2], num(c.get('WSD')), num(c.get('VEC')), int(num(c.get('PTY')) or 0), (num(c.get('RN1')) or 0), num(c.get('T1H'))]
        b = datetime.strptime(d + t, '%Y%m%d%H%M') - timedelta(hours=1)
        d, t = b.strftime('%Y%m%d'), b.strftime('%H00')
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


def main():
    now = datetime.now(KST)
    nb = now - timedelta(minutes=42)            # 실황: 매시 40분쯤부터
    fb = now - timedelta(minutes=47)            # 초단기예보: 매시 45분쯤부터
    if fb.minute < 30:
        fb -= timedelta(hours=1)
    nbase, fbase = (nb.strftime('%Y%m%d'), nb.strftime('%H00')), (fb.strftime('%Y%m%d'), fb.strftime('%H30'))
    gs = grids()
    log(f'격자 {len(gs)}곳 · 실황 {nbase} · 초단기예보 {fbase}')
    out = {'generated': now.isoformat(timespec='minutes'), 'src': '기상청 초단기실황·초단기예보', 'g': {}}
    ok_n = ok_f = 0

    def one(g):
        try:
            o = ncst(g, nbase)
        except RuntimeError as e:
            o = None; log(f'  {g} 실황 오류 {str(e)[:120]}')
        try:
            f = ufcst(g, fbase)
        except RuntimeError as e:
            f = None; log(f'  {g} 초단기예보 오류 {str(e)[:120]}')
        return g, o, f
    with ThreadPoolExecutor(4) as ex:
        for g, o, f in ex.map(one, gs):
            if not o and not f:
                continue
            e = {}
            if o:
                e['o'] = o; ok_n += 1
            if f:
                e['f'] = f; ok_f += 1
            out['g'][f'{g[0]},{g[1]}'] = e
    note(f'지금 날씨: 실황 {ok_n}/{len(gs)}곳, 초단기예보 {ok_f}/{len(gs)}곳')
    if not out['g']:
        sys.exit('하나도 받지 못했어요')
    p = os.path.join(SITE, 'data', 'now.json')
    with open(p, 'w') as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main()
