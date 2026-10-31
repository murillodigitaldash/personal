// uso: node stills.js <video.html> <saida_dir> t1 t2 ...
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs');
(async () => {
  const [html, out, ...times] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type()==='error' && errs.push(m.text()));
  await p.goto('file://' + path.resolve(html)); await p.evaluate(() => document.fonts.ready);
  console.log('DUR', await p.evaluate(() => window.DUR));
  for (const t of times) { await p.evaluate(t => window.renderAt(+t), t);
    await p.screenshot({ path: path.join(out, `t_${(+t).toFixed(2).padStart(6,'0')}.png`) }); }
  if (errs.length) console.log('ERROS:', errs);
  await b.close();
})();
