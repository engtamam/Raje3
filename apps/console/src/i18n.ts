/**
 * The kit's auth strings, in Arabic.
 *
 * WHY THIS FILE EXISTS AT ALL, and it is worth stating because the failure was visible on screen:
 * the kit's auth components read every label through `useAuthI18n()`, and OUTSIDE a provider that
 * seam degrades to returning the KEY. So an unwrapped app does not fall back to English — it paints
 * `auth.otp.hint 0505536720` at the person, with their phone number next to a dotted identifier.
 * It renders, it is not an error, and nothing fails: the exact shape of bug that ships.
 *
 * EVERY KEY THE KIT ASKS FOR IS ANSWERED HERE, including the screens we do not use yet
 * (`ForgotPassword`, `ChangePassword`, `SignupForm`). A key we leave out is not a missing
 * translation — it is that same raw identifier, on the day somebody wires the screen that needs it.
 * A guard in the console's build would be the next step if this list ever drifts.
 *
 * AND THE WORDING IS OURS, NOT A TRANSLATION OF THEIRS. «رقم الجوال» rather than "البريد
 * الإلكتروني" for `auth.email`, because in this product the login field IS the phone
 * (IDENTITY_LOGIN_FIELD=phone) and a label that says email would be simply false.
 */
import type { AuthI18n } from '../../../ui/packages/ui/src/auth/i18n';
import type { BlockDocI18n } from '../../../ui/packages/ui/src/components/blockdoc';

const AR: Record<string, string> = {
  // ── signing in ──────────────────────────────────────────────────────────────────────────
  'auth.signIn': 'تسجيل الدخول',
  // The login field is the PHONE in this deployment — see the module note.
  'auth.email': 'رقم الجوال',
  'auth.identifier': 'رقم الجوال',
  'auth.password': 'كلمة المرور',
  'auth.back': 'رجوع',
  'auth.createAccount': 'محل جديد',
  // Shown only to a person who belongs to more than one establishment. Ours are single-shop
  // today, so this is here to be correct rather than because it is on screen.
  'auth.pickOrg': 'اختر المحل',
  'auth.pickOrgHint': 'لك أكثر من محل — اختر الذي تريد الدخول إليه.',

  // ── creating an account (the kit's own form; ours is composed — see Door.tsx) ────────────
  'auth.name': 'الاسم',
  'auth.orgName': 'اسم المحل',
  'auth.company': 'منشأة',
  'auth.individual': 'فرد',

  // ── the code ────────────────────────────────────────────────────────────────────────────
  'auth.otp.title': 'أكّد رقمك',
  // The number is appended by the component, so this line must END where a number can follow.
  'auth.otp.hint': 'أرسلنا رمزاً على واتساب إلى',
  'auth.otp.code': 'رمز التحقق',
  'auth.otp.verify': 'تأكيد',
  'auth.otp.resend': 'إرسال الرمز مرة أخرى',
  'auth.otp.resendIn': 'إعادة الإرسال بعد',

  // ── the password ────────────────────────────────────────────────────────────────────────
  'auth.forgot.title': 'نسيت كلمة المرور',
  'auth.forgot.hint': 'أدخل رقم جوالك ونرسل لك رابط إعادة التعيين.',
  'auth.forgot.send': 'أرسل',
  'auth.forgot.sentTitle': 'تحقّق من رسائلك',
  'auth.forgot.sentHint': 'إن كان لهذا الرقم حساب، وصلته رسالة.',
  'auth.pw.changeTitle': 'تغيير كلمة المرور',
  'auth.pw.current': 'كلمة المرور الحالية',
  'auth.pw.new': 'كلمة المرور الجديدة',
  'auth.pw.confirm': 'تأكيد كلمة المرور',
  'auth.pw.mismatch': 'الكلمتان غير متطابقتين',
  'auth.pw.save': 'حفظ',

  // ── the legal gate ──────────────────────────────────────────────────────────────────────
  'auth.legal.accept': 'أوافق',
  // Followed by "1 / 3" from the component, so it reads as a label rather than a sentence.
  'auth.legal.step': 'المستند',
  'auth.legal.updated': 'حُدِّث هذا المستند — يلزم اطّلاعك عليه من جديد.',
  'auth.legal.unfilled': 'هذا المستند غير مكتمل — تواصل معنا.',

  // ── the one error the kit raises on its own ─────────────────────────────────────────────
  // Generic ON PURPOSE. Every refusal our own paths produce arrives as a written sentence and is
  // shown through `mapError`; this is only the last resort when nothing said anything.
  'auth.err.ERROR': 'تعذّر إكمال الطلب. حاول مرة أخرى.',
};

/**
 * The document viewer's strings — a SECOND seam, and the legal gate walks straight through it.
 *
 * `AcceptTerms` renders each document with `DocBlocksView`, which reads its own
 * `BlockDocI18nContext`. Wrapping the app in the auth provider alone would have left the terms
 * screen — the one screen a person must read before agreeing to it — printing `legal.section 1`.
 *
 * Most of these keys belong to the EDITOR, which we do not ship: a shop owner reads documents, he
 * does not author them. They are answered anyway, for the same reason the unused auth screens are.
 */
const LEGAL: Record<string, string> = {
  'legal.section': 'القسم',
  'legal.sections': 'الأقسام',
  'legal.noBlocks': 'لا يوجد محتوى',
  'legal.emptyBlock': 'فقرة فارغة',
  'legal.noFields': 'لا توجد حقول',
  'legal.addBlock': 'إضافة فقرة',
  'legal.addSection': 'إضافة قسم',
  'legal.removeSection': 'حذف القسم',
  'legal.moveUp': 'أعلى',
  'legal.moveDown': 'أسفل',
  'legal.cancel': 'إلغاء',
  'legal.badJson': 'صيغة غير صالحة',
  'legal.rawData': 'البيانات الخام',
  'legal.blockNavHint': 'اختر فقرة لتحريرها.',
  'legal.f.titleAr': 'العنوان بالعربية',
  'legal.f.titleEn': 'العنوان بالإنجليزية',
};

export const arabicBlockDoc: BlockDocI18n = {
  locale: 'ar',
  t: (key: string) => ({ ...LEGAL, ...SHARED }[key] ?? ''),
};

/**
 * A THIRD SEAM — the shared-component one (`ImtithalakUiProvider`), which `Pager` and the block
 * studio read. Three contexts in one kit, each defaulting to the identity translator, and each
 * silent about it. The pager is on «عملائي»: without this, a shop owner paging through his own
 * customers reads «pager.prev · pager.of · pager.next».
 *
 * The `studio.*` keys belong to the block AUTHOR, which we do not ship. Answered for the same
 * reason as the rest: an unanswered key is not a blank, it is an identifier on a screen.
 */
const SHARED: Record<string, string> = {
  'pager.label': 'التنقل بين الصفحات',
  'pager.prev': 'السابق',
  'pager.next': 'التالي',
  'pager.of': 'من',
  'studio.block.both': 'اللغتان',
  'studio.block.contents': 'المحتوى',
  'studio.block.viewLang': 'لغة العرض',
  'studio.block.list.add': 'إضافة',
  'studio.block.list.empty': 'لا عناصر',
  'studio.block.list.remove': 'حذف',
  'studio.block.list.addRow': 'إضافة صف',
  'studio.block.list.addCol': 'إضافة عمود',
  'studio.block.list.removeCol': 'حذف العمود',
};

/** The translator the shared components read. */
export const arabicShared = (key: string): string => SHARED[key] ?? LEGAL[key] ?? AR[key] ?? '';

export const arabicAuth: AuthI18n = {
  locale: 'ar',
  // A MISSING KEY RETURNS EMPTY, NOT THE KEY. Silence is a gap somebody notices as a blank label;
  // the identifier is a leak that looks like a system talking to itself — which is what put
  // `auth.otp.hint` on a real screen next to a real phone number.
  t: (key: string) => AR[key] ?? '',
};
