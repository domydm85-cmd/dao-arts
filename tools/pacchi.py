# ,_,
# (O,O)
# (   )   Mïmïr
# -"-"-
import shutil, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST, OUT = ROOT / 'dist', ROOT / 'pacchi'
MAX = 45 << 20
TESTI = {'.html', '.css', '.js', '.json', '.svg', '.txt', '.xml'}


def main():
    files = [f for f in sorted(DIST.rglob('*')) if f.is_file() and not any(p.startswith('.') for p in f.relative_to(DIST).parts)]
    gruppi, cur, peso = [], [], 0
    for f in files:
        s = f.stat().st_size
        if cur and peso + s > MAX:
            gruppi.append(cur)
            cur, peso = [], 0
        cur.append(f)
        peso += s
    gruppi.append(cur)
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()
    for i, g in enumerate(gruppi, 1):
        with zipfile.ZipFile(OUT / f'static-{i}.zip', 'w') as z:
            for f in g:
                z.write(f, 'static/' + f.relative_to(DIST).as_posix(),
                        zipfile.ZIP_DEFLATED if f.suffix.lower() in TESTI else zipfile.ZIP_STORED)
        print(f'static-{i}.zip: {len(g)} file, {(OUT / f"static-{i}.zip").stat().st_size / 1048576:.1f} MB')


if __name__ == '__main__':
    main()
