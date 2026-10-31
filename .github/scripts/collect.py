"""쭈갑 물때: 바다 날씨 자료 모으기 (GitHub Actions에서 하루 8번 실행)

- 기상청 단기예보: 출항지 앞바다 격자의 풍속·풍향·파고·하늘·강수 (앞으로 약 3일, 1시간 간격)
- 국립해양조사원 조위관측소 최신 관측: 실제 수온(지금, 24시간 전), 바람

결과는 앱이 읽는 data/weather.json 한 파일로 저장한다.
인증키는 GitHub 비밀 저장소(DATA_GO_KR_KEY)에서만 읽고, 로그나 파일에는 남기지 않는다.
"""
import json, math, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
# 붙여넣을 때 섞여 들어간 띄어쓰기·줄바꿈은 모두 지운다
KEY = re.sub(r'\s+', '', os.environ.get('DATA_GO_KR_KEY', ''))
OUT = next((a for a in sys.argv[1:] if not a.startswith('--')), 'weather.json')

# 출항지별: 예보 받을 앞바다 지점(앞쪽부터 시도, 파고가 나오는 첫 격자를 씀) · 수온 관측소
STATIONS = {
    'incheon':    {'sea': [(37.40, 126.45), (37.35, 126.35)], 'obs': 'DT_0001'},   # 인천
    'bangameori': {'sea': [(37.30, 126.48), (37.22, 126.36)], 'obs': 'DT_0008'},   # 안산
    'yeongheung': {'sea': [(37.22, 126.36), (37.20, 126.30)], 'obs': 'DT_0043'},   # 영흥도
    'anheung':    {'sea': [(36.67, 126.05), (36.62, 126.00)], 'obs': 'DT_0067'},   # 안흥
    'ocheon':     {'sea': [(36.40, 126.40), (36.35, 126.35)], 'obs': 'DT_0025'},   # 보령
    'hongwon':    {'sea': [(36.12, 126.42), (36.10, 126.35)], 'obs': 'DT_0051'},   # 서천마량
    'gunsan':     {'sea': [(35.95, 126.42), (35.90, 126.35)], 'obs': 'DT_0018'},   # 군산
    'gyeokpo':    {'sea': [(35.62, 126.38), (35.60, 126.30)], 'obs': 'DT_0068'},   # 위도
}
KMA_URL = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'
OBS_URL = 'https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService'


def log(*a):
    print(*a, flush=True)


def note(msg, level='notice'):
    print(f'::{level}::{msg}', flush=True)


def get_json(url, params, tries=2, timeout=12):
    """공공데이터포털 호출. 키는 주소에 넣되 오류 메시지에는 키를 빼고 보여준다."""
    q = urllib.parse.urlencode(params, safe='')
    full = f'{url}?serviceKey={KEY}&{q}'
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers={'Accept': 'application/json'}), timeout=timeout) as r:
                body = r.read().decode('utf-8', 'replace')
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                last = f'JSON 아님: {body[:200]}'
        except Exception as e:  # 네트워크·서버 오류는 잠시 뒤 다시
            last = f'{type(e).__name__}: {str(e)[:200]}'
        time.sleep(2)
    raise RuntimeError(f'{url.split("/")[-1]} {q} 실패 → {last}')


def unwrap(d):
    """응답이 response 로 감싸여 있거나 아닐 수 있어서 둘 다 받는다."""
    d = d.get('response', d)
    head = d.get('header', {})
    code = str(head.get('resultCode', ''))
    items = (((d.get('body') or {}).get('items') or {}) or {})
    items = items.get('item', []) if isinstance(items, dict) else items
    if isinstance(items, dict):
        items = [items]
    return code, head.get('resultMsg', ''), items or []


# 위경도 → 기상청 동네예보 격자 (기상청 공개 변환식, 람베르트 정각원추도법)
def to_grid(lat, lon):
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    s1, s2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5))
    sf = math.tan(math.pi * 0.25 + s1 * 0.5) ** sn * math.cos(s1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re * sf / math.tan(math.pi * 0.25 + lat * D * 0.5) ** sn
    th = lon * D - olon
    th = (th + 2 * math.pi) % (2 * math.pi)
    if th > math.pi:
        th -= 2 * math.pi
    th *= sn
    return int(ra * math.sin(th) + XO + 0.5), int(ro - ra * math.cos(th) + YO + 0.5)


def kma_base(now):
    """지금 받을 수 있는 가장 최근 발표 시각 (02·05·…·23시 발표, 10분 뒤부터 제공)"""
    c = now - timedelta(minutes=12)
    hours = [h for h in (2, 5, 8, 11, 14, 17, 20, 23) if h <= c.hour]
    if hours:
        return c.strftime('%Y%m%d'), f'{max(hours):02d}00'
    return (c - timedelta(days=1)).strftime('%Y%m%d'), '2300'


def prev_base(d, t):
    dt = datetime.strptime(d + t, '%Y%m%d%H%M') - timedelta(hours=3)
    return dt.strftime('%Y%m%d'), dt.strftime('%H%M')


SKY = {'1': 1, '3': 3, '4': 4}


def fetch_fcst(nx, ny, base):
    d, t = base
    for _ in range(3):   # 막 발표된 직후 자료가 없으면 한 단계 전 발표로
        code, msg, items = unwrap(get_json(KMA_URL, {'pageNo': 1, 'numOfRows': 1500, 'dataType': 'JSON', 'base_date': d, 'base_time': t, 'nx': nx, 'ny': ny}))
        if code in ('00', '0') and items:
            return (d, t), items
        log(f'  기상청 {d} {t} ({nx},{ny}) 자료 없음: {code} {msg}')
        d, t = prev_base(d, t)
    return None, []


def pack_fcst(items):
    """시각별 [풍속 m/s, 풍향 도, 파고 m, 하늘, 강수형태, 강수확률 %, 기온 ℃]"""
    by = {}
    for it in items:
        k = it['fcstDate'] + it['fcstTime'][:2]
        by.setdefault(k, {})[it['category']] = it['fcstValue']
    out = {}
    for k, c in sorted(by.items()):
        def num(cat):
            try:
                return round(float(c[cat]), 1)
            except (KeyError, ValueError, TypeError):
                return None
        wav = num('WAV')
        if wav is not None and wav < 0:
            wav = None
        out[k] = [num('WSD'), num('VEC'), wav, SKY.get(str(c.get('SKY', '')), None), int(num('PTY') or 0), num('POP'), num('TMP')]
    return out


def fetch_obs(code, now):
    """오늘·어제 매시 관측에서 가장 최근 수온과 24시간 전 수온"""
    rows = []
    for day in (now - timedelta(days=1), now):
        try:
            raw = get_json(OBS_URL, {'type': 'json', 'obsCode': code, 'reqDate': day.strftime('%Y%m%d'), 'min': 60, 'pageNo': 1, 'numOfRows': 300})
            c, msg, items = unwrap(raw)
        except RuntimeError as e:
            log('  관측 오류', e); continue
        if c not in ('00', '0') and not items:
            note(f'관측 {code} {day:%Y%m%d}: 결과코드 {c} {msg} :: {json.dumps(raw, ensure_ascii=False)[:300]}', 'warning')
        rows += items
    def f(v):
        try:
            return round(float(v), 1)
        except (TypeError, ValueError):
            return None
    pts = []
    for r in rows:
        t = str(r.get('obsrvnDt') or r.get('obsrvn_dt') or r.get('record_time') or '')[:16]
        w = f(r.get('wtem', r.get('water_temp')))
        if t and w is not None:
            pts.append((t, w, f(r.get('wspd')), f(r.get('wndrct')), f(r.get('artmp'))))
    if not pts:
        return None
    pts.sort()
    t, w, ws, wd, at = pts[-1]
    t_last = datetime.strptime(t[:16].replace('T', ' '), '%Y-%m-%d %H:%M')
    old = [p for p in pts if datetime.strptime(p[0][:16].replace('T', ' '), '%Y-%m-%d %H:%M') <= t_last - timedelta(hours=23)]
    return {'t': t, 'wtem': w, 'wtem24': old[-1][1] if old else None, 'wspd': ws, 'wdir': wd, 'atmp': at}


def main():
    if not KEY:
        sys.exit('DATA_GO_KR_KEY 비밀값이 없어요')
    now = datetime.now(KST)
    try:
        prev = json.load(open(OUT))
    except Exception:
        prev = {}
    base = kma_base(now)
    log(f'기준 시각 {now:%Y-%m-%d %H:%M} KST, 기상청 발표 {base[0]} {base[1]}')
    out = {'generated': now.isoformat(timespec='minutes'), 'stations': {}}
    cache = {}
    ok_f = ok_o = 0
    for key, cfg in STATIONS.items():
        pst = (prev.get('stations') or {}).get(key) or {}
        st = {'fc': {}, 'obs': pst.get('obs')}
        got = None
        for lat, lon in cfg['sea']:
            g = to_grid(lat, lon)
            if g not in cache:
                try:
                    used, items = fetch_fcst(g[0], g[1], base)
                    cache[g] = (used, pack_fcst(items))
                except RuntimeError as e:
                    note(f'{key} 예보 오류 {str(e)[:200]}', 'warning'); cache[g] = (None, {})
            used, fc = cache[g]
            if fc and any(v[2] is not None for v in fc.values()):
                got = (g, used, fc); break
            if fc and not got:
                got = (g, used, fc)   # 파고가 없어도 바람이라도
        if got:
            g, used, fc = got
            # 오늘 지나간 시간은 예전 자료를 남겨 둔다 (새 예보에는 없으므로)
            keep_from = (now - timedelta(hours=30)).strftime('%Y%m%d%H')
            merged = {k: v for k, v in (pst.get('fc') or {}).items() if k >= keep_from}
            merged.update(fc)
            st['fc'] = dict(sorted(merged.items()))
            st['grid'] = list(g); st['base'] = ' '.join(used) if used else None
            ok_f += 1
            note(f'{key}: 격자 {g}, 예보 {len(fc)}시간, 파고 {"있음" if any(v[2] is not None for v in fc.values()) else "없음"}')
        else:
            st['fc'] = pst.get('fc') or {}
            note(f'{key}: 예보 못 받음 (이전 자료 유지)', 'warning')
        o = fetch_obs(cfg['obs'], now)
        if o:
            o['code'] = cfg['obs']; st['obs'] = o; ok_o += 1
            note(f'{key} 수온 {o["wtem"]}℃ ({o["t"]}), 24시간 전 {o["wtem24"]}')
        out['stations'][key] = st
    if ok_f == 0 and ok_o == 0:
        sys.exit('예보·관측을 하나도 받지 못했어요 (인증키 활용신청 승인 대기 중일 수 있어요)')
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, 'w') as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))
    log(f'저장: 예보 {ok_f}/8곳, 수온 {ok_o}/8곳')


def diag():
    now = datetime.now(KST); d, t = kma_base(now)
    tests = [
        ('KMA https', KMA_URL, {'pageNo': 1, 'numOfRows': 20, 'dataType': 'JSON', 'base_date': d, 'base_time': t, 'nx': 55, 'ny': 124}),
        ('KMA http', KMA_URL.replace('https://', 'http://'), {'pageNo': 1, 'numOfRows': 20, 'dataType': 'JSON', 'base_date': d, 'base_time': t, 'nx': 55, 'ny': 124}),
        ('KHOA https', OBS_URL, {'type': 'json', 'obsCode': 'DT_0001', 'reqDate': now.strftime('%Y%m%d'), 'min': 60, 'pageNo': 1, 'numOfRows': 5}),
    ]
    for name, url, params in tests:
        t0 = time.time()
        q = urllib.parse.urlencode(params, safe='')
        try:
            with urllib.request.urlopen(f'{url}?serviceKey={KEY}&{q}', timeout=15) as r:
                body = r.read().decode('utf-8', 'replace')
            note(f'{name}: HTTP {r.status} {time.time() - t0:.1f}s :: {re.sub(r"\s+", " ", body)[:320].replace(KEY, "***")}')
        except Exception as e:
            note(f'{name}: 실패 {time.time() - t0:.1f}s :: {type(e).__name__} {str(e)[:200].replace(KEY, "***")}', 'warning')


if __name__ == '__main__':
    if '--diag' in sys.argv:
        diag()
    else:
        main()
