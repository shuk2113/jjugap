"""지도 자료 다듬기: OSM 육지 조각(타일로 잘린 것)을 하나로 합치고, 갯벌도 합친다"""
import json, os, subprocess, time
r = subprocess.run('pip install -q --break-system-packages shapely || sudo apt-get -qq install -y python3-shapely', shell=True, capture_output=True, text=True); print(r.stdout[-500:], r.stderr[-800:], flush=True)
import traceback
try:
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    from shapely import set_precision
    OUT = 'probe-out/osm'
    t = time.time()
    land = json.load(open(f'{OUT}/land.geojson'))
    geo = unary_union([shape(f['geometry']).buffer(0) for f in land['features']])
    print('land union', geo.geom_type, len(getattr(geo, 'geoms', [geo])), f'{time.time()-t:.0f}s', flush=True)
    json.dump({'type': 'Feature', 'properties': {}, 'geometry': mapping(set_precision(geo, 1e-6))}, open(f'{OUT}/land_union.geojson', 'w'))
    fl = []
    for l in open(f'{OUT}/flats.geojsonseq'):
        l = l.strip().strip('\x1e')
        if not l: continue
        g = shape(json.loads(l)['geometry'])
        if g.geom_type in ('Polygon', 'MultiPolygon'): fl.append(g.buffer(0))
        elif g.geom_type == 'LineString' and g.is_ring:
            from shapely.geometry import Polygon
            fl.append(Polygon(g.coords).buffer(0))
    fu = unary_union(fl).difference(geo.buffer(0))
    print('flats union', fu.geom_type, f'{time.time()-t:.0f}s', flush=True)
    json.dump({'type': 'Feature', 'properties': {}, 'geometry': mapping(set_precision(fu, 1e-5))}, open(f'{OUT}/flats_union.geojson', 'w'))
    for f in ('land_union.geojson', 'flats_union.geojson'): print(f, os.path.getsize(f'{OUT}/{f}') // 1024, 'KB')
    os.remove(f'{OUT}/land.geojson')
    open('probe-out/log.txt', 'w').write(f'done {time.time()-t:.0f}s')

except Exception:
    os.makedirs('probe-out', exist_ok=True); open('probe-out/log.txt', 'w').write(traceback.format_exc() + '\n' + r.stderr[-1500:])
