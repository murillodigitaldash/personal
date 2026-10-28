// Gera PDF a partir de um HTML paginado (@page) e, opcionalmente, PNGs de prévia por página.
// uso: node tools/pdf.js <arquivo.html> <saida.pdf>
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [src, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('pageerror', e => console.error('pageerror', e.message));
  await page.goto('file://' + path.resolve(src));
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
  await browser.close();
})();
