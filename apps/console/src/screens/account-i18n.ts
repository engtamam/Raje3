/**
 * Account.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary). Distinct
 * from account-panes-i18n.ts (`accountPanes.*`), which belongs to AccountPanes.tsx's own cards —
 * this file covers only the tab shell and its own sub-tabs and cards (ChangePasswordCard).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'account.tab.shop.label': 'منشأتي',
    'account.tab.shop.hint': 'هويّتك وفروعك وفريقك وربط واتساب',
    'account.tab.billing.label': 'متجر التطبيقات',
    'account.tab.billing.hint': 'تطبيقاتك ووسيلة الدفع',
    'account.tab.wallet.label': 'محفظتي',
    'account.tab.wallet.hint': 'رصيدك موزّعاً حسب الغرض',
    'account.tab.invoices.label': 'الفواتير',
    'account.tab.invoices.hint': 'فواتيرك وإيصالاتك',
    'account.tab.data.label': 'بياناتي',
    'account.tab.data.hint': 'تقريرك الأسبوعي، الاحتفاظ، التصدير، الاتفاقيات',

    'account.subtab.people': 'العاملون',
    'account.subtab.branches': 'الفروع',
    'account.subtab.branchesLocked': 'مقفل',
    'account.subtab.whatsapp': 'ربط واتساب',
    'account.subtab.identity': 'الهوية والإعدادات',

    'account.pageTitle': 'حسابي',
    'account.myBranchReadFailed': 'تعذّرت قراءة فرعك',
    'account.tabsAriaLabel': 'أقسام حسابي',
    'account.shopSubtabsAriaLabel': 'أقسام منشأتي',

    'account.changePassword.title': 'تغيير كلمة المرور',
    'account.changePassword.mismatch': 'كلمتا المرور الجديدتان غير متطابقتين.',
    'account.changePassword.failed': 'تعذّر تغيير كلمة المرور.',
    'account.changePassword.currentLabel': 'كلمة المرور الحالية',
    'account.changePassword.newLabel': 'كلمة المرور الجديدة',
    'account.changePassword.confirmLabel': 'تأكيد كلمة المرور الجديدة',
    'account.changePassword.success': 'تم تغيير كلمة المرور.',
    'account.changePassword.save': 'حفظ',
    'account.changePassword.cancel': 'إلغاء',
  },
  en: {
    'account.tab.shop.label': 'My Establishment',
    'account.tab.shop.hint': 'Your identity, branches, team, and WhatsApp connection',
    'account.tab.billing.label': 'App Store',
    'account.tab.billing.hint': 'Your apps and payment method',
    'account.tab.wallet.label': 'My Wallet',
    'account.tab.wallet.hint': 'Your balance broken down by purpose',
    'account.tab.invoices.label': 'Invoices',
    'account.tab.invoices.hint': 'Your invoices and receipts',
    'account.tab.data.label': 'My Data',
    'account.tab.data.hint': 'Your weekly report, retention, export, agreements',

    'account.subtab.people': 'People',
    'account.subtab.branches': 'Branches',
    'account.subtab.branchesLocked': 'Locked',
    'account.subtab.whatsapp': 'WhatsApp connection',
    'account.subtab.identity': 'Identity and settings',

    'account.pageTitle': 'My Account',
    'account.myBranchReadFailed': "Couldn't read your branch",
    'account.tabsAriaLabel': 'Account sections',
    'account.shopSubtabsAriaLabel': 'My Establishment sections',

    'account.changePassword.title': 'Change password',
    'account.changePassword.mismatch': "The two new passwords don't match.",
    'account.changePassword.failed': "Couldn't change the password.",
    'account.changePassword.currentLabel': 'Current password',
    'account.changePassword.newLabel': 'New password',
    'account.changePassword.confirmLabel': 'Confirm new password',
    'account.changePassword.success': 'Password changed.',
    'account.changePassword.save': 'Save',
    'account.changePassword.cancel': 'Cancel',
  },
  ur: {
    'account.tab.shop.label': 'میرا ادارہ',
    'account.tab.shop.hint': 'آپ کی شناخت، شاخیں، ٹیم، اور واٹس ایپ ربط',
    'account.tab.billing.label': 'ایپ سٹور',
    'account.tab.billing.hint': 'آپ کی ایپس اور ادائیگی کا طریقہ',
    'account.tab.wallet.label': 'میرا بٹوہ',
    'account.tab.wallet.hint': 'آپ کا بیلنس مقصد کے مطابق تقسیم',
    'account.tab.invoices.label': 'رسیدیں',
    'account.tab.invoices.hint': 'آپ کے انوائس اور رسیدیں',
    'account.tab.data.label': 'میرا ڈیٹا',
    'account.tab.data.hint': 'آپ کی ہفتہ وار رپورٹ، ڈیٹا رکھنا، برآمد، معاہدے',

    'account.subtab.people': 'عملہ',
    'account.subtab.branches': 'شاخیں',
    'account.subtab.branchesLocked': 'مقفل',
    'account.subtab.whatsapp': 'واٹس ایپ ربط',
    'account.subtab.identity': 'شناخت اور ترتیبات',

    'account.pageTitle': 'میرا اکاؤنٹ',
    'account.myBranchReadFailed': 'آپ کی شاخ نہیں پڑھ سکے',
    'account.tabsAriaLabel': 'اکاؤنٹ کے حصے',
    'account.shopSubtabsAriaLabel': 'میرا ادارہ کے حصے',

    'account.changePassword.title': 'پاس ورڈ تبدیل کریں',
    'account.changePassword.mismatch': 'دونوں نئے پاس ورڈ مماثل نہیں۔',
    'account.changePassword.failed': 'پاس ورڈ تبدیل نہیں ہو سکا۔',
    'account.changePassword.currentLabel': 'موجودہ پاس ورڈ',
    'account.changePassword.newLabel': 'نیا پاس ورڈ',
    'account.changePassword.confirmLabel': 'نئے پاس ورڈ کی تصدیق کریں',
    'account.changePassword.success': 'پاس ورڈ تبدیل ہو گیا۔',
    'account.changePassword.save': 'محفوظ کریں',
    'account.changePassword.cancel': 'منسوخ کریں',
  },
  ha: {
    'account.tab.shop.label': 'Kamfanina',
    'account.tab.shop.hint': "Ainihinka, rassa, ƙungiya, da haɗin WhatsApp",
    'account.tab.billing.label': 'App Store',
    'account.tab.billing.hint': 'Ayyukanka da hanyar biya',
    'account.tab.wallet.label': 'Walat Ɗina',
    'account.tab.wallet.hint': "Ma'aunin ka an rarraba shi bisa manufa",
    'account.tab.invoices.label': 'Bayanan Kuɗi',
    'account.tab.invoices.hint': 'Bayanan kuɗinka da rasitoci',
    'account.tab.data.label': 'Bayanaina',
    'account.tab.data.hint': "Rahoton ka na mako-mako, riƙewa, fitarwa, yarjejeniyoyi",

    'account.subtab.people': "Ma'aikata",
    'account.subtab.branches': 'Rassa',
    'account.subtab.branchesLocked': 'A kulle',
    'account.subtab.whatsapp': 'Haɗin WhatsApp',
    'account.subtab.identity': 'Ainihi da saitunan',

    'account.pageTitle': 'Asusuna',
    'account.myBranchReadFailed': 'Ba a iya karanta reshenka ba',
    'account.tabsAriaLabel': 'Sassan asusu',
    'account.shopSubtabsAriaLabel': 'Sassan Kamfanina',

    'account.changePassword.title': 'Canza kalmar sirri',
    'account.changePassword.mismatch': "Sabbin kalmomin sirri guda biyu ba iri ɗaya ba ne.",
    'account.changePassword.failed': 'Ba a iya canza kalmar sirri ba.',
    'account.changePassword.currentLabel': 'Kalmar sirri ta yanzu',
    'account.changePassword.newLabel': 'Sabuwar kalmar sirri',
    'account.changePassword.confirmLabel': 'Tabbatar da sabuwar kalmar sirri',
    'account.changePassword.success': 'An canza kalmar sirri.',
    'account.changePassword.save': 'Ajiye',
    'account.changePassword.cancel': 'Soke',
  },
  fil: {
    'account.tab.shop.label': 'Aking Establisemento',
    'account.tab.shop.hint': 'Ang pagkakakilanlan, branch, team, at koneksyon sa WhatsApp mo',
    'account.tab.billing.label': 'App Store',
    'account.tab.billing.hint': 'Mga app mo at paraan ng pagbabayad',
    'account.tab.wallet.label': 'Aking Wallet',
    'account.tab.wallet.hint': 'Ang balanse mo, hinati ayon sa layunin',
    'account.tab.invoices.label': 'Mga Invoice',
    'account.tab.invoices.hint': 'Mga invoice at resibo mo',
    'account.tab.data.label': 'Aking Data',
    'account.tab.data.hint': 'Ang lingguhang ulat mo, pagpapanatili ng data, pag-export, mga kasunduan',

    'account.subtab.people': 'Mga Tao',
    'account.subtab.branches': 'Mga Branch',
    'account.subtab.branchesLocked': 'Naka-lock',
    'account.subtab.whatsapp': 'Koneksyon sa WhatsApp',
    'account.subtab.identity': 'Pagkakakilanlan at settings',

    'account.pageTitle': 'Aking Account',
    'account.myBranchReadFailed': "Hindi mabasa ang branch mo",
    'account.tabsAriaLabel': 'Mga seksyon ng account',
    'account.shopSubtabsAriaLabel': 'Mga seksyon ng Aking Establisemento',

    'account.changePassword.title': 'Palitan ang password',
    'account.changePassword.mismatch': 'Hindi magkatugma ang dalawang bagong password.',
    'account.changePassword.failed': "Hindi mapalitan ang password.",
    'account.changePassword.currentLabel': 'Kasalukuyang password',
    'account.changePassword.newLabel': 'Bagong password',
    'account.changePassword.confirmLabel': 'Kumpirmahin ang bagong password',
    'account.changePassword.success': 'Napalitan na ang password.',
    'account.changePassword.save': 'I-save',
    'account.changePassword.cancel': 'Kanselahin',
  },
});
