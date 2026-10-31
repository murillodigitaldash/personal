// Render quadro a quadro com motion blur (3 subquadros, obturador 180°) → segmentos MP4.
// uso: node render.js <video.html> <saida_dir> [workers] [fps]
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs');
const { spawn } = require('child_process');
const [html, out, W = '4', F = '30'] = process.argv.slice(2);
const FPS = +F, SUB = 3, SHUTTER = 0.5; fs.mkdirSync(out, { recursive: true });
async function worker(id, n0, n1, browser) {
  const p = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + path.resolve(html)); await p.evaluate(() => document.fonts.ready);
  for (let t = 0; t < n0 / FPS; t += 0.1) await p.evaluate(t => window.renderAt(t), t); // aquece a timeline em ordem
  const seg = path.join(out, `seg_${String(id).padStart(2, '0')}.mp4`);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-c:v', 'mjpeg', '-i', '-',
    '-vf', `tmix=frames=${SUB},select='eq(mod(n\\,${SUB})\\,${SUB - 1})',setpts=N/${FPS}/TB`, '-r', String(FPS),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', seg],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let n = n0; n < n1; n++) for (let k = 0; k < SUB; k++) {
    const t = n / FPS + (k / (SUB - 1) - 0.5) * SHUTTER / FPS; // centrado no quadro
    await p.evaluate(t => window.renderAt(Math.max(0, t)), t);
    const buf = await p.screenshot({ type: 'jpeg', quality: 96 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (id === 0 && k === 0 && n % 30 === 0) console.log(`w0 ${n - n0}/${n1 - n0}`);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await p.close(); return seg;
}
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage(); await p.goto('file://' + path.resolve(html));
  const DUR = await p.evaluate(() => window.DUR); await p.close();
  const N = Math.ceil(DUR * FPS), nw = +W, per = Math.ceil(N / nw);
  console.log(`DUR ${DUR}s → ${N} quadros × ${SUB} subquadros, ${nw} workers`);
  const t0 = Date.now();
  const segs = await Promise.all([...Array(nw).keys()].map(i => worker(i, i * per, Math.min(N, (i + 1) * per), b)));
  fs.writeFileSync(path.join(out, 'segs.txt'), segs.map(s => `file '${path.basename(s)}'`).join('\n'));
  console.log(`ok em ${((Date.now() - t0) / 1000).toFixed(0)}s`); await b.close();
})();
