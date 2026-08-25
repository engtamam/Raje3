/**
 * The one place that builds a link to a legal document.
 *
 * The console is mounted under a prefix (`import.meta.env.BASE_URL`, e.g. `/app/`), and a legal
 * document is served by the console itself now — not by a separate marketing site — so a link to
 * one must carry that same prefix. `VITE_LEGAL_BASE` remains as an escape hatch for pointing at a
 * real external site later, without every caller needing to change.
 */
export function legalBase(): string {
  const configured = import.meta.env.VITE_LEGAL_BASE;
  if (configured) return configured.replace(/\/$/, '');
  return `${import.meta.env.BASE_URL}legal`.replace(/\/{2,}/g, '/');
}

export function legalUrl(slug: string): string {
  return `${legalBase()}/${slug}`;
}
