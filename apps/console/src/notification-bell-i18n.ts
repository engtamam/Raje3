/**
 * NotificationBell.tsx's own strings — registered once at import time (see operator-i18n.tsx's
 * own header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the rest of the console. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to
 * end, but have NOT been checked by a native speaker — same posture team-i18n.ts's own header
 * states for the same languages.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'notificationBell.label': 'الإشعارات',
    'notificationBell.title': 'الإشعارات',
    'notificationBell.markAllRead': 'تعليم الكل كمقروء',
    'notificationBell.empty': 'لا توجد إشعارات بعد.',
    'notificationBell.loadFailed': 'تعذّرت قراءة الإشعارات — حاول بعد قليل.',
    'notificationBell.ago.justNow': 'الآن',
    'notificationBell.ago.minutesAgo': 'قبل {n} دقيقة',
    'notificationBell.ago.hoursAgo': 'قبل {n} ساعة',
    'notificationBell.ago.yesterday': 'أمس',
    'notificationBell.ago.daysAgo': 'قبل {n} يوم',
  },
  en: {
    'notificationBell.label': 'Notifications',
    'notificationBell.title': 'Notifications',
    'notificationBell.markAllRead': 'Mark all as read',
    'notificationBell.empty': 'No notifications yet.',
    'notificationBell.loadFailed': "Couldn't read your notifications — try again shortly.",
    'notificationBell.ago.justNow': 'Just now',
    'notificationBell.ago.minutesAgo': '{n}m ago',
    'notificationBell.ago.hoursAgo': '{n}h ago',
    'notificationBell.ago.yesterday': 'Yesterday',
    'notificationBell.ago.daysAgo': '{n}d ago',
  },
  ur: {
    'notificationBell.label': 'اطلاعات',
    'notificationBell.title': 'اطلاعات',
    'notificationBell.markAllRead': 'سب کو پڑھا ہوا نشان زد کریں',
    'notificationBell.empty': 'ابھی کوئی اطلاع نہیں۔',
    'notificationBell.loadFailed': 'اطلاعات نہیں پڑھ سکے — تھوڑی دیر بعد کوشش کریں۔',
    'notificationBell.ago.justNow': 'ابھی',
    'notificationBell.ago.minutesAgo': '{n} منٹ پہلے',
    'notificationBell.ago.hoursAgo': '{n} گھنٹے پہلے',
    'notificationBell.ago.yesterday': 'کل',
    'notificationBell.ago.daysAgo': '{n} دن پہلے',
  },
  ha: {
    'notificationBell.label': 'Sanarwowi',
    'notificationBell.title': 'Sanarwowi',
    'notificationBell.markAllRead': "Yi alama duka an karanta",
    'notificationBell.empty': 'Babu sanarwa tukuna.',
    'notificationBell.loadFailed': "Ba a iya karanta sanarwowinka ba — sake gwadawa bayan ɗan lokaci.",
    'notificationBell.ago.justNow': 'Yanzu',
    'notificationBell.ago.minutesAgo': 'Mintuna {n} da suka wuce',
    'notificationBell.ago.hoursAgo': 'Awanni {n} da suka wuce',
    'notificationBell.ago.yesterday': 'Jiya',
    'notificationBell.ago.daysAgo': 'Kwanaki {n} da suka wuce',
  },
  fil: {
    'notificationBell.label': 'Mga Notification',
    'notificationBell.title': 'Mga Notification',
    'notificationBell.markAllRead': 'Markahan lahat na nabasa na',
    'notificationBell.empty': 'Wala pang notification.',
    'notificationBell.loadFailed': "Hindi mabasa ang mga notification mo — subukan ulit mamaya.",
    'notificationBell.ago.justNow': 'Ngayon lang',
    'notificationBell.ago.minutesAgo': '{n}m ang nakalipas',
    'notificationBell.ago.hoursAgo': '{n}h ang nakalipas',
    'notificationBell.ago.yesterday': 'Kahapon',
    'notificationBell.ago.daysAgo': '{n}d ang nakalipas',
  },
  bn: {
    'notificationBell.label': 'বিজ্ঞপ্তি',
    'notificationBell.title': 'বিজ্ঞপ্তি',
    'notificationBell.markAllRead': 'সব পঠিত হিসেবে চিহ্নিত করুন',
    'notificationBell.empty': 'এখনো কোনো বিজ্ঞপ্তি নেই।',
    'notificationBell.loadFailed': 'আপনার বিজ্ঞপ্তি পড়া যায়নি — একটু পরে আবার চেষ্টা করুন।',
    'notificationBell.ago.justNow': 'এইমাত্র',
    'notificationBell.ago.minutesAgo': '{n} মিনিট আগে',
    'notificationBell.ago.hoursAgo': '{n} ঘণ্টা আগে',
    'notificationBell.ago.yesterday': 'গতকাল',
    'notificationBell.ago.daysAgo': '{n} দিন আগে',
  },
});
