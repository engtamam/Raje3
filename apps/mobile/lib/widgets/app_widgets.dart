// Raje3 shared component library — mobile's own `rj-ui`.
//
// PORTED from the reference project's `lib/custom_widgets.dart` — a real,
// working component library (PrimaryButton/AppCard/AppTextField/AppAlert/
// EmptyState etc., every screen composing FROM these instead of redrawing
// its own Container+BoxDecoration combo). The SHAPE and the dark-mode
// awareness are theirs (`context.appColors`/`context.isDark`); every colour/
// radius/spacing/text style read through them comes from `theme/app_theme.dart`
// — never a literal, never a second copy of a token already generated there.
// `GoldButton`/`PremiumBadge`/`ThemeSwitchTile`'s premium styling from the
// reference project belong to ITS OWN subscription-tier branding and are not
// ported — Raje3 has no equivalent concept, and a widget nothing calls is
// dead code.
//
// Screens should compose these rather than hand-building a `Container` +
// `BoxDecoration` + `Material` + `InkWell` stack per button/card — that
// repetition, not bad code, is what made the pre-rebuild screens read as
// "a trial" despite clean code underneath.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/theme_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// The minimum gap a scroll-controlled bottom sheet always leaves above it — a real status-bar
/// inset on a phone, but ALSO a floor on a device that reports none (Chrome/Edge web have no
/// notch, so `MediaQuery.paddingOf(context).top` is 0 there). Without the floor the sheet's grab
/// handle sits flush against the browser's own top edge on web — found live testing in real
/// Chrome, not the headless web-server device this had first been checked against.
const double _appSheetMinTopGap = 44;

/// The one cap every scroll-controlled bottom sheet in this app uses for a long form's
/// `Container(constraints: BoxConstraints(maxHeight: ...))`. A literal fraction of screen height
/// (`* 0.9`, `* 0.92`) leaves a gap the screen BEHIND the sheet shows through — found live: a
/// hero header peeking above a tall form sheet, because the sheet's own cap stopped short of the
/// real usable height. This instead caps at the real usable height — the larger of the status
/// bar's own inset and [_appSheetMinTopGap] — so the sheet's rounded top corner always reads as a
/// sheet, never bare screen height (which a notch/camera cutout would push the grab handle
/// straight into, and which a web browser with no inset at all would touch outright).
double appSheetMaxHeight(BuildContext context) {
  final size = MediaQuery.sizeOf(context);
  final topInset = MediaQuery.paddingOf(context).top;
  final topGap = topInset > _appSheetMinTopGap ? topInset : _appSheetMinTopGap;
  return size.height - topGap;
}

/// ═══════════════════════════════════════════════════════════════════════════
/// PRIMARY BUTTON — the one call to action per screen.
/// ═══════════════════════════════════════════════════════════════════════════
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.isLoading = false,
    this.isDisabled = false,
    this.width,
    this.icon,
  });

  final String text;
  final VoidCallback? onPressed;
  final bool isLoading;
  final bool isDisabled;
  final double? width;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final disabled = isDisabled || isLoading || onPressed == null;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final onAccent = isDark ? AppDarkColors.accentContrast : AppColors.accentContrast;

    return SizedBox(
      width: width ?? double.infinity,
      child: Container(
        decoration: BoxDecoration(
          gradient: disabled ? null : primaryGradient(dark: isDark),
          color: disabled ? accent.withValues(alpha: 0.35) : null,
          borderRadius: AppRadius.standardRadius,
          boxShadow: disabled ? null : (isDark ? AppShadows.darkButton : AppShadows.button),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: disabled ? null : onPressed,
            borderRadius: AppRadius.standardRadius,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 24),
              child: isLoading
                  ? Center(
                      child: SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(color: onAccent, strokeWidth: 2),
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (icon != null) ...[
                          Icon(icon, color: onAccent, size: 20),
                          const SizedBox(width: 8),
                        ],
                        Text(text, style: AppTextStyles.button.copyWith(color: onAccent)),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// SECONDARY (OUTLINE) BUTTON
/// ═══════════════════════════════════════════════════════════════════════════
class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.isDisabled = false,
    this.width,
    this.icon,
  });

  final String text;
  final VoidCallback? onPressed;
  final bool isDisabled;
  final double? width;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final disabled = isDisabled || onPressed == null;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final color = disabled ? context.appColors.textMuted : accent;

    return SizedBox(
      width: width ?? double.infinity,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: AppRadius.standardRadius,
          border: Border.all(color: color, width: 1.5),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: disabled ? null : onPressed,
            borderRadius: AppRadius.standardRadius,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 22),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icon != null) ...[
                    Icon(icon, color: color, size: 20),
                    const SizedBox(width: 8),
                  ],
                  Text(text, style: AppTextStyles.button.copyWith(color: color)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// APP CARD — the one surface every list row/section should live on.
/// ═══════════════════════════════════════════════════════════════════════════
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding,
    this.onTap,
    this.hasShadow = true,
    this.hasBorder = true,
  });

  final Widget child;
  final double? padding;
  final VoidCallback? onTap;
  final bool hasShadow;
  final bool hasBorder;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final isDark = context.isDark;

    return Container(
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.cardRadius,
        border: hasBorder ? Border.all(color: colors.borderSubtle) : null,
        boxShadow: hasShadow ? (isDark ? AppShadows.darkCard : AppShadows.card) : null,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.cardRadius,
          child: Padding(
            padding: EdgeInsets.all(padding ?? AppSpacing.md),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// APP TEXT FIELD — one filled input style for every form in the app.
/// ═══════════════════════════════════════════════════════════════════════════
class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    this.labelText,
    this.hintText,
    this.controller,
    this.keyboardType,
    this.obscureText = false,
    this.prefixIcon,
    this.suffixIcon,
    this.onSuffixIconTap,
    this.validator,
    this.onChanged,
    this.enabled = true,
    this.maxLines = 1,
    this.textDirection,
  });

  final String? labelText;
  final String? hintText;
  final TextEditingController? controller;
  final TextInputType? keyboardType;
  final bool obscureText;
  final IconData? prefixIcon;
  final IconData? suffixIcon;
  final VoidCallback? onSuffixIconTap;
  final String? Function(String?)? validator;
  final ValueChanged<String>? onChanged;
  final bool enabled;
  final int? maxLines;
  final TextDirection? textDirection;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final danger = context.isDark ? AppDarkColors.danger : AppColors.danger;

    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      enabled: enabled,
      maxLines: maxLines,
      validator: validator,
      onChanged: onChanged,
      textDirection: textDirection,
      style: AppTextStyles.bodyMedium.copyWith(color: colors.textPrimary),
      decoration: InputDecoration(
        labelText: labelText,
        hintText: hintText,
        filled: true,
        fillColor: enabled ? colors.inputFill : colors.inputFillDisabled,
        contentPadding: const EdgeInsets.all(AppSpacing.md),
        border: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: colors.borderSubtle),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: colors.borderSubtle),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: accent, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: danger, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: danger, width: 1.5),
        ),
        labelStyle: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
        hintStyle: AppTextStyles.caption.copyWith(color: colors.textMuted),
        prefixIcon: prefixIcon != null ? Icon(prefixIcon, color: accent) : null,
        suffixIcon: suffixIcon != null
            ? IconButton(
                icon: Icon(suffixIcon, color: colors.textSecondary),
                onPressed: onSuffixIconTap,
              )
            : null,
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// ALERT BOX — inline success/warning/error/info banner.
/// ═══════════════════════════════════════════════════════════════════════════
enum AlertType { success, warning, error, info }

class AppAlert extends StatelessWidget {
  const AppAlert({
    super.key,
    required this.type,
    required this.message,
    this.title,
    this.onDismiss,
  });

  final AlertType type;
  final String message;
  final String? title;
  final VoidCallback? onDismiss;

  Color _bg(bool isDark) {
    switch (type) {
      case AlertType.success:
        return isDark ? AppDarkColors.successSoft : AppColors.successSoft;
      case AlertType.warning:
        return isDark ? AppDarkColors.warningSoft : AppColors.warningSoft;
      case AlertType.error:
        return isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft;
      case AlertType.info:
        return isDark ? AppDarkColors.infoSoft : AppColors.infoSoft;
    }
  }

  Color _accent(bool isDark) {
    switch (type) {
      case AlertType.success:
        return isDark ? AppDarkColors.success : AppColors.success;
      case AlertType.warning:
        return isDark ? AppDarkColors.warning : AppColors.warning;
      case AlertType.error:
        return isDark ? AppDarkColors.danger : AppColors.danger;
      case AlertType.info:
        return isDark ? AppDarkColors.info : AppColors.info;
    }
  }

  IconData get _icon {
    switch (type) {
      case AlertType.success:
        return Icons.check_circle_rounded;
      case AlertType.warning:
        return Icons.warning_rounded;
      case AlertType.error:
        return Icons.error_rounded;
      case AlertType.info:
        return Icons.info_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final colors = context.appColors;
    final accent = _accent(isDark);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: _bg(isDark),
        border: Border.all(color: accent.withValues(alpha: 0.25)),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_icon, color: accent, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (title != null) ...[
                  Text(title!, style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary)),
                  const SizedBox(height: 4),
                ],
                Text(message, style: AppTextStyles.bodySmall.copyWith(color: colors.textPrimary)),
              ],
            ),
          ),
          if (onDismiss != null) ...[
            const SizedBox(width: 8),
            IconButton(
              icon: Icon(Icons.close, size: 20, color: colors.textMuted),
              onPressed: onDismiss,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
            ),
          ],
        ],
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// BADGE — a small pill of status/meta text (e.g. a service count, a state).
/// ═══════════════════════════════════════════════════════════════════════════
class AppBadge extends StatelessWidget {
  const AppBadge({
    super.key,
    required this.text,
    this.backgroundColor,
    this.textColor,
    this.icon,
  });

  final String text;
  final Color? backgroundColor;
  final Color? textColor;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final bg = backgroundColor ?? (isDark ? AppDarkColors.accentSoft : AppColors.accentSoft);
    final fg = textColor ?? (isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(AppRadius.pill)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            text,
            style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w700, color: fg),
          ),
        ],
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// LOADING INDICATOR — the one spinner style across the app.
/// ═══════════════════════════════════════════════════════════════════════════
class AppLoadingIndicator extends StatelessWidget {
  const AppLoadingIndicator({super.key, this.size = 36, this.color});

  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    return Center(
      child: SizedBox(
        width: size,
        height: size,
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(color ?? accent),
          strokeWidth: 3,
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// EMPTY STATE — the one "nothing here yet / couldn't load it" layout,
/// so no screen invents its own icon+title+retry-button combination.
/// ═══════════════════════════════════════════════════════════════════════════
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.actionText,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String? message;
  final String? actionText;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 72, color: colors.textMuted.withValues(alpha: 0.5)),
            const SizedBox(height: AppSpacing.lg),
            Text(title, style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary),
                textAlign: TextAlign.center),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(message!, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
                  textAlign: TextAlign.center),
            ],
            if (actionText != null && onAction != null) ...[
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(text: actionText!, onPressed: onAction, width: 200),
            ],
          ],
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// KPI TILE — one small stat card (icon + number + label), a real dashboard's
/// summary row — see features/mobile_requests for its first real use.
/// ═══════════════════════════════════════════════════════════════════════════
enum KpiTone { info, warning, success, neutral }

class KpiTile extends StatelessWidget {
  const KpiTile({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.tone = KpiTone.neutral,
  });

  final IconData icon;
  final String label;
  final String value;
  final KpiTone tone;

  (Color soft, Color onSoft) _colors(bool isDark) {
    switch (tone) {
      case KpiTone.info:
        return (isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
            isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft);
      case KpiTone.warning:
        return (isDark ? AppDarkColors.warningSoft : AppColors.warningSoft,
            isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft);
      case KpiTone.success:
        return (isDark ? AppDarkColors.successSoft : AppColors.successSoft,
            isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft);
      case KpiTone.neutral:
        return (isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
            isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final isDark = context.isDark;
    final (soft, onSoft) = _colors(isDark);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: colors.borderSubtle),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(color: soft, borderRadius: BorderRadius.circular(AppRadius.sm)),
            child: Icon(icon, size: 17, color: onSoft),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(value,
              style: AppTextStyles.headlineSmall.copyWith(
                color: colors.textPrimary,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
          const SizedBox(height: 2),
          Text(label,
              style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
              maxLines: 1,
              overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// SEGMENTED FILTER — a horizontally-scrolling row of pill filter chips, each
/// optionally carrying a small count badge. The one filter-row style every
/// list screen (mobile requests, and whatever list screen comes after it)
/// should compose from rather than hand-rolling its own chip row.
/// ═══════════════════════════════════════════════════════════════════════════
class SegmentedFilterOption<T> {
  final T value;
  final String label;
  final int? badge;
  const SegmentedFilterOption({required this.value, required this.label, this.badge});
}

class SegmentedFilter<T> extends StatelessWidget {
  const SegmentedFilter({
    super.key,
    required this.options,
    required this.value,
    required this.onChanged,
  });

  final List<SegmentedFilterOption<T>> options;
  final T value;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final onAccent = context.isDark ? AppDarkColors.accentContrast : AppColors.accentContrast;

    final isDark = context.isDark;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final option in options) ...[
            _FilterChip(
              label: option.label,
              badge: option.badge,
              selected: option.value == value,
              accent: accent,
              onAccent: onAccent,
              colors: colors,
              isDark: isDark,
              onTap: () => onChanged(option.value),
            ),
            const SizedBox(width: AppSpacing.xs),
          ],
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.badge,
    required this.selected,
    required this.accent,
    required this.onAccent,
    required this.colors,
    required this.isDark,
    required this.onTap,
  });

  final String label;
  final int? badge;
  final bool selected;
  final Color accent;
  final Color onAccent;
  final AppThemeColors colors;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final fg = selected ? onAccent : colors.textSecondary;
    final badgeBg = isDark ? AppDarkColors.surface3 : AppColors.surface3;
    return Material(
      color: selected ? accent : colors.surfaceAlt,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(label, style: AppTextStyles.labelMedium.copyWith(color: fg)),
              if (badge != null) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: selected ? onAccent.withValues(alpha: 0.22) : badgeBg,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                  child: Text('$badge',
                      style: AppTextStyles.caption.copyWith(color: fg, fontWeight: FontWeight.w700)),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// ═══════════════════════════════════════════════════════════════════════════
/// THEME SWITCH TILE — drop-in ListTile for the settings/profile screen.
/// ═══════════════════════════════════════════════════════════════════════════
class ThemeSwitchTile extends StatelessWidget {
  const ThemeSwitchTile({super.key});

  @override
  Widget build(BuildContext context) {
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = themeProvider.isDark;
    final colors = context.appColors;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: AnimatedSwitcher(
        duration: AppMotion.base,
        child: Icon(
          isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
          key: ValueKey(isDark),
          color: accent,
          size: AppIconSizes.medium,
        ),
      ),
      title: Text(
        isDark ? S.of(context)!.themeDarkMode : S.of(context)!.themeLightMode,
        style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary),
      ),
      trailing: Switch(
        value: isDark,
        onChanged: (_) => themeProvider.toggle(),
        activeThumbColor: accent,
      ),
      onTap: themeProvider.toggle,
    );
  }
}
