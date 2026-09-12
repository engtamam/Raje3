/**
 * AssistantChat.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil were produced in this pass to unblock the mechanism end to
 * end but have NOT been checked by a native speaker. Review before this reaches a shop that
 * actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'assistantChat.intro': 'اطرح أي سؤال يخص المنصة، ليُجيبك مباشرة؛ وإن لم يعرف الإجابة يُخبرك بذلك صراحةً بدلاً من التخمين.',
    'assistantChat.emptyPrompt': 'اكتب سؤالك في الأسفل لتبدأ.',
    'assistantChat.inputPlaceholder': 'اكتب سؤالك هنا…',
    'assistantChat.inputAriaLabel': 'سؤالك',
    'assistantChat.send': 'إرسال',
    'assistantChat.sendFailed': 'تعذّر إرسال سؤالك.',
  },
  en: {
    'assistantChat.intro': "Ask anything about the platform — it answers you directly, and if it doesn't know, it says so plainly instead of guessing.",
    'assistantChat.emptyPrompt': 'Type your question below to begin.',
    'assistantChat.inputPlaceholder': 'Type your question here…',
    'assistantChat.inputAriaLabel': 'Your question',
    'assistantChat.send': 'Send',
    'assistantChat.sendFailed': "Couldn't send your question.",
  },
  ur: {
    'assistantChat.intro': 'پلیٹ فارم کے بارے میں کچھ بھی پوچھیں — یہ آپ کو براہ راست جواب دے گا، اور اگر جواب معلوم نہ ہو تو اندازہ لگانے کے بجائے صاف بتا دے گا۔',
    'assistantChat.emptyPrompt': 'شروع کرنے کے لیے نیچے اپنا سوال لکھیں۔',
    'assistantChat.inputPlaceholder': 'یہاں اپنا سوال لکھیں…',
    'assistantChat.inputAriaLabel': 'آپ کا سوال',
    'assistantChat.send': 'بھیجیں',
    'assistantChat.sendFailed': 'آپ کا سوال بھیجا نہیں جا سکا۔',
  },
  ha: {
    'assistantChat.intro': "Yi tambaya game da dandalin — zai amsa maka kai tsaye, kuma idan bai san amsar ba, zai gaya maka a fili maimakon tsinkaya.",
    'assistantChat.emptyPrompt': 'Rubuta tambayarka a ƙasa domin fara.',
    'assistantChat.inputPlaceholder': 'Rubuta tambayarka a nan…',
    'assistantChat.inputAriaLabel': 'Tambayarka',
    'assistantChat.send': 'Aika',
    'assistantChat.sendFailed': 'Ba a iya aika tambayarka ba.',
  },
  fil: {
    'assistantChat.intro': "Magtanong tungkol sa platform — direkta kang sasagutin, at kung hindi nito alam ang sagot, sasabihin nito nang tapat sa halip na manghula.",
    'assistantChat.emptyPrompt': 'I-type ang tanong mo sa ibaba para magsimula.',
    'assistantChat.inputPlaceholder': 'I-type ang tanong mo dito…',
    'assistantChat.inputAriaLabel': 'Tanong mo',
    'assistantChat.send': 'Ipadala',
    'assistantChat.sendFailed': 'Hindi maipadala ang tanong mo.',
  },
});
