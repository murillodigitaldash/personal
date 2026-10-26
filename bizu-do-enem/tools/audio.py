# Monta a narração com pausas, mixa efeitos sonoros, normaliza (−14 LUFS) e gera o .srt.
# uso: python3 tools/audio.py <dir_video> <json_config>
#  config: {"cuts": [[t, pausa], ...], "tail": 1.3, "sfx": [[nome, t_final, dB], ...], "srt": "entrega/X.srt"}
import json, subprocess, sys, os
d, cfg = sys.argv[1], json.loads(sys.argv[2])
cuts = cfg['cuts']; SFX = os.path.join(os.path.dirname(__file__), '..', 'video-001', 'audio', 'sfx')
T = lambda t: t + sum(p for c, p in cuts if t > c)
src = f'{d}/audio/narracao_take1.mp3'; pts = [0] + [c for c, _ in cuts] + [None]; parts = []
for i in range(len(pts) - 1):
    a, b = pts[i], pts[i + 1]; fn = f'{d}/audio/_p{i}.wav'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-af', f"atrim={a}" + (f":{b}" if b else "") + ",asetpts=PTS-STARTPTS", '-ac', '1', '-ar', '44100', fn], check=True); parts.append(fn)
    if i < len(cuts):
        sn = f'{d}/audio/_s{i}.wav'; subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', str(cuts[i][1]), sn], check=True); parts.append(sn)
ins = sum((['-i', p] for p in parts), [])
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + ins + ['-filter_complex', ''.join(f'[{k}]' for k in range(len(parts))) + f'concat=n={len(parts)}:v=0:a=1', f'{d}/audio/voz_editada.wav'], check=True)
[os.remove(p) for p in parts]
W = json.load(open(f'{d}/audio/palavras_take1.json')); DUR = T(W[-1]['e']) + cfg.get('tail', 1.3)
ins = ['-i', f'{d}/audio/voz_editada.wav']; fl = []; labs = []
for k, (f, t, g) in enumerate(cfg['sfx']):
    ins += ['-i', f'{SFX}/{f}.wav']; ms = int(t * 1000)
    fl.append(f'[{k+1}]adelay={ms}|{ms},volume={g}dB[e{k}]'); labs.append(f'[e{k}]')
fl.append("[0]aformat=channel_layouts=stereo,highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2[v]")
fl.append(f"[v]{''.join(labs)}amix=inputs={len(cfg['sfx'])+1}:normalize=0:duration=first,apad=whole_dur={DUR},atrim=0:{DUR}[m]")
fl.append("[m]loudnorm=I=-14:TP=-1.5:LRA=9:print_format=summary[out]")
r = subprocess.run(['ffmpeg', '-y', '-hide_banner'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[out]', '-ar', '48000', '-c:a', 'pcm_s16le', f'{d}/audio/mix_final.wav'], capture_output=True, text=True)
print('\n'.join(l for l in r.stderr.splitlines() if 'Output Integrated' in l or 'Output True' in l or 'rror' in l))
blocks = []; cur = []
for w in W:
    cur.append((w['w'], T(w['s']), T(w['e'])))
    if w['w'][-1] in '.?:,' or len(cur) >= 5: blocks.append(cur); cur = []
if cur: blocks.append(cur)
fmt = lambda t: f"{int(t//3600):02}:{int(t%3600//60):02}:{int(t%60):02},{int(round(t%1*1000))%1000:03}"
tt = [[b[0][1], b[-1][2] + .15] for b in blocks]
for i in range(len(tt) - 1): tt[i][1] = min(tt[i][1], tt[i+1][0] - .03)
os.makedirs(f'{d}/entrega', exist_ok=True)
open(f"{d}/{cfg['srt']}", 'w').write('\n\n'.join(f"{i}\n{fmt(a)} --> {fmt(e)}\n{' '.join(x[0] for x in b)}" for i, (b, (a, e)) in enumerate(zip(blocks, tt), 1)) + '\n')
print(f'DUR {DUR:.3f}s · {len(blocks)} blocos de legenda')
