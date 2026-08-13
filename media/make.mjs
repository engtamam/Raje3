/**
 * `node media/make.mjs` — ويخرج كل شيء.
 *
 * لا مسارات تُكتب، ولا مدد تُمرَّر، ولا ffmpeg يُبحَث عنه: يمرّ على كل صفحةٍ في `ads/`
 * و`tours/` ويصيّرها. والصفحة تعلن طولها ومقاسها يُشتقّ من مجلدها، فما بقي شيءٌ يُقال
 * باليد أصلاً.
 *
 * وواحدةٌ تفشل فلا تُسقط البقيّة: يُطبع الخطأ ويُكمَل، ويُلخَّص في النهاية — فبناءٌ يقف
 * عند أول عثرة يترك المكتبة نصفها قديم ونصفها جديد بلا أن يقول أيّهما.
 *
 *     node media/make.mjs            كل شيء
 *     node media/make.mjs proof      ما يطابق «proof» في اسمه
 */
import { spawn } from 'node:child_process';
import { readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const filter = process.argv[2] || '';

const pages = ['ads', 'tours']
  .filter((d) => existsSync(join(HERE, d)))
  .flatMap((d) => readdirSync(join(HERE, d))
    .filter((f) => f.endsWith('.html'))
    .map((f) => join(HERE, d, f)))
  .filter((f) => !filter || f.includes(filter));

if (!pages.length) {
  console.log('لا توجد صفحات للتصيير' + (filter ? ` تطابق «${filter}»` : '') + '.');
  process.exit(0);
}

const done = [];
const failed = [];

for (const page of pages) {
  const code = await new Promise((ok) => {
    const p = spawn(process.execPath, [join(HERE, 'record.mjs'), page], { stdio: 'inherit' });
    p.on('close', ok);
  });
  (code === 0 ? done : failed).push(page);
}

console.log('');
console.log(`تمّ ${done.length}` + (failed.length ? ` · فشل ${failed.length}` : ''));
for (const f of failed) console.log('  ✖ ' + f);
process.exit(failed.length ? 1 : 0);
