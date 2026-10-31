# Troca trechos estrangeiros da narração em PT por versões com sotaque nativo (mesma voz, geração separada).
# uso: python3 tools/splice.py <dir_video> <json_config>
#  config: {"pt": "audio/narracao_take1.mp3", "pt_words": "audio/palavras_take1.json",
#           "fx": "audio/ingles_take1.mp3", "fx_words": "audio/palavras_ingles.json",
#           "swaps": [[pt_i0, pt_i1, fx_i0, fx_i1], ...]}   (índices de palavra, inclusivos)
# saída: audio/narracao_nativa.wav e audio/palavras_nativa.json ({w,s,e}, tempos da nova narração)
import json, subprocess, sys
import numpy as np
d, cfg = sys.argv[1], json.loads(sys.argv[2]); SR = 44100
def load(p):
    r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', f'{d}/{p}', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)
def words(p):
    w = json.load(open(f'{d}/{p}')); w = w['words'] if isinstance(w, dict) else w
    return [{'w': x.get('text', x.get('w')), 's': x.get('start', x.get('s')), 'e': x.get('end', x.get('e'))} for x in w if x.get('type', 'word') == 'word']
pt, fx = load(cfg['pt']), load(cfg['fx']); PW, FW = words(cfg['pt_words']), words(cfg['fx_words'])
def bounds(W, i0, i1, total, pre=.05, post=.09):
    # corta no silêncio: no máximo metade do intervalo até a palavra vizinha
    a = W[i0]['s'] - min(pre, (W[i0]['s'] - W[i0-1]['e']) / 2 if i0 > 0 else pre)
    b = W[i1]['e'] + min(post, (W[i1+1]['s'] - W[i1]['e']) / 2 if i1 + 1 < len(W) else post)
    return max(a, 0), min(b, total)
def fade(x, ms=6):
    n = min(int(SR * ms / 1000), len(x) // 2); r = np.linspace(0, 1, n, dtype=np.float32)
    x = x.copy(); x[:n] *= r; x[-n:] *= r[::-1]; return x
out, ow, cur, shift = [], [], 0.0, 0.0
swaps = sorted(cfg['swaps']); k = 0; i = 0
while i < len(PW):
    if k < len(swaps) and i == swaps[k][0]:
        p0, p1, f0, f1 = swaps[k]
        a, b = bounds(PW, p0, p1, len(pt) / SR); fa, fb = bounds(FW, f0, f1, len(fx) / SR)
        out.append(fade(pt[int(cur * SR):int(a * SR)])); seg = fade(fx[int(fa * SR):int(fb * SR)]); out.append(seg)
        base = a + shift
        for j in range(f0, f1 + 1): ow.append({'w': FW[j]['w'], 's': round(base + FW[j]['s'] - fa, 3), 'e': round(base + FW[j]['e'] - fa, 3), 'fx': 1})
        shift += (fb - fa) - (b - a); cur = b; i = p1 + 1; k += 1
    else:
        ow.append({'w': PW[i]['w'], 's': round(PW[i]['s'] + shift, 3), 'e': round(PW[i]['e'] + shift, 3)}); i += 1
out.append(pt[int(cur * SR):]); y = np.concatenate(out)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'pcm_s16le', f'{d}/audio/narracao_nativa.wav'], input=y.tobytes(), check=True)
json.dump(ow, open(f'{d}/audio/palavras_nativa.json', 'w'), ensure_ascii=False)
print(f'{len(PW)}→{len(ow)} palavras · {len(pt)/SR:.2f}s → {len(y)/SR:.2f}s')
for x in ow:
    if x.get('fx'): print(f"  {x['w']:<12} {x['s']:.3f}-{x['e']:.3f}")
