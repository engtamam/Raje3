/**
 * A public legal document — reachable with no session, because the person who most needs to read
 * one has not signed up yet (the consent line on the door) or has never had an account at all (a
 * shop's customer looking up his rights). It is not a route inside `<App>`: `<App>` shows the door
 * to anyone signed out, and this must render for exactly that person.
 *
 * THE CONTENT IS NEVER TYPED HERE. `virtual:legal-docs` (scripts/legalDocsPlugin.ts) reads
 * deploy/seed/legal's YAML plus compliance-service's PDPL pack at build/dev time and produces the
 * real block document; a later edit to the Terms changes this page the next time it is built, with
 * nothing here to touch.
 *
 * THE RENDERER IS compliance-service's OWN, REUSED RATHER THAN REBUILT. `DocBlocksView` already
 * knows this exact block vocabulary and its `{{TOKEN}}` convention — it is what renders these same
 * documents inside the signed-in legal gate. `resolve` here is a plain lookup into the seed file's
 * `values:`, bilingual-aware the same way the template's own placeholders are.
 */
import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { DocBlocksView, type DocBlock } from '@base-ui/components/DocBlockRenderer';
import docs from 'virtual:legal-docs';
import { translate } from '../operator-i18n';
import './legal-i18n';

type Locale = 'ar' | 'en';

function resolverFor(values: Record<string, unknown>, locale: Locale) {
  return (key: string): string | undefined => {
    const v = values[key];
    if (typeof v === 'string') return v;
    if (v && typeof v === 'object') {
      const o = v as Record<string, unknown>;
      const picked = o[locale] ?? o.en ?? o.ar;
      return typeof picked === 'string' ? picked : undefined;
    }
    return undefined;
  };
}

export function Legal() {
  const { slug } = useParams<{ slug: string }>();
  const [locale, setLocale] = useState<Locale>('ar');
  const doc = docs.find((d) => d.slug === slug);
  // NO SESSION HERE (a signed-out visitor, or a shop's own customer) — `useOperatorI18n()` requires
  // `<OperatorI18nProvider>`, which this route sits outside of. `translate()` is the same
  // dictionary lookup, keyed directly by this screen's own `locale` state.
  const t = (key: string) => translate(locale, key);

  return (
    <main dir="rtl" className="mx-auto max-w-3xl px-6 py-10 bg-surface-0 min-h-dvh">
      <div className="flex items-center justify-between">
        <Link to="../.." relative="path" className="text-sm text-text-secondary underline">
          {t('legal.back')}
        </Link>
        {doc && (
          <button
            type="button"
            className="text-sm text-text-secondary underline"
            onClick={() => setLocale((l) => (l === 'ar' ? 'en' : 'ar'))}
          >
            {locale === 'ar' ? t('legal.switchToEnglish') : t('legal.switchToArabic')}
          </button>
        )}
      </div>
      {!doc ? (
        <div className="mt-8">
          <h1 className="text-xl font-semibold">{t('legal.notFoundTitle')}</h1>
          <p className="mt-2 text-text-secondary">
            {t('legal.availableDocs')}{' '}
            {docs.map((d) => (
              <Link key={d.slug} to={`../${d.slug}`} relative="path" className="underline mx-1">
                {d.title.ar}
              </Link>
            ))}
          </p>
        </div>
      ) : (
        <article>
          <h1 className="text-2xl font-bold mt-6" dir={locale === 'ar' ? 'rtl' : 'ltr'}>
            {locale === 'ar' ? doc.title.ar : doc.title.en}
          </h1>
          <div className="mt-8">
            <DocBlocksView
              blocks={doc.blocks as DocBlock[]}
              locale={locale}
              resolve={resolverFor(doc.values, locale)}
              unfilledLabel={t('legal.unfilled')}
            />
          </div>
        </article>
      )}
    </main>
  );
}
