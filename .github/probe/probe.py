"""출항지 후보 전국으로 모으기 (OSM, 남해 확장용): 이름이 항·항구·포구·선착장·부두·나루·마리나·물양장·여객터미널 등으로 끝나는 곳,
항구·마리나·여객선 터미널·부두 태그가 붙은 곳, '…포' 마을 이름. 거르기·정리는 앱 쪽에서 한다."""
import json, os, subprocess, sys, importlib, site, traceback, re
log = []
try:
    subprocess.run(f'{sys.executable} -m pip install -q --user --break-system-packages osmium', shell=True)
    importlib.invalidate_caches(); site.addsitedir(site.getusersitepackages())
    import osmium
    subprocess.run('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf', shell=True)
    log.append('pbf %d MB' % (os.path.getsize('kr.pbf') // 1e6))
    PAT = re.compile(r'(항|항구|포구|포|선착장|부두|나루|나루터|마리나|어항|여객터미널|여객선터미널|연안여객터미널|물양장|선창|도선장|부잔교|선착장\s*\(.*\)|항\s*\(.*\))$')
    BAD = re.compile(r'(공항|항공|항만공사|항만청|해양경찰|대합실|식당|횟집|회센터|마트|주유소|모텔|펜션|카페|병원|학교|교회|아파트|정류장$)')
    KEYS = {'harbour', 'seamark:type', 'leisure', 'amenity', 'landuse', 'man_made', 'waterway', 'place', 'highway', 'public_transport', 'mooring', 'industrial', 'route'}
    def keep(tags):
        nm = tags.get('name:ko') or tags.get('name') or ''
        nm = nm.strip()
        if not nm or len(nm) > 20: return None
        harb = ('harbour' in tags or tags.get('seamark:type') in ('harbour', 'small_craft_facility', 'ferry_terminal', 'harbour_basin')
                or tags.get('leisure') == 'marina' or tags.get('amenity') == 'ferry_terminal' or tags.get('landuse') in ('harbour', 'port')
                or tags.get('man_made') in ('pier', 'quay', 'breakwater', 'jetty') or tags.get('waterway') == 'dock' or tags.get('industrial') == 'port')
        name_ok = PAT.search(nm) and not BAD.search(nm)
        if not (harb or name_ok): return None
        if BAD.search(nm) and not harb: return None
        t = {k: tags[k] for k in KEYS if k in tags}
        return nm, t, harb
    out = []
    class H(osmium.SimpleHandler):
        def node(self, n):
            r = keep(n.tags)
            if r: out.append([r[0], round(n.location.lat, 6), round(n.location.lon, 6), r[1], 'n', 1 if r[2] else 0])
        def way(self, w):
            r = keep(w.tags)
            if not r: return
            try:
                la = [x.lat for x in w.nodes if x.location.valid()]; lo = [x.lon for x in w.nodes if x.location.valid()]
            except Exception: return
            if la: out.append([r[0], round(sum(la) / len(la), 6), round(sum(lo) / len(lo), 6), r[1], 'w', 1 if r[2] else 0])
    # 전국 (거르기는 물때 격자 범위로 나중에)
    H().apply_file('kr.pbf', locations=True, idx='flex_mem')
    os.makedirs('probe-out/osm', exist_ok=True)
    json.dump(out, open('probe-out/osm/ports_raw_all.json', 'w'), ensure_ascii=False)
    log.append('candidates %d (harbour-tagged %d)' % (len(out), sum(1 for o in out if o[5])))
    for q in ('국동', '녹동', '미조', '삼천포', '통영', '중앙동', '지세포', '장승포', '완도', '서망', '목포', '북항', '다대포', '도두', '한림', '모슬포', '서귀포', '성산', '추자', '거문도', '나로도', '여수'):
        log.append(q + ' ' + json.dumps([o[0] for o in out if q in o[0]][:8], ensure_ascii=False))
except Exception:
    log.append(traceback.format_exc())
open('probe-out/osm/log_ports_all.txt', 'w').write('\n'.join(log))
