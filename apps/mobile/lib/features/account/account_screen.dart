import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

/// "حسابي" — a fixed bottom-bar tab. Shows the real account fields this app
/// actually has (shop name, phone — see UserModel's own doc comment on why
/// there is no separate profile object), the theme switch, and logout.
///
/// NOT SHOWN HERE: an employee name or a shop logo. Neither exists as a real
/// field anywhere in this app's models or its signup/signin doors today —
/// [UserModel.fullName] holds the SHOP's name, not a staff member's, and no
/// door returns a logo asset. Adding either to this screen (or to the home
/// launcher's top bar) needs a real backend field first; faking one would be
/// exactly the kind of placeholder drift this codebase's own conventions
/// refuse.
class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  Future<void> _confirmLogout(BuildContext context) async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(s.accountLogoutConfirmTitle),
        content: Text(s.accountLogoutConfirmMessage),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(s.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(s.accountLogoutAction),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await context.read<AuthProvider>().logout();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final isDark = context.isDark;
    final surface0 = isDark ? AppDarkColors.surface0 : AppColors.surface0;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final user = context.watch<AuthProvider>().user;

    return Scaffold(
      backgroundColor: surface0,
      appBar: AppBar(title: Text(s.accountScreenTitle)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          AppCard(
            child: Row(
              children: [
                CircleAvatar(
                  radius: 28,
                  backgroundColor: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
                  child: Icon(Icons.storefront_rounded, color: accent, size: 28),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.fullName ?? '—',
                        style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        '${s.accountPhoneLabel}: ${user?.phone ?? '—'}',
                        style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          const AppCard(
            padding: 0,
            child: ThemeSwitchTile(),
          ),
          const SizedBox(height: AppSpacing.lg),
          SecondaryButton(
            text: s.accountLogoutAction,
            icon: Icons.logout_rounded,
            onPressed: () => _confirmLogout(context),
          ),
        ],
      ),
    );
  }
}
