/**
 * Steps.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino/Bengali-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'steps.previous': 'السابق',
    'steps.next': 'التالي',
  },
  en: {
    'steps.previous': 'Previous',
    'steps.next': 'Next',
  },
  ur: {
    'steps.previous': 'پچھلا',
    'steps.next': 'اگلا',
  },
  ha: {
    'steps.previous': 'Na baya',
    'steps.next': 'Na gaba',
  },
  fil: {
    'steps.previous': 'Nakaraan',
    'steps.next': 'Susunod',
  },
  bn: {
    'steps.previous': 'আগের',
    'steps.next': 'পরের',
  },
});
