"""Paints the seamless, neutral-coloured sky layers (Assets/Backgrounds/layers/*.webp) used by layered skies.
They tile horizontally and are tinted per scene (layer.tint), so they stay grey/white here.
Run:  python make_layers.py [outdir]    (needs numpy + Pillow). Re-running overwrites them."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

W, H = 2048, 512
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "Assets" / "Backgrounds" / "layers"

def tnoise(scale, seed):                         # horizontally seamless value noise
    r = np.random.default_rng(seed); gh = max(2, int(H / scale)); gw = max(2, int(W / scale)); g = r.random((gh, gw))
    big = np.tile(g, (1, 3)); im = Image.fromarray((big * 255).astype(np.uint8)).resize((gw * 3 * int(scale), gh * int(scale)), Image.BICUBIC)
    a = np.asarray(im.resize((W * 3, H), Image.BICUBIC), float) / 255; return a[:, W:2 * W]
def tfbm(scale, seed, octs=5):
    t = np.zeros((H, W)); a = 1.0; s = 0
    for o in range(octs): t += a * tnoise(max(4, scale / 2 ** o), seed + 11 * o); s += a; a *= 0.5
    return t / s
def save(rgb, alpha, name):
    OUT.mkdir(parents=True, exist_ok=True); a = np.dstack([np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)[..., None]]); Image.fromarray((a * 255).astype(np.uint8), "RGBA").save(OUT / (name + ".webp"), quality=88, method=6, exact=True); print("wrote", name)
def shade(alpha, lo=0.70, hi=1.0, dy=6):         # light from the top: darker underside
    s = np.clip(alpha - np.roll(alpha, -dy, 0), -1, 1) * 0.5 + 0.5
    v = lo + (hi - lo) * np.clip(s * 1.4, 0, 1); return np.dstack([v * 0.95, v * 0.97, v])

def cloud_bank(name, seed, cover, scale, bandy=(0.2, 0.9), soft=0.14):
    yy = np.linspace(0, 1, H)[:, None]; mid = sum(bandy) / 2; half = (bandy[1] - bandy[0]) / 2
    band = np.clip(1 - np.abs((yy - mid) / half), 0, 1) ** 0.7; n = tfbm(scale, seed)
    a = np.clip((n * band - (1 - cover) * 0.5) / soft, 0, 1); a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), float) / 255
    save(shade(a, dy=8), a * 0.92, name)
def cirrus(name, seed):
    n = tfbm(160, seed); sx = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((W // 6, H), Image.BICUBIC).resize((W, H), Image.BICUBIC), float) / 255   # stretch horizontally
    yy = np.linspace(0, 1, H)[:, None]; band = np.clip(1 - np.abs((yy - 0.5) / 0.5), 0, 1); a = np.clip((sx * band - 0.28) / 0.35, 0, 1) * 0.55
    save(np.ones((H, W, 3)), a, name)
def stars(name, seed):
    r = np.random.default_rng(seed); a = np.zeros((H, W)); n = 1500
    xs = r.integers(0, W, n); ys = (r.random(n) ** 1.2 * (H - 4)).astype(int); a[ys, xs] = r.random(n) ** 2.2
    big = np.zeros((H, W)); bx = r.integers(0, W, 90); by = r.integers(0, H - 4, 90); big[by, bx] = 1
    a = np.maximum(np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6)), float) / 255 * 1.6,
                   np.asarray(Image.fromarray((big * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)), float) / 255 * 3)
    rgb = np.ones((H, W, 3)); rgb[..., 2] = 1.0; rgb[..., 0] = 0.92; save(rgb, a, name)
def mist(name, seed):
    n = tfbm(220, seed, 4); yy = np.linspace(0, 1, H)[:, None]; band = np.clip(1 - np.abs((yy - 0.62) / 0.38), 0, 1) ** 1.4
    a = np.clip(n * band * 1.5 - 0.1, 0, 1) * 0.6; save(np.ones((H, W, 3)), a, name)
def periodic_ridge(seed, base, amp, jag=0.0, f0=2):
    r = np.random.default_rng(seed); x = np.arange(W) / W; h = np.zeros(W); a = 1.0
    for o in range(7): f = f0 * 2 ** o if o < 5 else f0 * 2 ** o; h += a * np.sin(x * TAU_(f) + r.random() * 6.28); a *= 0.52
    h = (h - h.min()) / (h.max() - h.min())
    if jag: j = np.abs(r.random(W) - 0.5) * 2; j = np.convolve(np.r_[j[-3:], j, j[:3]], np.ones(5) / 5, "valid")[:W]; h = h * (1 - jag) + j * jag
    return (base - amp * (0.3 + 0.7 * h)) * H
def TAU_(f): return 6.2831853 * f
def ridges(name, seed, base, amp, shade_v, jag=0.0, f0=2):
    top = periodic_ridge(seed, base, amp, jag, f0); yy = np.arange(H)[:, None]; a = np.clip(yy - top[None, :], 0, 1)
    v = shade_v * (1 - 0.25 * np.clip((yy - top[None, :]) / (amp * H + 1), 0, 1)); save(np.dstack([v, v, v]), a, name)
cloud_bank("clouds_puffy", 101, 0.55, 150, (0.15, 0.95)); cloud_bank("clouds_heavy", 202, 0.78, 190, (0.05, 0.95), soft=0.22)
cirrus("clouds_wisps", 303); stars("stars", 404); mist("mist", 505)
ridges("ridges_far", 606, 0.97, 0.38, 0.62, f0=2); ridges("ridges_near", 707, 1.0, 0.3, 0.38, f0=3); ridges("treeline", 808, 1.0, 0.16, 0.24, jag=0.85, f0=5)
