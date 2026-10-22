# ,_,
# (O,O)
# (   )   Mïmïr
# -"-"-
import hashlib, json, re, shutil, sys, time, zipfile, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST, OUT = ROOT / 'dist', ROOT / 'pacchi'
TESTI = {'.html', '.css', '.js', '.json', '.svg', '.txt', '.xml'}
GRANDE = 4 << 20
SECCHI = 16
NOME = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9_-][A-Za-z0-9._-]*)*$')


def secchio(rel, size):
    if Path(rel).suffix.lower() in TESTI:
        return 't'
    if size > GRANDE:
        return 'v' + hashlib.sha1(rel.encode()).hexdigest()[:6]
    return f'i{zlib.crc32(rel.encode()) % SECCHI:02d}'


def main():
    files, gruppi = {}, {}
    for f in sorted(DIST.rglob('*')):
        rel = f.relative_to(DIST).as_posix()
        if not f.is_file() or rel.startswith('.') or '/.' in rel:
            continue
        if not NOME.match(rel):
            sys.exit(f'nome non valido: {rel}')
        data = f.read_bytes()
        files[rel] = hashlib.sha1(data).hexdigest()
        gruppi.setdefault(secchio(rel, len(data)), []).append(rel)
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()
    pacchi, mappa = {}, {}
    for g, rels in sorted(gruppi.items()):
        tmp = OUT / f'{g}.zip'
        with zipfile.ZipFile(tmp, 'w') as z:
            for rel in rels:
                zi = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
                zi.external_attr = 0o644 << 16
                zi.compress_type = zipfile.ZIP_DEFLATED if g == 't' else zipfile.ZIP_STORED
                z.writestr(zi, (DIST / rel).read_bytes())
        sha = hashlib.sha1(tmp.read_bytes()).hexdigest()
        nome = f'{g}-{sha[:12]}.zip'
        tmp.rename(OUT / nome)
        pacchi[nome] = {'sha1': sha, 'byte': (OUT / nome).stat().st_size}
        for rel in rels:
            mappa[rel] = [files[rel], nome]
    man = {'versione': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'pacchi': pacchi, 'file': mappa}
    (OUT / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')), 'utf8')
    print(f'pacchi: {len(pacchi)}, file: {len(mappa)}, {sum(p["byte"] for p in pacchi.values()) / 1048576:.1f} MB')


if __name__ == '__main__':
    main()
