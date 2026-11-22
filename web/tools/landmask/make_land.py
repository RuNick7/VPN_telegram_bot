"""Rasterise Natural Earth land (world-atlas TopoJSON) into an equirectangular mask.
Row 0 = 90N, column 0 = 180W. White = land."""
import json, sys
from PIL import Image, ImageDraw

src, out, W = sys.argv[1], sys.argv[2], int(sys.argv[3])
H = W // 2
topo = json.load(open(src))
sx, sy = topo["transform"]["scale"]
tx, ty = topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)

def ring(idx):
    pts = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts

SS = 4
img = Image.new("L", (W * SS, H * SS), 0)
d = ImageDraw.Draw(img)
def px(p):
    return ((p[0] + 180) / 360 * W * SS, (90 - p[1]) / 180 * H * SS)
polys = []
for g in topo["objects"]["land"]["geometries"]:
    polys += g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
for poly in polys:
    for k, r in enumerate(poly):
        pts = ring(r)
        un = [pts[0]]
        for lon, lat in pts[1:]:
            prev = un[-1][0]
            while lon - prev > 180: lon -= 360
            while lon - prev < -180: lon += 360
            un.append((lon, lat))
        if abs(un[-1][0] - un[0][0]) > 180:
            pole = -90 if sum(q[1] for q in un) / len(un) < 0 else 90
            un += [(un[-1][0], pole), (un[0][0], pole)]
        for shift in (-360, 0, 360):
            d.polygon([px((q[0] + shift, q[1])) for q in un], fill=255 if k == 0 else 0)
img = img.resize((W, H), Image.LANCZOS)
if len(sys.argv) > 4 and sys.argv[4] == "1bit":
    img = img.convert("1", dither=Image.NONE)
img.save(out, optimize=True)
print(out, len(polys), "polygons")
