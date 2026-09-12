/**
 * AssistantHint.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to
 * end but have NOT been checked by a native speaker. Review before this reaches a shop that
 * actually has Urdu/Hausa/Filipino/Bengali-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'assistantHint.label': 'شرح',
    // Kept as the Arabic question mark for the ar/ur scripts — see the Latin '?' used for en/ha/fil.
    'assistantHint.questionMark': '؟',
    'assistantHint.noEntry': 'لا يتوفَّر شرح لهذا حالياً.',
    'assistantHint.fetchFailed': 'تعذّر جلب الشرح.',
  },
  en: {
    'assistantHint.label': 'Explain',
    'assistantHint.questionMark': '?',
    'assistantHint.noEntry': 'No explanation is available for this yet.',
    'assistantHint.fetchFailed': "Couldn't fetch the explanation.",
  },
  ur: {
    'assistantHint.label': 'وضاحت',
    'assistantHint.questionMark': '؟',
    'assistantHint.noEntry': 'ابھی اس کے لیے کوئی وضاحت دستیاب نہیں۔',
    'assistantHint.fetchFailed': 'وضاحت حاصل نہیں ہو سکی۔',
  },
  ha: {
    'assistantHint.label': 'Bayani',
    'assistantHint.questionMark': '?',
    'assistantHint.noEntry': 'Babu bayani a yanzu game da wannan.',
    'assistantHint.fetchFailed': 'Ba a iya samun bayanin ba.',
  },
  fil: {
    'assistantHint.label': 'Paliwanag',
    'assistantHint.questionMark': '?',
    'assistantHint.noEntry': 'Wala pang available na paliwanag para dito.',
    'assistantHint.fetchFailed': 'Hindi makuha ang paliwanag.',
  },
  bn: {
    'assistantHint.label': 'ব্যাখ্যা',
    'assistantHint.questionMark': '?',
    'assistantHint.noEntry': 'এর জন্য এখনো কোনো ব্যাখ্যা নেই।',
    'assistantHint.fetchFailed': 'ব্যাখ্যা আনা যায়নি।',
  },
});
