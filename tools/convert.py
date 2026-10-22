# ,_,
# (O,O)
# (   )   Mïmïr
# -"-"-
import hashlib, html, json, math, os, re, shutil, subprocess, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup, Comment
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MIRROR, DIST, CACHE, SRC = ROOT / 'mirror', ROOT / 'dist', ROOT / '.cache', ROOT / 'src'
BASE = os.environ.get('BASE', '/dao-arts/')
SITE_URL = os.environ.get('SITE_URL', 'https://domydm85-cmd.github.io/dao-arts/')
MEASURE = os.environ.get('MEASURE') == '1'
NOINDEX = os.environ.get('NOINDEX') == '1'
ORIGIN = 'https://www.dao-arts.it'
HOSTS = {'www.dao-arts.it', 'dao-arts.it'}
SIZED = re.compile(r'^(.*)-(\d+)x(\d+)(\.[a-z0-9]+)$', re.I)
IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
STD_WIDTHS = (320, 480, 640, 800, 1024, 1280, 1600, 2048)
MAX_W = 2048
BUNDLE_STYLE_IDS = {'global-styles-inline-css', 'rs-plugin-settings-inline-css', 'vino-app-inline-css', 'vino-google-fonts-inline-css'}
MONTHS = 'Gennaio Febbraio Marzo Aprile Maggio Giugno Luglio Agosto Settembre Ottobre Novembre Dicembre'.split()

REDIRECTS = json.loads((MIRROR / 'redirects.json').read_text('utf8'))
PAGES = {}
for _f in (MIRROR / 'pages').rglob('index.html'):
    _rel = _f.parent.relative_to(MIRROR / 'pages').as_posix()
    PAGES['' if _rel == '.' else _rel] = _f
SIZES = {} if MEASURE else json.loads((ROOT / 'content' / 'sizes.json').read_text('utf8')) if (ROOT / 'content' / 'sizes.json').exists() else {}
MEASURE_VIEWPORTS = (360, 430, 639, 640, 1023, 1024, 1199, 1200, 1279, 1280, 1439, 1440, 1920)


def page_href(key, fragment=''):
    return BASE + (urllib.parse.quote(key) + '/' if key else '') + (f'#{fragment}' if fragment else '')


def resolve_page(path):
    p = path if path.endswith('/') else path + '/'
    p = REDIRECTS.get(p, p)
    key = urllib.parse.unquote(p).strip('/')
    return key if key in PAGES else None


def split_url(url, base_url):
    absu = urllib.parse.urljoin(base_url, html.unescape(url.strip()))
    u = urllib.parse.urlsplit(absu)
    if u.netloc not in HOSTS:
        return absu, None
    return absu, u


def upload_key(u):
    path = urllib.parse.unquote(u.path)
    return path[len('/wp-content/uploads/'):] if path.startswith('/wp-content/uploads/') else None


class Images:
    def __init__(self):
        self.jobs = {}
        self._dims = {}

    def dims(self, key):
        if key not in self._dims:
            with Image.open(MIRROR / 'uploads' / key) as im:
                self._dims[key] = im.size
        return self._dims[key]

    def exists(self, key):
        return (MIRROR / 'uploads' / key).is_file()

    def animated(self, key):
        if not key.lower().endswith('.gif'):
            return False
        with Image.open(MIRROR / 'uploads' / key) as im:
            return getattr(im, 'n_frames', 1) > 1

    def family(self, key):
        m = SIZED.match(key)
        if m:
            orig = m.group(1) + m.group(4)
            if self.exists(orig):
                W, H = self.dims(orig)
                w, h = int(m.group(2)), int(m.group(3))
                if abs(W / H - w / h) < 0.02:
                    return orig
        return key

    def out(self, key, width=None):
        if self.animated(key):
            dst = 'wp-content/uploads/' + key
            self.jobs[dst] = (key, 'copy')
            return BASE + urllib.parse.quote(dst)
        W, _ = self.dims(key)
        if width is None and W > MAX_W:
            width = MAX_W
        p = Path(key)
        name = f'{p.stem}.webp' if width is None or width >= W else f'{p.stem}-w{width}.webp'
        dst = f'wp-content/uploads/{p.parent.as_posix()}/{name}'
        self.jobs[dst] = (key, None if width is None or width >= W else width)
        return BASE + urllib.parse.quote(dst)

    def candidates(self, keys):
        cands = {}
        for k in keys:
            if not self.exists(k):
                continue
            w = min(self.dims(k)[0], MAX_W)
            cands.setdefault(w, self.out(k))
        if not cands:
            return []
        fam = self.family(keys[0])
        if self.exists(fam) and not self.animated(fam):
            FW = self.dims(fam)[0]
            for w in STD_WIDTHS + (min(FW, MAX_W),):
                if w > FW:
                    continue
                if any(abs(w - c) / c < 0.12 for c in cands):
                    continue
                cands[w] = self.out(fam, w)
        return sorted((w, u) for w, u in cands.items())

    def pick(self, cands, need):
        for w, u in cands:
            if w >= need:
                return u
        return cands[-1][1]

    def run(self):
        def one(item):
            dst, (key, width) = item
            out = DIST / dst
            out.parent.mkdir(parents=True, exist_ok=True)
            cache = CACHE / 'img' / dst
            src = MIRROR / 'uploads' / key
            if width == 'copy':
                shutil.copy2(src, out)
                return
            if not cache.exists() or cache.stat().st_mtime < src.stat().st_mtime:
                cache.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(src) as im:
                    alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
                    im = im.convert('RGBA' if alpha else 'RGB')
                    if width:
                        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                    im.save(cache, 'WEBP', quality=88 if alpha else 82, method=5)
            if out.exists():
                out.unlink()
            os.link(cache, out)
        with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
            list(ex.map(one, self.jobs.items()))


IMG = Images()


def sizes_attr(widths, default=None):
    pts = [(v, w) for v, w in zip(MEASURE_VIEWPORTS, widths) if w]
    if not pts:
        return None
    parts, prev = [], 0
    for v, w in pts:
        parts.append(f'(max-width: {v}px) {math.ceil(max(w, prev))}px')
        prev = w
    parts.append(f'{math.ceil(default or pts[-1][1])}px')
    return ', '.join(parts)


CSS_SOURCES = {}


def css_source(url):
    if url in CSS_SOURCES:
        return CSS_SOURCES[url]
    u = urllib.parse.urlsplit(url)
    if u.netloc == 'fonts.googleapis.com':
        text = (MIRROR / 'assets' / 'fonts.googleapis.com' / 'css.css').read_text('utf8')
    else:
        text = (MIRROR / 'assets' / u.netloc / u.path.lstrip('/')).read_text('utf8', 'replace')
    text = lower_type_selectors(absolutize_css(text, url))
    CSS_SOURCES[url] = text
    return text


def lower_type_selectors(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    tag = re.compile(r'(^|[\s>+~,(])([A-Z][A-Z0-9]*)(?=$|[\s>+~,.#:\[)])')

    def prelude(m):
        sel = m.group(1)
        if sel.lstrip().startswith('@'):
            return m.group(0)
        return tag.sub(lambda t: t.group(1) + t.group(2).lower(), sel) + '{'
    return re.sub(r'([^{}]+)\{', prelude, css)


def absolutize_css(text, base_url):
    def rep(m):
        ref = m.group(2).strip()
        if ref.startswith(('data:', '#')) or not ref:
            return m.group(0)
        return f'url("{urllib.parse.urljoin(base_url, ref)}")'
    return re.sub(r'url\(\s*(["\']?)([^"\')]*)\1\s*\)', rep, text)


LIGHTBOX_HREF = re.compile(r'\.(jpe?g|png|gif|webp)$', re.I)


class Page:
    def __init__(self, key, raw, kind='page'):
        self.key, self.kind = key, kind
        self.url = ORIGIN + '/' + (key + '/' if key else '')
        self.soup = BeautifulSoup(raw, 'html.parser')
        self.css_bundle, self.css_inline = [], []
        self.mi = 0
        self.flags = set()

    def map_href(self, href):
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
            return href
        absu, u = split_url(href, self.url)
        if u is None:
            return href
        k = upload_key(u)
        if k:
            if not IMG.exists(k):
                return absu
            if k.lower().endswith(IMG_EXT):
                return IMG.out(IMG.family(k))
            dst = DIST / 'wp-content' / 'uploads' / k
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(MIRROR / 'uploads' / k, dst)
            return BASE + 'wp-content/uploads/' + urllib.parse.quote(k)
        path = urllib.parse.unquote(u.path) or '/'
        if path.startswith(('/wp-content/', '/wp-includes/', '/wp-admin', '/wp-json', '/feed')):
            return absu
        if u.query:
            q = urllib.parse.parse_qs(u.query)
            if 's' in q and path in ('', '/'):
                return BASE + 'search/?s=' + urllib.parse.quote(q['s'][0])
            return absu
        key = resolve_page(path)
        if key is None:
            return absu
        return page_href(key, u.fragment)

    def next_mi(self, el):
        if MEASURE:
            el['data-mi'] = str(self.mi)
        n = self.mi
        self.mi += 1
        return n

    def measured(self, n):
        return SIZES.get(self.key, {}).get(str(n))

    def img(self, el):
        n = self.next_mi(el)
        lazy = 'b-lazy' in (el.get('class') or []) and el.get('data-src')
        src = el.get('data-src' if lazy else 'src')
        if not src or src.startswith('data:'):
            return
        absu, u = split_url(src, self.url)
        k = upload_key(u) if u else None
        if not k or not IMG.exists(k):
            return
        keys = [k]
        if el.get('srcset'):
            for part in el['srcset'].split(','):
                bits = part.strip().split()
                if bits:
                    _, uu = split_url(bits[0], self.url)
                    kk = upload_key(uu) if uu else None
                    if kk and IMG.exists(kk):
                        keys.append(kk)
        if MEASURE:
            native = IMG.out(k)
            if lazy:
                el['src'] = native
                del el['data-src']
                el['class'] = el['class'] + ['b-loaded']
            else:
                el['src'] = native
                if el.get('srcset'):
                    el['srcset'] = ', '.join(f'{IMG.out(kk)} {IMG.dims(kk)[0]}w' for kk in dict.fromkeys(keys[1:]))
            return
        cands = IMG.candidates(keys)
        if not cands:
            return
        widths = self.measured(n)
        want = 2 * max(x for x in widths if x) if widths and any(widths) else min(IMG.dims(k)[0], MAX_W)
        fallback = IMG.pick(cands, want)
        srcset = ', '.join(f'{u} {w}w' for w, u in cands)
        if widths and any(widths):
            sizes = sizes_attr(widths, None if el.get('width') else IMG.dims(k)[0])
        elif el.get('width'):
            sizes = el.get('sizes') or '100vw'
        else:
            sizes = f'{IMG.dims(k)[0]}px'
        if lazy:
            el['data-src'] = fallback
            if len(cands) > 1:
                el['data-srcset'] = srcset
                el['data-sizes'] = sizes
        else:
            el['src'] = fallback
            if len(cands) > 1:
                el['srcset'] = srcset
                el['sizes'] = sizes
            elif el.get('srcset'):
                del el['srcset']
                el.attrs.pop('sizes', None)

    def bg_url(self, url, n):
        absu, u = split_url(url, self.url)
        k = upload_key(u) if u else None
        if not k or not IMG.exists(k):
            return url
        cands = IMG.candidates([k])
        widths = [x for x in (self.measured(n) or []) if x]
        need = max(widths) * 2 if widths else min(IMG.dims(k)[0], 1600)
        return IMG.pick(cands, need)

    def background(self, el):
        style = el.get('style', '')
        if 'url(' not in style:
            return
        n = self.next_mi(el)
        el['style'] = re.sub(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)', lambda m: f'url({self.bg_url(m.group(2), n)})', style)

    def convert(self):
        s = self.soup
        head, body = s.head, s.body
        if s.find('script', id='wpb_composer_front_js-js'):
            self.flags.add('vc_js')
        if s.find('iframe', class_='wp-embedded-content'):
            self.flags.add('embed')
        if s.select_one('.wpcf7 form'):
            self.flags.add('cf7')

        for el in head.find_all(['link', 'style']):
            if el.name == 'link':
                if 'stylesheet' not in (el.get('rel') or []):
                    continue
                href = el['href']
                href = ('https:' + href) if href.startswith('//') else urllib.parse.urljoin(ORIGIN + '/', href)
                self.css_bundle.append(('link', href.split('?')[0] if 'googleapis' not in href else href))
            else:
                text = el.string or ''
                if el.get('id') in BUNDLE_STYLE_IDS or (not el.get('id') and len(text) < 200 and 'wpb_animate' in text):
                    self.css_bundle.append(('style', lower_type_selectors(absolutize_css(text, self.url))))
                else:
                    self.css_inline.append(text)
            el.decompose()
        for el in body.find_all('style'):
            self.css_bundle.append(('style', lower_type_selectors(absolutize_css(el.string or '', self.url))))
            el.decompose()
        custom = ''.join(e.get('data-styles', '') for e in body.select('.custom-styles'))
        for e in body.select('.custom-styles'):
            e.decompose()
        if custom:
            self.css_inline.append(custom)

        for el in list(head.find_all(True)):
            if el.decomposed:
                continue
            if el.name == 'script' and el.get('type') != 'application/ld+json':
                el.decompose()
            elif el.name == 'link':
                rel = ' '.join(el.get('rel') or [])
                if rel != 'canonical' and 'icon' not in rel:
                    el.decompose()
            elif el.name == 'meta' and el.get('name') == 'generator':
                el.decompose()
            elif el.name == 'noscript':
                el.decompose()
        for c in s.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()

        for el in body.find_all('script'):
            if 'ak_js' in (el.string or ''):
                continue
            el.decompose()
        for svg in body.find_all('svg', recursive=False):
            if svg.find('filter', id=re.compile('^wp-duotone')):
                svg.decompose()
        for sel in ['#fb-root', '#cliSettingsPopup', '.cli-modal-backdrop']:
            for el in body.select(sel):
                el.decompose()

        self.bake_theme_dom()
        self.rewrite_resources()
        return self

    def bake_theme_dom(self):
        s, body = self.soup, self.soup.body
        for a in body.select('.vino-nav-overlay .vino-menu-content .main-nav > .menu li a'):
            a.wrap(s.new_tag('div', attrs={'class': 'item-wrapper'}))
        i = 0
        for cont in body.select('.nav-social-profiles, .vino-social-profiles, .vino-shares'):
            for a in cont.find_all('a'):
                if a.get('data-color'):
                    a['class'] = (a.get('class') or []) + [f'vino-social-st{i}']
                i += 1
        fn = body.find(id='fixed-nav')
        if fn and fn.get('data-height'):
            nav = fn.select_one('.nav')
            if nav:
                nav['style'] = f"height: {fn['data-height']}px;"
        bar = body.find(id='cookie-law-info-bar')
        if bar:
            bar['style'] = 'background-color: rgb(0, 0, 0); color: rgb(255, 255, 255); font-family: inherit; bottom: 0px; position: fixed; display: none;'
            for el, st in [('#cookie_action_close_header', 'color: rgb(255, 255, 255); background-color: rgb(0, 0, 0);'),
                           ('#CONSTANT_OPEN_URL', 'color: rgb(68, 68, 68);')]:
                e = body.select_one(el)
                if e:
                    e['style'] = st
        again = body.find(id='cookie-law-info-again')
        if again:
            again['style'] = 'background-color: rgb(0, 0, 0); color: rgb(255, 255, 255); position: fixed; font-family: inherit; width: auto; bottom: 0px; right: 100px; display: none;'
        for wpcf7 in body.select('div.wpcf7'):
            wpcf7['class'] = (wpcf7.get('class') or []) + ['form-style']
            for hs in wpcf7.select('.has-spinner'):
                hs.insert_after(s.new_tag('span', attrs={'class': 'wpcf7-spinner'}))
                hs['class'] = [c for c in hs['class'] if c != 'has-spinner']
            sub = wpcf7.select_one('.form-submit .wpcf7-submit')
            if sub is not None and sub.name == 'input':
                value = sub.get('value', '')
                fs = sub.find_parent(class_='form-submit')
                sub.decompose()
                btn = s.new_tag('button', attrs={'name': 'submit', 'type': 'submit', 'data-btn-text': value,
                                                 'class': 'btn vino-header btn-outline btn-md btn-contact wpcf7-form-control wpcf7-submit',
                                                 'tabindex': '5', 'id': 'submit'})
                span = s.new_tag('span', attrs={'class': 'btn-text'})
                span.string = value
                btn.append(span)
                fs.append(btn)
            for vi in wpcf7.select('.vino-input'):
                if vi.select_one('.wpcf7-validates-as-required'):
                    vi['class'] = (vi.get('class') or []) + ['input-required']
        for vi in body.select('.vino-input'):
            ta = vi.find('textarea')
            if ta and ta.parent:
                for lab in ta.parent.find_all('label'):
                    lab['class'] = (lab.get('class') or []) + ['label-textarea']
        for a in body.select('.post-content-wrapper a'):
            cls = a.get('class') or []
            if not set(cls) & {'vino-text-link', 'btn-text', 'comment-reply-link', 'vino-hover-text'} and not a.find(True):
                a['class'] = cls + ['vino-text-link']
        for a in body.select('.post-cat-tags .post-tags a'):
            a['class'] = (a.get('class') or []) + ['vino-hover-text']
        for el in body.select('.wpb_wrapper .widgettitle'):
            el['class'] = (el.get('class') or []) + ['h6']
        for pf in body.select('.vino-portfolio'):
            hs = pf.get('data-header-size')
            if hs:
                for h3 in pf.select('.portfolio-text h3'):
                    h3['class'] = (h3.get('class') or []) + [f'h{hs}']
            for ul in pf.select('.portfolio-text ul'):
                ul['style'] = 'font-size: 11px;'
        for pcw in body.select('.single-post > .row .post-content-wrapper'):
            hdrs = pcw.select('.post-header')
            if hdrs and hdrs[0].decode_contents().strip():
                for h in hdrs:
                    h['class'] = (h.get('class') or []) + ['background-el']
            else:
                for p in pcw.select('.content > p:first-of-type'):
                    p['class'] = (p.get('class') or []) + ['background-el']
        if 'product-template-default' not in (body.get('class') or []):
            for cr in body.select('.comment-respond'):
                for h5 in cr.find_all('h5'):
                    h5.wrap(s.new_tag('div', attrs={'class': 'small-12 large-3 columns'}))
                for form in cr.find_all('form'):
                    form.wrap(s.new_tag('div', attrs={'class': 'small-12 large-8 large-offset-1 columns'}))
                row = s.new_tag('div', attrs={'class': 'row'})
                for child in list(cr.contents):
                    row.append(child.extract())
                cr.append(row)
        for cl in body.select('#comments .comment-list'):
            lis = cl.find_all('li', class_='comment', recursive=False)
            if len(lis) == 1:
                lis[0]['class'] = lis[0]['class'] + ['first-li', 'last-li']
            elif len(lis) > 1:
                lis[-1]['class'] = lis[-1]['class'] + ['last-li']
                lis[0]['class'] = lis[0]['class'] + ['first-li']
            cl.insert(0, s.new_tag('div', attrs={'class': 'border-list'}))
        counter = 1
        for pm in body.select('.vino-portfolio-masonry'):
            cls = pm.get('class') or []
            cols = next((n for n in (2, 3, 4, 5, 6) if f'vino-{n}-col' in cls), None)
            for el in pm.select('article > div'):
                el['data-aos-delay'] = str(counter * 100)
                counter += 1
                if cols and counter > cols:
                    counter = 1

    def rewrite_resources(self):
        body = self.soup.body
        for el in self.soup.find_all(href=True):
            if el.name in ('a', 'area', 'link') and not (el.name == 'link' and 'canonical' in (el.get('rel') or [])):
                new = self.map_href(el['href'])
                if el.name == 'a' and new != el['href'] and LIGHTBOX_HREF.search(urllib.parse.urlsplit(el['href']).path):
                    _, u = split_url(el['href'], self.url)
                    k = upload_key(u) if u else None
                    if k and IMG.exists(k) and not IMG.animated(k):
                        cands = IMG.candidates([IMG.family(k)])
                        if len(cands) > 1:
                            el['data-mfp-srcset'] = ', '.join(f'{uu} {w}w' for w, uu in cands)
                            el['data-mfp-w'] = str(min(IMG.dims(IMG.family(k))[0], MAX_W))
                el['href'] = new
        for form in self.soup.find_all('form', action=True):
            if 'search-form' in (form.get('class') or []):
                form['action'] = BASE + 'search/'
            else:
                absu, u = split_url(form['action'], self.url)
                if u is not None:
                    form['action'] = ORIGIN + urllib.parse.urlunsplit(('', '', u.path, u.query, u.fragment))
        for el in body.find_all(True):
            if el.name == 'img':
                self.img(el)
            elif el.get('data-src') and 'b-lazy' in (el.get('class') or []):
                n = self.next_mi(el)
                el['data-src'] = self.bg_url(el['data-src'], n)
            if el.get('style') and 'url(' in el['style']:
                self.background(el)
        for el in body.find_all('iframe', src=True):
            new = self.map_href(el['src'].split('#')[0])
            frag = el['src'][len(el['src'].split('#')[0]):]
            if new != el['src'].split('#')[0]:
                el['src'] = new + frag
        for el in body.find_all(['video', 'source'], src=True):
            el['src'] = self.map_href(el['src'])

    def render(self, css_href, js_href, head_js, extra_js=''):
        s = self.soup
        head = s.head
        logo = s.select_one('img.vino-img-nav-top')
        pre = []
        for f in FONT_PRELOADS:
            pre.append(f'<link rel="preload" href="{f}" as="font" type="font/woff2" crossorigin>')
        if logo is not None and logo.get('src'):
            logo['fetchpriority'] = 'high'
            if logo.get('srcset'):
                pre.append(f'<link rel="preload" as="image" href="{logo["src"]}" imagesrcset="{logo["srcset"]}" imagesizes="{logo.get("sizes", "100vw")}" fetchpriority="high">')
            else:
                pre.append(f'<link rel="preload" as="image" href="{logo["src"]}" fetchpriority="high">')
        styles = ''.join(f'<style>{t}</style>' for t in self.css_inline)
        spec = json.dumps({'prefetch': [{'source': 'document', 'where': {'and': [{'href_matches': BASE + '*'}, {'not': {'href_matches': BASE + 'wp-content/*'}}]}, 'eagerness': 'moderate'}]})
        block = (f'<script>{head_js}</script>' + ''.join(pre) + f'<link rel="stylesheet" href="{css_href}">' + styles +
                 '<style>img,video{-webkit-touch-callout:none;-webkit-user-drag:none;user-select:none}</style>' +
                 f'<script type="speculationrules">{spec}</script><script src="{js_href}" defer></script>' + extra_js)
        frag = BeautifulSoup(block, 'html.parser')
        title = head.find('title')
        anchor = title if title else head.find('meta')
        for node in reversed(list(frag.contents)):
            anchor.insert_after(node)
        if NOINDEX:
            robots = head.find('meta', attrs={'name': 'robots'})
            if robots is None:
                robots = s.new_tag('meta', attrs={'name': 'robots'})
                head.insert(0, robots)
            robots['content'] = 'noindex, nofollow'
        if 'vc_js' in self.flags:
            s.html['data-vc'] = '1'
        s.html['data-base'] = BASE
        return '<!DOCTYPE html>\n' + str(s.html)


FONT_PRELOADS = []


def it_date(iso):
    d = datetime.fromisoformat(iso.replace('Z', '+00:00'))
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def search_entry(key, raw):
    s = BeautifulSoup(raw, 'html.parser')
    body_cls = s.body.get('class') or []
    if not ({'single', 'page'} & set(body_cls)) or 'home' in body_cls:
        return None
    title_el = s.select_one('.single-portfolio-header h1, .page-header h1.page-title, h1.page-title')
    title = title_el.get_text(' ', strip=True) if title_el else re.sub(r'\s*«\s*Daò\s*$', '', s.title.get_text(strip=True))
    t = s.select_one('time.entry-date')
    iso = t['datetime'] if t and t.get('datetime') else None
    if not iso:
        ld = s.find('script', type='application/ld+json')
        if ld:
            for g in json.loads(ld.string).get('@graph', []):
                if g.get('datePublished'):
                    iso = g['datePublished']
                    break
    cats = [{'n': a.get_text(strip=True), 'u': a['href']} for a in s.select('.post-categories .post-cat a')]
    main = s.select_one('.page-wrapper')
    for el in main.select('script, style, .single-portfolio-prev-next, .adjacent-posts, .single-post-meta'):
        el.decompose()
    text = re.sub(r'\s+', ' ', main.get_text(' ', strip=True))
    return {'t': title, 'u': key, 'd': iso, 'dt': it_date(iso) if iso else '', 'c': cats, 'x': text[:4000]}


def head_script(vc):
    classes = ('flexbox canvas canvastext webgl geolocation postmessage no-websqldatabase indexeddb hashchange history draganddrop '
               'websockets rgba hsla multiplebgs backgroundsize borderimage borderradius boxshadow textshadow opacity cssanimations '
               'csscolumns cssgradients cssreflections csstransforms csstransforms3d csstransitions fontface generatedcontent video audio '
               'localstorage sessionstorage webworkers no-applicationcache svg inlinesvg smil svgclippaths')
    return ("(function(h){var t='ontouchstart'in window,c=h.className.replace(/\\bno-js\\b/,'js');"
            f"c+=' {classes} '+(t?'touch':'no-touch')+' '+('MozAppearance'in h.style?'-moz-':'-webkit-');"
            "if(h.getAttribute('data-vc'))c+=' js_active '+('ontouchstart'in h?'vc_mobile':'vc_desktop')+' vc_transform';"
            "h.className=c})(document.documentElement)")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / 'assets' / 'css').mkdir(parents=True)
    (DIST / 'assets' / 'js').mkdir(parents=True)
    (DIST / 'assets' / 'fonts').mkdir(parents=True)

    pages = []
    for key, f in sorted(PAGES.items()):
        kind = 'embed' if key.endswith('/embed') else 'page'
        pages.append(Page(key, f.read_text('utf8', 'replace'), kind))
    search_tpl = Page('search', (MIRROR / 'templates' / 'search.html').read_text('utf8', 'replace'))
    empty_tpl = (MIRROR / 'templates' / 'search-empty.html').read_text('utf8', 'replace')
    nf = Page('404', (MIRROR / 'templates' / '404.html').read_text('utf8', 'replace'))

    for p in pages + [search_tpl, nf]:
        if p.kind == 'embed':
            continue
        p.convert()

    sw = search_tpl.soup.select_one('.blog-simple-wrapper')
    proto = str(sw.select_one('.post-header'))
    for el in sw.select('.post-header'):
        el.decompose()
    nav = sw.select_one('nav.pagination')
    if nav:
        nav.decompose()
    sw['data-search-proto'] = proto
    empty = Page('search', empty_tpl)
    empty.convert()
    sw['data-search-empty'] = str(empty.soup.select_one('.page-wrapper-inner'))
    title = search_tpl.soup.select_one('.search-results-header .page-title span')
    if title:
        title.string = ''
    for i in search_tpl.soup.select('input[name="s"]'):
        i['value'] = ''
    pages_out = [p for p in pages if p.kind != 'embed'] + [search_tpl, nf]

    bundles = {}
    for p in pages_out:
        sig = hashlib.sha1(json.dumps(p.css_bundle).encode()).hexdigest()[:10]
        bundles.setdefault(sig, {'items': p.css_bundle, 'pages': []})['pages'].append(p)
        p.bundle = sig

    IMG.run()

    js_files = {}
    job = {'css': [], 'js': [], 'safelist': SAFELIST}
    raw_js = CACHE / 'site.js'
    CACHE.mkdir(exist_ok=True)
    shutil.copy2(SRC / 'site.js', raw_js)
    job['js'].append({'in': str(raw_js), 'out': str(CACHE / 'site.min.js')})

    tmp = CACHE / 'purge'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    hs = head_script(True)
    for sig, b in bundles.items():
        raw_css = tmp / f'{sig}.css'
        parts = []
        for kind, val in b['items']:
            parts.append(css_source(val) if kind == 'link' else val)
        raw_css.write_text('\n'.join(parts), 'utf8')
        content = []
        for i, p in enumerate(b['pages']):
            hf = tmp / f'{sig}-{i}.html'
            hf.write_text(str(p.soup), 'utf8')
            content.append(str(hf))
        (tmp / 'head.js').write_text(hs, 'utf8')
        content += [str(SRC / 'site.js'), str(tmp / 'head.js'),
                    str(MIRROR / 'assets/www.dao-arts.it/wp-content/plugins/contact-form-7/includes/js/index.js')]
        job['css'].append({'in': str(raw_css), 'out': str(tmp / f'{sig}.min.css'), 'content': content})
    (tmp / 'job.json').write_text(json.dumps(job), 'utf8')
    subprocess.run(['node', str(ROOT / 'tools' / 'optimize.mjs'), str(tmp / 'job.json')], check=True, cwd=ROOT)

    finals = {sig: (tmp / f'{sig}.min.css').read_text('utf8') for sig in bundles}
    glyphs = set()
    for css in finals.values():
        for val in re.findall(r'content:\s*"([^"]*)"', css):
            val = re.sub(r'\\([0-9a-fA-F]{1,6})\s?', lambda m: chr(int(m.group(1), 16)), val)
            glyphs |= {ord(ch) for ch in val if 0xF000 <= ord(ch) <= 0xF8FF}
    fa_url = subset_fontawesome(glyphs)
    css_hrefs = {}
    for sig, css in finals.items():
        css = localize_css(css, fa_url)
        h = hashlib.sha1(css.encode()).hexdigest()[:10]
        (DIST / 'assets' / 'css' / f'{h}.css').write_text(css, 'utf8')
        css_hrefs[sig] = BASE + f'assets/css/{h}.css'

    js_min = (CACHE / 'site.min.js').read_text('utf8')
    jh = hashlib.sha1(js_min.encode()).hexdigest()[:10]
    (DIST / 'assets' / 'js' / f'site.{jh}.js').write_text(js_min, 'utf8')
    js_href = BASE + f'assets/js/site.{jh}.js'
    cf7 = MIRROR / 'assets/www.dao-arts.it/wp-content/plugins/contact-form-7/includes/js/index.js'
    shutil.copy2(cf7, DIST / 'assets' / 'js' / 'cf7.js')
    emb = MIRROR / 'assets/www.dao-arts.it/wp-includes/js/wp-embed.min.js'
    shutil.copy2(emb, DIST / 'assets' / 'js' / 'wp-embed.js')

    for p in pages_out:
        extra = ''
        if 'cf7' in p.flags:
            extra += ('<script>var wpcf7={"api":{"root":"https:\\/\\/www.dao-arts.it\\/wp-json\\/","namespace":"contact-form-7\\/v1"}};</script>'
                      f'<script src="{BASE}assets/js/cf7.js" defer></script>')
        if 'embed' in p.flags:
            extra += f'<script src="{BASE}assets/js/wp-embed.js" defer></script>'
        out_html = p.render(css_hrefs[p.bundle], js_href, hs, extra)
        dst = DIST / (p.key if p.key not in ('', '404') else '') / ('index.html' if p.key != '404' else '404.html')
        if p.key == 'search':
            dst = DIST / 'search' / 'index.html'
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(out_html, 'utf8')

    for p in pages:
        if p.kind != 'embed':
            continue
        p.rewrite_resources()
        dst = DIST / p.key / 'index.html'
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text('<!DOCTYPE html>\n' + str(p.soup.html), 'utf8')
    IMG.run()

    entries = []
    for key, f in sorted(PAGES.items()):
        if key.endswith('/embed') or re.search(r'(^|/)page/\d+$', key):
            continue
        e = search_entry(key, f.read_text('utf8', 'replace'))
        if e:
            e['u'] = page_href(key)
            for c in e['c']:
                c['u'] = Page(key, '<html><body></body></html>').map_href(c['u'])
            entries.append(e)
    (DIST / 'search.json').write_text(json.dumps(entries, ensure_ascii=False, separators=(',', ':')), 'utf8')
    (DIST / '.nojekyll').write_text('')
    total = sum(f.stat().st_size for f in DIST.rglob('*') if f.is_file())
    print(f'pagine: {len(pages_out)}, bundle CSS: {len(bundles)}, immagini: {len(IMG.jobs)}, dist: {total / 1e6:.1f} MB')


SAFELIST = {
    'standard': ['js', 'no-js', 'touch', 'no-touch', '-webkit-', '-moz-', 'js_active', 'vc_desktop', 'vc_mobile', 'vc_transform',
                 'no-scroll', 'open', 'vino-overlay-open', 'show-fixed-nav', 'show-arrow', 'b-loaded', 'loaded', 'loading',
                 'aos-init', 'aos-animate', 'active-input', 'input-required', 'label-textarea', 'hover-not-ready', 'is_stuck',
                 'at_bottom', 'sent', 'invalid', 'failed', 'spam', 'aborted', 'unaccepted', 'submitting', 'resetting',
                 'payment-required', 'init', 'swiper-slide-active', 'swiper-slide-next', 'swiper-slide-prev', 'swiper-slide-duplicate'],
    'deep': ['^mfp-', '^wpcf7', '^cli', '^cookie', '^swiper'],
    'greedy': ['^mfp-', '^wpcf7-', '^swiper-'],
}

FONT_FILES = {}


def prune_font_faces(css):
    faces = re.findall(r'@font-face\{[^}]*\}', css)
    rest = re.sub(r'@font-face\{[^}]*\}', '', css)
    for f in faces:
        m = re.search(r'font-family:\s*["\']?([^;"\'}]+)', f)
        fam = m.group(1).strip() if m else ''
        if fam and not re.search(r'font(-family)?:[^;}]*\b' + re.escape(fam) + r'\b', rest, re.I):
            css = css.replace(f, '')
    return css


def localize_css(css, fa_url):
    css = prune_font_faces(css)
    def font_face(m):
        block = m.group(0)
        if 'FontAwesome' in block:
            block = re.sub(r'src:[^;}]*[;]?', '', block)
            return block.replace('{', '{src:url(' + fa_url + ') format("woff2");', 1)
        return block
    css = re.sub(r'@font-face\{[^}]*\}', font_face, css)

    def url(m):
        ref = m.group(1).strip('"\'')
        if ref.startswith('data:') or ref.startswith(BASE):
            return m.group(0)
        u = urllib.parse.urlsplit(ref)
        if u.netloc == 'fonts.gstatic.com':
            name = Path(u.path).name
            dst = DIST / 'assets' / 'fonts' / name
            if not dst.exists():
                shutil.copy2(MIRROR / 'assets' / 'fonts.gstatic.com' / u.path.lstrip('/'), dst)
            return f'url({BASE}assets/fonts/{name})'
        if u.netloc in HOSTS:
            k = upload_key(u)
            if k and IMG.exists(k):
                return f'url({IMG.out(k)})'
            srcf = MIRROR / 'assets' / 'www.dao-arts.it' / urllib.parse.unquote(u.path).lstrip('/')
            if srcf.exists():
                name = hashlib.sha1(u.path.encode()).hexdigest()[:8] + '-' + srcf.name
                dst = DIST / 'assets' / 'media' / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(srcf, dst)
                return f'url({BASE}assets/media/{name})'
        return m.group(0)
    css = re.sub(r'url\(([^)]+)\)', url, css)
    IMG.run()
    return css


def subset_fontawesome(glyphs):
    src = MIRROR / 'assets/www.dao-arts.it/wp-content/themes/vino/assets/fonts/fontawesome-webfont.woff2'
    out = DIST / 'assets' / 'fonts' / 'fa.woff2'
    unicodes = ','.join(f'U+{g:04X}' for g in sorted(glyphs)) or 'U+F000'
    subprocess.run([sys.executable, '-m', 'fontTools.subset', str(src), f'--unicodes={unicodes}', '--flavor=woff2',
                    f'--output-file={out}', '--no-hinting', '--desubroutinize'], check=True)
    print(f'FontAwesome: {len(glyphs)} glifi, {out.stat().st_size} B')
    return BASE + 'assets/fonts/fa.woff2'


if __name__ == '__main__':
    gcss = (MIRROR / 'assets' / 'fonts.googleapis.com' / 'css.css').read_text('utf8')
    for block in re.findall(r'@font-face\s*\{[^}]*\}', gcss):
        if 'U+0000-00FF' in block and re.search(r"font-weight:\s*(400|500)", block):
            fu = re.search(r'url\((https://fonts\.gstatic\.com/[^)]+)\)', block).group(1)
            FONT_PRELOADS.append(BASE + 'assets/fonts/' + Path(urllib.parse.urlsplit(fu).path).name)
    main()
