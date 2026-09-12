/**
 * ServiceGrid.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
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
    'serviceGrid.offered': 'عليه عرض',
    'serviceGrid.redeemable': 'يمكن استبداله بنقاطه',
  },
  en: {
    'serviceGrid.offered': 'On offer',
    'serviceGrid.redeemable': 'Redeemable with points',
  },
  ur: {
    'serviceGrid.offered': 'اس پر آفر ہے',
    'serviceGrid.redeemable': 'پوائنٹس سے حاصل کیا جا سکتا ہے',
  },
  ha: {
    'serviceGrid.offered': 'Yana da tayi',
    'serviceGrid.redeemable': 'Ana iya samun sa da maki',
  },
  fil: {
    'serviceGrid.offered': 'May alok',
    'serviceGrid.redeemable': 'Puwedeng makuha gamit ang puntos',
  },
  bn: {
    'serviceGrid.offered': 'অফার আছে',
    'serviceGrid.redeemable': 'পয়েন্ট দিয়ে নেওয়া যায়',
  },
});
