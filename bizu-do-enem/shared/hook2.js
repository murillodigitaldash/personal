// Bizu do Enem — gancho 2.0 (31/10/2026): selo de contagem regressiva e legenda queimada da fala.
// uso: const H = HOOK2.init({faltam: 7, words: W, T}); ... MOTION.ready(t => H.update(t));
const HOOK2 = (() => {
  function init({ faltam, words, T = t => t, y = 1360 }) {
    const st = document.querySelector('#stage');
    st.insertAdjacentHTML('beforeend', `
      <div id="h2badge" style="position:absolute;right:150px;top:318px;z-index:41;display:flex;align-items:center;gap:10px;padding:10px 18px;border-radius:999px;background:var(--amarelo);color:var(--navy);font:900 24px/1 var(--display);letter-spacing:.5px;box-shadow:0 8px 24px rgba(255,196,0,.35)">
        <span style="width:12px;height:12px;border-radius:50%;background:#E5484D"></span>FALTAM ${faltam} DIAS</div>
      <div id="h2cap" style="position:absolute;left:60px;width:870px;top:${y}px;height:120px;z-index:42;display:flex;align-items:center;justify-content:center;text-align:center">
        <div id="h2txt" style="padding:14px 26px;border-radius:22px;background:rgba(11,16,32,.82);border:1.5px solid rgba(255,255,255,.12);font:800 44px/1.15 var(--display);letter-spacing:-.5px;color:#fff;max-width:870px"></div></div>`);
    // blocos de até 4 palavras, quebrando em pontuação
    const B = []; let cur = [];
    words.forEach(w => { cur.push(w); if (/[.?!:;,]$/.test(w.w) || cur.length >= 4) { B.push(cur); cur = []; } });
    if (cur.length) B.push(cur);
    const blocks = B.map(b => ({ s: T(b[0].s), e: T(b[b.length - 1].e), w: b.map(x => ({ w: x.w, s: T(x.s) })) }));
    const box = document.querySelector('#h2cap'), txt = document.querySelector('#h2txt');
    let last = -2;
    function update(t) {
      let i = blocks.findIndex((b, k) => t >= b.s - .05 && (k + 1 >= blocks.length ? t <= b.e + .6 : t < blocks[k + 1].s - .05));
      box.style.visibility = i < 0 ? 'hidden' : 'visible';
      if (i < 0) return;
      txt.innerHTML = blocks[i].w.map(x => `<span style="color:${t >= x.s ? '#FFC400' : '#fff'}">${x.w}</span>`).join(' ');
      last = i;
    }
    return { update, blocks };
  }
  return { init };
})();
