/**
 * WelcomeTrial.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 *
 * ALL FIVE LOCALES ARE REGISTERED HERE for completeness, even though this screen currently reads
 * strings through a fixed Arabic `t` (see WelcomeTrial.tsx's own note on why: it can render before
 * `OperatorI18nProvider` mounts, right after a fresh signup, so it cannot safely call
 * `useOperatorI18n()`).
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'welcomeTrial.day.0': 'الأحد', 'welcomeTrial.day.1': 'الاثنين', 'welcomeTrial.day.2': 'الثلاثاء',
    'welcomeTrial.day.3': 'الأربعاء', 'welcomeTrial.day.4': 'الخميس', 'welcomeTrial.day.5': 'الجمعة',
    'welcomeTrial.day.6': 'السبت',
    'welcomeTrial.month.0': 'يناير', 'welcomeTrial.month.1': 'فبراير', 'welcomeTrial.month.2': 'مارس',
    'welcomeTrial.month.3': 'أبريل', 'welcomeTrial.month.4': 'مايو', 'welcomeTrial.month.5': 'يونيو',
    'welcomeTrial.month.6': 'يوليو', 'welcomeTrial.month.7': 'أغسطس', 'welcomeTrial.month.8': 'سبتمبر',
    'welcomeTrial.month.9': 'أكتوبر', 'welcomeTrial.month.10': 'نوفمبر', 'welcomeTrial.month.11': 'ديسمبر',

    'welcomeTrial.dialogLabel': 'أهلاً بك في راجِع',
    'welcomeTrial.title': 'أهلاً بك في راجِع',
    'welcomeTrial.subtitle': 'محلّك جاهز، وتجربتك المجانية بدأت الآن — كل شيء مفتوح أمامك بلا أي إعداد.',
    'welcomeTrial.trialUntil': 'تجربتك سارية حتى {date}',
    'welcomeTrial.start': 'لنبدأ',
    'welcomeTrial.footer': 'راجِع · السعودية',
  },
  en: {
    'welcomeTrial.day.0': 'Sunday', 'welcomeTrial.day.1': 'Monday', 'welcomeTrial.day.2': 'Tuesday',
    'welcomeTrial.day.3': 'Wednesday', 'welcomeTrial.day.4': 'Thursday', 'welcomeTrial.day.5': 'Friday',
    'welcomeTrial.day.6': 'Saturday',
    'welcomeTrial.month.0': 'January', 'welcomeTrial.month.1': 'February', 'welcomeTrial.month.2': 'March',
    'welcomeTrial.month.3': 'April', 'welcomeTrial.month.4': 'May', 'welcomeTrial.month.5': 'June',
    'welcomeTrial.month.6': 'July', 'welcomeTrial.month.7': 'August', 'welcomeTrial.month.8': 'September',
    'welcomeTrial.month.9': 'October', 'welcomeTrial.month.10': 'November', 'welcomeTrial.month.11': 'December',

    'welcomeTrial.dialogLabel': 'Welcome to Raje3',
    'welcomeTrial.title': 'Welcome to Raje3',
    'welcomeTrial.subtitle': "Your shop is ready, and your free trial has just started — everything is open to you with no setup at all.",
    'welcomeTrial.trialUntil': 'Your trial runs through {date}',
    'welcomeTrial.start': "Let's start",
    'welcomeTrial.footer': 'Raje3 · Saudi Arabia',
  },
  ur: {
    'welcomeTrial.day.0': 'اتوار', 'welcomeTrial.day.1': 'پیر', 'welcomeTrial.day.2': 'منگل',
    'welcomeTrial.day.3': 'بدھ', 'welcomeTrial.day.4': 'جمعرات', 'welcomeTrial.day.5': 'جمعہ',
    'welcomeTrial.day.6': 'ہفتہ',
    'welcomeTrial.month.0': 'جنوری', 'welcomeTrial.month.1': 'فروری', 'welcomeTrial.month.2': 'مارچ',
    'welcomeTrial.month.3': 'اپریل', 'welcomeTrial.month.4': 'مئی', 'welcomeTrial.month.5': 'جون',
    'welcomeTrial.month.6': 'جولائی', 'welcomeTrial.month.7': 'اگست', 'welcomeTrial.month.8': 'ستمبر',
    'welcomeTrial.month.9': 'اکتوبر', 'welcomeTrial.month.10': 'نومبر', 'welcomeTrial.month.11': 'دسمبر',

    'welcomeTrial.dialogLabel': 'راجِع میں خوش آمدید',
    'welcomeTrial.title': 'راجِع میں خوش آمدید',
    'welcomeTrial.subtitle': 'آپ کی دکان تیار ہے، اور آپ کا مفت آزمائشی دورانیہ ابھی شروع ہو چکا ہے — سب کچھ آپ کے لیے بلا کسی سیٹ اپ کے کھلا ہے۔',
    'welcomeTrial.trialUntil': 'آپ کی آزمائش {date} تک جاری ہے',
    'welcomeTrial.start': 'شروع کریں',
    'welcomeTrial.footer': 'راجِع · سعودی عرب',
  },
  ha: {
    'welcomeTrial.day.0': 'Lahadi', 'welcomeTrial.day.1': 'Litinin', 'welcomeTrial.day.2': 'Talata',
    'welcomeTrial.day.3': 'Laraba', 'welcomeTrial.day.4': 'Alhamis', 'welcomeTrial.day.5': "Jumma'a",
    'welcomeTrial.day.6': 'Asabar',
    'welcomeTrial.month.0': 'Janairu', 'welcomeTrial.month.1': 'Fabrairu', 'welcomeTrial.month.2': 'Maris',
    'welcomeTrial.month.3': 'Afirilu', 'welcomeTrial.month.4': 'Mayu', 'welcomeTrial.month.5': 'Yuni',
    'welcomeTrial.month.6': 'Yuli', 'welcomeTrial.month.7': 'Agusta', 'welcomeTrial.month.8': 'Satumba',
    'welcomeTrial.month.9': 'Oktoba', 'welcomeTrial.month.10': 'Nuwamba', 'welcomeTrial.month.11': 'Disamba',

    'welcomeTrial.dialogLabel': 'Barka da zuwa Raje3',
    'welcomeTrial.title': 'Barka da zuwa Raje3',
    'welcomeTrial.subtitle': "Shagon ka a shirye yake, kuma gwajin ka na kyauta ya fara yanzu — komai a buɗe gare ka ba tare da wani shiri ba.",
    'welcomeTrial.trialUntil': 'Gwajin ka yana aiki har zuwa {date}',
    'welcomeTrial.start': 'Mu fara',
    'welcomeTrial.footer': 'Raje3 · Saudiyya',
  },
  fil: {
    'welcomeTrial.day.0': 'Linggo', 'welcomeTrial.day.1': 'Lunes', 'welcomeTrial.day.2': 'Martes',
    'welcomeTrial.day.3': 'Miyerkules', 'welcomeTrial.day.4': 'Huwebes', 'welcomeTrial.day.5': 'Biyernes',
    'welcomeTrial.day.6': 'Sabado',
    'welcomeTrial.month.0': 'Enero', 'welcomeTrial.month.1': 'Pebrero', 'welcomeTrial.month.2': 'Marso',
    'welcomeTrial.month.3': 'Abril', 'welcomeTrial.month.4': 'Mayo', 'welcomeTrial.month.5': 'Hunyo',
    'welcomeTrial.month.6': 'Hulyo', 'welcomeTrial.month.7': 'Agosto', 'welcomeTrial.month.8': 'Setyembre',
    'welcomeTrial.month.9': 'Oktubre', 'welcomeTrial.month.10': 'Nobyembre', 'welcomeTrial.month.11': 'Disyembre',

    'welcomeTrial.dialogLabel': 'Maligayang pagdating sa Raje3',
    'welcomeTrial.title': 'Maligayang pagdating sa Raje3',
    'welcomeTrial.subtitle': 'Handa na ang tindahan mo, at nagsimula na ang libre mong trial — bukas ang lahat sa iyo nang walang kailangang i-set up.',
    'welcomeTrial.trialUntil': 'Aktibo ang trial mo hanggang {date}',
    'welcomeTrial.start': 'Simulan na',
    'welcomeTrial.footer': 'Raje3 · Saudi Arabia',
  },
});
