/** `auth.ts`'s own strings — the one generic refusal it throws when the server said nothing at
 *  all. Same per-module registration pattern as every screen. Note: `sentenceFor` (api.ts) only
 *  "keeps" a thrown message when it is Arabic script — in another locale this key falls back to
 *  the render site's own translated fallback instead, which is still correct, just less specific. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: { 'auth.requestFailed': 'تعذّر إكمال الطلب. حاول مرة أخرى.' },
  en: { 'auth.requestFailed': 'Could not complete the request. Try again.' },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: { 'auth.requestFailed': 'درخواست مکمل نہیں ہو سکی۔ دوبارہ کوشش کریں۔' },
  ha: { 'auth.requestFailed': 'An kasa kammala buƙatar. A sake gwadawa.' },
  fil: { 'auth.requestFailed': 'Hindi natapos ang kahilingan. Subukan ulit.' },
  bn: { 'auth.requestFailed': 'অনুরোধ সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।' },
});
