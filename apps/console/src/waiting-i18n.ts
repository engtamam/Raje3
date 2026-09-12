/**
 * Waiting.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil were produced in this pass to unblock the mechanism end to
 * end but have NOT been checked by a native speaker. Review before this reaches a shop that
 * actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: { 'waiting.default': 'لحظة من فضلك…' },
  en: { 'waiting.default': 'One moment…' },
  ur: { 'waiting.default': 'ایک لمحہ…' },
  ha: { 'waiting.default': 'Jira kaɗan…' },
  fil: { 'waiting.default': 'Sandali lang…' },
});
