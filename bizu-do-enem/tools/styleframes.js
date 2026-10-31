const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dir = process.argv[2]; const safe = process.argv[3]==='safe';
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('console', m => console.log('console:', m.text()));
  p.on('pageerror', e => console.log('ERR', e.message));
  for (let f = 1; f <= +(process.argv[4]||8); f++) {
    await p.goto('file://' + path.join(dir, 'frames.html') + `?f=${f}` + (safe?'&safe=1':''));
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(dir, `${safe?'safe_':''}sf0${f}.png`) });
  }
  await b.close();
})();
