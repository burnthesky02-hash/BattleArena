"""Paints the stock sky/environment backdrops used by the 2.5D engine (hub scenes and battle arenas).
Run:  python make_backgrounds.py   ->  Assets/Backgrounds/*.webp   (needs numpy + Pillow)
Re-running overwrites the files, so keep hand-made images under another name."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

W, H = 1920, 1080
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "Assets" / "Backgrounds"
rng = np.random.default_rng(7)

def hexc(s): s = s.lstrip("#"); return np.array([int(s[i:i+2], 16) for i in (0, 2, 4)], float) / 255
def gradient(stops):
    ys = np.linspace(0, 1, H)[:, None]; pos = [p for p, _ in stops]; cols = np.array([hexc(c) for _, c in stops])
    img = np.stack([np.interp(ys[:, 0], pos, cols[:, k]) for k in range(3)], -1)
    return np.repeat(img[:, None, :], W, 1)
def noise(scale, seed):
    r = np.random.default_rng(seed); g = r.random((max(2, int(H / scale)), max(2, int(W / scale))))
    return np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), float) / 255
def fbm(scale, seed, oct=5):
    t = np.zeros((H, W)); a = 1.0; tot = 0
    for o in range(oct): t += a * noise(scale / 2 ** o, seed + o * 17); tot += a; a *= 0.5
    return t / tot
def over(base, col, a): a = np.clip(a, 0, 1)[..., None]; return base * (1 - a) + np.asarray(col, float) * a
def clouds(img, col, seed, y0, y1, cover=0.5, soft=0.18, scale=240, squash=0.45):
    n = fbm(scale, seed); yy = np.linspace(0, 1, H)[:, None]
    band = np.clip(1 - np.abs((yy - (y0 + y1) / 2) / ((y1 - y0) / 2)), 0, 1) ** 0.8
    m = np.clip((n * band - (1 - cover) * 0.55) / soft, 0, 1)
    return over(img, hexc(col) if isinstance(col, str) else col, m * 0.85)
def ridge(img, col, base, amp, seed, rough=0.0, haze=None, hazeamt=0.0, jag=0.0):
    r = np.random.default_rng(seed); n = 1100; x = np.linspace(0, 1, W)
    h = np.zeros(W); a = 1.0
    for o in range(6):
        ph = r.random() * 6.28; f = 1.4 * 2 ** o; h += a * np.sin(x * f * 6.28 + ph) * (1 if o < 2 else 0.8); a *= 0.5 if jag == 0 else 0.62
    h = (h - h.min()) / (h.max() - h.min() + 1e-6)
    if jag: h = h * 0.6 + 0.4 * np.abs(np.convolve(r.random(W), np.ones(5) / 5, "same") - 0.5) * 2
    top = (base - amp * h) * H; yy = np.arange(H)[:, None]
    mask = np.clip(yy - top[None, :], 0, 1)
    c = hexc(col) if isinstance(col, str) else col
    layer = np.ones((H, W, 3)) * c
    if haze is not None: grad = np.clip((yy - top[None, :]) / (amp * H * 0.9 + 1), 0, 1)[..., None]; layer = layer * (1 - 0.0) + (hexc(haze) * hazeamt) * (1 - grad)
    return img * (1 - mask[..., None]) + layer * mask[..., None]
def glow(img, cx, cy, r, col, strength):
    yy, xx = np.mgrid[0:H, 0:W]; d = np.hypot((xx - cx * W) / (r * W), (yy - cy * H) / (r * W)); return img + hexc(col) * np.exp(-d * d * 3.2)[..., None] * strength
def stars(img, n, seed, ymax=0.7, bright=1.0):
    r = np.random.default_rng(seed); a = np.zeros((H, W))
    xs = (r.random(n) * W).astype(int); ys = (r.random(n) ** 1.4 * ymax * H).astype(int); a[ys, xs] = r.random(n) ** 3 * bright
    a = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.7)), float) / 255
    return img + a[..., None] * np.array([1, 1, 1.0]) * 1.4
def grain(img, amt=0.012): return img + (np.random.default_rng(1).random((H, W, 1)) - 0.5) * amt
def vign(img, s=0.28):
    yy, xx = np.mgrid[0:H, 0:W]; d = np.hypot((xx / W - 0.5) * 1.1, (yy / H - 0.5)); return img * (1 - s * np.clip(d * 1.4 - 0.25, 0, 1))[..., None]
def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True); a = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(a).save(OUT / (name + ".webp"), quality=86, method=6); print("wrote", name)

def sunset():
    i = gradient([(0, "#1a1442"), (.35, "#4a2f7a"), (.58, "#c25a7e"), (.76, "#f39a68"), (.9, "#ffd28a"), (1, "#ffe6b0")])
    i = glow(i, .62, .74, .45, "#ffb060", .9); i = glow(i, .62, .74, .09, "#fff0c0", 1.2)
    i = clouds(i, "#e0709a", 3, .2, .6, .55, scale=300); i = clouds(i, "#ffc08a", 9, .45, .75, .45, scale=200); i = clouds(i, "#5a3a80", 21, .1, .4, .5, scale=360)
    i = ridge(i, "#7a4a82", .86, .16, 4, haze="#ffb070", hazeamt=.4); i = ridge(i, "#4a2f62", .92, .14, 6); i = ridge(i, "#241638", 1.0, .12, 8)
    save(vign(grain(i)), "sunset_peaks")
def clear_day():
    i = gradient([(0, "#2a62c8"), (.4, "#5a9ae6"), (.75, "#a8d4f6"), (1, "#e6f4ff")])
    i = glow(i, .78, .18, .3, "#fff6d0", .5); i = clouds(i, "#ffffff", 5, .1, .6, .5, soft=.22, scale=280); i = clouds(i, "#f0f6ff", 12, .4, .78, .4, scale=200)
    i = ridge(i, "#8fb8d8", .9, .1, 2, haze="#e6f4ff", hazeamt=.3); i = ridge(i, "#5e9a78", .96, .09, 11); i = ridge(i, "#386a48", 1.02, .07, 13)
    save(vign(grain(i), .18), "clear_day")
def starry():
    i = gradient([(0, "#03041a"), (.45, "#0b1238"), (.8, "#1b2c66"), (1, "#324a86")])
    i = stars(i, 2600, 5, .8); i = glow(i, .72, .2, .32, "#8aa8ff", .35); i = glow(i, .72, .2, .035, "#ffffff", 1.4)
    i = clouds(i, "#2a3c7a", 31, .5, .85, .35, scale=320)
    i = ridge(i, "#1f2d5a", .88, .15, 14, haze="#3a58a0", hazeamt=.4); i = ridge(i, "#111a3c", .95, .12, 16); i = ridge(i, "#080c20", 1.02, .1, 18)
    save(vign(grain(i)), "starry_night")
def storm():
    i = gradient([(0, "#12161e"), (.5, "#2c3440"), (.85, "#4a5560"), (1, "#66727a")])
    i = clouds(i, "#8a96a0", 41, .0, .7, .8, soft=.3, scale=220); i = clouds(i, "#1a2028", 43, .05, .5, .7, soft=.3, scale=300)
    i = glow(i, .3, .35, .22, "#b8d0ff", .35)
    i = ridge(i, "#2e3a42", .92, .1, 20, haze="#66727a", hazeamt=.3); i = ridge(i, "#161c20", 1.0, .1, 22)
    save(vign(grain(i), .35), "storm_clouds")
def volcanic():
    i = gradient([(0, "#140404"), (.4, "#4a0e08"), (.7, "#b02a0c"), (.9, "#ff7a1c"), (1, "#ffc040")])
    i = clouds(i, "#2a0a08", 51, .05, .6, .75, soft=.3, scale=240); i = glow(i, .5, .95, .5, "#ff8a2a", .9)
    i = clouds(i, "#ff6a20", 53, .55, .85, .3, scale=180)
    i = ridge(i, "#3a0c08", .88, .2, 24, jag=1, haze="#ff7a20", hazeamt=.5); i = ridge(i, "#1c0604", .97, .16, 26, jag=1); i = ridge(i, "#080202", 1.02, .1, 28, jag=1)
    save(vign(grain(i), .3), "volcanic_ash")
def cavern():
    i = gradient([(0, "#03070a"), (.5, "#0a1a22"), (.85, "#143640"), (1, "#1e5560")])
    i = glow(i, .5, .75, .5, "#2a9aa0", .35); i = clouds(i, "#1a4a56", 61, .4, .95, .5, scale=260)
    for k, (c, b, a) in enumerate([("#0e2a32", .8, .22), ("#08181e", .9, .2), ("#030a0e", 1.0, .18)]): i = ridge(i, c, b, a, 30 + k * 2, jag=1)
    yy = np.arange(H)[:, None]; r = np.random.default_rng(9)                     # stalactites hanging from the top
    x = np.linspace(0, 1, W); top = np.zeros(W)
    for _ in range(26): cx = r.random(); w = .012 + r.random() * .03; hh = (.08 + r.random() * .3) * H; top = np.maximum(top, hh * np.clip(1 - np.abs(x - cx) / w, 0, 1) ** 1.3)
    m = np.clip(top[None, :] - yy, 0, 1)[..., None]; i = i * (1 - m) + hexc("#020608") * m
    save(vign(grain(i), .4), "cavern_glow")
def dawn():
    i = gradient([(0, "#2c2c68"), (.35, "#7a5a98"), (.6, "#e08a9a"), (.8, "#ffc088"), (1, "#fff0c8")])
    i = glow(i, .3, .84, .4, "#ffe0a0", .9); i = glow(i, .3, .84, .07, "#ffffff", 1.1)
    i = clouds(i, "#f0a0b0", 71, .25, .65, .5, scale=300); i = clouds(i, "#fff0d0", 73, .55, .85, .4, scale=200)
    i = ridge(i, "#a898c0", .88, .1, 32, haze="#ffe0b0", hazeamt=.5); i = ridge(i, "#7a6a9a", .94, .09, 34, haze="#ffd0a0", hazeamt=.3); i = ridge(i, "#4a3e68", 1.0, .08, 36)
    save(vign(grain(i), .2), "dawn_mist")
for f in (sunset, clear_day, starry, storm, volcanic, cavern, dawn): f()
