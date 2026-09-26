import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «الحملات»'s own visual identity — a distinct tone per message CLASS (never Material defaults),
/// mirrored from Messages.tsx's own `CLASS_TONE`/`SECTION_TONE` but pushed further: mobile has
/// room to be more visual than a dense desktop table, so each class gets a real two-stop gradient
/// for its icon chip rather than a single flat tint, and campaign STATE gets its own separate
/// palette so the two questions ("what kind of message is this" vs "is this campaign running")
/// never compete for the same colour.
class MsgClassStyle {
  final Color solid;
  final Color soft;
  final Color onSoft;
  final List<Color> gradient;
  final IconData icon;

  const MsgClassStyle({
    required this.solid,
    required this.soft,
    required this.onSoft,
    required this.gradient,
    required this.icon,
  });
}

/// `service` (خدمية) — teal/info: calm, operational, "this just confirms something happened".
/// `personal` (شخصية) — rose/success-adjacent warmth: "this is between the shop and one person".
/// `marketing` (تسويقية) — amber-to-coral: the class an owner is legally answerable for (consent,
/// billing, the quiet window), so it is the loudest on purpose — same reasoning Messages.tsx's
/// own header comment gives for why marketing wears `warning`, never a third shade of neutral.
/// `offers` (عروض) — violet-to-magenta, the app's own accent family: goal-only cards a shop
/// launches by hand, visually tied to the accent used everywhere else "you decide, we don't".
MsgClassStyle msgClassStyle(String cls, bool isDark) {
  switch (cls) {
    case 'personal':
      return MsgClassStyle(
        solid: isDark ? const Color(0xFFFF9FB2) : const Color(0xFFE64980),
        soft: isDark ? const Color(0xFF3A1B29) : const Color(0xFFFDE8EF),
        onSoft: isDark ? const Color(0xFFFFC2D1) : const Color(0xFFB43A63),
        gradient: isDark
            ? const [Color(0xFFFF9FB2), Color(0xFFE86AA0)]
            : const [Color(0xFFE64980), Color(0xFFFF8FAB)],
        icon: Icons.favorite_rounded,
      );
    case 'marketing':
      return MsgClassStyle(
        solid: isDark ? const Color(0xFFFFC078) : const Color(0xFFE8590C),
        soft: isDark ? const Color(0xFF3A2610) : const Color(0xFFFDECDA),
        onSoft: isDark ? const Color(0xFFFFD8A8) : const Color(0xFFB1490C),
        gradient: isDark
            ? const [Color(0xFFFFC078), Color(0xFFFF922B)]
            : const [Color(0xFFE8590C), Color(0xFFFFA94D)],
        icon: Icons.campaign_rounded,
      );
    case 'offers':
      return MsgClassStyle(
        solid: isDark ? AppDarkColors.accent : AppColors.accent,
        soft: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
        onSoft: isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft,
        gradient: isDark
            ? const [Color(0xFFA78BFA), Color(0xFFE599F7)]
            : const [Color(0xFF7C3AED), Color(0xFFC77DFF)],
        icon: Icons.auto_awesome_rounded,
      );
    case 'service':
    default:
      return MsgClassStyle(
        solid: isDark ? const Color(0xFF63D9C9) : const Color(0xFF0C9C8D),
        soft: isDark ? const Color(0xFF0F332F) : const Color(0xFFDFF6F2),
        onSoft: isDark ? const Color(0xFF9FEDE1) : const Color(0xFF0C6D62),
        gradient: isDark
            ? const [Color(0xFF63D9C9), Color(0xFF4FA9E8)]
            : const [Color(0xFF0C9C8D), Color(0xFF3DBEB0)],
        icon: Icons.verified_rounded,
      );
  }
}

/// Campaign lifecycle state — a SEPARATE palette from class colour above, on purpose (this file's
/// own header note): "is it running" and "what kind is it" must never share one colour channel.
class MsgStateStyle {
  final Color solid;
  final Color soft;
  final Color onSoft;
  final String labelKey;

  const MsgStateStyle({required this.solid, required this.onSoft, required this.soft, required this.labelKey});
}

MsgStateStyle msgStateStyle(String state, bool isScheduled, bool isDark) {
  final s = isScheduled ? 'scheduled' : state;
  switch (s) {
    case 'active':
      return MsgStateStyle(
        solid: isDark ? AppDarkColors.success : AppColors.success,
        soft: isDark ? AppDarkColors.successSoft : AppColors.successSoft,
        onSoft: isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft,
        labelKey: 'active',
      );
    case 'paused':
      return MsgStateStyle(
        solid: isDark ? AppDarkColors.warning : AppColors.warning,
        soft: isDark ? AppDarkColors.warningSoft : AppColors.warningSoft,
        onSoft: isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft,
        labelKey: 'paused',
      );
    case 'scheduled':
      return MsgStateStyle(
        solid: isDark ? AppDarkColors.accent : AppColors.accent,
        soft: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
        onSoft: isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft,
        labelKey: 'scheduled',
      );
    case 'done':
    default:
      return MsgStateStyle(
        solid: isDark ? AppDarkColors.textMuted : AppColors.textMuted,
        soft: isDark ? AppDarkColors.surface3 : AppColors.surface3,
        onSoft: isDark ? AppDarkColors.textSecondary : AppColors.textSecondary,
        labelKey: 'done',
      );
  }
}

/// Delivery outcome tone — mirrors Messages.tsx's own three-state receipt logic (قرأها/وصلت/خرجت
/// vs. امتنعت), never a single ambiguous "sent" colour for all four.
Color msgOutcomeColor(String outcome, bool delivered, bool read, bool isDark) {
  if (outcome != 'sent') return isDark ? AppDarkColors.warning : AppColors.warning;
  if (read) return isDark ? AppDarkColors.success : AppColors.success;
  return isDark ? AppDarkColors.textMuted : AppColors.textMuted;
}
