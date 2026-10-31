# Preenche o template da composição com as palavras da narração: python3 tools/build_tpl.py video-XXX [palavras.json]
import json, sys
d = sys.argv[1]; wf = sys.argv[2] if len(sys.argv) > 2 else 'audio/palavras_take1.json'
W = json.load(open(f'{d}/{wf}'))
s = open(f'{d}/motion/video.tpl.html').read().replace('__WORDS__', json.dumps([{'w': x['w'], 's': x['s'], 'e': x['e']} for x in W], ensure_ascii=False))
open(f'{d}/motion/video.html', 'w').write(s)
