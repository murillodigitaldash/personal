# uso: python3 prancha.py <dir_styleframes> "<titulo>" "<rotulo1>" "<rotulo2>" ...
import sys, glob
from PIL import Image, ImageDraw, ImageFont
d0, titulo, labels = sys.argv[1], sys.argv[2], sys.argv[3:]
def f(name, sz):
    p = [x for x in glob.glob('/usr/share/fonts/**/*', recursive=True) if name in x.split('/')[-1]]; return ImageFont.truetype(p[0], sz)
n = len(labels); cols = 4 if n > 6 else 3; rows = (n + cols - 1) // cols
def board(prefix, out):
    W, H, m, top, lab = 540, 960, 40, 150, 56
    B = Image.new('RGB', (cols*W + (cols+1)*m, top + rows*(H+lab) + (rows+1)*m), '#0B1122'); d = ImageDraw.Draw(B)
    d.text((m, 46), titulo, font=f('InterDisplay-ExtraBold', 40), fill='#FFFFFF')
    d.text((m, 108), "Prancha de styleframes · 9:16 · 1080×1920 · para aprovação" + (" · áreas seguras em vermelho" if prefix else ""), font=f('JetBrainsMono-Regular', 24), fill='#A9B1C4')
    for k in range(n):
        r, c = divmod(k, cols); x = m + c*(W+m); y = top + m + r*(H+lab+m)
        B.paste(Image.open(f'{d0}/{prefix}sf{k+1:02d}.png').resize((W, H), Image.LANCZOS), (x, y))
        d.text((x, y+H+16), labels[k], font=f('JetBrainsMono-Medium', 22), fill='#FFC400' if k in (0, n-1) else '#E7EAF0')
    B.save(f'{d0}/{out}')
board('', 'prancha_v1.png'); board('safe_', 'prancha_v1_areas_seguras.png')
