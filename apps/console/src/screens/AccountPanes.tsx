/**
 * The panes of «حسابي» that were stubs, built against what the services actually serve.
 *
 * EACH ONE IS BUILT FROM ITS ACTION OR IT IS NOT OFFERED AT ALL. Nothing here renders a control
 * whose action is missing from the catalogue: the gateway has already filtered by capability, so a
 * manager opening this page sees a shorter page rather than buttons that will refuse him.
 *
 * AND WHERE WE HAVE NO ACTION, THE PANE SAYS SO PLAINLY rather than showing a field that does
 * nothing. A disabled password box is worse than a sentence naming where the password is changed —
 * the box implies the product forgot to wire it, the sentence tells him what to do.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { riyalsLabel } from '../money';
import { Button } from '@base-ui/design-system/Button';
import { DENIED, hasFailed, isLoading, isDenied, isReady, type Loading } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, downloadUrl, type Catalog } from '../catalog';
import type { Session } from '../session';
// ONE DEFINITION, RENDERED WHERE IT BELONGS. The card was written for «فريقي» and stayed there
// when it moved; importing it keeps a single implementation rather than a second copy that drifts.
import { VehiclesCard } from './Team';

interface Tenant {
  id?: string;
  name?: string;
  status?: string;
  // `accent`, NOT `colour` — the name is portal's, and portal is the only reader: it derives the
  // customer page's whole palette from this one field. A prettier name here writes to a field
  // nothing reads, which is how a colour picker becomes decoration.
  branding?: { logo_url?: string; accent?: string; tone?: string };
  config?: { locale?: string; timezone?: string; calendar?: string };
}

// ── منشأتي ───────────────────────────────────────────────────────────────────────────────────

/**
 * The name and the mark HIS CUSTOMER sees — which is the whole reason this pane is not cosmetic.
 *
 * The customer page (spec 12) carries the establishment's identity and nothing of ours: no
 * platform name, no logo, no line in the footer. So this field is not "a profile"; it is the only
 * place the thing his customer reads is set.
 */
export function ShopPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [t, setT] = useState<Tenant | null | undefined>(undefined);
  // NO `saving` HERE. The save is delegated to `BrandCard`, which owns its own busy state — this
  // pane held a second one that nothing ever set and nothing ever read, so a reviewer looking for
  // «does the save show progress» found a variable that said yes and a screen that said nothing.
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');

  const canRead = action(catalog, 'tenant.view_self');
  const canBrand = action(catalog, 'tenant.update_branding');

  const load = () => {
    if (!canRead) { setT(null); return; }
    call<Tenant>(session, canRead).then(setT).catch(() => setT(null));
  };
  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (t === undefined) return <Skeleton height={160} />;
  if (!t) return <Quiet>لا تملك صلاحية عرض بيانات المنشأة.</Quiet>;

  const saveBranding = async (branding: { logo_url: string; accent: string }) => {
    if (!canBrand) throw new Error('لا تملك صلاحية تعديل الهوية.');
    // MERGED, NOT REPLACED. `branding` is a free-form record on the tenant and other things live
    // in it; sending our two fields alone would quietly drop whatever else is there.
    //
    // WRAPPED IN `branding`, WHICH IS THE WHOLE BUG THAT WAS HERE. tenant-service's body model is
    // `BrandingIn { branding: dict }`, and this sent the fields at the top level — so every save
    // came back 422 and the owner could not set his shop's name, logo or colour AT ALL. Nothing on
    // the screen said why: 422 carries a pydantic error list, not a sentence, and the pane simply
    // failed. The field names inside are the server's; only the envelope was missing.
    await call(session, canBrand, { branding: { ...(t?.branding ?? {}), ...branding } });
    load();
  };

  /**
   * THE SHOP'S NAME — ONE NAME, WRITTEN IN ONE PLACE.
   *
   * `operations.set_shop_name`, not the registry directly: the registry's rename is an internal
   * route, and the proxy is what turns the owner's token into a call only a service may make.
   */
  const saveName = async (name: string) => {
    const a = action(catalog, 'operations.set_shop_name');
    if (!a) throw new Error('لا تملك صلاحية تغيير اسم المحل.');
    await call(session, a, { name });
    load();
  };

  return (
    <div className="flex flex-col gap-4">
      {/* WHAT THIS SHOP DOES, BESIDE WHO IT IS. It stood among the branch settings, which made it
          read as a per-branch switch — and it is not one: `operations.shop_vehicles` is a fact
          about the whole establishment, and no shop works on cars in one branch and not another. */}
      <VehiclesCard session={session} catalog={catalog} />
      {/* WHAT HE IS, IN FOUR FACTS — a grid of cells rather than four label/value lines. Four rows
          of «label ………… value» read as a form he has to fill; four cells read as a card about his
          shop, which is what they are: not one of them is editable here. */}
      <section className="grid grid-cols-2 gap-2">
        <Fact label="اسم المنشأة" value={t.name || '—'} wide />
        <Fact label="حالة الحساب" value={t.status === 'active' ? 'فعّال' : (t.status || '—')} />
        {/* FROM THE SERVER, NOT FROM THE BROWSER. Every reminder is scheduled against this
            timezone; reading the device's would schedule an owner travelling abroad into his
            customers' small hours. */}
        <Fact label="التوقيت" value={t.config?.timezone || 'Asia/Riyadh'} />
        <Fact label="التقويم" value={t.config?.calendar === 'hijri' ? 'هجري' : 'ميلادي'} wide />
      </section>

      {canBrand ? <BrandCard tenant={t} onSave={saveBranding} onSaveName={saveName} /> : null}
    </div>
  );
}

/**
 * THE MARK AND THE COLOUR HIS CUSTOMER SEES — with a default, so nobody has to decide.
 *
 * WHY NO FILE SERVICE STANDS BEHIND THIS. There was one, and the logo was the only file in the
 * entire product: no attachments, no documents, no upload anywhere else. A whole service, a whole
 * store, a whole erasure target under PDPL and a whole attack surface, for one picture per shop.
 * It is gone, and the image is reduced here and kept inline on the establishment's own record.
 *
 * And pictures in campaigns later do not bring it back: Meta does not send an image we host — it
 * is uploaded to their endpoint, which hands back a handle, and they serve it. Our own copy would
 * be weight with no reader.
 *
 * REDUCED IN THE BROWSER, NEVER SENT WHOLE. A photo off a phone is three or four megabytes, and
 * the tenant record is read on nearly every screen. 256px is larger than the 64px the customer
 * page draws, which covers a dense display, and small enough that a record stays a record.
 */
function BrandCard({ tenant, onSave, onSaveName }:
    { tenant: Tenant;
      onSave: (b: { logo_url: string; accent: string }) => Promise<void>;
      onSaveName: (name: string) => Promise<void> }) {
  /**
   * THE NAME HIS CUSTOMER READS, and it could not be edited anywhere.
   *
   * It is captured once at signup and printed in large type at the top of the page his customers
   * open, and it signs every WhatsApp message that goes out. A typo there — or, as happened, a
   * password autofilled into the field — was permanent from the console's point of view.
   *
   * THE TENANT'S OWN `name` — the only name a shop has. It heads the page his customers open
   * and signs every WhatsApp message, and `ci/check_a_shop_has_one_name.py` keeps it single.
   */
  const [name, setName] = useState(tenant.name ?? '');
  const [logo, setLogo] = useState(tenant.branding?.logo_url ?? '');
  const [colour, setColour] = useState(tenant.branding?.accent || DEFAULT_COLOUR);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');

  const pick = async (file: File | null | undefined) => {
    if (!file) return;
    setError(''); setSaid('');
    try {
      setLogo(await shrink(file));
    } catch {
      // NAMED, NOT GENERIC. It fails when the file is not an image or the browser cannot decode
      // it, and either way he is otherwise left looking at an unchanged square.
      setError('تعذّر قراءة الصورة. اختر صورة بصيغة PNG أو JPG.');
    }
  };

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setError(''); setSaid('');
    try {
      // TWO WRITES, ONE PRESS, AND THE NAME GOES FIRST — it is the field he actually came to
      // fix, and if the branding call fails he must not be told the name did not save either.
      if (name.trim() && name.trim() !== (tenant.name ?? '')) await onSaveName(name.trim());
      await onSave({ logo_url: logo, accent: colour });
      setSaid('حُفظ. هذا ما يراه عميلك.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر الحفظ.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="text-sm text-text-secondary">هويّتك كما يراها عميلك</h3>

      {/* THE PREVIEW IS THE CUSTOMER'S HEADER, not a swatch beside a button. The first version put
          a 64px tile next to «ارفع شعارك» and the shop's name overflowed it — because that tile
          was pretending to be two things: a colour sample and a logo frame. This is the actual
          band the customer page draws at the top of his page, at the width it is drawn. He is not
          picking a colour; he is looking at his page. */}
      <div
        className="flex flex-col items-center gap-2 rounded-card px-4 py-5 text-center"
        style={{ background: colour }}
      >
        {logo ? (
          <img src={logo} alt="شعار منشأتك"
               className="size-14 rounded-2xl bg-white/15 object-contain" />
        ) : null}
        <span className="max-w-full truncate text-lg font-semibold text-white">
          {name || tenant.name || 'محلّك'}
        </span>
        <span className="text-xs text-white/75">صفحتك لدى المتجر</span>
      </div>

      {/* THE NAME, DIRECTLY UNDER THE PREVIEW THAT SHOWS IT. Editing a field and watching the
          band above it change is the whole explanation of what this name is for. */}
      <label className="flex flex-col gap-1">
        <span className="text-sm text-text-secondary">اسم محلّك كما يراه عميلك</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          autoComplete="organization"
          className="h-11 rounded-xl bg-surface-2 px-3"
        />
      </label>

      {/* FULL WIDTH, BECAUSE IT IS THE ACTION OF THIS CARD. A short pill floating at one end of
          a wide card reads as a footnote, and it is the one thing on the card he came here to
          press. «إزالة» sits beside it only when there is something to remove, and takes the width
          it needs rather than half the row — the two are not equals. */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="grid min-h-11 flex-1 cursor-pointer place-items-center rounded-xl bg-surface-2 px-3 text-sm">
          {logo ? 'تغيير الشعار' : 'ارفع شعارك'}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ''; }}
          />
        </label>
        {logo ? (
          <button type="button" onClick={() => setLogo('')}
                  className="min-h-11 rounded-xl bg-surface-2 px-3 text-sm text-text-secondary">
            إزالة
          </button>
        ) : null}
        <p className="basis-full text-xs text-text-secondary">
          بلا شعار يظهر اسم محلّك — وهذا كافٍ، لا شيء ناقص.
        </p>
      </div>

      {/* ── his colour, chosen directly ─────────────────────────────────────────────────────
          A PALETTE IS OUR TASTE OFFERED AS HIS CHOICE. Seven swatches asked a shop owner to
          approve one of our colours instead of entering his own — and rendered as eight circles
          the size of a fist, a full screen of decoration for one field. His brand colour is a
          fact he already knows; the control's job is to accept it, not to propose alternatives.

          THE NATIVE PICKER IS THE ONE CONTROL HERE BETTER THAN ANYTHING WE WOULD DRAW: it knows
          the platform's own colour UI, and it accepts a pasted hex from his brand book. */}
      <div className="flex flex-col gap-2">
        <span className="text-sm text-text-secondary">لون علامتك</span>
        <div className="flex items-center gap-3">
          <label className="relative size-12 shrink-0 cursor-pointer overflow-hidden rounded-xl border border-border-subtle"
                 style={{ background: colour }}>
            <input type="color" value={colour} aria-label="اختر لون علامتك"
                   className="absolute inset-0 cursor-pointer opacity-0"
                   onChange={(e) => setColour(e.target.value)} />
          </label>
          {/* THE CODE ITSELF, TYPEABLE. A designer hands over «#1F6F5C», and hunting for it in a
              colour wheel is a worse experience than a text box. Normalised on the way in so a
              missing «#» or lower case does not read as a different colour to the preview. */}
          <input
            value={colour}
            aria-label="رمز اللون"
            dir="ltr"
            maxLength={7}
            onChange={(e) => {
              const raw = e.target.value.trim();
              const hex = raw.startsWith('#') ? raw : `#${raw}`;
              setColour(/^#[0-9a-fA-F]{6}$/.test(hex) ? hex.toUpperCase() : raw);
            }}
            className="h-11 w-32 rounded-xl bg-surface-2 px-3 text-center tabular-nums"
          />
          <button
            type="button"
            onClick={() => setColour(DEFAULT_COLOUR)}
            className="min-h-11 rounded-xl px-3 text-sm text-text-secondary"
          >
            العودة للافتراضي
          </button>
        </div>
      </div>

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {said ? <p className="text-sm text-text-secondary">{said}</p> : null}
      <div><Button type="submit" disabled={busy}>حفظ</Button></div>
    </form>
  );
}

/** Our own gold — what a shop that has never thought about this gets, and a place to return to. */
const DEFAULT_COLOUR = '#B08A3E';

/** The longest side, in pixels, a stored logo is reduced to. See BrandCard for why. */
const LOGO_PX = 256;

/**
 * A picked file, drawn small and returned as an inline image.
 *
 * WEBP, WITH A JPEG BEHIND IT. WebP is roughly half the bytes at the same quality and every
 * browser this app supports draws it — but `toDataURL` quietly returns a PNG when a format is
 * unsupported, so the result is checked rather than trusted.
 */
function shrink(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, LOGO_PX / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) { reject(new Error('no 2d context')); return; }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const webp = canvas.toDataURL('image/webp', 0.85);
      resolve(webp.startsWith('data:image/webp') ? webp : canvas.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('undecodable')); };
    img.src = url;
  });
}

function Fact({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`flex flex-col gap-1 rounded-card bg-surface-1 p-3 shadow-sm ${wide ? 'col-span-2' : ''}`}>
      <span className="text-xs text-text-secondary">{label}</span>
      <span className="truncate">{value}</span>
    </div>
  );
}

// ── بياناتي وأوراقي ──────────────────────────────────────────────────────────────────────────

/**
 * PDPL, AS A CONTROL HE CAN PRESS — not as a paragraph.
 *
 * The right to access, export, correct and erase is his by law; a product that describes the right
 * and offers no way to use it has not granted it. `compliance.open_my_dsar` is that way, and this
 * pane exists to put it one tap from where he already is.
 */
export function DataPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  // ── THE WEEKLY REPORT, WHICH ARRIVED HERE BY WAY OF TWO OTHER SCREENS ────────────────────
  //
  // It began on «محلّي», first thing on the shop's dashboard: a checkbox about ONE PERSON'S
  // WhatsApp above every number the screen exists to show, pushing his retention rate below the
  // fold. It moved to «دخولي», beside his phone number, which was right — until «دخولي» turned
  // out to be three cards of prose and this one switch, a tab nobody opened twice.
  //
  // So it lives with his other preferences. PER PERSON and not per shop (the route says so): a
  // manager may want the report and the owner may not, and one flag on the establishment makes
  // unsubscribing an act that silently switches a colleague off.
  const [digest, setDigest] = useState(true);
  const digestAction = action(catalog, 'insights.digest');
  const [busy, setBusy] = useState('');
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');
  const canAsk = action(catalog, 'compliance.open_my_dsar');

  useEffect(() => {
    // `decided: false` means he has never chosen, and the default (subscribed) is then the honest
    // thing to show. A FAILED READ CHANGES NOTHING: flipping the switch to «off» because a request
    // timed out would tell him he had unsubscribed when he had not.
    const dg = action(catalog, 'insights.digest_state');
    if (!dg) return;
    call<{ on?: boolean; decided?: boolean }>(session, dg)
      .then((x) => { if (x?.decided) setDigest(Boolean(x.on)); })
      .catch(() => undefined);
  }, [session, catalog]);

  /**
   * `type`, NOT `kind` — read off compliance-service rather than guessed, which is how the first
   * version of this shipped a 422 to a button an owner pressed. The four values are the service's
   * own DSAR_TYPES (access / export / erasure / correction), i.e. the PDPL rights themselves.
   */
  const ask = async (type: string, label: string) => {
    if (!canAsk) return;
    setBusy(type); setError(''); setSaid('');
    try {
      const opened = await call<{ id?: string; dsar_id?: string }>(session, canAsk, { type });

      // AND THE CODE THAT PROVES IT IS HIS, sent now rather than promised. compliance mints it at
      // creation and holds no channel — so until this call existed the request was recorded, the
      // 30-day clock started, and nothing could ever verify it. PDPL Article 4 is the whole point:
      // nothing personal is released before the subject proves the channel is his.
      const deliver = action(catalog, 'reminders.send_dsar_code');
      const id = opened?.id ?? opened?.dsar_id ?? '';
      let codeSent = false;
      if (deliver && id) {
        // NOT FATAL. The request IS recorded; a code that failed to go is retried, and telling
        // him his request vanished because a message did would be a worse lie than the delay.
        codeSent = await call<{ sent?: boolean }>(session, deliver, { dsar_id: id })
          .then((r) => Boolean(r?.sent))
          .catch(() => false);
      }
      // WHAT IT ACTUALLY DID, and no more. The request is recorded — that part is real and the
      // 30-day clock in the regulation starts from it. What it does NOT do yet is hand him a file:
      // access and export stay `verified: false` until identity is confirmed (the service refuses
      // to release personal data before that, correctly), and no service is registered as a data
      // target on this cluster, so a dispatch would find nobody to ask. Saying «نردّ خلال 30
      // يوماً» was a promise nothing behind it could keep.
      setSaid(codeSent
        ? `سجّلنا طلبك: ${label}. أرسلنا رمز تأكيد على واتساب رقمك — أدخله لنبدأ التنفيذ.`
        : `سجّلنا طلبك: ${label}. نتواصل معك لتأكيد هويتك قبل تنفيذه — لا تخرج أي بيانات شخصية قبل هذا التأكيد.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تسجيل الطلب.');
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {digestAction ? (
        <label className="flex items-center justify-between gap-3 rounded-card bg-surface-1 p-3 shadow-sm">
          <span className="flex flex-col">
            <span className="text-sm">تقريري الأسبوعي على واتساب</span>
            <span className="text-xs text-text-secondary">
              صباح الأحد — أسبوعك في تسعة أسطر، بلا فتح اللوحة. لك وحدك: إيقافه لا يوقفه عن زملائك.
            </span>
          </span>
          <input
            type="checkbox"
            checked={digest}
            aria-label="تقريري الأسبوعي على واتساب"
            onChange={async (e) => {
              const on = e.target.checked;
              setDigest(on);
              // THE SWITCH FOLLOWS THE SERVER, NOT THE OTHER WAY ROUND. A failed save that leaves
              // the box ticked teaches him he is subscribed when he is not — and he finds out by
              // a report that never comes.
              await call(session, digestAction, { on }).catch(() => setDigest(!on));
            }}
            className="size-6 shrink-0 accent-[var(--accent)]"
          />
        </label>
      ) : null}
      <Card>
        <h3 className="mb-1">الاحتفاظ بالبيانات</h3>
        <p className="text-sm text-text-secondary">
          زيارات عملائك وسجلّ رسائلهم محفوظة داخل المملكة. تبقى ما دام حسابك فعّالاً، وتُحذف بعد
          إغلاقه وفق المدة المعلنة في سياسة الخصوصية.
        </p>
      </Card>

      {canAsk ? (
        <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <h3>حقوقك في بياناتك</h3>
          <p className="text-sm text-text-secondary">
            نظام حماية البيانات الشخصية يمنحك هذه الطلبات، وهذه أزرارها — لا عنوان بريد تراسله.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('access', 'الاطّلاع على بياناتي')}>
              الاطّلاع على بياناتي
            </Button>
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('export', 'تصدير نسخة')}>
              تصدير نسخة
            </Button>
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('correction', 'تصحيح بيان')}>
              تصحيح بيان
            </Button>
            {/* ERASURE SITS APART AND IS NOT STYLED AS DANGER — it is a right, not an accident.
                What it must not be is adjacent to a routine button by a few pixels. */}
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('erasure', 'حذف بياناتي')}>
              حذف بياناتي
            </Button>
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {said ? <p className="text-sm">{said}</p> : null}
        </div>
      ) : null}

      <Card>
        <h3 className="mb-1">الاتفاقيات</h3>
        <p className="text-sm text-text-secondary">
          شروط الاستخدام، سياسة الخصوصية، واتفاقية معالجة البيانات — وافقت عليها عند فتح المحل،
          وهي متاحة لك في أي وقت.
        </p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <a className="underline" href="/legal/terms" target="_blank" rel="noreferrer">شروط الاستخدام</a>
          <a className="underline" href="/legal/privacy" target="_blank" rel="noreferrer">سياسة الخصوصية</a>
          <a className="underline" href="/legal/dpa" target="_blank" rel="noreferrer">اتفاقية معالجة البيانات</a>
        </div>
      </Card>
    </div>
  );
}

// ── the small shared pieces ──────────────────────────────────────────────────────────────────

function Card({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">{children}</div>;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-text-secondary">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Quiet({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-card bg-surface-2 p-4 text-sm text-text-secondary">{children}</p>
  );
}

// ── الفواتير ─────────────────────────────────────────────────────────────────────────────────

interface Invoice {
  id: string; number?: string; status?: string; total_minor?: number; issued_at?: string;
  /** "receipt" | "tax_invoice" — frozen the moment the invoice was paid (models.py's own
   *  comment). Empty on a legacy row with nothing stamped; treated as "no tax invoice exists"
   *  rather than guessed at. */
  doc_type?: string;
}

/**
 * His invoices, and the document he actually needs.
 *
 * TWO DOWNLOADS, NOT ONE, because they are two different papers: the tax invoice is what his
 * accountant files, the receipt is proof he paid. Offering only "download" and picking one for him
 * sends half the shops to support. THIS WAS WRITTEN AND NEVER BUILT (audit #4, 2026-08-22) — the
 * three routes existed, tested, for months; this pane listed invoices and stopped there.
 *
 * WHY «تنزيل المستند» IS THE ONE ALWAYS OFFERED. `/document` self-selects the right paper (the
 * tax invoice if one was issued and still backed, the receipt otherwise) and never refuses — the
 * other two routes 409 on a mismatch (`/pdf` on a receipt-only invoice, `/receipt` before it is
 * paid), and this pane has no reliable way to predict that from the list alone for `/pdf`'s own
 * live-profile check. «الإيصال» is offered SEPARATELY only when `doc_type` says a tax invoice was
 * actually issued — the one case where a second, different paper genuinely exists to ask for.
 */
export function InvoicesPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [rows, setRows] = useState<Loading<Invoice[]>>(undefined);
  const [downloading, setDownloading] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const canList = action(catalog, 'billing.my_invoices');
  const canDocument = action(catalog, 'billing.invoice_document');
  const canReceipt = action(catalog, 'billing.invoice_receipt');

  const download = async (a: ReturnType<typeof action>, key: string, invoiceId: string) => {
    if (!a) return;
    setDownloading(key); setDownloadError('');
    try {
      const url = await downloadUrl(session, a, { id: invoiceId });
      window.open(url, '_blank', 'noreferrer');
    } catch {
      // NO SENTENCE FROM THE SERVER TO SHOW — a PDF route answers with a status, not a body. One
      // fixed sentence here beats printing a raw HTTP code at an owner looking for his invoice.
      setDownloadError('تعذّر تنزيل المستند الآن. حاول بعد قليل.');
    } finally {
      setDownloading('');
    }
  };

  useEffect(() => {
    if (!canList) { setRows(DENIED); return; }
    call<{ invoices: Invoice[] }>(session, canList)
      .then((x) => setRows(x.invoices ?? []))
      .catch(() => setRows(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!canList) return null;
  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). The guard read `=== null` and the failure
  // handler set `null`, so a failed read rendered this for ever and the sentence written
  // for the failure was unreachable. `undefined` waits; `null` says so.
  if (isLoading(rows)) return <Skeleton height={80} />;

  return (
    <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="text-sm text-text-secondary">فواتيري</h3>
      {isDenied(rows) ? (
        // A ROLE ANSWER, AND IT SAYS WHICH. «لا فواتير بعد» to somebody whose role simply
        // excludes billing is a fact about the shop that is not his to be given (م · 2).
        <p className="text-sm text-text-secondary">لا يشمل دورك فواتير المحل.</p>
      ) : hasFailed(rows) ? (
        // HE CAME HERE FOR HIS ACCOUNTANT. «لا فواتير بعد» to a shop that has been paying for
        // months is a sentence that sends him looking for a receipt he will not find.
        <p className="text-sm text-text-secondary">
          تعذّرت قراءة فواتيرك الآن — والخلل عندنا. أعد المحاولة بعد قليل.
        </p>
      ) : rows.length === 0 ? (
        // NOT AN APOLOGY. No invoices before the first subscription is the correct state, and
        // «لا توجد فواتير» dressed as an empty-state illustration would imply something failed.
        <p className="text-sm text-text-secondary">لا فواتير بعد — تصدر أول فاتورة مع أول باقة.</p>
      ) : (
        <>
          {downloadError ? <p className="text-sm text-danger">{downloadError}</p> : null}
          <ul className="flex flex-col gap-2">
            {rows.map((v) => (
              <li key={v.id} className="flex flex-col gap-2 border-b border-surface-2 pb-2 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex flex-col">
                    <span className="tabular-nums" dir="ltr">{v.number || v.id}</span>
                    <span className="text-sm text-text-secondary">{(v.issued_at || '').slice(0, 10)}</span>
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="tabular-nums">
                      {v.total_minor ? riyalsLabel(v.total_minor) : '—'}
                    </span>
                    <Badge tone={v.status === 'paid' ? 'success' : 'warning'}>
                      {v.status === 'paid' ? 'مدفوعة' : 'غير مدفوعة'}
                    </Badge>
                  </span>
                </div>
                {/* «تنزيل المستند» — self-selects the right paper and never refuses; the ONLY
                    download offered when no tax invoice was issued for this row. */}
                <div className="flex flex-wrap gap-2">
                  {canDocument ? (
                    <Button variant="ghost" size="sm" disabled={downloading === `doc:${v.id}`}
                            onClick={() => void download(canDocument, `doc:${v.id}`, v.id)}>
                      {downloading === `doc:${v.id}` ? 'يُنزَّل…' : 'تنزيل المستند'}
                    </Button>
                  ) : null}
                  {/* THE SECOND PAPER, ONLY WHEN IT GENUINELY EXISTS: a tax invoice was issued for
                      this row (so «تنزيل المستند» above already gave him that one) AND it is
                      paid — a receipt for money not yet collected is not a real document. */}
                  {canReceipt && v.doc_type === 'tax_invoice' && v.status === 'paid' ? (
                    <Button variant="ghost" size="sm" disabled={downloading === `receipt:${v.id}`}
                            onClick={() => void download(canReceipt, `receipt:${v.id}`, v.id)}>
                      {downloading === `receipt:${v.id}` ? 'يُنزَّل…' : 'تنزيل الإيصال'}
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

// ── مفاتيح الربط ─────────────────────────────────────────────────────────────────────────────

interface MachineAccount {
  client_id: string;
  name?: string;
  status?: string;
  created?: number;
  last_used_at?: number;
  caps?: string[];
}

function whenAgo(ts?: number): string {
  if (!ts) return 'لم يُستعمل قط';
  const days = Math.floor((Date.now() / 1000 - ts) / 86_400);
  if (days <= 0) return 'اليوم';
  if (days === 1) return 'أمس';
  if (days < 30) return `قبل ${days} يوماً`;
  return `قبل ${Math.floor(days / 30)} شهراً`;
}

/**
 * WHO HOLDS A KEY TO THIS SHOP — and the owner could not see it.
 *
 * A till company's credential writes visits in his name, does not expire when an employee leaves,
 * and outlives the contract that created it: he changes point-of-sale vendor and the old key is
 * still valid, still able to post sales into his shop. It is closer to a key to the building than
 * to a login.
 *
 * AND A KEY NOBODY CAN SEE IS A KEY NOBODY REVOKES. Issuing and rotating were both reachable; the
 * LIST was not, so the answer to «من يملك مفتاحاً لمحلي؟» was nowhere in the product.
 *
 * THE OWNER'S ALONE (deploy/seed/roles.json says why): a manager runs the shop day to day, and
 * this is not a daily errand — it is the one thing that survives him.
 */
export function KeysPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [rows, setRows] = useState<Loading<MachineAccount[]>>(undefined);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const canList = action(catalog, 'identity.list_service_accounts');
  const canRevoke = action(catalog, 'identity.revoke_service_account');

  const load = () => {
    if (!canList) { setRows(null); return; }
    call<{ service_accounts: MachineAccount[] }>(session, canList)
      .then((x) => setRows(x.service_accounts ?? []))
      .catch(() => setRows(null));
  };
  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (rows === undefined) return <Skeleton height={140} />;
  if (rows === null) {
    // THREE ANSWERS, NOT TWO — and the middle one was missing, which made the screen lie.
    //
    // «مفاتيح الربط يراها المالك وحده» was shown to the OWNER as well, because the pane cannot
    // reach the list at all: identity-service declares `identity.list_service_accounts` in its
    // ADMIN actions, so it never appears in the user catalogue this app is built from — while the
    // owner's role already holds `service_accounts:read`. He has the right and no door.
    //
    // So the sentence now depends on WHY: a manager is told it is the owner's, and the owner is
    // told the truth, which is that this is ours to open. Escalated to the platform; until it
    // lands, a screen that blames his account for our gap is the worse failure.
    // AND THE SESSION HOLDS NO CAPABILITIES, deliberately (session.ts): everything this app shows
    // is decided by the catalogue, so the pane cannot ask «is this person the owner». It therefore
    // says the one thing that is true either way and blames nobody — «ours, not yours» is the safe
    // side of that uncertainty, because the owner DOES have the right today.
    if (!canList) {
      return <Quiet>عرض مفاتيح الربط لم يُفتح بعد من طرفنا. وإصدار المفاتيح وسحبها يتمّان معنا مباشرةً حتى ذلك الحين.</Quiet>;
    }
    return <Quiet>تعذّر عرض مفاتيح الربط الآن. أعد المحاولة بعد قليل.</Quiet>;
  }

  const revoke = async (row: MachineAccount) => {
    if (!canRevoke) return;
    setBusy(row.client_id);
    setError('');
    try {
      await call(session, canRevoke, { client_id: row.client_id });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر السحب.');
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <p className="text-sm text-text-secondary">
        برامج تكتب زيارات باسم محلك — نظام الكاشير مثلاً. المفتاح لا ينتهي بمرور الوقت،
        فاسحب ما لم يعد يُستعمل.
      </p>

      {isDenied(rows) ? (
        <Quiet>لا يشمل دورك مفاتيح الأنظمة المرتبطة.</Quiet>
      ) : !isReady(rows) || rows.length === 0 ? (
        <Quiet>لا يوجد برنامج مرتبط بمحلك. تُصدَر المفاتيح عند ربط نظام الكاشير.</Quiet>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.client_id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-1 p-3 shadow-sm">
              <span className="flex flex-col">
                <span>{row.name || row.client_id}</span>
                <span className="text-sm text-text-secondary">
                  {/* LAST USED IS THE WHOLE POINT. «صدر في 2024» tells him nothing he can act on;
                      «لم يُستعمل منذ 4 أشهر» is a key to revoke this afternoon. */}
                  آخر استعمال: {whenAgo(row.last_used_at)}
                </span>
              </span>
              <span className="flex items-center gap-2">
                {row.status && row.status !== 'active'
                  ? <Badge tone="neutral">موقوف</Badge>
                  : null}
                {canRevoke && row.status !== 'revoked' ? (
                  <Button variant="danger" disabled={busy === row.client_id}
                          onClick={() => revoke(row)}>
                    سحب المفتاح
                  </Button>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}

      {error ? <p role="alert" className="text-danger">{error}</p> : null}
    </section>
  );
}
