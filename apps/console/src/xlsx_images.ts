/**
 * Extracting a picture pasted into a row of an .xlsx file, by row number — the client-side half
 * of services-images-board.md's phase 2.
 *
 * WHY THIS EXISTS RATHER THAN A SERVER-SIDE PARSER. `services/operations/app/api/v1/staff.py`'s
 * own `ServiceImportRow` docstring is explicit: "the console parses the spreadsheet client-side
 * and sends structured rows, never a raw file; this service has no business knowing what a .csv
 * or .xlsx looks like." xlsx is a zip of XML — unzipping and parsing it is real CPU work, and
 * doing that on OUR server for every shop's import would load our shared infrastructure with
 * work the owner's own browser can do for free. So this file owns the whole thing: unzip, read
 * the drawing anchors, map a picture back to the ROW it was pasted into, hand back base64 bytes
 * + a MIME type per row — nothing here ever leaves the browser except the final bulk_import call.
 *
 * WHAT AN XLSX ACTUALLY CARRIES, JUST ENOUGH OF IT. An .xlsx is a zip. A picture anchored inside
 * a sheet is stored three times over: the bytes under `xl/media/imageN.<ext>`; a DRAWING
 * (`xl/drawings/drawingN.xml`) placing an ANCHOR (a "from row/col" box) that points at a drawing
 * relationship id (`r:embed="rIdN"`); and `xl/drawings/_rels/drawingN.xml.rels`, resolving that id
 * to the media file. This module reads exactly those three parts.
 *
 * NEITHER THE NAMESPACE PREFIX NOR THE TARGET PATH FORM IS RELIABLE ACROSS WRITERS, verified
 * against real output, not assumed: openpyxl (this product's own template generator) emits the
 * drawing tags with NO PREFIX at all (`<from>`, `<row>` — the spreadsheetDrawing namespace
 * declared as the DEFAULT) and ABSOLUTE relationship targets (`Target="/xl/drawings/drawing1.xml"`);
 * Excel/Google Sheets/LibreOffice conventionally prefix with `xdr:` and write targets RELATIVE to
 * the referencing part (`Target="../drawings/drawing1.xml"`). Every tag match below tolerates an
 * optional `\w+:` prefix, and `resolvePart` below resolves both an absolute and a relative target.
 */
import JSZip from 'jszip';

export interface ExtractedImage {
  /** The 1-indexed spreadsheet row the picture's anchor starts on (matches `ParsedRow.line`). */
  row: number;
  /** Raw bytes, base64-encoded — never a data: URL prefix, matches `CatalogueImageIn.data_base64`. */
  base64: string;
  contentType: string;
}

const EXT_TO_TYPE: Record<string, string> = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp',
};

function bytesToBase64(bytes: Uint8Array): string {
  // No btoa(String.fromCharCode(...bytes)) — that blows the call stack on anything but a tiny
  // image (V8's argument-spread limit is well under a real photo's byte count). Chunked instead.
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

/** An OOXML relationship `Target`, resolved against the part that references it — handles both
 *  an ABSOLUTE target ("/xl/media/image1.png") and a RELATIVE one ("../media/image1.png",
 *  relative to `fromDir`) since real writers use either form (see module docstring). */
function resolvePart(target: string, fromDir: string): string {
  if (target.startsWith('/')) return target.slice(1);
  const parts = fromDir.split('/').filter(Boolean);
  for (const seg of target.split('/')) {
    if (seg === '..') parts.pop();
    else if (seg && seg !== '.') parts.push(seg);
  }
  return parts.join('/');
}

/** `attr(tag, "Target")` — order-independent attribute read off one XML start-tag, since real
 *  writers do not agree on attribute order (openpyxl: Type, Target, Id; a typical Excel export:
 *  Id, Type, Target). */
function attr(tag: string, name: string): string | undefined {
  return new RegExp(`${name}="([^"]*)"`).exec(tag)?.[1];
}

/** Every `<Relationship .../>` in a `.rels` part, as `Id -> {type, target}`. */
function readRels(xml: string): Map<string, { type: string; target: string }> {
  const out = new Map<string, { type: string; target: string }>();
  const re = /<Relationship\b[^>]*\/>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml))) {
    const id = attr(m[0], 'Id');
    const type = attr(m[0], 'Type');
    const target = attr(m[0], 'Target');
    if (id && type && target) out.set(id, { type, target });
  }
  return out;
}

/** The FIRST sheet's drawing, if it has one — every workbook this product's import produces or
 *  accepts is single-sheet (see the template generator), so there is no "which sheet" question
 *  to answer. A workbook with no drawing at all (no pasted pictures) returns []. */
export async function extractRowImages(file: ArrayBuffer | Uint8Array): Promise<ExtractedImage[]> {
  const zip = await JSZip.loadAsync(file);

  const sheetRelsXml = await zip.file('xl/worksheets/_rels/sheet1.xml.rels')?.async('string');
  if (!sheetRelsXml) return [];
  const sheetRels = readRels(sheetRelsXml);
  const drawingRel = [...sheetRels.values()].find((r) => r.type.endsWith('/drawing'));
  if (!drawingRel) return [];
  const drawingPath = resolvePart(drawingRel.target, 'xl/worksheets');

  const drawingXml = await zip.file(drawingPath)?.async('string');
  if (!drawingXml) return [];

  const drawingDir = drawingPath.slice(0, drawingPath.lastIndexOf('/'));
  const drawingRelsPath = `${drawingDir}/_rels/${drawingPath.slice(drawingPath.lastIndexOf('/') + 1)}.rels`;
  const drawingRelsXml = await zip.file(drawingRelsPath)?.async('string');
  const drawingRels = drawingRelsXml ? readRels(drawingRelsXml) : new Map();

  const out: ExtractedImage[] = [];
  // Each anchor starts with `<from>` (optionally `xdr:from`) holding a `<row>` — a 0-indexed row
  // AGAINST THE SHEET (row 0 is the header), and a blip somewhere inside pointing at a
  // relationship id. `oneCellAnchor` and `twoCellAnchor` are the two shapes a pasted picture can
  // take; both carry the same `<from>` block.
  const anchorRe = /<(?:\w+:)?(?:one|two)CellAnchor\b[\s\S]*?<\/(?:\w+:)?(?:one|two)CellAnchor>/g;
  let anchor: RegExpExecArray | null;
  while ((anchor = anchorRe.exec(drawingXml))) {
    const block = anchor[0];
    const fromMatch = /<(?:\w+:)?from>([\s\S]*?)<\/(?:\w+:)?from>/.exec(block);
    const rowMatch = fromMatch && /<(?:\w+:)?row>(\d+)<\/(?:\w+:)?row>/.exec(fromMatch[1]);
    const ridMatch = /r:embed="([^"]+)"/.exec(block);
    if (!rowMatch || !ridMatch) continue;
    const rel = drawingRels.get(ridMatch[1]);
    if (!rel) continue;
    const mediaPath = resolvePart(rel.target, drawingDir);
    const mediaFile = zip.file(mediaPath);
    if (!mediaFile) continue;
    const ext = (mediaPath.split('.').pop() || '').toLowerCase();
    const contentType = EXT_TO_TYPE[ext];
    if (!contentType) continue;  // an embedded .emf/.wmf or similar — not a photo we accept
    const bytes = await mediaFile.async('uint8array');
    // row 0 = the header, row 1 = the first data row = `line` 2 (parseRows' own "+1 header,
    // +1 one-indexed") — so the anchor's row, shifted by one, IS the matching `ParsedRow.line`.
    out.push({ row: parseInt(rowMatch[1], 10) + 1, base64: bytesToBase64(bytes), contentType });
  }
  return out;
}

/** The column-letter prefix of a cell reference ("C7" -> "C"). */
function colOf(cellRef: string): string {
  return /^[A-Z]+/.exec(cellRef)?.[0] ?? '';
}

/** `xl/sharedStrings.xml` — an .xlsx text cell stores an INDEX into this table, not its own text,
 *  so a value only makes sense read back through it. Absent (a workbook with no text at all, or
 *  one that inlines every string) is a valid, empty table. */
async function readSharedStrings(zip: JSZip): Promise<string[]> {
  const xml = await zip.file('xl/sharedStrings.xml')?.async('string');
  if (!xml) return [];
  const out: string[] = [];
  const siRe = /<si>([\s\S]*?)<\/si>/g;
  let m: RegExpExecArray | null;
  while ((m = siRe.exec(xml))) {
    // A rich-text run (<r><t>a</t></r><r><t>b</t></r>) concatenates to one string, same as a
    // plain <t>text</t> — a shop's bold/colored word inside a cell must not become two columns.
    const parts = [...m[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]);
    out.push(decodeXmlEntities(parts.join('')));
  }
  return out;
}

function decodeXmlEntities(s: string): string {
  // NUMERIC ENTITIES FIRST, AND THIS IS NOT OPTIONAL. openpyxl (this product's own template
  // generator) writes every non-ASCII character — Arabic text included — as `&#1234;`/`&#x4D2;`,
  // never as literal UTF-8 bytes in the XML. Skipping this step silently turned every Arabic cell
  // into its own escape sequence rather than the text it holds — found by this module's own test
  // against a real generated fixture, not assumed.
  return s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(parseInt(dec, 10)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}

/** Every data row of the FIRST sheet, as plain objects keyed by its own header row — the same
 *  shape `csvToObjects(parseCsv(text))` already produces for a .csv, so `parseRows` (or its
 *  object-based twin) never needs to know which file format it came from. Column ORDER is not
 *  assumed — a header is matched to a data cell by COLUMN LETTER, the same way a CSV column is
 *  matched by its position, so a shop that reorders columns still imports correctly. */
export async function readXlsxRows(file: ArrayBuffer | Uint8Array): Promise<Record<string, string>[]> {
  const zip = await JSZip.loadAsync(file);
  const sheetXml = await zip.file('xl/worksheets/sheet1.xml')?.async('string');
  if (!sheetXml) return [];
  const shared = await readSharedStrings(zip);

  const rowRe = /<row\b[^>]*r="(\d+)"[^>]*>([\s\S]*?)<\/row>/g;
  // `([\s\S]*?)` DIRECTLY, NEVER WRAPPED IN A REDUNDANT `(?:...)?` — that nested optional-around-
  // lazy overshoots past an EMPTY cell's own immediate `</c>` and swallows the next cell entirely
  // (reproduced directly: `<c r="E2" ...></c><c r="F2">...</c>` matched E2's body as everything up
  // to F2's OWN closing tag, when E2's cell is genuinely empty). A lazy star alone already means
  // "zero or more, prefer fewer" — the outer `?` added nothing but this bug.
  const cellRe = /<c\b([^>]*)>([\s\S]*?)<\/c>|<c\b([^>]*)\/>/g;

  function cellsOf(rowInner: string): Map<string, string> {
    const out = new Map<string, string>();
    let m: RegExpExecArray | null;
    cellRe.lastIndex = 0;
    while ((m = cellRe.exec(rowInner))) {
      const attrs = m[1] ?? m[3] ?? '';
      const ref = attr(`<c ${attrs}>`, 'r');
      if (!ref) continue;
      const type = attr(`<c ${attrs}>`, 't');
      const body = m[2] ?? '';
      let value = '';
      if (type === 's') {
        const idx = /<v>(\d+)<\/v>/.exec(body)?.[1];
        value = idx !== undefined ? (shared[parseInt(idx, 10)] ?? '') : '';
      } else if (type === 'inlineStr') {
        value = decodeXmlEntities(/<t[^>]*>([\s\S]*?)<\/t>/.exec(body)?.[1] ?? '');
      } else {
        value = decodeXmlEntities(/<v>([\s\S]*?)<\/v>/.exec(body)?.[1] ?? '');
      }
      out.set(colOf(ref), value);
    }
    return out;
  }

  const rows: { n: number; cells: Map<string, string> }[] = [];
  let rm: RegExpExecArray | null;
  while ((rm = rowRe.exec(sheetXml))) {
    rows.push({ n: parseInt(rm[1], 10), cells: cellsOf(rm[2]) });
  }
  if (rows.length === 0) return [];

  const header = rows[0];
  const headerByCol = new Map<string, string>();
  for (const [col, text] of header.cells) headerByCol.set(col, text.trim().toLowerCase());

  return rows.slice(1).map((r) => {
    const obj: Record<string, string> = {};
    for (const [col, name] of headerByCol) {
      if (name) obj[name] = r.cells.get(col) ?? '';
    }
    return obj;
  });
}
