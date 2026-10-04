import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// One tinted "what happened here" reading per status — mirrors console's own `STATUS_VARS`
/// (Bookings.tsx), mapped onto this app's existing semantic tokens rather than inventing new
/// color constants (no new token = nothing for scripts/gen_mobile_theme.py to ever drift from).
class BookingStatusTone {
  final Color color;
  final Color soft;
  final String label;
  const BookingStatusTone({required this.color, required this.soft, required this.label});
}

BookingStatusTone bookingStatusTone(String status, bool dark) {
  switch (status) {
    case 'attended':
      return BookingStatusTone(
        color: dark ? AppDarkColors.success : AppColors.success,
        soft: dark ? AppDarkColors.successSoft : AppColors.successSoft,
        label: 'حضر',
      );
    case 'no_show':
      return BookingStatusTone(
        color: dark ? AppDarkColors.danger : AppColors.danger,
        soft: dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
        label: 'لم يحضر',
      );
    case 'cancelled':
      return BookingStatusTone(
        color: dark ? AppDarkColors.textMuted : AppColors.textMuted,
        soft: dark ? AppDarkColors.surface2 : AppColors.surface2,
        label: 'ملغى',
      );
    case 'booked':
    default:
      return BookingStatusTone(
        color: dark ? AppDarkColors.accent : AppColors.accent,
        soft: dark ? AppDarkColors.accentSoft : AppColors.accentSoft,
        label: 'محجوز',
      );
  }
}
