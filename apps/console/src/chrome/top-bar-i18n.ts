/** `TopBar.tsx`'s own strings — same per-screen registration pattern as every other screen. */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'topBar.account': 'حسابي',
    'topBar.signOut': 'تسجيل الخروج',
    'topBar.support': 'الدعم الفني',
    'topBar.home': 'الرئيسية — متجر التطبيقات',
    'topBar.aiUnits.label': 'رصيد وحدات الذكاء الاصطناعي',
    'topBar.aiUnits.breakdown': 'المضمّن: {included} · من الشحن: {topup}',
  },
  en: {
    'topBar.account': 'My account',
    'topBar.signOut': 'Sign out',
    'topBar.support': 'Support',
    'topBar.home': 'Home — App store',
    'topBar.aiUnits.label': 'AI units balance',
    'topBar.aiUnits.breakdown': 'Included: {included} · From top-up: {topup}',
  },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag `account-panes-i18n.ts`'s own header
  // carries for these same four locales.
  ur: {
    'topBar.account': 'میرا اکاؤنٹ',
    'topBar.signOut': 'لاگ آؤٹ',
    'topBar.support': 'سپورٹ',
    'topBar.home': 'ہوم — ایپ اسٹور',
    'topBar.aiUnits.label': 'AI یونٹس کا بیلنس',
    'topBar.aiUnits.breakdown': 'شامل: {included} · ٹاپ اپ سے: {topup}',
  },
  ha: {
    'topBar.account': 'Asusuna',
    'topBar.signOut': 'Fita',
    'topBar.support': 'Taimako',
    'topBar.home': 'Gida — Kantin app',
    'topBar.aiUnits.label': 'Ma’aunin AI',
    'topBar.aiUnits.breakdown': 'Cikin shirin: {included} · Daga cajin: {topup}',
  },
  fil: {
    'topBar.account': 'Aking account',
    'topBar.signOut': 'Mag-sign out',
    'topBar.support': 'Suporta',
    'topBar.home': 'Home — App store',
    'topBar.aiUnits.label': 'Balanse ng AI units',
    'topBar.aiUnits.breakdown': 'Kasama: {included} · Mula sa top-up: {topup}',
  },
  bn: {
    'topBar.account': 'আমার অ্যাকাউন্ট',
    'topBar.signOut': 'লগ আউট',
    'topBar.support': 'সহায়তা',
    'topBar.home': 'হোম — অ্যাপ স্টোর',
    'topBar.aiUnits.label': 'AI ইউনিট ব্যালেন্স',
    'topBar.aiUnits.breakdown': 'অন্তর্ভুক্ত: {included} · টপ-আপ থেকে: {topup}',
  },
});
