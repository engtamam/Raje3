/**
 * Writing his own wording for one message — with blanks he cannot get wrong.
 *
 * THE PROBLEM EVERY TEMPLATE EDITOR HAS. WhatsApp numbers its blanks and names nothing: the body
 * that leaves is «أهلاً {{1}}، حان وقت {{2}}». An owner asked to type that will mistype it, leave a
 * gap in the numbering, or ask for a blank his message has no value for — and every one of those
 * failures appears LATER: at Meta's review, or worse, at a send that quietly never happens.
 *
 * SO HE NEVER TYPES A NUMBER. He taps «اسم العميل» and a chip appears; the numbering is generated
 * from the order the chips sit in when he saves. A chip is `contenteditable=false`, so it cannot
 * be half-deleted into `{{1` — backspace removes the whole thing, which is what he meant anyway.
 *
 * AND THE PALETTE OFFERS ONLY WHAT THIS MESSAGE CAN FILL. A visit confirmation knows the customer
 * and the shop; it does not know a coupon code. Offering one would let him write a text that
 * passes Meta's review and then renders nothing — the exact failure the reason registry exists
 * to prevent, made impossible here rather than caught later.
 *
 * THE CARET TRICK IS BORROWED, and it is the one thing a hand-rolled contentEditable always gets
 * wrong: re-rendering on every keystroke moves the caret to the end. The element keeps a copy of
 * what it is showing in `data-src`, and we only rewrite it when the OUTSIDE value differs from
 * that copy — so typing never causes a rewrite, and an external change still lands.
 */
import { useEffect, useRef, useState } from 'react';
// STAYS ON THE KIT'S MODAL, DELIBERATELY. This one opens NESTED — while MessagePreview's own
// Modal is already open (`writing` inside it, MessagePreview.tsx) — and rj-ui/Modal's own scope
// note says exactly this case is unhandled: a single-dialog implementation with no stacking
// registry, so two of them open at once would both bind Escape and both close together. The
// kit's Modal exists precisely to coordinate that; reimplementing its registry here risks the
// bug it was built to prevent the moment this modal ever had to coexist with another one — which
// is exactly what happens the first time an owner opens the editor from inside the preview.
import { Modal } from '@base-ui/design-system/Modal';
import { Button } from '../rj-ui/Button';
import { Lock, Plus } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

export interface Slot { id: string; label: string; sample?: string }

/**
 * The one blank he does not choose and cannot delete — the stop link on a promotional message,
 * the consent invitation on everything else.
 *
 * IT COMES FROM THE SERVER, NAMED. The screen never works out WHICH address this message owes:
 * that rule has one owner (`reasons.mandatory_tail`), read by the library generator and the draft
 * path too, and a fourth reader here is the drift this product has already paid for once.
 */
export interface Mandatory { id: string; label: string; sample?: string; note?: string }

/** What the editor holds while he writes: the text, and what each chip in it means. */
interface Draft { html: string }

const CHIP =
  'rich-chip mx-0.5 inline-block rounded-md bg-surface-2 px-1.5 py-0.5 text-xs ' +
  'font-medium text-text-secondary align-baseline';

function chipHtml(slot: Slot): string {
  // `data-kind` is the whole contract with the serialiser below: the DOM is the model, and this
  // attribute is what survives the round trip through the browser's own editing.
  return `<span contenteditable="false" data-kind="${slot.id}" class="${CHIP}">${slot.label}</span>`;
}

/**
 * The inverse of `readBack`: his saved body — WhatsApp's `{{1}}` numbering — back into the editor's
 * own markup, so «عدّل نصّي» opens on what he wrote rather than on a blank box.
 *
 * THE ORDER IS THE MEANING. `{{1}}` is the first slot this reason declares, `{{2}}` the second —
 * the same contract `readBack` writes out, read the other way. A number with no slot behind it is
 * left as the literal text: it is a template we no longer understand, and silently deleting a
 * blank out of his message would be worse than showing it to him as it is.
 */
function toHtml(body: string, slots: Slot[]): string {
  const escape = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escape(body)
    .replace(/\{\{(\d+)\}\}/g, (whole, n) => {
      const slot = slots[Number(n) - 1];
      return slot ? chipHtml(slot) : whole;
    })
    .replace(/\n/g, '<br>');
}

/**
 * His saved body WITHOUT the address the server appended to it.
 *
 * WHY IT IS TAKEN OFF BEFORE HE SEES IT. The tail is the last blank of every saved text, and it is
 * no longer in the palette — so `toHtml` would find no slot for that number and leave it in the
 * box as a literal «{{4}}»: the one thing this editor exists to make sure he never sees. He does
 * not edit it, cannot move it, and the server puts it back on the next save, so the honest thing
 * to show him is his own sentence, with the locked strip below saying what follows it.
 */
function withoutTail(body: string, mandatory?: Mandatory): string {
  if (!mandatory) return body;
  return body.replace(/\s*\{\{\d+\}\}\s*$/, '');
}

/** Walk the editable and read back the text and the meanings, in the order they appear. */
function readBack(root: HTMLElement): { body: string; fills: string[] } {
  const fills: string[] = [];
  let body = '';
  const walk = (node: Node) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        body += child.textContent ?? '';
        return;
      }
      const el = child as HTMLElement;
      const kind = el.getAttribute?.('data-kind');
      if (kind) {
        // THE NUMBER IS GENERATED HERE AND NOWHERE ELSE, from position. Meta refuses a gap, and a
        // gap is exactly what hand-numbering produces the first time a chip is deleted.
        fills.push(kind);
        body += `{{${fills.length}}}`;
        return;
      }
      if (el.tagName === 'BR' || el.tagName === 'DIV' || el.tagName === 'P') body += '\n';
      walk(el);
    });
  };
  walk(root);
  return { body: body.replace(/\n{3,}/g, '\n\n').trim(), fills };
}

export function TextEditor({
  session, catalog, reasonId, label, slots, mandatory, body, replaces, onClose, onSaved,
}: {
  session: Session;
  catalog: Catalog;
  reasonId: string;
  label: string;
  slots: Slot[];
  /** The address this message owes its reader — shown LOCKED, never offered as a chip. */
  mandatory?: Mandatory;
  /** WHAT HE WROTE LAST TIME. The editor opened blank while his saved text sat one component away
   *  in `Mine.body`, unpassed — so «عدّل نصّي» meant «اكتبه again from nothing», and the second
   *  edit of any template was a rewrite. `draft` was declared for this and never set. */
  body?: string;
  /** The name of the text this one supersedes, when he is editing rather than writing his first.
   *  Meta freezes a name at approval, so a revision is a NEW name at the next version — and the
   *  old text keeps sending until Meta approves the new one. */
  replaces?: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState<Draft>({ html: toHtml(withoutTail(body ?? '', mandatory), slots) });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  /** What the customer would read — the same substitution the preview does, done live. */
  const [sample, setSample] = useState('');

  // THE CARET-STABLE SYNC. Only rewrite when the value we hold differs from what the element says
  // it is showing; typing therefore never causes a rewrite.
  useEffect(() => {
    const el = box.current;
    if (el && el.getAttribute('data-src') !== draft.html) {
      el.innerHTML = draft.html;
      el.setAttribute('data-src', draft.html);
    }
  }, [draft]);

  const refresh = () => {
    const el = box.current;
    if (!el) return;
    const { body, fills } = readBack(el);
    let shown = body;
    fills.forEach((kind, i) => {
      const slot = slots.find((s) => s.id === kind);
      shown = shown.replace(`{{${i + 1}}}`, slot?.sample || slot?.label || '');
    });
    // WHAT ACTUALLY ARRIVES, not what he typed. The server appends the address at save, so a
    // preview that stopped at his last word would show him a shorter message than the one his
    // customer reads — and «كما تصل عميلك» is the one line on this screen that may not be
    // approximately true.
    setSample(mandatory ? `${shown} ${mandatory.sample || mandatory.label}` : shown);
  };

  const insert = (slot: Slot) => {
    const el = box.current;
    if (!el) return;
    el.focus();
    // AT THE CARET, NOT AT THE END. He is writing a sentence, and a chip that always lands after
    // the full stop is a chip he has to drag — which is the interaction we are avoiding.
    const ok = document.execCommand('insertHTML', false, chipHtml(slot) + '&nbsp;');
    if (!ok) el.insertAdjacentHTML('beforeend', chipHtml(slot) + '&nbsp;');
    el.setAttribute('data-src', el.innerHTML);
    refresh();
  };

  const save = async () => {
    const el = box.current;
    const a = action(catalog, 'reminders.write_template');
    if (!el || !a) return;
    const { body, fills } = readBack(el);
    if (!body.trim()) { setError('اكتب نصّ الرسالة أولاً.'); return; }
    setSaving(true); setError('');
    try {
      const out = await call<{ ok?: boolean; error?: string }>(
        session, a, { reason_id: reasonId, body, fills, replaces: replaces ?? '' });
      // THE SERVER'S OWN SENTENCE, never re-worded here. It knows why it refused — a link, a blank
      // this message cannot fill, an app entitlement limit — and two vocabularies for one refusal is how an
      // owner comes to believe there are two problems.
      if (out?.error) { setError(out.error); return; }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} size="lg"
           title={`نصّك لرسالة «${label}»`}
           subtitle="اكتب كما تحب، وأضف الفراغات بنقرة — نحن نرقّمها.">
      <div className="flex flex-col gap-4">
        {/* ── the palette: only what THIS message can fill ─────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-text-secondary">أضف:</span>
          {slots.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => insert(s)}
              className="flex items-center gap-1 rounded-full border border-border-subtle bg-surface-2 px-2.5 py-1 text-xs hover:bg-surface-3"
            >
              <Plus size={12} aria-hidden />
              {s.label}
            </button>
          ))}
        </div>

        <div
          ref={box}
          contentEditable
          role="textbox"
          aria-multiline="true"
          aria-label="نصّ الرسالة"
          dir="rtl"
          onInput={refresh}
          onBlur={refresh}
          className="min-h-[7rem] rounded-card border border-border-subtle bg-surface-1 p-3 text-sm leading-relaxed outline-none focus:border-accent"
        />

        {/* ── the one blank he does not choose, shown rather than hidden ────────────────
            LOCKED, NOT ABSENT. An owner who does not see it in his text believes it is not in
            his text — and the first he learns otherwise is a customer's reply, or a letter from
            a regulator about a promotional message with no way to stop it. It is deliberately
            NOT in the palette above: offering it as a chip would let him drop a second one
            mid-sentence, which the save then refuses. */}
        {mandatory ? (
          <div className="flex flex-wrap items-center gap-2 rounded-card border border-dashed border-border-subtle bg-surface-2 px-3 py-2">
            <span className="text-xs text-text-secondary">وفي آخر الرسالة دائماً:</span>
            <span className={CHIP} aria-label={`${mandatory.label} — مقفل`}>{mandatory.label}</span>
            <Lock size={12} aria-hidden className="text-text-secondary" />
            <span className="text-xs text-text-secondary">{mandatory.note}</span>
          </div>
        ) : null}

        {/* ── what the customer reads ──────────────────────────────────────────────────── */}
        <section className="flex flex-col gap-2">
          <h3 className="text-xs text-text-secondary">كما تصل عميلك</h3>
          {/* WHATSAPP'S OWN SENT-BUBBLE GREEN, FIXED — same literal colours as MessagePreview.tsx's
              own `Bubble` and rj-ui/WhatsAppPreview.tsx's phone mockup, never the theme's
              `bg-surface-2` (owner's own instruction: "خلي المثال ثابت في رسالة خضراء مثل
              الواتساب"). A brand colour, not a semantic one. */}
          <div className="rounded-2xl rounded-ss-sm bg-[#DCF8C6] p-3 text-sm leading-relaxed text-[#111b21] shadow-sm">
            {sample || '…'}
          </div>
        </section>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-between gap-3 border-t border-border-subtle pt-3">
          {/* SAID BEFORE HE PRESSES, not after. The wait is Meta's and it is a day; an owner who
              learns that afterwards concludes we are slow. */}
          <span className="text-xs text-text-secondary">
            يُحفظ عندك أولاً — ولا يصل عميلك حتى يعتمده واتساب.
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>إلغاء</Button>
            <Button onClick={save} disabled={saving}>حفظ</Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
