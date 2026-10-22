/*
     ,_,
    (O,O)
    (   )   Mïmïr
  ---"-"---
*/
(() => {
  'use strict';
  const d = document, w = window, html = d.documentElement, body = d.body;
  const $ = (s, r = d) => r.querySelector(s);
  const $$ = (s, r = d) => Array.from(r.querySelectorAll(s));
  const MOBILE_UA = /Android|iPhone|iPad|iPod|webOS|BlackBerry|Opera Mini|Opera Mobi|IEMobile|Windows Phone|Kindle/i.test(navigator.userAgent);
  const EASE = {
    quadOut: t => t * (2 - t),
    quintOut: t => 1 - Math.pow(1 - t, 5),
    swing: t => 0.5 - Math.cos(t * Math.PI) / 2,
  };
  const CSS_EASE = { power1Out: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)', power4Out: 'cubic-bezier(0.23, 1, 0.32, 1)', swing: 'cubic-bezier(0.37, 0, 0.63, 1)' };
  const px = v => parseFloat(v) || 0;
  const BASE_URL = html.dataset.base || '/';
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const loaded = img => new Promise(r => {
    if (!img || (img.complete && img.naturalWidth)) return r();
    img.addEventListener('load', r, { once: true });
    img.addEventListener('error', r, { once: true });
  });
  const scrollTween = (to, ms, ease) => {
    const from = w.scrollY, t0 = performance.now();
    const step = now => {
      const p = Math.min(1, (now - t0) / ms);
      w.scrollTo(0, from + (to - from) * ease(p));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  const outer = el => {
    const cs = getComputedStyle(el);
    return { w: px(cs.width) + px(cs.marginLeft) + px(cs.marginRight), h: px(cs.height) + px(cs.marginTop) + px(cs.marginBottom) };
  };
  function layout(cont) {
    const sel = cont.dataset.itemSelector;
    const items = Array.from(cont.children).filter(el => el.matches(sel));
    if (!items.length) return;
    const cs = getComputedStyle(cont);
    const padL = px(cs.paddingLeft), padT = px(cs.paddingTop);
    const borderBox = cs.boxSizing === 'border-box';
    const contW = px(cs.width) - (borderBox ? padL + px(cs.paddingRight) + px(cs.borderLeftWidth) + px(cs.borderRightWidth) : 0);
    const sizeW = px(cs.width) + (borderBox ? 0 : padL + px(cs.paddingRight));
    items.forEach(it => { it.style.position = 'absolute'; });
    let maxY = 0;
    if (cont.dataset.layout === 'fitRows') {
      let x = 0, y = 0;
      items.forEach(it => {
        const s = outer(it);
        if (x !== 0 && s.w + x > contW) { x = 0; y = maxY; }
        it.style.left = ((x + padL) / sizeW * 100) + '%';
        it.style.top = (y + padT) + 'px';
        maxY = Math.max(maxY, y + s.h);
        x += s.w;
      });
    } else {
      const sizer = Array.from(cont.children).find(el => el.classList.contains('grid-sizer')) || items[0];
      let colW = outer(sizer).w || contW;
      let cols = contW / colW;
      const excess = colW - (contW % colW);
      cols = Math.max(1, Math[excess && excess < 1 ? 'round' : 'floor'](cols));
      const colYs = new Array(cols).fill(0);
      items.forEach(it => {
        const s = outer(it);
        const rem = s.w % colW;
        const span = Math.min(cols, Math[rem && rem < 1 ? 'round' : 'ceil'](s.w / colW));
        let group = colYs;
        if (span > 1) {
          group = [];
          for (let i = 0; i <= cols - span; i++) group.push(Math.max(...colYs.slice(i, i + span)));
        }
        const y = Math.min(...group), col = group.indexOf(y);
        it.style.left = ((colW * col + padL) / sizeW * 100) + '%';
        it.style.top = (y + padT) + 'px';
        for (let i = col; i < col + span; i++) colYs[i] = y + s.h;
      });
      maxY = Math.max(...colYs);
    }
    cont.style.position = 'relative';
    cont.style.height = (maxY + (borderBox ? padT + px(cs.paddingBottom) + px(cs.borderTopWidth) + px(cs.borderBottomWidth) : 0)) + 'px';
  }
  const grids = [];
  [['.vino-single-gallery-grid', '.vino-gallery-image', 'masonry'],
   ['.single-gallery-masonry', 'article', 'masonry'],
   ['.vino-portfolio-masonry', 'article', null]].forEach(([sel, item, mode]) => {
    $$(sel).forEach(c => {
      if (c.classList.contains('vino-parallax-portfolio')) return;
      c.dataset.itemSelector = item;
      c.dataset.layout = mode || (c.classList.contains('vino-grid') ? 'fitRows' : 'masonry');
      grids.push(c);
    });
  });
  const relayout = () => grids.forEach(layout);
  const relayoutPortfolios = () => grids.filter(c => c.classList.contains('vino-portfolio-masonry')).forEach(layout);
  relayout();
  let lastW = w.innerWidth, rT;
  w.addEventListener('resize', () => {
    clearTimeout(rT);
    rT = setTimeout(() => { if (w.innerWidth !== lastW) { lastW = w.innerWidth; relayout(); } }, 100);
  });
  if (d.fonts && d.fonts.ready) d.fonts.ready.then(relayout);

  const lazyDone = el => {
    el.classList.add('b-loaded');
    const p = el.parentNode;
    if (p && p.classList) { p.classList.remove('loading'); p.classList.add('loaded'); }
    relayoutPortfolios();
    setTimeout(() => $$('.hover-not-ready').forEach(h => { if (h.contains(el)) h.classList.remove('hover-not-ready'); }), 700);
  };
  const lazyLoad = el => {
    const src = el.getAttribute('data-src');
    if (!src) return;
    el.removeAttribute('data-src');
    if (el.tagName === 'IMG') {
      el.addEventListener('load', () => lazyDone(el), { once: true });
      el.addEventListener('error', () => lazyDone(el), { once: true });
      if (el.dataset.srcset) { el.sizes = el.dataset.sizes || '100vw'; el.srcset = el.dataset.srcset; }
      el.src = src;
    } else {
      const im = new Image();
      im.onload = im.onerror = () => { el.style.backgroundImage = `url("${src}")`; lazyDone(el); };
      im.src = src;
    }
  };
  const lazyIO = 'IntersectionObserver' in w ? new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { lazyIO.unobserve(e.target); lazyLoad(e.target); }
  }), { rootMargin: '150px 0px' }) : null;
  const observeLazy = root => $$('.b-lazy[data-src]', root).forEach(el => (lazyIO ? lazyIO.observe(el) : lazyLoad(el)));
  observeLazy(d);

  function revealSingleImages() {
    const vh = w.innerHeight;
    $$('.vc_single_image-wrapper:not(.loaded)').forEach(wr => {
      const img = $('img', wr);
      const mark = () => wr.classList.add('loaded');
      if (!img || (img.complete && img.naturalWidth)) return mark();
      const r = wr.parentNode.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh) return mark();
      img.loading = 'eager';
      Promise.race([loaded(img), wait(2500)]).then(mark);
    });
  }

  const overlay = $('.transition-overlay');
  const siteLoaded = () => d.dispatchEvent(new Event('vinoSiteLoaded'));
  const logo = $('.vino-img-nav-top');
  Promise.race([Promise.all([loaded(logo), d.fonts ? d.fonts.ready : 0]), wait(1500)]).then(() => {
    revealSingleImages();
    if (!overlay) return siteLoaded();
    const a = overlay.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 400, easing: CSS_EASE.power4Out });
    a.onfinish = () => { overlay.style.opacity = '0'; overlay.style.visibility = 'hidden'; siteLoaded(); };
  });

  d.addEventListener('vinoSiteLoaded', () => {
    const els = $$('[data-aos]');
    body.setAttribute('data-aos-easing', 'ease-out-quad');
    body.setAttribute('data-aos-duration', '600');
    body.setAttribute('data-aos-delay', '0');
    els.forEach(el => el.classList.add('aos-init'));
    if (!('IntersectionObserver' in w)) return els.forEach(el => el.classList.add('aos-animate'));
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('aos-animate'); io.unobserve(e.target); }
    }), { rootMargin: '0px 0px -50px 0px' });
    els.forEach(el => io.observe(el));
  }, { once: true });

  const fixedNav = $('#fixed-nav');
  if (fixedNav) {
    const limit = (parseFloat(fixedNav.dataset.height) || 0) + 300;
    let shown = false, ticking = false;
    const check = () => {
      ticking = false;
      const on = w.scrollY > limit;
      if (on !== shown) { shown = on; fixedNav.classList.toggle('show-fixed-nav', on); }
    };
    w.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(check); } }, { passive: true });
    check();
  }

  const navOverlay = $('.vino-nav-overlay'), bodyOverlay = $('.vino-body-overlay');
  const contentWidth = () => {
    const cs = getComputedStyle(body);
    return body.clientWidth - px(cs.paddingLeft) - px(cs.paddingRight);
  };
  $$('.vino-nav-burger').forEach(b => b.addEventListener('click', () => {
    if (!navOverlay) return;
    const open = navOverlay.classList.toggle('vino-overlay-open');
    if (!open) {
      setTimeout(() => {
        body.classList.remove('no-scroll');
        body.style.width = 'auto';
        if (fixedNav) fixedNav.style.width = 'auto';
      }, 600);
    } else {
      const cw = contentWidth() + 'px';
      body.style.width = cw;
      if (fixedNav) fixedNav.style.width = cw;
      body.classList.add('no-scroll');
    }
    if (bodyOverlay) bodyOverlay.classList.toggle('open');
  }));
  if (bodyOverlay) bodyOverlay.addEventListener('click', () => {
    navOverlay.classList.remove('vino-overlay-open');
    bodyOverlay.classList.remove('open');
    setTimeout(() => { body.classList.remove('no-scroll'); body.style.width = 'auto'; }, 600);
  });

  const search = $('.overlay-search');
  if (search) {
    const form = $('form', search);
    $$('.open-overlay-search').forEach(b => b.addEventListener('click', () => {
      search.style.display = 'flex';
      search.style.visibility = 'visible';
      search.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, easing: CSS_EASE.power1Out, fill: 'forwards' });
      form.animate([{ opacity: 0, transform: 'scale(1.5)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 400, easing: CSS_EASE.power1Out, fill: 'forwards' });
      setTimeout(() => { const i = $('input', search); if (i) i.focus({ preventScroll: true }); }, 50);
    }));
    const close = () => {
      const a = search.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 400, easing: CSS_EASE.power1Out, fill: 'forwards' });
      form.animate([{ opacity: 1, transform: 'scale(1)' }, { opacity: 0, transform: 'scale(1.5)' }], { duration: 400, easing: CSS_EASE.power1Out, fill: 'forwards' });
      a.onfinish = () => { search.style.display = 'none'; search.style.visibility = 'hidden'; };
    };
    search.addEventListener('click', e => {
      if (e.target === search || e.target.closest('.overlay-search-close')) close();
    });
  }

  const up = $('#scroll-up');
  if (up) {
    const check = () => up.classList.toggle('show-arrow', w.scrollY > 300);
    w.addEventListener('scroll', check, { passive: true });
    check();
    up.addEventListener('click', e => { e.preventDefault(); scrollTween(0, 1500, EASE.quintOut); });
  }

  const fixedNavH = () => (fixedNav ? fixedNav.getBoundingClientRect().height : 0);
  const toAnchor = hash => {
    if (!hash || hash === '#') return false;
    let t;
    try { t = $(hash); } catch { return false; }
    if (!t) return false;
    scrollTween(t.getBoundingClientRect().top + w.scrollY - fixedNavH(), 1000, EASE.quadOut);
    return true;
  };
  d.addEventListener('click', e => {
    const a = e.target.closest('a[href*="#"]');
    if (!a || a.hasAttribute('data-mfp-srcset')) return;
    const u = new URL(a.href, location.href);
    if (u.pathname === location.pathname && u.hash && toAnchor(u.hash)) {
      e.preventDefault();
      history.pushState('', '', u.hash);
    }
  });
  if (location.hash) setTimeout(() => toAnchor(location.hash), 500);

  w.addEventListener('load', () => {
    $$('.vino-single-portfolio').forEach(p => {
      const g = $('.vino-single-gallery', p), c = $('.single-portfolio-content', p);
      if (!g || !c) return;
      if (c.offsetHeight + 30 < g.offsetHeight - 30) {
        c.style.position = 'sticky';
        c.style.top = ((fixedNav ? fixedNav.offsetHeight : 0) + 40) + 'px';
      }
    });
    if (body.classList.contains('single-post')) {
      const meta = $('.single-post-meta'), inner = $('.single-post-inner-content');
      if (meta) {
        meta.style.position = 'sticky';
        meta.style.top = '40px';
        let bottom = false;
        const check = () => {
          const at = inner && w.scrollY + w.innerHeight >= (inner.offsetHeight / 4) * 3;
          if (at !== bottom) { bottom = at; meta.classList.toggle('at_bottom', at); }
        };
        w.addEventListener('scroll', check, { passive: true });
        check();
      }
      const ct = $('.comments-title');
      if (ct) { ct.style.position = 'sticky'; ct.style.top = '120px'; }
    }
    $$('.single-portfolio-large.vino-single-portfolio').forEach(p => {
      const c = $('.single-portfolio-content', p), bg = $('.portfolio-bg', p);
      if (c && bg) bg.style.height = (c.offsetHeight + 360) + 'px';
    });
  });

  const mfp = (() => {
    let items = [], index = 0, bg, wrap, container, content, img, counter, wH = 0, last, scrollTop = 0;
    const el = (tag, cls, attrs = {}) => { const e = d.createElement(tag); if (cls) e.className = cls; Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); return e; };
    const fixedPos = !MOBILE_UA;
    function size() {
      wH = w.innerHeight;
      if (!fixedPos) wrap.style.height = wH + 'px';
      if (img) {
        const cs = getComputedStyle(img);
        img.style.maxHeight = (wH - px(cs.paddingTop) - px(cs.paddingBottom)) + 'px';
      }
    }
    function render() {
      const it = items[index];
      content.textContent = '';
      container.classList.remove('mfp-s-ready', 'mfp-s-error', 'mfp-image-holder', 'mfp-iframe-holder');
      if (it.type === 'iframe') {
        container.classList.add('mfp-iframe-holder', 'mfp-s-ready');
        const sc = el('div', 'mfp-iframe-scaler');
        const close = el('button', 'mfp-close', { title: 'Close (Esc)', type: 'button' });
        close.textContent = '×';
        const fr = el('iframe', 'mfp-iframe', { src: it.src, frameborder: '0', allowfullscreen: '' });
        sc.append(close, fr);
        content.append(sc);
        img = null;
      } else {
        container.classList.add('mfp-image-holder', 'mfp-s-loading');
        const fig = el('div', 'mfp-figure');
        const close = el('button', 'mfp-close', { title: 'Close (Esc)', type: 'button' });
        close.textContent = '×';
        const figure = el('figure');
        img = el('img', 'mfp-img', { alt: 'undefined' });
        if (it.srcset) { img.sizes = it.w ? `(max-width: ${it.w}px) 100vw, ${it.w}px` : '100vw'; img.srcset = it.srcset; }
        const cap = el('figcaption');
        const bar = el('div', 'mfp-bottom-bar');
        const title = el('div', 'mfp-title');
        counter = el('div', 'mfp-counter');
        counter.textContent = items.length > 1 ? `${index + 1} of ${items.length}` : '';
        bar.append(title, counter);
        cap.append(bar);
        figure.append(img, cap);
        fig.append(close, figure);
        const show = () => { container.classList.remove('mfp-s-loading'); container.classList.add('mfp-s-ready'); };
        img.addEventListener('load', show, { once: true });
        img.addEventListener('error', () => { container.classList.remove('mfp-s-loading'); container.classList.add('mfp-s-error'); }, { once: true });
        img.src = it.src;
        content.append(fig);
        size();
        if (img.complete && img.naturalWidth) show();
      }
      [index + 1, index - 1, index + 2].forEach(i => {
        const p = items[(i + items.length) % items.length];
        if (p && p.type !== 'iframe') { const pre = new Image(); if (p.srcset) { pre.sizes = p.w ? `(max-width: ${p.w}px) 100vw, ${p.w}px` : '100vw'; pre.srcset = p.srcset; } pre.src = p.src; }
      });
    }
    function go(i) { index = (i + items.length) % items.length; render(); }
    function close() {
      if (!wrap) return;
      bg.remove(); wrap.remove();
      html.style.overflow = '';
      html.style.marginRight = '';
      w.removeEventListener('resize', size);
      d.removeEventListener('keydown', key);
      wrap = null;
      if (last && last.focus) last.focus({ preventScroll: true });
    }
    function key(e) {
      if (e.key === 'Escape') close();
      else if (items.length > 1 && e.key === 'ArrowLeft') go(index - 1);
      else if (items.length > 1 && e.key === 'ArrowRight') go(index + 1);
    }
    function open(list, i) {
      items = list; index = i; last = d.activeElement; scrollTop = w.scrollY;
      bg = el('div', 'mfp-bg');
      wrap = el('div', 'mfp-wrap' + (items.length > 1 ? ' mfp-gallery' : '') + ' mfp-close-btn-in mfp-auto-cursor', { tabindex: '-1' });
      container = el('div', 'mfp-container');
      content = el('div', 'mfp-content');
      const pre = el('div', 'mfp-preloader');
      pre.textContent = 'Loading...';
      container.append(content, pre);
      if (items.length > 1) {
        const l = el('button', 'mfp-arrow mfp-arrow-left mfp-prevent-close', { title: 'Previous (Left arrow key)', type: 'button' });
        const r = el('button', 'mfp-arrow mfp-arrow-right mfp-prevent-close', { title: 'Next (Right arrow key)', type: 'button' });
        l.addEventListener('click', e => { e.stopPropagation(); go(index - 1); });
        r.addEventListener('click', e => { e.stopPropagation(); go(index + 1); });
        container.append(l, r);
      }
      wrap.append(container);
      if (fixedPos) {
        wrap.style.overflowX = 'hidden';
        wrap.style.overflowY = 'auto';
        const sb = w.innerWidth - html.clientWidth;
        if (sb > 0) html.style.marginRight = sb + 'px';
        html.style.overflow = 'hidden';
      } else {
        wrap.style.top = scrollTop + 'px';
        wrap.style.position = 'absolute';
        bg.style.height = Math.max(html.scrollHeight, body.scrollHeight) + 'px';
        bg.style.position = 'absolute';
      }
      body.append(bg, wrap);
      wrap.addEventListener('click', e => {
        const t = e.target;
        if (t.closest('.mfp-close')) return close();
        if (t.classList.contains('mfp-img')) return items.length > 1 ? go(index + 1) : close();
        if (t.closest('.mfp-prevent-close')) return;
        if (!t.closest('.mfp-content')) close();
      });
      d.addEventListener('keydown', key);
      w.addEventListener('resize', size);
      render();
      setTimeout(() => { if (wrap) { bg.classList.add('mfp-ready'); wrap.classList.add('mfp-ready'); wrap.focus({ preventScroll: true }); } }, 16);
    }
    return { open };
  })();
  const LB_SCOPES = '.vino-single-gallery, .single-gallery-masonry';
  d.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    const scope = a.closest(LB_SCOPES);
    if (!scope || scope.classList.contains('single-gallery-slider')) return;
    e.preventDefault();
    const links = $$('a', scope);
    const list = links.map(l => ({ src: l.href, srcset: l.dataset.mfpSrcset, w: +l.dataset.mfpW || 0, type: l.classList.contains('mfp-iframe') ? 'iframe' : 'image' }));
    mfp.open(list, links.indexOf(a));
  });

  $$('.vino-post-gallery').forEach(g => {
    const wrapper = $('.swiper-wrapper', g);
    if (!wrapper) return;
    const slides = $$('.swiper-slide', wrapper);
    g.classList.add('swiper-container-horizontal');
    if (slides.length < 2) return;
    const first = slides[0].cloneNode(true), lastS = slides[slides.length - 1].cloneNode(true);
    first.classList.add('swiper-slide-duplicate');
    lastS.classList.add('swiper-slide-duplicate');
    wrapper.append(first);
    wrapper.prepend(lastS);
    let i = 1, busy = false;
    const all = () => $$('.swiper-slide', wrapper);
    const set = (anim) => {
      wrapper.style.transitionDuration = anim ? '1000ms' : '0ms';
      wrapper.style.transform = `translate3d(${-i * g.clientWidth}px, 0, 0)`;
      all().forEach((s, k) => {
        s.style.width = g.clientWidth + 'px';
        s.classList.toggle('swiper-slide-active', k === i);
        s.classList.toggle('swiper-slide-next', k === i + 1);
        s.classList.toggle('swiper-slide-prev', k === i - 1);
      });
    };
    const move = dir => {
      if (busy) return;
      busy = true;
      i += dir;
      set(true);
      setTimeout(() => {
        if (i === 0) i = slides.length;
        if (i === slides.length + 1) i = 1;
        set(false);
        busy = false;
      }, 1000);
    };
    set(false);
    const arrows = g.parentNode.querySelector('.vino-carousel-arrows') || g.querySelector('.vino-carousel-arrows');
    if (arrows) {
      const prev = $('.arrow-prev', arrows), next = $('.arrow-next', arrows);
      if (prev) prev.addEventListener('click', () => move(-1));
      if (next) next.addEventListener('click', () => move(1));
    }
    w.addEventListener('resize', () => set(false));
  });

  $$('.blog-list, .blog-grid').forEach(blog => {
    const btn = $('.vino-load-more', blog);
    const inner = blog.classList.contains('blog-list') ? $('.blog-post-content', blog) : $('.blog-grid-wrapper', blog);
    if (!btn || !inner) return;
    let page = 2, busy = false;
    btn.addEventListener('click', e => {
      e.preventDefault();
      if (busy) return;
      busy = true;
      const ds = blog.dataset;
      const data = new URLSearchParams({ page, posts_per_page: ds.ppp || '', imgbg: ds.imgbg || '', categories: ds.cat || '', grid_class: ds.gridClass || '',
        alignment: ds.alignment || '', show_img: ds.showImg || '', show_cat: ds.showCat || '', style: ds.style || '' });
      fetch('https://www.dao-arts.it/wp-json/wp/v2/blog/', { method: 'POST', body: data })
        .then(r => r.json())
        .then(res => {
          inner.insertAdjacentHTML('beforeend', String(res.output || '').replace(/https?:\/\/(www\.)?dao-arts\.it\/(?!wp-content)/g, BASE_URL));
          observeLazy(inner);
          setTimeout(() => $$('.post-meta:not(.loaded-post)').forEach(m => m.classList.add('loaded-post')), 100);
          if (res.next === false) btn.remove(); else page = res.next;
        })
        .finally(() => { busy = false; });
    });
  });

  w.addEventListener('load', () => {
    const top = el => el.getBoundingClientRect().top + w.scrollY;
    $$('.first-li').forEach(li => {
      const av = $('.comment-author-avatar', li), bl = li.parentElement.querySelector(':scope > .border-list');
      if (av && bl) bl.style.top = (top(av) - top(li.parentElement)) + 'px';
    });
    $$('.last-li').forEach(li => {
      const av = $('.comment-author-avatar', li), bl = li.parentElement.querySelector(':scope > .border-list');
      if (!av || !bl) return;
      const listBottom = top(li) + li.offsetHeight;
      const nested = li.querySelector(':scope > .comment-list > .last-li .comment-author-avatar');
      bl.style.bottom = (listBottom - (nested ? top(nested) + 30 : top(av) + 60)) + 'px';
    });
  });

  $$('.vino-input').forEach(vi => {
    const field = () => $('input, textarea, select', vi);
    const f = field();
    if (!f) return;
    if (f.value.length) vi.classList.add('active-input');
    vi.addEventListener('focusin', e => { if (e.target.matches('input, textarea, select')) vi.classList.add('active-input'); });
    vi.addEventListener('focusout', e => { if (e.target.matches('input, textarea, select')) vi.classList.toggle('active-input', field().value.length > 0); });
  });
  $$('.wpcf7 .vino-input').forEach(vi => vi.addEventListener('keyup', () => {
    if (!$('span.wpcf7-not-valid-tip', vi)) return;
    const f = $('input, textarea, select', vi);
    f.classList.toggle('wpcf7-not-valid', f.value.length === 0);
  }));

  const bar = $('#cookie-law-info-bar');
  if (bar) {
    if (!/(^|;\s*)viewed_cookie_policy=/.test(d.cookie)) bar.style.display = 'block';
    const accept = $('#cookie_action_close_header');
    if (accept) accept.addEventListener('click', e => {
      e.preventDefault();
      d.cookie = 'viewed_cookie_policy=yes; max-age=31536000; path=/; SameSite=Lax';
      const cs = getComputedStyle(bar);
      bar.style.overflow = 'hidden';
      const a = bar.animate([
        { height: bar.offsetHeight + 'px', paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, marginTop: cs.marginTop, marginBottom: cs.marginBottom },
        { height: '0px', paddingTop: '0px', paddingBottom: '0px', marginTop: '0px', marginBottom: '0px' },
      ], { duration: 500, easing: CSS_EASE.swing });
      a.onfinish = () => { bar.style.display = 'none'; bar.style.overflow = ''; };
    });
  }

  const results = $('[data-search-proto]');
  if (results) {
    const q = (new URLSearchParams(location.search).get('s') || '').trim();
    const page = Math.max(1, parseInt(new URLSearchParams(location.search).get('paged'), 10) || 1);
    $$('input[name="s"]').forEach(i => { i.value = q; if (q) i.closest('.vino-input')?.classList.add('active-input'); });
    const label = $('.search-results-header .page-title span');
    if (label) label.textContent = ' ' + q;
    if (q) d.title = `Hai cercato ${q} « Daò`;
    const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const words = norm(q).split(/\s+/).filter(Boolean);
    fetch(BASE_URL + 'search.json').then(r => r.json()).then(data => {
      const scored = data.map(e => {
        const t = norm(e.t), x = norm(e.x);
        const inTitle = words.length && words.every(wd => t.includes(wd));
        const any = words.length && words.every(wd => t.includes(wd) || x.includes(wd));
        return { e, s: !any ? 0 : inTitle && t.includes(norm(q)) ? 1 : inTitle ? 2 : words.some(wd => t.includes(wd)) ? 3 : x.includes(norm(q)) ? 5 : 6 };
      }).filter(r => r.s).sort((a, b) => a.s - b.s || (b.e.d || '').localeCompare(a.e.d || ''));
      if (!scored.length) {
        const wrapper = $('.page-wrapper-inner');
        wrapper.outerHTML = results.dataset.searchEmpty;
        $$('input[name="s"]').forEach(i => { i.value = q; });
        return;
      }
      const per = 10, total = Math.ceil(scored.length / per), cur = Math.min(page, total);
      const tpl = d.createElement('template');
      tpl.innerHTML = results.dataset.searchProto;
      const proto = tpl.content.firstElementChild;
      scored.slice((cur - 1) * per, cur * per).forEach(({ e }) => {
        const n = proto.cloneNode(true);
        $$('a[rel="bookmark"], .post-title a, .blog-simple-more a', n).forEach(a => { a.href = e.u; });
        const time = $('time', n);
        if (time) { time.textContent = e.dt; time.setAttribute('datetime', e.d || ''); }
        const span = $('.post-title a span', n);
        if (span) span.textContent = e.t;
        const ul = $('.post-cat-meta', n);
        $$('li:not(.posted-on):not(.categories-in-class)', ul).forEach(li => li.remove());
        e.c.forEach(c => { const li = d.createElement('li'); const a = d.createElement('a'); a.href = c.u; a.title = c.n; a.textContent = c.n; li.append(a); ul.append(li); });
        results.append(n);
      });
      if (total > 1) {
        const link = p => `${location.pathname}?s=${encodeURIComponent(q)}${p > 1 ? '&paged=' + p : ''}`;
        let h = '<nav class="navigation pagination" aria-label="Articoli"><h2 class="screen-reader-text">Navigazione articoli</h2><div class="nav-links">';
        if (cur > 1) h += `<a class="prev page-numbers" href="${link(cur - 1)}"><div class="previous-page arrow arrow-prev"><div class="arrow-icon"><i class="fa fa-angle-left"></i></div></div></a>`;
        let dots = false;
        for (let n = 1; n <= total; n++) {
          if (n === cur) { h += `<span aria-current="page" class="page-numbers current">${n}</span>`; dots = true; }
          else if (n <= 1 || (n >= cur - 1 && n <= cur + 1) || n > total - 1) { h += `<a class="page-numbers" href="${link(n)}">${n}</a>`; dots = true; }
          else if (dots) { h += '<span class="page-numbers dots">…</span>'; dots = false; }
        }
        if (cur < total) h += `<a class="next page-numbers" href="${link(cur + 1)}"><div class="next-page arrow arrow-next"><div class="arrow-icon"><i class="fa fa-angle-right"></i></div></div></a>`;
        results.insertAdjacentHTML('beforeend', h + '</div></nav>');
      }
    });
  }

  const protetta = t => {
    for (let n = t, i = 0; n && n.nodeType === 1 && n !== body && i < 4; n = n.parentElement, i++) {
      if (n.tagName === 'IMG' || n.tagName === 'VIDEO' || getComputedStyle(n).backgroundImage !== 'none') return true;
    }
    return false;
  };
  ['contextmenu', 'dragstart'].forEach(ev => d.addEventListener(ev, e => { if (protetta(e.target)) e.preventDefault(); }));
  $$('video').forEach(v => v.setAttribute('controlslist', 'nodownload'));
})();
