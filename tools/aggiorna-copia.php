<?php
/*
     ,_,
    (O,O)
    (   )   Mïmïr
  ---"-"---
*/
const SORGENTE = 'https://github.com/domydm85-cmd/dao-arts/releases/download/copia/';
const TEMPO = 45;

header('Content-Type: application/json');
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex');

$base = __DIR__ . '/static';
$lavoro = $base . '/.copia';
$fileStato = $lavoro . '/stato.json';

function fine($dati, $codice = 200)
{
    http_response_code($codice);
    echo json_encode($dati);
    exit;
}

function valido($p)
{
    return is_string($p) && preg_match('#^[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9_-][A-Za-z0-9._-]*)*$#', $p) === 1;
}

function scarica($url, $dest)
{
    $fp = fopen($dest, 'wb');
    if (!$fp) {
        return false;
    }
    $c = curl_init($url);
    curl_setopt_array($c, [
        CURLOPT_FILE => $fp,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_TIMEOUT => 90,
        CURLOPT_FAILONERROR => true,
        CURLOPT_USERAGENT => 'Mozilla/5.0',
    ]);
    if (is_file(__DIR__ . '/wp-includes/certificates/ca-bundle.crt')) {
        curl_setopt($c, CURLOPT_CAINFO, __DIR__ . '/wp-includes/certificates/ca-bundle.crt');
    }
    $ok = curl_exec($c) && curl_getinfo($c, CURLINFO_HTTP_CODE) === 200;
    curl_close($c);
    fclose($fp);
    return $ok;
}

function svuota($dir)
{
    if (!is_dir($dir)) {
        return;
    }
    foreach (array_diff(scandir($dir), ['.', '..']) as $n) {
        is_dir("$dir/$n") ? svuota("$dir/$n") : unlink("$dir/$n");
    }
    rmdir($dir);
}

if (!is_dir($lavoro) && !mkdir($lavoro, 0755, true)) {
    fine(['esito' => 'errore', 'dove' => 'cartella'], 500);
}
$stato = is_file($fileStato) ? json_decode(file_get_contents($fileStato), true) : null;
if (!is_array($stato) || !isset($stato['file'])) {
    $stato = ['versione' => null, 'file' => []];
}

if (isset($_GET['stato'])) {
    fine([
        'versione' => $stato['versione'],
        'file' => count($stato['file']),
        'zip' => class_exists('ZipArchive'),
        'radice' => realpath($_SERVER['DOCUMENT_ROOT']) === realpath(__DIR__),
    ]);
}

$lock = fopen("$lavoro/lock", 'c');
if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) {
    fine(['esito' => 'occupato']);
}
ignore_user_abort(true);
@set_time_limit(120);
$inizio = microtime(true);

if (!scarica(SORGENTE . 'manifest.json', "$lavoro/manifest.json")) {
    fine(['esito' => 'errore', 'dove' => 'manifest'], 502);
}
$m = json_decode(file_get_contents("$lavoro/manifest.json"), true);
unlink("$lavoro/manifest.json");
if (!is_array($m) || !isset($m['versione'], $m['file'], $m['pacchi'])) {
    fine(['esito' => 'errore', 'dove' => 'manifest'], 502);
}

$serve = [];
foreach ($m['file'] as $p => $f) {
    if (!valido($p) || !isset($m['pacchi'][$f[1]])) {
        fine(['esito' => 'errore', 'dove' => $p], 502);
    }
    if (isset($stato['file'][$p]) && $stato['file'][$p] === $f[0] && is_file("$base/$p")) {
        continue;
    }
    $serve[$f[1]][] = $p;
}

$fatti = 0;
foreach ($serve as $pacco => $nomi) {
    if ($fatti && microtime(true) - $inizio > TEMPO) {
        break;
    }
    if (!valido($pacco)) {
        fine(['esito' => 'errore', 'dove' => $pacco], 502);
    }
    $zipFile = "$lavoro/$pacco";
    if (!scarica(SORGENTE . $pacco, $zipFile) || sha1_file($zipFile) !== $m['pacchi'][$pacco]['sha1']) {
        @unlink($zipFile);
        fine(['esito' => 'errore', 'dove' => $pacco], 502);
    }
    $zip = new ZipArchive();
    if ($zip->open($zipFile) !== true || !$zip->extractTo("$lavoro/estratti", $nomi)) {
        fine(['esito' => 'errore', 'dove' => $pacco], 500);
    }
    $zip->close();
    unlink($zipFile);
    foreach ($nomi as $p) {
        if (sha1_file("$lavoro/estratti/$p") !== $m['file'][$p][0]) {
            fine(['esito' => 'errore', 'dove' => $p], 500);
        }
        if (!is_dir(dirname("$base/$p"))) {
            mkdir(dirname("$base/$p"), 0755, true);
        }
        rename("$lavoro/estratti/$p", "$base/$p");
        $stato['file'][$p] = $m['file'][$p][0];
        $fatti++;
    }
    svuota("$lavoro/estratti");
    file_put_contents($fileStato, json_encode($stato));
    unset($serve[$pacco]);
}

$mancanti = array_sum(array_map('count', $serve));
if ($mancanti === 0) {
    foreach (array_keys($stato['file']) as $p) {
        if (!isset($m['file'][$p])) {
            if (valido($p) && is_file("$base/$p")) {
                unlink("$base/$p");
            }
            unset($stato['file'][$p]);
        }
    }
    $stato['versione'] = $m['versione'];
    file_put_contents($fileStato, json_encode($stato));
}
fine(['esito' => 'ok', 'versione' => $m['versione'], 'fatti' => $fatti, 'mancanti' => $mancanti]);
