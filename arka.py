"""Ortak zemin: stadyum isiklari + sicak parilti + ince dalga cizgileri. Tema: perfkart.TH ('sl' bordo-altin, 'cl' lacivert)."""
import math, random
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1080, 1350
SK = {  # tema -> (taban rengi ust, taban alt, huzme, duman, toz)
    "sl": dict(b0=(34, 6, 15), b1=(104, 15, 32), beam=(255, 176, 96), smoke=(150, 30, 48), dust=(1.0, .78, .45)),
    "cl": dict(b0=(5, 10, 34), b1=(18, 42, 118), beam=(140, 185, 255), smoke=(22, 48, 140), dust=(.6, .8, 1.0)),
}


def _noise(sc, seed):
    r = np.random.RandomState(seed)
    a = r.rand(H // sc + 2, W // sc + 2).astype("float32")
    return np.asarray(Image.fromarray((a * 255).astype("uint8")).resize((W, H), Image.BICUBIC), dtype="float32") / 255


def bg(t, kind="sl", seed=8):
    c = SK[kind]
    rnd = random.Random(seed)
    y = np.linspace(0, 1, H)[:, None]
    base = np.zeros((H, W, 3), "float32")
    for i in range(3):
        base[..., i] = c["b0"][i] + (c["b1"][i] - c["b0"][i]) * y
    img = Image.fromarray(base.clip(0, 255).astype("uint8"))
    # stadyum huzmeleri
    beams = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(beams)
    for ax, tx, sp in ((120, 330, 120), (540, 540, 150), (960, 750, 120)):
        bd.polygon([(ax - 14, -20), (ax + 14, -20), (tx + sp, 980), (tx - sp, 980)], fill=255)
    beams = beams.filter(ImageFilter.GaussianBlur(48))
    fade = Image.linear_gradient("L").transpose(Image.FLIP_TOP_BOTTOM).resize((W, H))
    beams = ImageChops.multiply(beams, fade).point(lambda v: int(v * 0.30))
    img = Image.composite(Image.new("RGB", (W, H), c["beam"]), img, beams)
    # duman
    n = _noise(220, 1) * 0.6 + _noise(90, 2) * 0.3 + _noise(40, 3) * 0.1
    sm = np.clip((n - 0.42) * 2.2, 0, 1) * np.clip((np.linspace(0, 1, H)[:, None] - 0.25) * 1.6, 0, 1)
    img = Image.composite(Image.new("RGB", (W, H), c["smoke"]), img, Image.fromarray((sm * 120).astype("uint8")))
    # sag ust sicak parilti
    gl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gl).ellipse((W - 560, -330, W + 340, 560), fill=120)
    gl = gl.filter(ImageFilter.GaussianBlur(130))
    img = Image.composite(Image.new("RGB", (W, H), tuple(t["acc"])), img, gl.point(lambda v: int(v * 0.55)))
    # bokeh + toz
    bk = Image.new("RGB", (W, H), (0, 0, 0))
    bdr = ImageDraw.Draw(bk)
    for _ in range(18):
        x, yy, r = rnd.randrange(W), rnd.randrange(H), rnd.randint(6, 26)
        v = rnd.randint(18, 42)
        bdr.ellipse([x - r, yy - r, x + r, yy + r], fill=(int(v * c["dust"][0]), int(v * c["dust"][1]), int(v * c["dust"][2])))
    img = ImageChops.screen(img, bk.filter(ImageFilter.GaussianBlur(5)))
    dd = Image.new("RGB", (W, H), (0, 0, 0))
    d2 = ImageDraw.Draw(dd)
    for _ in range(380):
        x, yy = rnd.randrange(W), rnd.randrange(H)
        v = rnd.randint(90, 220)
        d2.ellipse([x - 1, yy - 1, x + 1, yy + 1], fill=(int(v * c["dust"][0]), int(v * c["dust"][1]), int(v * c["dust"][2])))
    img = ImageChops.screen(img, dd.filter(ImageFilter.GaussianBlur(0.6)))
    # vinyet
    vg = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(v * 0.8))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, vg)
    # ince dalga cizgileri (altta)
    ov = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(26):
        pts = [(x * 2, (H * 0.80 + i * 14 + 70 * math.sin(x / 170 + i * .22) + 40 * math.sin(x / 70 + i * .5)) * 2) for x in range(0, W + 1, 8)]
        d.line(pts, fill=tuple(t["acc"]) + (max(12, 78 - i * 2),), width=3)
    ov = ov.resize((W, H), Image.LANCZOS)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
