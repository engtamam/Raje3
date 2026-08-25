// Turns deploy/seed/legal/*.yaml into a document a public route can render — the real published
// text, read at build/dev time rather than copied by hand into a component. A later edit to a
// document's wording needs no code change here: it is picked up the next time this plugin loads.
//
// TWO SOURCES, ONE DOCUMENT. Most of these files are not the whole document — they are the VALUES
// that fill a template. compliance-service's PDPL pack (platform/services/compliance-service/app/
// data/pdpl-templates/*.yaml) holds the actual clause text with `{{TOKEN}}` placeholders, in the
// same block vocabulary its own renderer already understands (`{ kind: {…fields} }`); our seed file
// supplies the values and whatever this business adds beyond the template (`additions`,
// `categories`, `removed`). `terms.yaml` is the one document with no template at all — the PDPL
// pack has no service contract, so its `clauses:` are the whole document and are converted to the
// same block shape here. Reading the pack is a READ ONLY use of platform/, the same way vite.config
// already consumes platform/ui as source: nothing under platform/ is written.
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import * as yaml from 'js-yaml';
import type { Plugin } from 'vite';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// ONLY THE DOCUMENTS A PERSON MAY READ WITHOUT AN ACCOUNT. `accept` gates a subscription and its
// text must be readable before that acceptance; `public` is a disclosure by definition. Everything
// else — `reference` (the DPA, incorporated by reference into the Terms rather than published on
// its own) and `internal` (the DPIA, the ROPA) — is deliberately excluded: it was never meant to
// be reached by a URL.
const READABLE = new Set(['public', 'accept']);

// Which seed file fills which template in the pack — the same mapping ci/check_legal.py uses to
// verify every token is answered. `''` means the document is entirely our own (terms.yaml).
const TEMPLATES: Record<string, string> = {
  'privacy-policy.yaml': 'doc01_privacy_policy.yaml',
  'cookies.yaml': 'doc12_cookies.yaml',
  'data-subject-rights.yaml': 'doc03_data_subject_rights.yaml',
};

type Bilingual = { ar?: string; en?: string };
type DocBlock = Record<string, Record<string, unknown>>;

function isBilingual(v: unknown): v is Bilingual {
  return Boolean(v) && typeof v === 'object'
    && (typeof (v as Bilingual).ar === 'string' || typeof (v as Bilingual).en === 'string');
}

function humanize(key: string): Bilingual {
  const en = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return { ar: en, en };
}

// A clause map (terms.yaml's `clauses:`, or a seed document's `additions:`) → `clause` blocks. Each
// entry is `{ title?, ar, en }` or, for additions, just `{ ar, en }` — the key itself becomes the
// title when the entry carries none of its own.
function clausesToBlocks(map: Record<string, unknown>): DocBlock[] {
  return Object.entries(map).map(([key, raw]) => {
    const entry = (raw ?? {}) as Record<string, unknown>;
    const title = isBilingual(entry.title) ? entry.title : humanize(key);
    const ar = typeof entry.ar === 'string' ? entry.ar : '';
    const en = typeof entry.en === 'string' ? entry.en : '';
    return { clause: { title, paras: [{ ar, en }] } };
  });
}

// A category list (cookies' / the privacy policy's tables) → one `clause` per row, its `name`
// becoming the title and every other field folded into a labelled paragraph — generic on purpose,
// since the fields differ between documents (purpose/consent/retention vs. examples/required).
function categoriesToBlocks(list: unknown[]): DocBlock[] {
  return list.map((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>;
    const title = isBilingual(item.name) ? item.name : { ar: '', en: '' };
    const paras: Bilingual[] = [];
    for (const [key, value] of Object.entries(item)) {
      if (key === 'name' || !isBilingual(value)) continue;
      const label = humanize(key);
      paras.push({
        ar: `${label.ar}: ${value.ar ?? value.en ?? ''}`,
        en: `${label.en}: ${value.en ?? value.ar ?? ''}`,
      });
    }
    return { clause: { title, paras } };
  });
}

// A plain list of bilingual notes (cookies' `removed:`) → prose blocks with no heading of their own.
function notesToBlocks(list: unknown[]): DocBlock[] {
  return list
    .filter(isBilingual)
    .map((n) => ({ lead: { text: { ar: n.ar ?? '', en: n.en ?? '' } } }));
}

function sectionHeading(ar: string, en: string): DocBlock {
  return { section: { level: 2, text: { ar, en } } };
}

export interface LegalDoc {
  slug: string;
  publication: string;
  title: { ar: string; en: string };
  blocks: DocBlock[];
  // Raw `values:`, bilingual-aware — the resolver a reader's locale looks `{{TOKEN}}` up against.
  values: Record<string, unknown>;
}

function loadPackBlocks(packDir: string, file: string): DocBlock[] {
  const parsed = yaml.load(readFileSync(`${packDir}/${file}`, 'utf8')) as
    { blocks?: DocBlock[] } | null;
  const blocks = parsed?.blocks ?? [];
  // The page renders its own bilingual heading above the document; the template's own `cover`
  // block would repeat it a second time immediately below.
  return blocks.filter((b) => b && typeof b === 'object' && !('cover' in b));
}

function buildDocs(seedDir: string, packDir: string): LegalDoc[] {
  const docs: LegalDoc[] = [];
  for (const file of readdirSync(seedDir)) {
    if (!file.endsWith('.yaml')) continue;
    const slug = file.replace(/\.yaml$/, '');
    const parsed = yaml.load(readFileSync(`${seedDir}/${file}`, 'utf8')) as
      Record<string, unknown> | null;
    if (!parsed || typeof parsed !== 'object') continue;
    const publication = String(parsed.publication ?? '');
    if (!READABLE.has(publication)) continue;

    const values = (parsed.values as Record<string, unknown>) ?? {};
    const templateFile = TEMPLATES[file];
    const baseBlocks = templateFile ? loadPackBlocks(packDir, templateFile) : [];

    const extra: DocBlock[] = [];
    if (parsed.clauses && typeof parsed.clauses === 'object') {
      // terms.yaml only: the whole document, no template beneath it.
      extra.push(...clausesToBlocks(parsed.clauses as Record<string, unknown>));
    }
    if (parsed.categories && Array.isArray(parsed.categories)) {
      extra.push(sectionHeading('الفئات', 'Categories'));
      extra.push(...categoriesToBlocks(parsed.categories));
    }
    if (parsed.additions && typeof parsed.additions === 'object') {
      extra.push(sectionHeading('إضافات', 'Additions'));
      extra.push(...clausesToBlocks(parsed.additions as Record<string, unknown>));
    }
    if (parsed.removed && Array.isArray(parsed.removed)) {
      extra.push(sectionHeading('ما لا نستخدمه', 'What we do not use'));
      extra.push(...notesToBlocks(parsed.removed));
    }

    const titleBlock = TITLES[slug];
    docs.push({
      slug,
      publication,
      title: titleBlock ?? humanize(slug),
      blocks: [...baseBlocks, ...extra],
      values,
    });
  }
  return docs;
}

// A friendly heading for a document a filename alone does not name well. A file this list does not
// know about still renders — under a heading built from its filename — so a new legal document
// becomes reachable the moment it exists, with no matching entry required here.
const TITLES: Record<string, { ar: string; en: string }> = {
  terms: { ar: 'الشروط والأحكام', en: 'Terms and Conditions' },
  'privacy-policy': { ar: 'سياسة الخصوصية', en: 'Privacy Policy' },
  cookies: { ar: 'سياسة ملفات الارتباط', en: 'Cookie Policy' },
  'data-subject-rights': { ar: 'حقوق أصحاب البيانات', en: 'Data Subject Rights Notice' },
  'affiliate-agreement': { ar: 'اتفاقية المسوّقين', en: 'Affiliate Agreement' },
};

export function legalDocsPlugin(): Plugin {
  const virtualId = 'virtual:legal-docs';
  const resolvedId = `\0${virtualId}`;
  const seedDir = here('../../../deploy/seed/legal');
  const packDir = here('../../../platform/services/compliance-service/app/data/pdpl-templates');

  return {
    name: 'legal-docs',
    resolveId(id) {
      if (id === virtualId) return resolvedId;
      return undefined;
    },
    load(id) {
      if (id !== resolvedId) return undefined;
      const docs = buildDocs(seedDir, packDir);
      return `export default ${JSON.stringify(docs)};`;
    },
    configureServer(server) {
      // A change to a .yaml source must be seen without a manual restart — vite otherwise only
      // watches files it has actually imported, and a virtual module's real dependency is invisible
      // to it.
      for (const dir of [seedDir, packDir]) {
        server.watcher.add(dir);
      }
      server.watcher.on('change', (file) => {
        if (!file.startsWith(seedDir) && !file.startsWith(packDir)) return;
        const mod = server.moduleGraph.getModuleById(resolvedId);
        if (mod) server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: 'full-reload' });
      });
    },
  };
}
