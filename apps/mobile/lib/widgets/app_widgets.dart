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
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide.none,
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
