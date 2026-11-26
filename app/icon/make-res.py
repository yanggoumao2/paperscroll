"""Turn the rendered masters into Android launcher/splash resources and web icons."""
from pathlib import Path
from PIL import Image, ImageDraw
D = Path(__file__).parent
RES = D.parent / "android" / "app" / "src" / "main" / "res"
WEB = D.parent.parent / "web"
full = Image.open(D / "master-full.png").convert("RGBA")
fg = Image.open(D / "master-fg.png").convert("RGBA")
splash = Image.open(D / "master-splash.png").convert("RGBA")

def rounded(img, r=0.22):
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, img.width - 1, img.height - 1), int(img.width * r), fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0)); out.paste(img, (0, 0), m); return out

def circle(img):
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).ellipse((0, 0, img.width - 1, img.height - 1), fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0)); out.paste(img, (0, 0), m); return out

for dpi, s in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    d = RES / f"mipmap-{dpi}"
    rounded(full).resize((s, s), Image.LANCZOS).save(d / "ic_launcher.png")
    circle(full).resize((s, s), Image.LANCZOS).save(d / "ic_launcher_round.png")
    f = round(s * 108 / 48)
    fg.resize((f, f), Image.LANCZOS).save(d / "ic_launcher_foreground.png")
nod = RES / "drawable-nodpi"; nod.mkdir(exist_ok=True)
splash.resize((864, 864), Image.LANCZOS).save(nod / "splash_icon.png")
rounded(full).resize((512, 512), Image.LANCZOS).save(WEB / "icon-512.png")
rounded(full).resize((192, 192), Image.LANCZOS).save(WEB / "icon-192.png")
print("ok")
