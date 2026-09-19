import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// Helper class for showing themed snackbar notifications.
///
/// Uses the app's color system for consistent visual feedback.
/// All snackbars use floating behavior with rounded corners,
/// matching the app's design system.
///
/// Usage:
/// ```dart
/// SnackbarHelper.showSuccess(context, 'تم الحفظ بنجاح');
/// SnackbarHelper.showError(context, 'حدث خطأ في الاتصال');
/// SnackbarHelper.showWarning(context, 'يرجى إكمال جميع الحقول');
/// SnackbarHelper.showInfo(context, 'جاري التحميل...');
/// ```
class SnackbarHelper {
  SnackbarHelper._(); // Prevent instantiation

  /// Default duration for snackbar display.
  static const Duration _defaultDuration = Duration(seconds: 3);

  /// Duration for longer messages.
  static const Duration _longDuration = Duration(seconds: 5);

  // ─────────────────────────────────────────────────────────────────────────
  // SUCCESS
  // ─────────────────────────────────────────────────────────────────────────

  /// Show a success snackbar with a green background.
  ///
  /// Use for: successful operations (save, delete, update, etc.)
  static void showSuccess(
    BuildContext context,
    String message, {
    Duration? duration,
    SnackBarAction? action,
  }) {
    _show(
      context,
      message: message,
      backgroundColor: AppColors.success,
      icon: Icons.check_circle_rounded,
      duration: duration,
      action: action,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR
  // ─────────────────────────────────────────────────────────────────────────

  /// Show an error snackbar with a red background.
  ///
  /// Use for: failed operations, API errors, validation failures.
  static void showError(
    BuildContext context,
    String message, {
    Duration? duration,
    SnackBarAction? action,
  }) {
    _show(
      context,
      message: message,
      backgroundColor: AppColors.error,
      icon: Icons.error_rounded,
      duration: duration ?? _longDuration,
      action: action,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // WARNING
  // ─────────────────────────────────────────────────────────────────────────

  /// Show a warning snackbar with an orange background.
  ///
  /// Use for: incomplete data, approaching limits, soft errors.
  static void showWarning(
    BuildContext context,
    String message, {
    Duration? duration,
    SnackBarAction? action,
  }) {
    _show(
      context,
      message: message,
      backgroundColor: AppColors.warning,
      icon: Icons.warning_rounded,
      duration: duration,
      action: action,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INFO
  // ─────────────────────────────────────────────────────────────────────────

  /// Show an info snackbar with a blue background.
  ///
  /// Use for: informational messages, hints, loading states.
  static void showInfo(
    BuildContext context,
    String message, {
    Duration? duration,
    SnackBarAction? action,
  }) {
    _show(
      context,
      message: message,
      backgroundColor: AppColors.info,
      icon: Icons.info_rounded,
      duration: duration,
      action: action,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CUSTOM
  // ─────────────────────────────────────────────────────────────────────────

  /// Show a custom-colored snackbar.
  ///
  /// Use for: special cases that don't fit the standard categories.
  static void showCustom(
    BuildContext context, {
    required String message,
    required Color backgroundColor,
    IconData? icon,
    Duration? duration,
    SnackBarAction? action,
  }) {
    _show(
      context,
      message: message,
      backgroundColor: backgroundColor,
      icon: icon,
      duration: duration,
      action: action,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOADING
  // ─────────────────────────────────────────────────────────────────────────

  /// Show a persistent loading snackbar.
  ///
  /// Returns the [ScaffoldFeatureController] so the caller can dismiss it:
  /// ```dart
  /// final controller = SnackbarHelper.showLoading(context, 'جاري الحفظ...');
  /// await saveData();
  /// controller.close();
  /// ```
  static ScaffoldFeatureController<SnackBar, SnackBarClosedReason> showLoading(
    BuildContext context,
    String message,
  ) {
    // Dismiss any existing snackbar
    ScaffoldMessenger.of(context).hideCurrentSnackBar();

    final snackBar = SnackBar(
      content: Row(
        children: [
          const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.white),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.bodySmall.copyWith(
                color: AppColors.white,
              ),
            ),
          ),
        ],
      ),
      backgroundColor: AppColors.primary,
      behavior: SnackBarBehavior.floating,
      duration: const Duration(minutes: 5), // Long duration, meant to be dismissed manually
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.standardRadius,
      ),
      margin: const EdgeInsets.all(AppSpacing.md),
    );

    return ScaffoldMessenger.of(context).showSnackBar(snackBar);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // DISMISS
  // ─────────────────────────────────────────────────────────────────────────

  /// Dismiss the currently displayed snackbar.
  static void dismiss(BuildContext context) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
  }

  /// Dismiss all snackbars.
  static void dismissAll(BuildContext context) {
    ScaffoldMessenger.of(context).clearSnackBars();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL
  // ─────────────────────────────────────────────────────────────────────────

  /// Internal method to create and show a snackbar.
  static void _show(
    BuildContext context, {
    required String message,
    required Color backgroundColor,
    IconData? icon,
    Duration? duration,
    SnackBarAction? action,
  }) {
    // Dismiss any existing snackbar to prevent stacking
    ScaffoldMessenger.of(context).hideCurrentSnackBar();

    final snackBar = SnackBar(
      content: Row(
        children: [
          if (icon != null) ...[
            Icon(
              icon,
              color: AppColors.white,
              size: AppIconSizes.medium,
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.bodySmall.copyWith(
                color: AppColors.white,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
      backgroundColor: backgroundColor,
      behavior: SnackBarBehavior.floating,
      duration: duration ?? _defaultDuration,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.standardRadius,
      ),
      margin: const EdgeInsets.all(AppSpacing.md),
      action: action ??
          SnackBarAction(
            label: 'إغلاق',
            textColor: AppColors.white.withValues(alpha: 0.9),
            onPressed: () {
              ScaffoldMessenger.of(context).hideCurrentSnackBar();
            },
          ),
    );

    ScaffoldMessenger.of(context).showSnackBar(snackBar);
  }
}
