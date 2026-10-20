# ,_,
# (O,O)
# (   )   Mïmïr
# -"-"-
import json, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
MIRROR = ROOT / 'mirror'
ORIGIN = 'https://www.dao-arts.it'
HOSTS = ('www.dao-arts.it', 'dao-arts.it')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
EXCLUDE_PREFIX = re.compile(r'^/(wp-admin|wp-login|wp-json|xmlrpc|wp-includes|wp-content|comments)(/|$)', re.I)
EXCLUDE_END = re.compile(r'/(feed|embed|trackback)/?$|\.(xml|php|txt|jpe?g|png|gif|webp|pdf|mp4|mov|zip)$', re.I)
EXTRA_PAGES = ['/?s=dao', '/pagina-inesistente-404/']
EMBEDS = re.compile(r'class="wp-embedded-content"[^>]*src="([^"#]+)')


def fetch(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.geturl(), r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, url, e.read()
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return 0, url, b''


def norm_path(href, base=ORIGIN + '/'):
    u = urllib.parse.urlsplit(urllib.parse.urljoin(base, href.strip()))
    if u.netloc not in HOSTS:
        return None
    return urllib.parse.unquote(u.path) or '/'


def wanted(path):
    return not EXCLUDE_PREFIX.search(path) and not EXCLUDE_END.search(path)


def slash(path):
    return path if path.endswith('/') or '.' in path.rsplit('/', 1)[-1] else path + '/'


def page_file(path):
    p = path.strip('/')
    return MIRROR / 'pages' / p / 'index.html' if p else MIRROR / 'pages' / 'index.html'


def sitemap_urls():
    _, _, idx = fetch(ORIGIN + '/sitemap_index.xml')
    urls = []
    for sm in re.findall(r'<loc>([^<]+)</loc>', idx.decode()):
        _, _, body = fetch(sm)
        urls += [u for u in re.findall(r'<loc>([^<]+)</loc>', body.decode()) if '/wp-content/' not in u]
    return urls


def mirror_pages():
    redirects, seen, done = {}, set(), {}
    queue = [slash(norm_path(u)) for u in sitemap_urls()]

    def one(path):
        status, final, body = fetch(ORIGIN + urllib.parse.quote(path))
        return path, status, final, body

    while queue:
        batch = [p for p in dict.fromkeys(queue) if p and p not in seen]
        queue = []
        seen.update(batch)
        with ThreadPoolExecutor(6) as ex:
            for path, status, final, body in ex.map(one, batch):
                if status != 200:
                    print('  !', status, path)
                    continue
                fpath = norm_path(final)
                if fpath.rstrip('/') != path.rstrip('/'):
                    redirects[path] = fpath
                if fpath in done:
                    continue
                done[fpath] = True
                f = page_file(fpath)
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(body)
                html = body.decode('utf8', 'replace')
                soup = BeautifulSoup(html, 'html.parser')
                for a in soup.find_all('a', href=True):
                    if '?' in a['href']:
                        continue
                    p = norm_path(a['href'], final)
                    if p and wanted(p):
                        queue.append(slash(p))
                for m in EMBEDS.finditer(html):
                    p = norm_path(m.group(1))
                    if p:
                        queue.append(slash(p))
        print(f'  pagine: {len(done)}, in coda: {len(queue)}')
    for extra in EXTRA_PAGES:
        status, final, body = fetch(ORIGIN + extra)
        name = 'search' if '?s=' in extra else '404'
        (MIRROR / 'templates').mkdir(parents=True, exist_ok=True)
        (MIRROR / 'templates' / f'{name}.html').write_bytes(body)
        print(f'  template {name}: {status}')
    (MIRROR / 'redirects.json').write_text(json.dumps(redirects, indent=1, ensure_ascii=False))
    print('pagine salvate:', len(done), 'redirect:', len(redirects))


def asset_path(url):
    u = urllib.parse.urlsplit(url)
    return MIRROR / 'assets' / u.netloc / u.path.lstrip('/')


def mirror_assets():
    pages = list((MIRROR / 'pages').rglob('index.html')) + list((MIRROR / 'templates').glob('*.html'))
    css, js = set(), set()
    for f in pages:
        soup = BeautifulSoup(f.read_text('utf8', 'replace'), 'html.parser')
        for l in soup.find_all('link', rel='stylesheet'):
            css.add(urllib.parse.urljoin(ORIGIN + '/', l['href']))
        for s in soup.find_all('script', src=True):
            js.add(urllib.parse.urljoin(ORIGIN + '/', s['src']).split('?')[0])
    for url in sorted(css):
        if 'fonts.googleapis.com' in url:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            body = urllib.request.urlopen(req, timeout=60).read()
            dst = MIRROR / 'assets' / 'fonts.googleapis.com' / 'css.css'
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(body)
            for fu in set(re.findall(r'url\((https://fonts\.gstatic\.com/[^)]+)\)', body.decode())):
                _, _, fb = fetch(fu)
                fd = asset_path(fu)
                fd.parent.mkdir(parents=True, exist_ok=True)
                fd.write_bytes(fb)
            continue
        status, _, body = fetch(url.split('?')[0])
        dst = asset_path(url.split('?')[0])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(body)
        for ref in re.findall(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)', body.decode('utf8', 'replace')):
            if ref.startswith('data:') or ref.startswith('#'):
                continue
            ru = urllib.parse.urljoin(url, ref).split('?')[0].split('#')[0]
            if urllib.parse.urlsplit(ru).netloc not in HOSTS:
                continue
            st, _, rb = fetch(ru)
            if st == 200:
                rd = asset_path(ru)
                rd.parent.mkdir(parents=True, exist_ok=True)
                rd.write_bytes(rb)
    for url in sorted(js):
        if url.endswith(('contact-form-7/includes/js/index.js', 'wp-embed.min.js')) and urllib.parse.urlsplit(url).netloc in HOSTS:
            status, _, body = fetch(url)
            dst = asset_path(url)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(body)
    print('asset CSS:', len(css))


UPLOAD = re.compile(r'(?:https?:)?//(?:www\.)?dao-arts\.it/wp-content/uploads/([^"\'\s)?#,]+)')


def mirror_uploads():
    keys = set()
    for f in list((MIRROR / 'pages').rglob('index.html')) + list((MIRROR / 'templates').glob('*.html')):
        keys |= {urllib.parse.unquote(k) for k in UPLOAD.findall(f.read_text('utf8', 'replace'))}
    for f in (MIRROR / 'assets').rglob('*.css'):
        keys |= {urllib.parse.unquote(k) for k in UPLOAD.findall(f.read_text('utf8', 'replace'))}
    sized = re.compile(r'^(.*)-(\d+)x(\d+)(\.[a-z0-9]+)$', re.I)
    keys |= {m.group(1) + m.group(4) for k in keys if (m := sized.match(k))}
    keys = {k for k in keys if not k.endswith('.css')}

    def get(k):
        dst = MIRROR / 'uploads' / k
        if dst.exists() and dst.stat().st_size:
            return k, 'cache'
        status, _, body = fetch(ORIGIN + '/wp-content/uploads/' + urllib.parse.quote(k))
        if status != 200:
            return k, f'ERR {status}'
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(body)
        return k, 'ok'
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(get, sorted(keys)))
    errs = [r for r in res if r[1].startswith('ERR')]
    print('upload:', len(res), 'errori:', len(errs))
    for k, e in errs:
        print('  ', e, k)


if __name__ == '__main__':
    args = set(sys.argv[1:]) or {'--pages', '--assets', '--uploads'}
    if '--pages' in args:
        mirror_pages()
    if '--assets' in args:
        mirror_assets()
    if '--uploads' in args:
        mirror_uploads()
