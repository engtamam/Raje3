/**
 * TodayBookingsStrip.tsx's own strings — registered once at import time (see operator-i18n.tsx's
 * own header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'todayBookings.am': 'ص',
    'todayBookings.pm': 'م',
    'todayBookings.listSeparator': '، ',
    'todayBookings.attended': 'فُتحت الزيارة ✓',
    'todayBookings.attendFailed': 'تعذّر فتح الزيارة.',
    'todayBookings.readFailed': 'تعذّرت قراءة حجوزات اليوم.',
    'todayBookings.attend': 'حضر',
  },
  en: {
    'todayBookings.am': 'AM',
    'todayBookings.pm': 'PM',
    'todayBookings.listSeparator': ', ',
    'todayBookings.attended': 'Visit opened ✓',
    'todayBookings.attendFailed': "Couldn't open the visit.",
    'todayBookings.readFailed': "Couldn't read today's bookings.",
    'todayBookings.attend': 'Arrived',
  },
  ur: {
    'todayBookings.am': 'صبح',
    'todayBookings.pm': 'شام',
    'todayBookings.listSeparator': '، ',
    'todayBookings.attended': 'وزٹ کھل گئی ✓',
    'todayBookings.attendFailed': 'وزٹ نہیں کھل سکی۔',
    'todayBookings.readFailed': 'آج کی بکنگز نہیں پڑھ سکے۔',
    'todayBookings.attend': 'آ گیا',
  },
  ha: {
    'todayBookings.am': 'safe',
    'todayBookings.pm': 'yamma',
    'todayBookings.listSeparator': '، ',
    'todayBookings.attended': 'An buɗe ziyara ✓',
    'todayBookings.attendFailed': 'Ba a iya buɗe ziyara ba.',
    'todayBookings.readFailed': 'Ba a iya karanta ajiyar yau ba.',
    'todayBookings.attend': 'Ya zo',
  },
  fil: {
    'todayBookings.am': 'AM',
    'todayBookings.pm': 'PM',
    'todayBookings.listSeparator': ', ',
    'todayBookings.attended': 'Nabuksan ang bisita ✓',
    'todayBookings.attendFailed': "Hindi mabuksan ang bisita.",
    'todayBookings.readFailed': "Hindi mabasa ang mga booking ngayong araw.",
    'todayBookings.attend': 'Dumating',
  },
});
