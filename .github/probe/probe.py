"""지도 자료 받기: OpenStreetMap 육지(해안선)와 섬 이름 (서해 중부 범위만 잘라서)"""
import json, os, subprocess, time
OUT = 'probe-out/osm'; os.makedirs(OUT, exist_ok=True)
BB = (125.3, 35.1, 127.4, 38.1)   # 경도·위도 범위
def sh(c):
    t = time.time(); print('$', c, flush=True)
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    print((r.stdout + r.stderr)[-1500:], f'({time.time()-t:.0f}s)', flush=True)
    return r.returncode
log = []
sh('sudo apt-get -qq update && sudo apt-get -qq install -y gdal-bin osmium-tool > /dev/null')
# 1) 육지 다각형 (OSM 해안선으로 만든 것, 매일 갱신)
sh('wget -q https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip -O land.zip && unzip -q land.zip')
shp = subprocess.run('ls land-polygons-split-4326/*.shp', shell=True, capture_output=True, text=True).stdout.strip()
sh(f'ogr2ogr -f GeoJSON -clipsrc {BB[0]} {BB[1]} {BB[2]} {BB[3]} -lco COORDINATE_PRECISION=6 {OUT}/land.geojson {shp}')
log.append(f'land.geojson {os.path.getsize(f"{OUT}/land.geojson") // 1024} KB')
sh('ls -la land-polygons-split-4326/ | head; cat land-polygons-split-4326/README.txt 2>/dev/null | head -30')
# 2) 섬·지명 (Geofabrik 한국 추출본)
sh('wget -q https://download.geofabrik.de/asia/south-korea-latest.osm.pbf -O kr.pbf && ls -la kr.pbf && osmium fileinfo kr.pbf | head -20')
sh(f'osmium extract -b {BB[0]},{BB[1]},{BB[2]},{BB[3]} kr.pbf -o box.pbf --overwrite')
sh('osmium tags-filter box.pbf nwr/place=island,islet,archipelago nwr/natural=peninsula,cape,bay,reef nwr/place=locality nwr/leisure=marina nwr/harbour nwr/seamark:type=harbour -o places.pbf --overwrite')
sh(f'osmium export places.pbf -f geojsonseq -o {OUT}/places.geojsonseq --overwrite --attributes=type,id')
# 갯벌
sh('osmium tags-filter box.pbf nwr/wetland=tidalflat -o flats.pbf --overwrite')
sh(f'osmium export flats.pbf -f geojsonseq -o {OUT}/flats.geojsonseq --overwrite')
for f in os.listdir(OUT): log.append(f'{f} {os.path.getsize(f"{OUT}/{f}") // 1024} KB')
sh('osmium fileinfo -e kr.pbf | grep -i "timestamp\\|Last" | head -5 > probe-out/osm/when.txt; cat probe-out/osm/when.txt')
open('probe-out/log.txt', 'w').write('\n'.join(log))
print('\n'.join(log))
