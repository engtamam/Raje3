/**
 * The rail's own strings — the nine section labels `nav.ts::SECTIONS` carries, plus the shell
 * chrome App.tsx feeds `<AppShell labels={…}>` — both real, visible Arabic text that sat OUTSIDE
 * operator-i18n entirely until now (found live 2026-09-14: an owner switched languages and every
 * screen's own content translated while the sidebar around it stayed Arabic, unconditionally).
 *
 * WHY THIS WAS MISSED BY THE STANDING GATE. `ci/check_operator_i18n_coverage.py`'s Part B scans
 * `src/screens/*.tsx` for Arabic text — by design, since that is where a screen's own content
 * lives. `nav.ts` and `App.tsx` are shell/chrome files, not screens, so neither was ever in that
 * glob. The gate itself now also walks these two files explicitly (see that script's own note) —
 * this file is the fix on both sides: the missing keys, and the missing coverage that let them
 * stay missing.
 *
 * KEYED BY SECTION ID (`nav.<id>`), NOT BY THE LITERAL LABEL — `nav.ts::Section.id` is already the
 * stable identity every other consumer (`check_roles.py`, the router) keys off; a key built from
 * the Arabic text itself would have to be renamed the day the Arabic wording changes, for a screen
 * that never reads that text as a key.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'nav.shop': 'محلّي',
    'nav.visit': 'تسجيل زيارة',
    'nav.bookings': 'الحجوزات',
    'nav.customers': 'جهات الاتصال',
    'nav.rating': 'التقييم',
    'nav.partner-loyalty': 'ولاء الشركاء',
    'nav.mobile-requests': 'خدمات متنقلة',
    'nav.mutual-benefit': 'تبادل منافع',
    'nav.services': 'خدماتي ومنتجاتي',
    'nav.messages': 'الحملات',
    'nav.points': 'نقاط الولاء',
    'nav.store': 'متجر التطبيقات',
    'nav.support': 'الدعم الفني',
    'nav.unavailableSuffix': '{label} · متعذّر الآن',
    'shell.collapse': 'طيّ القائمة',
    'shell.expand': 'فتح القائمة',
    'shell.signOut': 'تسجيل الخروج',
    'shell.account': 'حسابي',
  },
  en: {
    'nav.shop': 'My Shop',
    'nav.visit': 'Record a visit',
    'nav.bookings': 'Bookings',
    'nav.customers': 'Contacts',
    'nav.rating': 'Ratings',
    'nav.partner-loyalty': 'Partner Loyalty',
    'nav.mobile-requests': 'Mobile Services',
    'nav.mutual-benefit': 'Mutual Benefit',
    'nav.services': 'Services & products',
    'nav.messages': 'Campaigns',
    'nav.points': 'My points',
    'nav.store': 'App store',
    'nav.support': 'Support',
    'nav.unavailableSuffix': '{label} · unavailable now',
    'shell.collapse': 'Collapse menu',
    'shell.expand': 'Expand menu',
    'shell.signOut': 'Sign out',
    'shell.account': 'My account',
  },
  ur: {
    'nav.shop': 'میری دکان',
    'nav.visit': 'وزٹ درج کریں',
    'nav.bookings': 'بکنگز',
    'nav.customers': 'رابطے',
    'nav.rating': 'ریٹنگز',
    'nav.partner-loyalty': 'پارٹنر وفاداری',
    'nav.mobile-requests': 'موبائل سروسز',
    'nav.mutual-benefit': 'اسٹریٹجک شراکت',
    'nav.services': 'سروسز اور پروڈکٹس',
    'nav.messages': 'مہمّات',
    'nav.points': 'میرے پوائنٹس',
    'nav.store': 'ایپ اسٹور',
    'nav.support': 'سپورٹ',
    'nav.unavailableSuffix': '{label} · ابھی دستیاب نہیں',
    'shell.collapse': 'مینو بند کریں',
    'shell.expand': 'مینو کھولیں',
    'shell.signOut': 'سائن آؤٹ',
    'shell.account': 'میرا اکاؤنٹ',
  },
  ha: {
    'nav.shop': 'Shagona',
    'nav.visit': 'Rubuta ziyara',
    'nav.bookings': 'Ajiye lokaci',
    'nav.customers': 'Masu Tuntuɓa',
    'nav.rating': 'Kimantawa',
    'nav.partner-loyalty': 'Amincin Abokan Hulɗa',
    'nav.mobile-requests': 'Hidimomin Tafi-da-gidanka',
    'nav.mutual-benefit': 'Haɗin Gwiwa Mai Dabara',
    'nav.services': 'Sabis da kayayyaki',
    'nav.messages': 'Kamfen',
    'nav.points': 'Makina',
    'nav.store': 'Kantin app',
    'nav.support': 'Taimako',
    'nav.unavailableSuffix': '{label} · ba ya samuwa yanzu',
    'shell.collapse': 'Rufe menu',
    'shell.expand': 'Buɗe menu',
    'shell.signOut': 'Fita',
    'shell.account': 'Asusuna',
  },
  fil: {
    'nav.shop': 'Ang tindahan ko',
    'nav.visit': 'Itala ang bisita',
    'nav.bookings': 'Mga booking',
    'nav.customers': 'Mga Kontak',
    'nav.rating': 'Mga rating',
    'nav.partner-loyalty': 'Katapatan ng Kasosyo',
    'nav.mobile-requests': 'Mobile na Serbisyo',
    'nav.mutual-benefit': 'Estratehikong Partnership',
    'nav.services': 'Mga serbisyo at produkto',
    'nav.messages': 'Mga kampanya',
    'nav.points': 'Mga puntos ko',
    'nav.store': 'App store',
    'nav.support': 'Suporta',
    'nav.unavailableSuffix': '{label} · hindi available ngayon',
    'shell.collapse': 'Isara ang menu',
    'shell.expand': 'Buksan ang menu',
    'shell.signOut': 'Mag-sign out',
    'shell.account': 'Account ko',
  },
  bn: {
    'nav.shop': 'আমার দোকান',
    'nav.visit': 'ভিজিট নথিভুক্ত করুন',
    'nav.bookings': 'বুকিং',
    'nav.customers': 'পরিচিতি',
    'nav.rating': 'রেটিং',
    'nav.partner-loyalty': 'অংশীদার আনুগত্য',
    'nav.mobile-requests': 'ভ্রাম্যমাণ সেবা',
    'nav.mutual-benefit': 'কৌশলগত অংশীদারিত্ব',
    'nav.services': 'সেবা ও পণ্য',
    'nav.messages': 'ক্যাম্পেইন',
    'nav.points': 'আমার পয়েন্ট',
    'nav.store': 'অ্যাপ স্টোর',
    'nav.support': 'সহায়তা',
    'nav.unavailableSuffix': '{label} · এখন উপলব্ধ নেই',
    'shell.collapse': 'মেনু বন্ধ করুন',
    'shell.expand': 'মেনু খুলুন',
    'shell.signOut': 'সাইন আউট',
    'shell.account': 'আমার অ্যাকাউন্ট',
  },
});
