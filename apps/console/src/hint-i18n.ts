/**
 * Hint.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header for
 * why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil were produced in this pass to unblock the mechanism end to
 * end but have NOT been checked by a native speaker. Review before this reaches a shop that
 * actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'hint.label': 'شرح',
    // Kept as the Arabic question mark for the ar/ur scripts — see the Latin '?' used for en/ha/fil.
    'hint.questionMark': '؟',
  },
  en: { 'hint.label': 'Explain', 'hint.questionMark': '?' },
  ur: { 'hint.label': 'وضاحت', 'hint.questionMark': '؟' },
  ha: { 'hint.label': 'Bayani', 'hint.questionMark': '?' },
  fil: { 'hint.label': 'Paliwanag', 'hint.questionMark': '?' },
});
