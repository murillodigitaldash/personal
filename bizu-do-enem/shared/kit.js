// Bizu do Enem — componentes compartilhados (styleframes e motion)
const KIT = (() => {
  const CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 12.5l5 5L19.5 7"/></svg>`;
  const CROSS = (c = '#A9B1C4') => `<svg viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
  const tok = (k, s = 64, cls = '') => `<div class="tok ${k} ${cls}" style="--s:${s}px">${k === 'ok' ? CHECK : k === 'warn' ? CROSS('#FFC400') : CROSS()}</div>`;
  const MARK = (size, { bg = '#6C3BFF', fg = '#fff', bolt = '#FFC400' } = {}) => `<svg width="${size}" height="${size}" viewBox="0 0 120 120">
    <rect width="120" height="120" rx="34" fill="${bg}"/><rect x="27" y="20" width="17" height="78" rx="8.5" fill="${fg}"/>
    <circle cx="60" cy="72" r="23" fill="none" stroke="${fg}" stroke-width="17"/>
    <path d="M92 10 L81 29 L90 29 L84 45 L103 24 L93 24 L100 10 Z" fill="${bolt}"/></svg>`;
  const brand = (ch, l) => `<div class="brand">${MARK(54)}<div class="word">bizu<b>DO ENEM</b></div></div><div class="chapter"><i>${ch}</i> / ${l}</div>`;
  const shell = i => `<div class="frame">${i}<div class="vignette"></div><div class="grain"></div><div class="safe"><div class="top"></div><div class="bot"></div><div class="right"></div></div></div>`;
  const ctaFollow = (sub = 'pra revisar na véspera') => `
    <div class="card" style="width:846px;padding:36px 40px;display:flex;align-items:center;gap:30px">
      <div style="width:120px;height:120px;border-radius:32px;background:var(--amarelo);display:grid;place-items:center;box-shadow:0 0 50px rgba(255,196,0,.45)">
        <svg width="58" height="58" viewBox="0 0 24 24" fill="#0F172A"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4.5L5 21V4a1 1 0 0 1 1-1z"/></svg></div>
      <div><div style="font:800 44px/1 var(--display)">Salva</div><div class="note" style="color:var(--cinza-2);margin-top:10px">${sub}</div></div></div>
    <div class="card" style="width:846px;padding:36px 40px;display:flex;align-items:center;gap:30px">
      ${MARK(120)}
      <div style="flex:1"><div style="font:900 44px/1 var(--display);letter-spacing:-1.5px">bizu <span style="font:800 22px/1 var(--display);letter-spacing:3px;color:var(--amarelo);vertical-align:8px">DO ENEM</span></div>
        <div class="note" style="color:var(--cinza-2);margin-top:10px">um bizu por vídeo</div></div>
      <div class="pill" style="background:var(--roxo);font-size:32px;padding:20px 30px;box-shadow:0 14px 40px rgba(108,59,255,.5)">Seguir</div></div>`;
  const page = () => { const P = new URLSearchParams(location.search); if (P.get('safe')) document.body.classList.add('show-safe'); return +(P.get('f') || 1); };
  return { CHECK, CROSS, tok, MARK, brand, shell, ctaFollow, page };
})();
