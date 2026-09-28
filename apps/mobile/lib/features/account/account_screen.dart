import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/constants/app_constants.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/utils/device_info.dart';
import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «حسابي» — a GROUPED LIST, never the console's own top tab strip. Researched deliberately
/// (2026-09-22, real 2026 mobile-UX sources): a horizontal tab bar is the wrong primitive for a
/// settings surface this deep on a phone-width screen — the accepted pattern (iOS Settings,
/// Android's own Settings app, and every mobile-native guide surveyed for this pass) is a single
/// scrollable list of grouped rows, most-used/lowest-risk at the top, destructive/rare actions
/// pushed to the bottom. Per [[mobile-app-brand-vs-design-craft]]'s own reconfirmed rule: this
/// layout is NOT copied from apps/console/src/screens/Account.tsx — only the backend doors below
/// (`/account/me/name`) are shared with it.
///
/// SCOPED TO WHAT IS REAL TODAY. Console's «حسابي» also carries منشأتي/الفريق/الفوترة/محفظتي/
/// الفواتير spread across a top tab strip — reorganised here per [[no-placeholder-drift]]: every
/// row below opens a real, data-backed screen, never a placeholder. «الفوترة» is ONE consolidated
/// billing screen (subscription status + usage + renewal preview + invoices, never console's own
/// three-way split — see `billing_screen.dart`'s own header note); محفظتي is deliberately absent
/// (dead feature, hidden in console too, [[base-plan-is-dead-code]]-adjacent owner call).
///
/// NO AI-ASSISTANT ROW HERE, DELIBERATELY (owner's own call, 2026-09-22) — it briefly showed a
/// status-only row here (no toggle: this app has no per-shop on/off switch at all, see
/// [[task-mobile-ai-assistant]]), same reasoning every OTHER app already follows: an app's status
/// belongs on its OWN screen, reached from «تطبيقاتي», never bundled into «حسابي» because that
/// screen does not exist yet. Removed rather than kept as a stopgap — it moves to its own screen
/// the same day «تطبيقاتي» is actually built, not before.
/// The legal documents are served by THE SAME SERVER the app already talks to, under the
/// CONSOLE'S OWN mount path — `/app/` (apps/console/vite.config.ts's own `base`), not the bare
/// domain root: `{domain}/legal/terms` 200s too, but only because "/" itself is the marketing
/// landing page's own catch-all, not the console's legal route — found live in this exact testing
/// pass (a first fix landed on `/legal/terms` and opened the landing page, not the document).
/// `{baseUrl}/app/legal/{slug}` is apps/console/src/legal/url.ts's own `legalUrl()` for the exact
/// same server this app already calls via `ApiConstants.baseUrl` — never a second, hardcoded
/// marketing domain (an earlier `app.raje3.com.sa` guess failed to even resolve).
String _legalUrl(String slug) => '${ApiConstants.baseUrl}/app/legal/$slug';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final auth = context.watch<AuthProvider>();
    final user = auth.user;
    final dark = context.isDark;

    return KbAnchor(
      id: 'account',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xxl),
            children: [
              Text(s.accountPageTitle, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              _Reveal(
                index: 0,
                child: _IdentityCard(
                  name: user?.ownerName,
                  phone: user?.phone ?? '',
                  dark: dark,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _SectionLabel(text: s.accountShopSectionTitle),
              const SizedBox(height: AppSpacing.sm),
              _Reveal(
                index: 1,
                child: KbAnchor(
                  id: 'account.shop_row',
                  child: _Row(
                    icon: Icons.storefront_rounded,
                    tone: AppTone.success,
                    label: s.accountShopIdentityRow,
                    onTap: () => context.push(RouteNames.shopIdentityPath),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _SectionLabel(text: s.accountBillingSectionTitle),
              const SizedBox(height: AppSpacing.sm),
              _Reveal(
                index: 2,
                child: KbAnchor(
                  id: 'account.billing_row',
                  child: _Row(
                    icon: Icons.receipt_long_rounded,
                    tone: AppTone.accent,
                    label: s.accountBillingRow,
                    onTap: () => context.push(RouteNames.billingPath),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _SectionLabel(text: s.accountLegalSectionTitle),
              const SizedBox(height: AppSpacing.sm),
              _Reveal(
                index: 3,
                child: KbAnchor(
                  id: 'account.terms_row',
                  child: _Row(
                    icon: Icons.description_rounded,
                    tone: AppTone.info,
                    label: s.accountTermsRow,
                    onTap: () => openUrl(_legalUrl('terms'), context),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              _Reveal(
                index: 4,
                child: KbAnchor(
                  id: 'account.privacy_row',
                  child: _Row(
                    icon: Icons.privacy_tip_rounded,
                    tone: AppTone.info,
                    label: s.accountPrivacyRow,
                    onTap: () => openUrl(_legalUrl('privacy-policy'), context),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _SectionLabel(text: s.accountSecuritySectionTitle),
              const SizedBox(height: AppSpacing.sm),
              CapabilityGate(
                requires: const ['identity.change_password'],
                child: _Reveal(
                  index: 5,
                  child: KbAnchor(
                    id: 'account.change_password_row',
                    child: _Row(
                      icon: Icons.lock_rounded,
                      tone: AppTone.warning,
                      label: s.accountChangePasswordRow,
                      onTap: () => _openChangePassword(context),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _Reveal(
                index: 6,
                child: KbAnchor(
                  id: 'account.sign_out_row',
                  child: _Row(
                    icon: Icons.logout_rounded,
                    tone: AppTone.danger,
                    label: s.accountSignOutRow,
                    onTap: () => _confirmSignOut(context),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              const KbAnchor(id: 'account.version_footer', child: _VersionFooter()),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmSignOut(BuildContext context) async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.accountSignOutConfirmTitle),
        content: Text(s.accountSignOutConfirmBody),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.accountSignOutCancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(s.accountSignOutConfirm, style: const TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    await context.read<AuthProvider>().logout();
    if (context.mounted) context.go(RouteNames.loginPath);
  }

  void _openChangePassword(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _ChangePasswordSheet(),
    );
  }
}

class _VersionFooter extends StatelessWidget {
  const _VersionFooter();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: FutureBuilder<String>(
        future: DeviceInfoHelper.getFullVersion(),
        builder: (context, snapshot) {
          final version = snapshot.data;
          if (version == null) return const SizedBox.shrink();
          return Text(
            '${AppConstants.appNameAr} $version',
            style: TextStyle(fontSize: 12, color: context.isDark ? AppDarkColors.textMuted : AppColors.textMuted),
          );
        },
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel({required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
      child: Text(
        text,
        style: AppTextStyles.labelMedium.copyWith(
          color: AppColors.textMuted,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}

/// The identity header — same gradient-card language [HomeScreen]'s own hero and
/// [LoyaltyBalanceCard] already established for this app, reused here for consistency of
/// PREMIUM CRAFT, never for literal content (this card shows nothing either of those does).
class _IdentityCard extends StatefulWidget {
  final String? name;
  final String phone;
  final bool dark;
  const _IdentityCard({required this.name, required this.phone, required this.dark});

  @override
  State<_IdentityCard> createState() => _IdentityCardState();
}

class _IdentityCardState extends State<_IdentityCard> {
  bool _editing = false;
  bool _saving = false;
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final s = S.of(context)!;
    final value = _controller.text.trim();
    if (value.isEmpty) return;
    setState(() => _saving = true);
    final ok = await context.read<AuthProvider>().updateOwnerName(value);
    if (!mounted) return;
    setState(() {
      _saving = false;
      if (ok) _editing = false;
    });
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.accountSaveNameFailed)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final gradient = primaryGradient(dark: widget.dark);
    final displayName = widget.name?.isNotEmpty == true ? widget.name! : widget.phone;

    return KbAnchor(
      id: 'account.identity_card',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: Colors.white,
      child: Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: AppRadius.cardRadius,
        boxShadow: widget.dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Stack(
        children: [
          Positioned.directional(
            textDirection: Directionality.of(context),
            top: -28,
            end: -24,
            child: Container(
              width: 110,
              height: 110,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.08),
              ),
            ),
          ),
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.person_rounded, color: Colors.white, size: 28),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: _editing
                    ? Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _controller,
                              autofocus: true,
                              enabled: !_saving,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                              cursorColor: Colors.white,
                              decoration: InputDecoration(
                                isDense: true,
                                hintText: s.accountNameFieldHint,
                                hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.6)),
                                enabledBorder: const UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white54)),
                                focusedBorder: const UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white)),
                              ),
                              onSubmitted: (_) => _save(),
                            ),
                          ),
                          if (_saving)
                            const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          else
                            IconButton(
                              icon: const Icon(Icons.check_rounded, color: Colors.white),
                              onPressed: _save,
                            ),
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  displayName,
                                  overflow: TextOverflow.ellipsis,
                                  style: AppTextStyles.headlineSmall
                                      .copyWith(color: Colors.white, fontWeight: FontWeight.w800),
                                ),
                              ),
                              IconButton(
                                icon: Icon(Icons.edit_rounded,
                                    color: Colors.white.withValues(alpha: 0.85), size: 18),
                                onPressed: () {
                                  _controller.text = widget.name ?? '';
                                  setState(() => _editing = true);
                                },
                              ),
                            ],
                          ),
                          // ONLY WHEN IT SAYS SOMETHING THE NAME ABOVE DID NOT ALREADY SAY — a
                          // shop with no name set falls back to showing the phone as the name
                          // itself (`displayName`), and repeating it here read as the same
                          // number printed twice (found live, this exact screen's first render).
                          if (widget.phone.isNotEmpty && displayName != widget.phone)
                            Text(
                              widget.phone,
                              style: AppTextStyles.bodyMedium.copyWith(
                                color: Colors.white.withValues(alpha: 0.85),
                                fontFamily: AppTextStyles.englishFont,
                              ),
                            ),
                        ],
                      ),
              ),
            ],
          ),
        ],
      ),
      ),
      ),
    );
  }
}

/// A gentle staggered entrance — the SAME fade+rise [HomeScreen]'s own `_Reveal` established for
/// this app (duplicated rather than imported: one small private widget in each of two files beats
/// a shared abstraction two call sites don't yet justify). Pure polish — every row below is fully
/// correct with this removed entirely.
class _Reveal extends StatelessWidget {
  final int index;
  final Widget child;
  const _Reveal({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    final delay = index.clamp(0, 8) * 60;
    return TweenAnimationBuilder<double>(
      key: ValueKey('account-reveal-$index'),
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 320 + delay),
      curve: Curves.easeOutCubic,
      builder: (context, t, _) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 12), child: child),
      ),
    );
  }
}

/// EVERY ROW WEARS ITS OWN TONE, not a flat neutral card with a colour dot on the icon — a soft
/// gradient wash (tone at low opacity, never solid — this is a calm settings list, not a hero) and
/// a two-stop gradient icon chip, the same "size/colour follow the entity" discipline
/// [LoyaltyBalanceCard]/[HomeScreen]'s own bento tiles already established for this app. Found
/// live (the owner's own words): the flat white-card version read as "بدائية" next to the rest of
/// the app's own premium visual language.
class _Row extends StatelessWidget {
  final IconData icon;
  final AppTone tone;
  final String label;
  final VoidCallback? onTap;

  const _Row({
    required this.icon,
    required this.tone,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = ToneColors.of(context, tone);
    final dark = context.isDark;
    final chevronColor = dark ? AppDarkColors.textMuted : AppColors.textMuted;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

    return RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: colors.solid,
      child: Material(
      color: Colors.transparent,
      borderRadius: AppRadius.cardRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.cardRadius,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: AppRadius.cardRadius,
            border: Border.all(color: border),
            gradient: LinearGradient(
              begin: AlignmentDirectional.centerStart,
              end: AlignmentDirectional.centerEnd,
              colors: [colors.soft.withValues(alpha: dark ? 0.22 : 0.55), surface],
            ),
            boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppRadius.md),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [colors.solid, colors.solid.withValues(alpha: 0.75)],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: colors.solid.withValues(alpha: 0.35),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Icon(icon, color: Colors.white, size: 20),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(label,
                      style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                ),
                if (onTap != null)
                  Icon(
                    Directionality.of(context) == TextDirection.rtl
                        ? Icons.chevron_left_rounded
                        : Icons.chevron_right_rounded,
                    color: chevronColor,
                    size: 20,
                  ),
              ],
            ),
          ),
        ),
      ),
      ),
    );
  }
}

/// AUTHENTICATED CHANGE, NOT A RESET FLOW — this is a signed-in owner/operator changing his own
/// password from inside a real session (current + new + confirm), never the unauthenticated
/// "forgot password" screen. Same three-field shape apps/console/src/screens/Account.tsx's own
/// `ChangePasswordCard` already established for this exact real action
/// (`identity.change_password`), never copied visually — only the backend door is shared.
class _ChangePasswordSheet extends StatefulWidget {
  const _ChangePasswordSheet();

  @override
  State<_ChangePasswordSheet> createState() => _ChangePasswordSheetState();
}

class _ChangePasswordSheetState extends State<_ChangePasswordSheet> {
  final _formKey = GlobalKey<FormState>();
  final _oldController = TextEditingController();
  final _newController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _obscureOld = true;
  bool _obscureNew = true;
  bool _saving = false;
  String? _error;
  bool _done = false;

  @override
  void dispose() {
    _oldController.dispose();
    _newController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
      _done = false;
    });
    final result = await context.read<AuthProvider>().changePassword(
          oldPassword: _oldController.text,
          newPassword: _newController.text,
        );
    if (!mounted) return;
    setState(() {
      _saving = false;
      if (result.ok) {
        _done = true;
        _oldController.clear();
        _newController.clear();
        _confirmController.clear();
      } else {
        _error = result.message.isNotEmpty ? result.message : s.accountChangePasswordFailed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.accountChangePasswordRow, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'account.change_password.current_field',
                child: TextFormField(
                  controller: _oldController,
                  obscureText: _obscureOld,
                  textDirection: TextDirection.ltr,
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: s.accountCurrentPasswordLabel,
                    suffixIcon: IconButton(
                      icon: Icon(_obscureOld ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                          size: 20),
                      onPressed: () => setState(() => _obscureOld = !_obscureOld),
                    ),
                  ),
                  validator: (v) => Validators.validateRequired(v)?.text(context),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'account.change_password.new_field',
                child: TextFormField(
                  controller: _newController,
                  obscureText: _obscureNew,
                  textDirection: TextDirection.ltr,
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: s.accountNewPasswordLabel,
                    suffixIcon: IconButton(
                      icon: Icon(_obscureNew ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                          size: 20),
                      onPressed: () => setState(() => _obscureNew = !_obscureNew),
                    ),
                  ),
                  validator: (v) => Validators.validatePassword(v)?.text(context),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'account.change_password.confirm_field',
                child: TextFormField(
                  controller: _confirmController,
                  obscureText: _obscureNew,
                  textDirection: TextDirection.ltr,
                  decoration: InputDecoration(isDense: true, hintText: s.accountConfirmNewPasswordLabel),
                  validator: (v) =>
                      Validators.validateConfirmPassword(v, _newController.text)?.text(context),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
              ],
              if (_done) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(s.accountChangePasswordSuccess,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.success)),
              ],
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'account.change_password.submit',
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _saving ? null : _submit,
                    child: _saving
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(s.save),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
