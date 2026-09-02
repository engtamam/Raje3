/**
 * A minimal, correct CSV parser — RFC 4180 quoting (a quoted field may hold a comma, a newline, or
 * an escaped `""`), nothing pulled in for it. The service catalogue import (Services.tsx) is the
 * only caller today; kept generic (returns raw string[][]) rather than baking in that screen's
 * own column names, so a second importer never has to duplicate the quoting logic to reuse this.
 */

/** Parses CSV text into rows of raw string cells — no header handling, no type coercion, that is
 *  the caller's own job (this screen's own column meanings are not this file's business). Handles
 *  a trailing newline, CRLF and LF line endings, and a quoted field spanning multiple lines. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;
  // Normalise CRLF up front — the quote-aware scan below only has to reason about \n.
  const s = text.replace(/\r\n/g, '\n');

  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') { field += '"'; i++; }   // escaped quote
        else inQuotes = false;
      } else {
        field += c;
      }
      continue;
    }
    if (c === '"') { inQuotes = true; continue; }
    if (c === ',') { row.push(field); field = ''; continue; }
    if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; continue; }
    field += c;
  }
  // The last field/row has no trailing delimiter to close it — flush whatever remains, unless the
  // file's very last character was already a newline (that already flushed an empty nothing).
  if (field !== '' || row.length > 0) { row.push(field); rows.push(row); }
  return rows.filter((r) => !(r.length === 1 && r[0].trim() === ''));   // drop blank lines
}

/** Rows -> objects keyed by the FIRST row's own headers, trimmed and lower-cased for matching —
 *  "Name"/"name"/" Name " all reach a caller's `row.name` the same way. A short row (fewer cells
 *  than headers) pads with '' rather than throwing; a long one drops the extra cells — a ragged
 *  file is the caller's validation to report, not this function's to refuse. */
export function csvToObjects(rows: string[][]): Record<string, string>[] {
  if (rows.length === 0) return [];
  const headers = rows[0].map((h) => h.trim().toLowerCase());
  return rows.slice(1).map((r) => {
    const obj: Record<string, string> = {};
    headers.forEach((h, i) => { obj[h] = (r[i] ?? '').trim(); });
    return obj;
  });
}
