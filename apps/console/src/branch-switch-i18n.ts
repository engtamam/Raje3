/**
 * BranchSwitch.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino/Bengali-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'branchSwitch.readFailed': 'تعذّرت قراءة فروعك — الأرقام تعرض المحل كاملاً.',
    'branchSwitch.addBranch': 'إضافة فرع',
    'branchSwitch.shownBranch': 'الفرع المعروض',
    'branchSwitch.allBranches': 'كل الفروع',
    'branchSwitch.unnamedBranch': 'فرع بلا اسم',
    'branchSwitch.outsideView': '{outside} زيارة خارج هذا العرض — في فروعٍ أخرى أو بلا فرع محدَّد.',
  },
  en: {
    'branchSwitch.readFailed': "Couldn't read your branches — the numbers show the whole shop.",
    'branchSwitch.addBranch': 'Add branch',
    'branchSwitch.shownBranch': 'Branch shown',
    'branchSwitch.allBranches': 'All branches',
    'branchSwitch.unnamedBranch': 'Unnamed branch',
    'branchSwitch.outsideView': '{outside} visits outside this view — in other branches or with no branch set.',
  },
  ur: {
    'branchSwitch.readFailed': 'آپ کی شاخیں نہیں پڑھ سکے — اعداد پورا محل دکھاتے ہیں۔',
    'branchSwitch.addBranch': 'شاخ شامل کریں',
    'branchSwitch.shownBranch': 'دکھائی گئی شاخ',
    'branchSwitch.allBranches': 'تمام شاخیں',
    'branchSwitch.unnamedBranch': 'بے نام شاخ',
    'branchSwitch.outsideView': '{outside} وزٹس اس منظر سے باہر — دیگر شاخوں میں یا بغیر متعین شاخ کے۔',
  },
  ha: {
    'branchSwitch.readFailed': "Ba a iya karanta rassanka ba — lambobi suna nuna dukkan shago.",
    'branchSwitch.addBranch': 'Ƙara reshe',
    'branchSwitch.shownBranch': 'Reshen da ake nunawa',
    'branchSwitch.allBranches': 'Dukkan rassa',
    'branchSwitch.unnamedBranch': 'Reshe mara suna',
    'branchSwitch.outsideView': "Ziyara {outside} a wajen wannan kallo — a wasu rassan ko ba tare da reshe da aka saita ba.",
  },
  fil: {
    'branchSwitch.readFailed': "Hindi mabasa ang mga branch mo — ang mga numero ay ipinapakita ang buong tindahan.",
    'branchSwitch.addBranch': 'Magdagdag ng branch',
    'branchSwitch.shownBranch': 'Ipinapakitang branch',
    'branchSwitch.allBranches': 'Lahat ng branch',
    'branchSwitch.unnamedBranch': 'Branch na walang pangalan',
    'branchSwitch.outsideView': '{outside} bisita sa labas ng view na ito — sa ibang branch o walang itinakdang branch.',
  },
  bn: {
    'branchSwitch.readFailed': 'আপনার শাখাগুলো পড়া যায়নি — সংখ্যাগুলো পুরো দোকান দেখাচ্ছে।',
    'branchSwitch.addBranch': 'শাখা যোগ করুন',
    'branchSwitch.shownBranch': 'প্রদর্শিত শাখা',
    'branchSwitch.allBranches': 'সব শাখা',
    'branchSwitch.unnamedBranch': 'নামহীন শাখা',
    'branchSwitch.outsideView': '{outside} ভিজিট এই দৃশ্যের বাইরে — অন্য শাখায় বা কোনো নির্ধারিত শাখা ছাড়া।',
  },
});
