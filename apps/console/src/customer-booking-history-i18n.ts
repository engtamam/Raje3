/**
 * CustomerBookingHistory.tsx's own strings — registered once at import time (see
 * operator-i18n.tsx's own header for why this is a small per-screen file rather than one giant
 * dictionary). Booking status labels and AM/PM letters are NOT re-declared here — they're read
 * from `screens/bookings-i18n.ts`'s own `bookings.status.*`/`bookings.am`/`bookings.pm` keys,
 * imported alongside this file, so the same wording never drifts between the two screens.
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
    'customerBookingHistory.title': 'الحجوزات',
    'customerBookingHistory.attendanceRate': 'نسبة الحضور: {rate}٪',
    'customerBookingHistory.upcoming': 'القادمة',
    'customerBookingHistory.past': 'السابقة',
  },
  en: {
    'customerBookingHistory.title': 'Bookings',
    'customerBookingHistory.attendanceRate': 'Attendance rate: {rate}%',
    'customerBookingHistory.upcoming': 'Upcoming',
    'customerBookingHistory.past': 'Past',
  },
  ur: {
    'customerBookingHistory.title': 'بکنگز',
    'customerBookingHistory.attendanceRate': 'حاضری کی شرح: {rate}٪',
    'customerBookingHistory.upcoming': 'آنے والی',
    'customerBookingHistory.past': 'گزشتہ',
  },
  ha: {
    'customerBookingHistory.title': 'Ajiya',
    'customerBookingHistory.attendanceRate': 'Yawan halarta: {rate}%',
    'customerBookingHistory.upcoming': 'Masu zuwa',
    'customerBookingHistory.past': 'Da suka wuce',
  },
  fil: {
    'customerBookingHistory.title': 'Mga Booking',
    'customerBookingHistory.attendanceRate': 'Attendance rate: {rate}%',
    'customerBookingHistory.upcoming': 'Paparating',
    'customerBookingHistory.past': 'Nakaraan',
  },
  bn: {
    'customerBookingHistory.title': 'বুকিং',
    'customerBookingHistory.attendanceRate': 'উপস্থিতির হার: {rate}%',
    'customerBookingHistory.upcoming': 'আসন্ন',
    'customerBookingHistory.past': 'অতীত',
  },
});
