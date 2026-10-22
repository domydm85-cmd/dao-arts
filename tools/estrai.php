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

$zips = glob(__DIR__ . '/static-[0-9].zip');
sort($zips);
if (!$zips) {
    $n = is_dir(__DIR__ . '/static') ? iterator_count(new RecursiveIteratorIterator(new RecursiveDirectoryIterator(__DIR__ . '/static', FilesystemIterator::SKIP_DOTS))) : 0;
    if ($n) {
        unlink(__FILE__);
    }
    exit($n ? "<p>Fatto: $n file in static. Questo file si è cancellato da solo.</p>" : '<p>Nessuno zip static-N.zip nella cartella principale.</p>');
}

$zip = $zips[0];
$nome = basename($zip);
$ok = false;
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
    $ok = $z->extractTo(__DIR__);
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
    $ok = $z->extract(PCLZIP_OPT_PATH, __DIR__) !== 0;
    $metodo = 'PclZip';
    if (!$ok) {
        exit("<p>$nome: errore ($metodo) " . esc_html($z->errorInfo(true)) . '</p>');
    }
}
if (!$ok) {
    exit("<p>$nome: errore durante l'estrazione ($metodo).</p>");
}
unlink($zip);
echo '<meta http-equiv="refresh" content="1">';
echo "<p>$nome estratto ($metodo). Vado avanti…</p>";
