/*
     ,_,
    (O,O)
    (   )   Mïmïr
  ---"-"---
*/
import { readFileSync, writeFileSync } from 'node:fs';
import { PurgeCSS } from 'purgecss';
import { transform } from 'lightningcss';
import { minify } from 'terser';

const job = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const toRegex = list => (list || []).map(s => new RegExp(s));

for (const t of job.css || []) {
  const [res] = await new PurgeCSS().purge({
    content: t.content,
    css: [t.in],
    fontFace: false,
    keyframes: true,
    variables: true,
    rejected: false,
    safelist: {
      standard: [...(job.safelist?.standard || []), ...toRegex(job.safelist?.standardRe)],
      deep: toRegex(job.safelist?.deep),
      greedy: toRegex(job.safelist?.greedy),
    },
  });
  const { code, warnings } = transform({
    filename: t.in,
    code: Buffer.from(res.css),
    minify: true,
    errorRecovery: true,
  });
  writeFileSync(t.out, code);
  console.log(`css ${t.out}: ${readFileSync(t.in).length} -> ${code.length} B (${warnings.length} avvisi)`);
}

for (const t of job.js || []) {
  const out = await minify(readFileSync(t.in, 'utf8'), {
    ecma: 2020,
    compress: { passes: 2 },
    mangle: true,
    format: { comments: false },
  });
  writeFileSync(t.out, out.code);
  console.log(`js ${t.out}: ${out.code.length} B`);
}
