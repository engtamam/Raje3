/** `bookingPayment.ts`'s own strings — the three payment-status labels. Same per-module
 *  registration pattern as every screen. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'bookingPayment.label.none': 'بدون عربون',
    'bookingPayment.label.deposit': 'عربون',
    'bookingPayment.label.paid': 'مدفوع',
  },
  en: {
    'bookingPayment.label.none': 'No deposit',
    'bookingPayment.label.deposit': 'Deposit',
    'bookingPayment.label.paid': 'Paid',
  },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: {
    'bookingPayment.label.none': 'بغیر ایڈوانس',
    'bookingPayment.label.deposit': 'ایڈوانس',
    'bookingPayment.label.paid': 'ادا شدہ',
  },
  ha: {
    'bookingPayment.label.none': 'Babu ajiya',
    'bookingPayment.label.deposit': 'Ajiya',
    'bookingPayment.label.paid': 'An biya',
  },
  fil: {
    'bookingPayment.label.none': 'Walang deposit',
    'bookingPayment.label.deposit': 'Deposit',
    'bookingPayment.label.paid': 'Bayad na',
  },
  bn: {
    'bookingPayment.label.none': 'জমা ছাড়া',
    'bookingPayment.label.deposit': 'জমা',
    'bookingPayment.label.paid': 'পরিশোধিত',
  },
});
