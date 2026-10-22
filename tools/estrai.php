<?php
/*
     ,_,
    (O,O)
    (   )   Mïmïr
  ---"-"---
*/
require __DIR__ . '/wp-load.php';
if (!current_user_can('manage_options')) {
    auth_redirect();
}
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
@set_time_limit(300);

$nuova = __DIR__ . '/.copia-nuova';
$vecchia = __DIR__ . '/.copia-vecchia';

function cancella($dir)
{
    if (!is_dir($dir)) {
        return;
    }
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
    foreach ($it as $f) {
        $f->isDir() ? rmdir($f->getPathname()) : unlink($f->getPathname());
    }
    rmdir($dir);
}

$zips = glob(__DIR__ . '/static-[0-9].zip');
sort($zips);
if (!$zips) {
    if (!is_dir("$nuova/static")) {
        exit('<p>Nessuno zip static-N.zip nella cartella principale.</p>');
    }
    cancella($vecchia);
    if (is_dir(__DIR__ . '/static') && !rename(__DIR__ . '/static', $vecchia)) {
        exit('<p>Non riesco a spostare la copia attuale.</p>');
    }
    rename("$nuova/static", __DIR__ . '/static');
    cancella($nuova);
    cancella($vecchia);
    $n = iterator_count(new RecursiveIteratorIterator(new RecursiveDirectoryIterator(__DIR__ . '/static', FilesystemIterator::SKIP_DOTS)));
    unlink(__FILE__);
    exit("<p>Fatto: $n file nella nuova copia. Questo file si è cancellato da solo.</p>");
}

$zip = $zips[0];
$nome = basename($zip);
if (!is_dir($nuova)) {
    mkdir($nuova, 0755);
}
if (class_exists('ZipArchive')) {
    $z = new ZipArchive();
    if ($z->open($zip) !== true) {
        exit("<p>$nome: non si apre, va ricaricato.</p>");
    }
    for ($i = 0; $i < $z->numFiles; $i++) {
        $e = $z->getNameIndex($i);
        if (strpos($e, 'static/') !== 0 || strpos($e, '..') !== false) {
            exit("<p>$nome: contiene $e, mi fermo.</p>");
        }
    }
    $ok = $z->extractTo($nuova);
    $z->close();
    $metodo = 'ZipArchive';
} else {
    require_once ABSPATH . 'wp-admin/includes/class-pclzip.php';
    $z = new PclZip($zip);
    $lista = $z->listContent();
    if (!$lista) {
        exit("<p>$nome: non si apre (" . esc_html($z->errorInfo(true)) . '), va ricaricato.</p>');
    }
    foreach ($lista as $e) {
        if (strpos($e['filename'], 'static/') !== 0 || strpos($e['filename'], '..') !== false) {
            exit("<p>$nome: contiene {$e['filename']}, mi fermo.</p>");
        }
    }
    $ok = $z->extract(PCLZIP_OPT_PATH, $nuova) !== 0;
    $metodo = 'PclZip';
}
if (!$ok) {
    exit("<p>$nome: errore durante l'estrazione ($metodo).</p>");
}
unlink($zip);
echo '<meta http-equiv="refresh" content="1">';
echo "<p>$nome estratto ($metodo). Vado avanti…</p>";
