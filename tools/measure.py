# ,_,
# (O,O)
# (   )   Mïmïr
# -"-"-
import functools, http.server, json, os, socketserver, sys, tempfile, threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get('BASE', '/dao-arts/')
VIEWPORTS = (360, 430, 639, 640, 1023, 1024, 1199, 1200, 1279, 1280, 1439, 1440, 1920)

JS = """() => {
  const out = {};
  document.querySelectorAll('[data-mi]').forEach(el => {
    const cs = getComputedStyle(el);
    const w = el.getClientRects().length ? parseFloat(cs.width) : 0;
    out[el.dataset.mi] = Number.isFinite(w) ? Math.round(w * 10) / 10 : 0;
  });
  return out;
}"""


def serve():
    root = ROOT / 'dist'
    if BASE.strip('/'):
        root = Path(tempfile.mkdtemp())
        (root / BASE.strip('/')).symlink_to(ROOT / 'dist')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{srv.server_address[1]}'


def urls():
    out = {}
    for f in (ROOT / 'dist').rglob('index.html'):
        rel = f.parent.relative_to(ROOT / 'dist').as_posix()
        out['' if rel == '.' else rel] = BASE + ('' if rel == '.' else rel + '/')
    out['404'] = BASE + '404.html'
    return out


def run(vw, origin, pages):
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': vw, 'height': 900})
        pg = ctx.new_page()
        for key, url in pages:
            pg.goto(origin + url, wait_until='load')
            pg.wait_for_timeout(250)
            res[key] = pg.evaluate(JS)
        b.close()
    return vw, res


if __name__ == '__main__':
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    origin = serve()
    pages = sorted(urls().items())
    data = {}
    with ProcessPoolExecutor(procs) as ex:
        for vw, res in ex.map(run, VIEWPORTS, [origin] * len(VIEWPORTS), [pages] * len(VIEWPORTS)):
            print('viewport', vw, 'ok', flush=True)
            for key, m in res.items():
                for mi, w in m.items():
                    data.setdefault(key, {}).setdefault(mi, [0] * len(VIEWPORTS))[VIEWPORTS.index(vw)] = w
    (ROOT / 'content').mkdir(exist_ok=True)
    (ROOT / 'content' / 'sizes.json').write_text(json.dumps(data, separators=(',', ':')), 'utf8')
    print('pagine misurate:', len(data), 'elementi:', sum(len(v) for v in data.values()))
