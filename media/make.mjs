/**
 * `node media/make.mjs` — ويخرج كل شيء.
 *
 * لا مسارات تُكتب، ولا مدد تُمرَّر، ولا ffmpeg يُبحَث عنه: يمرّ على كل صفحةٍ في `ads/`
 * وكل رحلةٍ في `tours/scripts/` ويصيّرها. والصفحة تعلن طولها ومقاسها يُشتقّ من مجلدها،
 * فما بقي شيءٌ يُقال باليد أصلاً.
 *
 * صفحات `ads/*.html` مصمَّمة يدويًا — ثابتة، بلا اتصال بالتطبيق الحي، فتُصوَّر بساعةٍ
 * مزوّرة (`record.mjs`). ورحلات `tours/scripts/*.mjs` بيانات تصف تفاعلاً مع التطبيق
 * الحي نفسه، فتُصوَّر بزمنٍ حقيقي (`record-tour.mjs`) — انظر رأس ذاك الملف لسبب الفرق.
 * كلا الأمرين يُشتقّان من امتداد الملف ومكانه، لا من قائمةٍ تُكتب هنا باليد.
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

function glob(dir, ext) {
  const full = join(HERE, dir);
  if (!existsSync(full)) return [];
  return readdirSync(full).filter((f) => f.endsWith(ext)).map((f) => join(full, f));
}

// { file, recorder } pairs — the recorder to use is a property of WHERE a page lives and WHAT
// kind of file it is, never a name added to a manual list.
const jobs = [
  ...glob('ads', '.html').map((file) => ({ file, recorder: 'record.mjs' })),
  ...glob('tours/scripts', '.mjs').map((file) => ({ file, recorder: 'record-tour.mjs' })),
].filter((j) => !filter || j.file.includes(filter));

if (!jobs.length) {
  console.log('لا توجد صفحات للتصيير' + (filter ? ` تطابق «${filter}»` : '') + '.');
  process.exit(0);
}

const done = [];
const failed = [];

for (const { file, recorder } of jobs) {
  const script = recorder === 'record.mjs' ? join(HERE, recorder) : join(HERE, 'tours', recorder);
  const code = await new Promise((ok) => {
    const p = spawn(process.execPath, [script, file], { stdio: 'inherit' });
    p.on('close', ok);
  });
  (code === 0 ? done : failed).push(file);
}

console.log('');
console.log(`تمّ ${done.length}` + (failed.length ? ` · فشل ${failed.length}` : ''));
for (const f of failed) console.log('  ✖ ' + f);
process.exit(failed.length ? 1 : 0);
