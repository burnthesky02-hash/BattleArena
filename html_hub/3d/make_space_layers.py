"""Paints Assets/Backgrounds/layers/planet.webp, the ringed gas giant in the asteroid base's sky (stars.webp comes from make_layers.py).
Run:  python make_space_layers.py [outdir]    (numpy + Pillow)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "Assets" / "Backgrounds" / "layers"
N = 1024; R = 300; CX = CY = N // 2
rng = np.random.default_rng(7)
yy, xx = np.mgrid[0:N, 0:N].astype(float)
dx, dy = (xx - CX) / R, (yy - CY) / R; r2 = dx * dx + dy * dy
disc = (r2 <= 1).astype(float); z = np.sqrt(np.clip(1 - r2, 0, 1))
# banded gas giant: bands follow latitude, wobbled by noise
def noise(s, seed):
    g = np.random.default_rng(seed).random((N // s + 2, N // s + 2)); return np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC), float) / 255
lat = dy + 0.06 * (noise(64, 1) - 0.5) + 0.03 * (noise(24, 2) - 0.5)
bands = 0.5 + 0.5 * np.sin(lat * 19) * 0.6 + 0.25 * np.sin(lat * 47 + 1.3)
cols = np.array([[.78, .55, .36], [.93, .80, .60], [.62, .40, .30], [.88, .70, .52]])
t = np.clip(bands, 0, 1) * 3; i = np.clip(t.astype(int), 0, 2); f = (t - i)[..., None]
col = cols[i] * (1 - f) + cols[i + 1] * f
# light from the upper left, soft terminator
light = np.clip((-dx * 0.55 - dy * 0.45) * 0.9 + z * 0.75, 0, 1) ** 1.2
rgb = col * (0.12 + 0.95 * light)[..., None]
alpha = disc.copy()
# atmosphere glow
glow = np.clip(1 - np.abs(np.sqrt(r2) - 1.0) * 9, 0, 1) * (np.sqrt(r2) > 0.97) * 0.35
# ring: tilted ellipse, half behind / half in front of the planet
ang = np.deg2rad(-17); ca, sa = np.cos(ang), np.sin(ang)
rx, ry = dx * ca + dy * sa, -dx * sa + dy * ca; rr = np.sqrt(rx ** 2 + (ry / 0.26) ** 2)
ring = np.clip(1 - np.abs(rr - 1.75) / 0.42, 0, 1) * ((rr > 1.35) & (rr < 2.2)); ring *= 0.55 + 0.45 * np.sin(rr * 55) ** 2
ring = ring * (0.6 + 0.4 * noise(8, 3)); front = (ry > 0); ringcol = np.array([.86, .76, .6])
shade_in_planet = ring * front
out_rgb = np.zeros((N, N, 3)); out_a = np.zeros((N, N))
# back half of the ring, then the planet, then the front half
back = ring * (~front); out_rgb += ringcol * back[..., None]; out_a = np.maximum(out_a, back * 0.8)
m = alpha[..., None]; out_rgb = out_rgb * (1 - m) + rgb * m; out_a = np.maximum(out_a, alpha)
fr = ring * front * 0.9; out_rgb = out_rgb * (1 - fr[..., None]) + ringcol * fr[..., None]; out_a = np.maximum(out_a, fr)
g = np.asarray(Image.fromarray((glow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), float) / 255
out_rgb = out_rgb + np.array([.5, .6, .9]) * g[..., None] * 0.6; out_a = np.maximum(out_a, g)
OUT.mkdir(parents=True, exist_ok=True)
Image.fromarray((np.dstack([np.clip(out_rgb, 0, 1), np.clip(out_a, 0, 1)[..., None]]) * 255).astype(np.uint8), "RGBA").save(OUT / "planet.webp", quality=90, method=6)
print("wrote", OUT / "planet.webp")
