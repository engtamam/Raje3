/**
 * «الهوية» — what the establishment IS, and who he is: name/logo/colour his customer sees, his own
 * personal security (password), and the machine keys that can act in his name.
 *
 * Mirrors apps/mobile/lib/features/account/shop_identity_screen.dart's OWN SCOPE, not its layout —
 * the mobile screen bundles the exact same three concerns (brand, facts, vehicles) behind one
 * destination reached from the account hub; this is the console's own wide-layout version of the
 * same destination, reached from the «الهوية» tab instead of a pushed route. Personal security
 * (ChangePasswordCard) and machine keys (KeysPane) share this file rather than the shop-identity one
 * because the tab that hosts them (Account.tsx's own `tabsFor`) already groups "per-person/
 * per-establishment facts" as one errand — splitting them into three separate files here would
 * recreate the exact one-generic-tab problem this rebuild exists to fix, just one level lower.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Building2, CalendarDays, Clock, KeyRound } from 'lucide-react';
import { Badge } from '../../rj-ui/Badge';
import { Card } from '../../rj-ui/Card';
import { Button } from '../../rj-ui/Button';
import { Field, Input } from '../../rj-ui/Field';
import { Skeleton } from '../../rj-ui/Skeleton';
import { isDenied, isReady, type Loading } from '../../loading';
import { action, call, type Catalog } from '../../catalog';
import type { Session } from '../../session';
import { AssistantHint } from '../../AssistantHint';
// ONE DEFINITION, RENDERED WHERE IT BELONGS. The card was written for «فريقي» and stayed there
// when it moved; importing it keeps a single implementation rather than a second copy that drifts.
import { VehiclesCard } from '../Team';
import { useOperatorI18n, tf } from '../../operator-i18n';
import '../account-panes-i18n';
// `ChangePasswordCard` below reads `account.changePassword.*` keys, registered by this file —
// imported directly rather than relying on AccountScreen.tsx to have loaded it first.
import '../account-i18n';
import { Quiet } from './shared';

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

/**
 * The name and the mark HIS CUSTOMER sees — which is the whole reason this pane is not cosmetic.
 *
 * The customer page (spec 12) carries the establishment's identity and nothing of ours: no
 * platform name, no logo, no line in the footer. So this field is not "a profile"; it is the only
 * place the thing his customer reads is set.
 */
export function ShopPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t: tr } = useOperatorI18n();
  const [t, setT] = useState<Tenant | null | undefined>(undefined);

  const canRead = action(catalog, 'tenant.view_self');
  const canBrand = action(catalog, 'tenant.update_branding');

  const load = () => {
    if (!canRead) { setT(null); return; }
    call<Tenant>(session, canRead).then(setT).catch(() => setT(null));
  };
  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (t === undefined) return <Skeleton height={160} />;
  if (!t) return <Quiet>{tr('accountPanes.noReadPermission')}</Quiet>;

  const saveBranding = async (branding: { logo_url: string; accent: string }) => {
    if (!canBrand) throw new Error(tr('accountPanes.noBrandPermission'));
    // MERGED, NOT REPLACED. `branding` is a free-form record on the tenant and other things live
    // in it; sending our two fields alone would quietly drop whatever else is there.
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
    if (!a) throw new Error(tr('accountPanes.noNamePermission'));
    await call(session, a, { name });
    load();
  };

  return (
    <div className="flex flex-col gap-4">
      {/* WHAT HIS CUSTOMER SEES, FIRST. This pane's own opening comment already said the brand
          card is "the whole reason this pane is not cosmetic," so it leads; personal preferences
          and administrative toggles follow. */}
      {canBrand ? <BrandCard tenant={t} onSave={saveBranding} onSaveName={saveName} /> : null}

      {/* WHAT HE IS, IN FOUR FACTS — a grid of cells rather than four label/value lines. Four rows
          of «label ………… value» read as a form he has to fill; four cells read as a card about his
          shop, which is what they are: not one of them is editable here. */}
      <section className="grid grid-cols-2 gap-2">
        <Fact icon={<Building2 size={16} />} label={tr('accountPanes.fact.name')} value={t.name || '—'} wide />
        <Fact label={tr('accountPanes.fact.status')}
              value={<Badge tone={t.status === 'active' ? 'success' : 'neutral'}>
                       {t.status === 'active' ? tr('accountPanes.status.active') : (t.status || '—')}
                     </Badge>}
              hint={<AssistantHint anchor="account.tenant_status" session={session} />} />
        {/* FROM THE SERVER, NOT FROM THE BROWSER. Every reminder is scheduled against this
            timezone; reading the device's would schedule an owner travelling abroad into his
            customers' small hours. */}
        <Fact icon={<Clock size={16} />} label={tr('accountPanes.fact.timezone')} value={t.config?.timezone || 'Asia/Riyadh'} />
        <Fact icon={<CalendarDays size={16} />} label={tr('accountPanes.fact.calendar')}
              value={t.config?.calendar === 'hijri' ? tr('accountPanes.calendar.hijri') : tr('accountPanes.calendar.gregorian')} wide />
      </section>

      {/* WHAT THIS SHOP DOES, BESIDE WHO IT IS — a fact about the whole establishment, no shop
          works on cars in one branch and not another. */}
      <VehiclesCard session={session} catalog={catalog} />
    </div>
  );
}

function Fact({ label, value, wide, hint, icon }:
    { label: string; value: React.ReactNode; wide?: boolean; hint?: React.ReactNode;
      icon?: React.ReactNode }) {
  return (
    <Card className={`flex items-start gap-2.5 p-3 ${wide ? 'col-span-2' : ''}`}>
      {icon ? (
        <span aria-hidden
             className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-on-soft">
          {icon}
        </span>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-center gap-1 text-xs text-text-secondary">
          {label}
          {hint}
        </span>
        <span className="truncate">{value}</span>
      </div>
    </Card>
  );
}

/**
 * THE MARK AND THE COLOUR HIS CUSTOMER SEES — with a default, so nobody has to decide.
 *
 * WHY NO FILE SERVICE STANDS BEHIND THIS. There was one, and the logo was the only file in the
 * entire product: no attachments, no documents, no upload anywhere else. It is gone, and the image
 * is reduced here and kept inline on the establishment's own record.
 *
 * REDUCED IN THE BROWSER, NEVER SENT WHOLE. A photo off a phone is three or four megabytes, and
 * the tenant record is read on nearly every screen. 256px is larger than the 64px the customer
 * page draws, which covers a dense display, and small enough that a record stays a record.
 */
function BrandCard({ tenant, onSave, onSaveName }:
    { tenant: Tenant;
      onSave: (b: { logo_url: string; accent: string }) => Promise<void>;
      onSaveName: (name: string) => Promise<void> }) {
  const { t } = useOperatorI18n();
  /**
   * THE NAME HIS CUSTOMER READS, and it could not be edited anywhere.
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
      setError(t('accountPanes.imageReadFailed'));
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
      setSaid(t('accountPanes.identitySaved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('accountPanes.identitySaveFailed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="text-sm text-text-secondary">{t('accountPanes.brandTitle')}</h3>

      {/* THE PREVIEW IS THE CUSTOMER'S HEADER, not a swatch beside a button — the actual band the
          customer page draws at the top of his page, at the width it is drawn. */}
      <div
        className="flex flex-col items-center gap-2 rounded-card px-4 py-5 text-center"
        style={{ background: colour }}
      >
        {logo ? (
          <img src={logo} alt={t('accountPanes.logoAlt')}
               className="size-14 rounded-2xl bg-white/15 object-contain" />
        ) : null}
        <span className="max-w-full truncate text-lg font-semibold text-white">
          {name || tenant.name || t('accountPanes.defaultShopName')}
        </span>
        <span className="text-xs text-white/75">{t('accountPanes.storePage')}</span>
      </div>

      {/* THE NAME, DIRECTLY UNDER THE PREVIEW THAT SHOWS IT. Editing a field and watching the
          band above it change is the whole explanation of what this name is for. */}
      <label className="flex flex-col gap-1">
        <span className="text-sm text-text-secondary">{t('accountPanes.shopNameLabel')}</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          autoComplete="organization"
          className="h-11 rounded-xl bg-surface-2 px-3"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <label className="grid min-h-11 flex-1 cursor-pointer place-items-center rounded-xl bg-surface-2 px-3 text-sm">
          {logo ? t('accountPanes.changeLogo') : t('accountPanes.uploadLogo')}
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
            {t('accountPanes.removeLogo')}
          </button>
        ) : null}
        <p className="basis-full text-xs text-text-secondary">
          {t('accountPanes.noLogoNote')}
        </p>
      </div>

      {/* ── his colour, chosen directly ─────────────────────────────────────────────────────
          A PALETTE IS OUR TASTE OFFERED AS HIS CHOICE. His brand colour is a fact he already
          knows; the control's job is to accept it, not to propose alternatives.
          THE NATIVE PICKER IS THE ONE CONTROL HERE BETTER THAN ANYTHING WE WOULD DRAW: it knows
          the platform's own colour UI, and it accepts a pasted hex from his brand book. */}
      <div className="flex flex-col gap-2">
        <span className="text-sm text-text-secondary">{t('accountPanes.brandColor')}</span>
        <div className="flex items-center gap-3">
          <label className="relative size-12 shrink-0 cursor-pointer overflow-hidden rounded-xl border border-border-subtle"
                 style={{ background: colour }}>
            <input type="color" value={colour} aria-label={t('accountPanes.pickColorAriaLabel')}
                   className="absolute inset-0 cursor-pointer opacity-0"
                   onChange={(e) => setColour(e.target.value)} />
          </label>
          <input
            value={colour}
            aria-label={t('accountPanes.colorCodeAriaLabel')}
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
            {t('accountPanes.resetToDefault')}
          </button>
        </div>
      </div>

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {said ? <p className="text-sm text-text-secondary">{said}</p> : null}
      <div><Button type="submit" disabled={busy}>{t('accountPanes.save')}</Button></div>
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

// ── password ─────────────────────────────────────────────────────────────────────────────────

/** Collapsed by default — a control this sensitive earns the extra tap rather than sitting open on
 *  a page loaded a dozen times a day (same balance apps/console/src/affiliates/AffiliateAccount.tsx's
 *  own ChangePasswordCard already struck for the affiliate side of this product). The three-field
 *  pattern (current + new + confirm) rather than a reset flow: this is an AUTHENTICATED change made
 *  while he already holds a session, never the unauthenticated "forgot password" screen. Same shape
 *  apps/mobile/lib/features/account/account_screen.dart's own `_ChangePasswordSheet` uses for the
 *  same real action (`identity.change_password`) — only the backend door is shared, never the UI. */
export function ChangePasswordCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [open, setOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
             className="flex items-center gap-2 rounded-card bg-surface-1 p-4 text-sm shadow-sm">
        <KeyRound size={16} className="text-text-secondary" /> {t('account.changePassword.title')}
      </button>
    );
  }

  async function submit() {
    if (!newPassword) return;
    if (newPassword !== confirm) { setError(t('account.changePassword.mismatch')); return; }
    const a = action(catalog, 'identity.change_password');
    if (!a) return;
    setBusy(true); setError(''); setDone(false);
    try {
      await call(session, a, { old_password: oldPassword, new_password: newPassword });
      setDone(true);
      setOldPassword(''); setNewPassword(''); setConfirm('');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('account.changePassword.failed'));
    } finally { setBusy(false); }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <KeyRound size={16} /> {t('account.changePassword.title')}
      </div>
      <Field label={t('account.changePassword.currentLabel')} htmlFor="acct-cp-old">
        <Input id="acct-cp-old" type="password" autoComplete="current-password" dir="ltr"
              value={oldPassword}
              onChange={(e) => { setOldPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label={t('account.changePassword.newLabel')} htmlFor="acct-cp-new">
        <Input id="acct-cp-new" type="password" autoComplete="new-password" dir="ltr"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label={t('account.changePassword.confirmLabel')} htmlFor="acct-cp-confirm">
        <Input id="acct-cp-confirm" type="password" autoComplete="new-password" dir="ltr"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setDone(false); }} />
      </Field>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {done ? <p className="text-sm text-success">{t('account.changePassword.success')}</p> : null}
      <div className="flex items-center gap-2">
        <Button type="button" disabled={busy || !oldPassword || !newPassword} onClick={submit}>
          {t('account.changePassword.save')}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{t('account.changePassword.cancel')}</Button>
      </div>
    </Card>
  );
}

// ── connection keys ──────────────────────────────────────────────────────────────────────────

interface MachineAccount {
  client_id: string;
  name?: string;
  status?: string;
  created?: number;
  last_used_at?: number;
  caps?: string[];
}

function whenAgo(ts: number | undefined, t: (key: string) => string): string {
  if (!ts) return t('accountPanes.neverUsed');
  const days = Math.floor((Date.now() / 1000 - ts) / 86_400);
  if (days <= 0) return t('accountPanes.today');
  if (days === 1) return t('accountPanes.yesterday');
  if (days < 30) return tf(t, 'accountPanes.daysAgo', { n: days });
  return tf(t, 'accountPanes.monthsAgo', { n: Math.floor(days / 30) });
}

/**
 * WHO HOLDS A KEY TO THIS SHOP — and the owner could not see it.
 *
 * A till company's credential writes visits in his name, does not expire when an employee leaves,
 * and outlives the contract that created it. It is closer to a key to the building than to a login.
 *
 * AND A KEY NOBODY CAN SEE IS A KEY NOBODY REVOKES. Issuing and rotating were both reachable; the
 * LIST was not, so the answer to «من يملك مفتاحاً لمحلي؟» was nowhere in the product.
 *
 * THE OWNER'S ALONE (deploy/seed/roles.json says why): a manager runs the shop day to day, and
 * this is not a daily errand — it is the one thing that survives him.
 */
export function KeysPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
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
    // told the truth, which is that this is ours to open.
    if (!canList) {
      return <Quiet>{t('accountPanes.keys.notOpenedYet')}</Quiet>;
    }
    return <Quiet>{t('accountPanes.keys.readFailed')}</Quiet>;
  }

  const revoke = async (row: MachineAccount) => {
    if (!canRevoke) return;
    setBusy(row.client_id);
    setError('');
    try {
      await call(session, canRevoke, { client_id: row.client_id });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('accountPanes.keys.revokeFailed'));
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <p className="text-sm text-text-secondary">
        {t('accountPanes.keys.desc')}
      </p>

      {isDenied(rows) ? (
        <Quiet>{t('accountPanes.keys.noPermission')}</Quiet>
      ) : !isReady(rows) || rows.length === 0 ? (
        <Quiet>{t('accountPanes.keys.empty')}</Quiet>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.client_id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
              <span className="flex flex-col">
                <span>{row.name || row.client_id}</span>
                <span className="text-sm text-text-secondary">
                  {/* LAST USED IS THE WHOLE POINT. «صدر في 2024» tells him nothing he can act on;
                      «لم يُستعمل منذ 4 أشهر» is a key to revoke this afternoon. */}
                  {tf(t, 'accountPanes.keys.lastUsed', { ago: whenAgo(row.last_used_at, t) })}
                </span>
              </span>
              <span className="flex items-center gap-2">
                {row.status && row.status !== 'active'
                  ? <Badge tone="neutral">{t('accountPanes.keys.stopped')}</Badge>
                  : null}
                {canRevoke && row.status !== 'revoked' ? (
                  <Button variant="danger" disabled={busy === row.client_id}
                          onClick={() => revoke(row)}>
                    {t('accountPanes.keys.revoke')}
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
