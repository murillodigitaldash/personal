// Bizu do Enem — motor de motion compartilhado (GSAP + render por tempo)
// uso: const {tl, show, up, out, chap, sweep, mask, $, $$} = MOTION.init({chapters:[...], dur});
//      ... monta cenas em #scenes e a timeline ...; MOTION.ready();
const MOTION = (() => {
  // aleatoriedade determinística: todos os workers de render veem os mesmos valores
  Math.random = (() => { let x = 20261026; return () => ((x = Math.imul(x ^ (x >>> 15), x | 1) ^ (x + Math.imul(x ^ (x >>> 7), x | 61)), ((x ^ (x >>> 14)) >>> 0) / 4294967296)); })();
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const mask = (txt, id, cls = '') => `<div class="mask"><span id="${id}" class="${cls}">${txt}</span></div>`;
  let tl, DUR;
  function init({ chapters, dur }) {
    DUR = dur;
    const st = $('#stage'); st.classList.add('frame');
    st.insertAdjacentHTML('afterbegin', '<div class="glow" id="g1"></div><div class="glow" id="g2"></div><div class="glow" id="g3"></div>');
    st.insertAdjacentHTML('beforeend', `<div class="brand">${KIT.MARK(54)}<div class="word">bizu<b>DO ENEM</b></div></div>
      <div class="chapter"><div id="chapInner">${chapters.map((c, i) => `<div><i>${String(i + 1).padStart(2, '0')}</i> / ${c}</div>`).join('')}</div></div>
      <div id="sweep"></div><div class="vignette"></div><div class="grain"></div>`);
    gsap.defaults({ ease: 'power3.out', duration: .6 });
    tl = gsap.timeline({ paused: true });
    const show = (sel, t0, t1) => { tl.set(sel, { visibility: 'visible' }, t0); if (t1 != null) tl.set(sel, { visibility: 'hidden' }, t1); };
    const up = (sel, t, o = {}) => tl.from(sel, { yPercent: 110, duration: .7, ease: 'expo.out', ...o }, t);
    const out = (sel, t, o = {}) => tl.to(sel, { yPercent: -110, duration: .42, ease: 'power3.in', ...o }, t);
    const chap = (i, t) => tl.to('#chapInner', { y: -26 * i, duration: .5, ease: 'power3.inOut' }, t);
    const sweep = t => { tl.fromTo('#sweep', { x: 0 }, { x: 1700, duration: .55, ease: 'power2.inOut', immediateRender: false }, t);
      tl.fromTo('#sweep', { opacity: 0 }, { opacity: 1, duration: .27, yoyo: true, repeat: 1, ease: 'sine.inOut', immediateRender: false }, t); };
    const pulse = (sel, t, s = 1.1) => tl.fromTo(sel, { scale: 1 }, { scale: s, duration: .2, yoyo: true, repeat: 1, ease: 'power2.out', immediateRender: false }, t);
    // fundo vivo + câmera
    tl.fromTo('#g1', { x: 0, y: 0 }, { x: -260, y: 180, duration: DUR, ease: 'sine.inOut' }, 0);
    tl.fromTo('#g2', { x: 0, y: 0 }, { x: 380, y: -260, duration: DUR, ease: 'sine.inOut' }, 0);
    tl.fromTo('#g3', { x: 0, y: 0, opacity: .4 }, { x: -420, y: -200, opacity: 1, duration: DUR, ease: 'sine.inOut' }, 0);
    tl.fromTo('#scenes', { scale: 1 }, { scale: 1.035, duration: DUR, ease: 'sine.inOut', transformOrigin: '50% 45%' }, 0);
    tl.from('#stage .brand', { opacity: 0, x: -30, duration: .6 }, 0.05);
    tl.from('#stage .chapter', { opacity: 0, duration: .5 }, 0.2);
    return { tl, show, up, out, chap, sweep, pulse, mask, $, $$ };
  }
  function ready(post) {
    tl.to({}, { duration: DUR }, 0);
    const grain = $('#stage .grain');
    window.DUR = DUR;
    window.renderAt = t => { tl.seek(t, false);
      const f = Math.floor(t * 24), r = (Math.sin(f * 12.9898) * 43758.5453) % 1;
      grain.style.transform = `translate(${(r * 120) | 0}px,${((r * 7.31 % 1) * 120) | 0}px)`;
      if (post) post(t); };
    window.renderAt(0);
  }
  return { init, ready, mask, $, $$ };
})();
