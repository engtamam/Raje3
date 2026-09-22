// Signing back into an existing shop — phone + password, and nothing else.
//
// WIRED TO THE REAL DOOR: POST /api/v1/signup/signin
// (services/operations/app/api/v1/signup.py -> core/signup.py::sign_in),
// which resolves the shop from the phone number and forwards to identity's
// own membership mint. No email field exists on this route, so none exists
// here either.
//
// VISUAL CRAFT COPIED FROM THE REFERENCE PROJECT'S OWN login_screen.dart
// (staggered entry animation, shake-on-error, elevated card, gradient
// submit button with a loading state) — this session's own standing rule:
// our brand tokens (AppColors/AppTextStyles/AppRadius), their layout craft.
// The OTP-mode toggle in their version is NOT ported here: this door's real
// OTP path is a REFUSAL-triggered detour (see VerifyPhoneScreen), never a
// mode the customer picks up front — porting a toggle nothing on our side
// answers would be UI for a door that never opens.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/auth/verify_phone_screen.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _passwordFocus = FocusNode();
  bool _obscure = true;
  bool _submitting = false;

  late final AnimationController _entryController;
  late final AnimationController _shakeController;
  late final CurvedAnimation _logoAnim;
  late final CurvedAnimation _titleAnim;
  late final CurvedAnimation _formAnim;
  late final CurvedAnimation _actionsAnim;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))
      ..forward();
    _shakeController = AnimationController(vsync: this, duration: const Duration(milliseconds: 500));
    _logoAnim = CurvedAnimation(
        parent: _entryController, curve: const Interval(0.0, 0.4, curve: Curves.easeOutBack));
    _titleAnim = CurvedAnimation(parent: _entryController, curve: const Interval(0.15, 0.5, curve: Curves.easeOut));
    _formAnim = CurvedAnimation(parent: _entryController, curve: const Interval(0.3, 0.7, curve: Curves.easeOut));
    _actionsAnim = CurvedAnimation(parent: _entryController, curve: const Interval(0.5, 1.0, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    _passwordFocus.dispose();
    _entryController.dispose();
    _shakeController.dispose();
    super.dispose();
  }

  Future<void> _submit(AuthProvider auth) async {
    if (!_formKey.currentState!.validate()) {
      _shakeController.forward(from: 0.0);
      return;
    }
    setState(() => _submitting = true);

    final phone = _phoneController.text.trim();
    final password = _passwordController.text;
    final ok = await auth.login(phone, password);
    if (!mounted) return;
    setState(() => _submitting = false);

    if (ok) {
      // Router's own redirect takes over once AuthState flips to authenticated
      // — see app_router.dart's `_globalRedirect`. No manual navigation here.
      return;
    }
    _shakeController.forward(from: 0.0);

    // «أكّد رقم جوالك أولاً» — a step, not a wall. See AuthProvider's own
    // docstring on `errorReason`.
    if (auth.errorReason == 'unverified') {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => VerifyPhoneScreen(phone: phone, password: password)),
      );
    }
  }

  double _shakeWave(double t) =>
      (t < 0.25) ? 1.0 : (t < 0.5) ? -1.0 : (t < 0.75) ? 0.6 : -0.3;

  @override
  Widget build(BuildContext context) {
    return KbAnchor(
      id: 'auth.login',
      child: Scaffold(
      backgroundColor: AppColors.surface0,
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: SafeArea(
          child: Consumer<AuthProvider>(
            builder: (context, auth, _) => Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                child: Form(
                  key: _formKey,
                  child: AnimatedBuilder(
                    animation: _entryController,
                    builder: (context, _) => Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(height: AppSpacing.xxl),
                        _buildLogo(),
                        const SizedBox(height: AppSpacing.xl),
                        _buildTitle(),
                        const SizedBox(height: AppSpacing.xxl),
                        _buildForm(auth),
                        const SizedBox(height: AppSpacing.lg),
                        _buildActions(),
                        const SizedBox(height: AppSpacing.xl),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
      ),
    );
  }

  // THE WORDMARK, THE ONLY MARK — same source as the web console's own
  // apps/console/src/brand/Mark.tsx (`Wordmark`): no icon, no box, no glyph.
  // The owner's own instruction (2026-09-16) removed the drawn icon
  // everywhere in the product for exactly this: راجِع, set in type, IS the
  // logo. Cairo, weight 800, the brand accent colour, the kasra always
  // written (راجَع/راجِع are different words — see Mark.tsx's own note).
  // One edit to the brand (the name, the accent colour) changes this and
  // the website together, since both read from the same real sources.
  Widget _buildLogo() {
    return Opacity(
      opacity: _logoAnim.value.clamp(0.0, 1.0),
      child: Transform.scale(
        scale: 0.85 + (_logoAnim.value * 0.15),
        child: Text(
          S.of(context)!.appName,
          style: const TextStyle(
            fontFamily: AppTextStyles.arabicFont,
            fontWeight: FontWeight.w800,
            fontSize: 52,
            color: AppColors.accent,
            height: 1,
          ),
        ),
      ),
    );
  }

  Widget _buildTitle() {
    return Opacity(
      opacity: _titleAnim.value,
      child: Transform.translate(
        offset: Offset(0, 20 * (1 - _titleAnim.value)),
        child: Text(S.of(context)!.authLoginSubtitle, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
      ),
    );
  }

  Widget _buildForm(AuthProvider auth) {
    return Opacity(
      opacity: _formAnim.value,
      child: Transform.translate(
        offset: Offset(0, 30 * (1 - _formAnim.value)),
        child: AnimatedBuilder(
          animation: _shakeController,
          builder: (context, child) {
            final shakeOffset = _shakeController.isAnimating
                ? 10.0 * (1 - _shakeController.value) * _shakeWave(_shakeController.value)
                : 0.0;
            return Transform.translate(offset: Offset(shakeOffset, 0), child: child);
          },
          child: Container(
            padding: const EdgeInsets.all(AppSpacing.lg),
            decoration: AppCardDecorations.elevated,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildErrorBanner(auth),
                _buildPhoneField(),
                const SizedBox(height: AppSpacing.md),
                _buildPasswordField(auth),
                const SizedBox(height: AppSpacing.lg),
                _buildSubmitButton(auth),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildErrorBanner(AuthProvider auth) {
    if (auth.error == null || auth.errorReason == 'unverified') return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: AnimatedSize(
        duration: AppMotion.base,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.danger.withValues(alpha: 0.08),
            borderRadius: AppRadius.standardRadius,
            border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 20),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(auth.error!,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger, fontWeight: FontWeight.w500)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhoneField() {
    return KbAnchor(
      id: 'auth.login.phone_field',
      child: TextFormField(
      controller: _phoneController,
      keyboardType: TextInputType.phone,
      textInputAction: TextInputAction.next,
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.left,
      inputFormatters: [
        FilteringTextInputFormatter.allow(RegExp(r'[\d+ ]')),
        LengthLimitingTextInputFormatter(15),
      ],
      onFieldSubmitted: (_) => _passwordFocus.requestFocus(),
      validator: (v) => Validators.validatePhone(v)?.text(context),
      style: AppTextStyles.bodyMedium.copyWith(fontFamily: AppTextStyles.englishFont, letterSpacing: 1.2),
      decoration: AppInputDecorations.standard.copyWith(
        labelText: S.of(context)!.authPhoneLabel,
        hintText: '05XXXXXXXX',
        prefixIcon: const Icon(Icons.phone_android_rounded, color: AppColors.textMuted),
      ),
      ),
    );
  }

  Widget _buildPasswordField(AuthProvider auth) {
    return KbAnchor(
      id: 'auth.login.password_field',
      child: TextFormField(
      controller: _passwordController,
      focusNode: _passwordFocus,
      obscureText: _obscure,
      textInputAction: TextInputAction.done,
      onFieldSubmitted: (_) => _submit(auth),
      validator: (v) => Validators.validateRequired(v, fieldName: S.of(context)!.authPasswordLabel)?.text(context),
      style: AppTextStyles.bodyMedium.copyWith(fontFamily: AppTextStyles.englishFont),
      decoration: AppInputDecorations.standard.copyWith(
        labelText: S.of(context)!.authPasswordLabel,
        prefixIcon: const Icon(Icons.lock_outline_rounded, color: AppColors.textMuted),
        suffixIcon: IconButton(
          icon: Icon(_obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
              color: AppColors.textMuted),
          onPressed: () => setState(() => _obscure = !_obscure),
        ),
      ),
      ),
    );
  }

  Widget _buildSubmitButton(AuthProvider auth) {
    final busy = _submitting || auth.isLoading;
    return KbAnchor(
      id: 'auth.login.submit',
      child: AnimatedContainer(
      duration: AppMotion.base,
      height: 52,
      decoration: BoxDecoration(
        gradient: busy
            ? LinearGradient(colors: [
                AppColors.accent.withValues(alpha: 0.5),
                AppColors.accentHover.withValues(alpha: 0.5),
              ])
            : appPrimaryGradient,
        borderRadius: AppRadius.standardRadius,
        boxShadow: busy
            ? []
            : [BoxShadow(color: AppColors.accent.withValues(alpha: 0.3), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: busy ? null : () => _submit(auth),
          borderRadius: AppRadius.standardRadius,
          child: Center(
            child: busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                        strokeWidth: 2.5, valueColor: AlwaysStoppedAnimation<Color>(AppColors.accentContrast)),
                  )
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.login_rounded, color: AppColors.accentContrast, size: 20),
                      const SizedBox(width: AppSpacing.sm),
                      Text(S.of(context)!.login,
                          style: AppTextStyles.button.copyWith(color: AppColors.accentContrast, fontSize: 16)),
                    ],
                  ),
          ),
        ),
      ),
      ),
    );
  }

  Widget _buildActions() {
    return Opacity(
      opacity: _actionsAnim.value,
      child: Transform.translate(
        offset: Offset(0, 20 * (1 - _actionsAnim.value)),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(child: Container(height: 1, color: AppColors.borderSubtle)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  child: Text(S.of(context)!.authNoShopYetLabel, style: AppTextStyles.caption),
                ),
                Expanded(child: Container(height: 1, color: AppColors.borderSubtle)),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'auth.login.open_shop_cta',
              child: SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton.icon(
                onPressed: () => context.pushNamed(RouteNames.signup),
                icon: const Icon(Icons.storefront_outlined, size: 20),
                label: Text(S.of(context)!.authOpenNewShopCta,
                    style: AppTextStyles.button.copyWith(color: AppColors.accent, fontSize: 15)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.accent,
                  side: const BorderSide(color: AppColors.accent, width: 1.5),
                  shape: RoundedRectangleBorder(borderRadius: AppRadius.standardRadius),
                ),
              ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
