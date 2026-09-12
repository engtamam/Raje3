/**
 * TextEditor.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
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
    'textEditor.error.emptyBody': 'يُرجى كتابة نص الرسالة أولاً.',
    'textEditor.error.saveFailed': 'تعذّر حفظ النص.',
    'textEditor.title': 'نصّك لرسالة «{label}»',
    'textEditor.subtitle': 'اكتب نصّك بحرّية، وأضف الفراغات بنقرة واحدة — نتولّى ترقيمها.',
    'textEditor.addLabel': 'إضافة:',
    'textEditor.bodyAriaLabel': 'نص الرسالة',
    'textEditor.mandatoryLine': 'وفي نهاية الرسالة دائماً:',
    'textEditor.mandatoryAriaLabel': '{label} — مقفل',
    'textEditor.previewTitle': 'كما يصل عميلك',
    'textEditor.approvalNote': 'يُحفظ عندك أولاً، ولا يصل عميلك حتى يعتمده واتساب.',
    'textEditor.cancel': 'إلغاء',
    'textEditor.save': 'حفظ',
  },
  en: {
    'textEditor.error.emptyBody': 'Write the message text first.',
    'textEditor.error.saveFailed': "Couldn't save.",
    'textEditor.title': 'Your text for the "{label}" message',
    'textEditor.subtitle': 'Write however you like, and add the blanks with a tap — we number them.',
    'textEditor.addLabel': 'Add:',
    'textEditor.bodyAriaLabel': 'Message text',
    'textEditor.mandatoryLine': 'And always at the end of the message:',
    'textEditor.mandatoryAriaLabel': '{label} — locked',
    'textEditor.previewTitle': 'As your customer reads it',
    'textEditor.approvalNote': "Saved on your side first — your customer doesn't see it until WhatsApp approves it.",
    'textEditor.cancel': 'Cancel',
    'textEditor.save': 'Save',
  },
  ur: {
    'textEditor.error.emptyBody': 'پہلے پیغام کا متن لکھیں۔',
    'textEditor.error.saveFailed': 'محفوظ نہیں ہو سکا۔',
    'textEditor.title': '«{label}» کے پیغام کے لیے آپ کا متن',
    'textEditor.subtitle': 'آپ جیسے چاہیں لکھیں، اور خالی جگہیں ایک ٹیپ سے شامل کریں — نمبر ہم دیں گے۔',
    'textEditor.addLabel': 'شامل کریں:',
    'textEditor.bodyAriaLabel': 'پیغام کا متن',
    'textEditor.mandatoryLine': 'اور پیغام کے آخر میں ہمیشہ:',
    'textEditor.mandatoryAriaLabel': '{label} — مقفل',
    'textEditor.previewTitle': 'جیسا آپ کا گاہک پڑھے گا',
    'textEditor.approvalNote': 'پہلے آپ کے پاس محفوظ ہوتا ہے — واٹس ایپ کی منظوری تک آپ کا گاہک اسے نہیں دیکھتا۔',
    'textEditor.cancel': 'منسوخ کریں',
    'textEditor.save': 'محفوظ کریں',
  },
  ha: {
    'textEditor.error.emptyBody': 'Rubuta rubutun saƙon tukuna.',
    'textEditor.error.saveFailed': 'Ba a iya ajiyewa ba.',
    'textEditor.title': 'Rubutunka don saƙon "{label}"',
    'textEditor.subtitle': 'Rubuta yadda kake so, ka ƙara wuraren fanko da danna ɗaya — mu ke lambatawa.',
    'textEditor.addLabel': 'Ƙara:',
    'textEditor.bodyAriaLabel': 'Rubutun saƙo',
    'textEditor.mandatoryLine': 'Kuma koyaushe a ƙarshen saƙon:',
    'textEditor.mandatoryAriaLabel': '{label} — a kulle',
    'textEditor.previewTitle': 'Yadda abokin cinikinka zai karanta',
    'textEditor.approvalNote': "Ana ajiye shi a wajenka tukuna — abokin cinikinka ba zai gani ba sai WhatsApp ya amince.",
    'textEditor.cancel': 'Soke',
    'textEditor.save': 'Ajiye',
  },
  fil: {
    'textEditor.error.emptyBody': 'Isulat muna ang teksto ng mensahe.',
    'textEditor.error.saveFailed': 'Hindi ma-save.',
    'textEditor.title': 'Ang teksto mo para sa mensaheng "{label}"',
    'textEditor.subtitle': 'Isulat ayon sa gusto mo, at idagdag ang mga puwang nang isang tap — kami ang bibilang nito.',
    'textEditor.addLabel': 'Idagdag:',
    'textEditor.bodyAriaLabel': 'Teksto ng mensahe',
    'textEditor.mandatoryLine': 'At palagi sa dulo ng mensahe:',
    'textEditor.mandatoryAriaLabel': '{label} — naka-lock',
    'textEditor.previewTitle': 'Ang babasahin ng customer mo',
    'textEditor.approvalNote': 'Nase-save muna sa iyo — hindi ito makikita ng customer mo hanggang aprubahan ng WhatsApp.',
    'textEditor.cancel': 'Kanselahin',
    'textEditor.save': 'I-save',
  },
});
