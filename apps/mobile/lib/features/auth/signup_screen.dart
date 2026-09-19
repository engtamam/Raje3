// Opening a new shop — phone + password + shop name, and nothing else.
//
// THE THREE-FIELD FORM IS NOT A SIMPLIFICATION — it is the REAL contract.
// See services/operations/app/core/signup.py's own module docstring: the
// commercial register, the address, the VAT number and even the trade type
// are all asked later from a screen where it is obvious why, and a shop now
// opens with an empty catalogue rather than a wrong guess. There is no email
// field here because the real `POST /api/v1/signup` route
// (services/operations/app/api/v1/signup.py::OpenShopIn) has never had one.
//
// SAME VISUAL LANGUAGE AS login_screen.dart, elevated card + gradient
// action — one product, not two screens styled independently.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/auth/verify_phone_screen.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  final _shopNameController = TextEditingController();
  bool _obscure = true;
  bool _submitting = false;

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
    _shopNameController.dispose();
    super.dispose();
  }

  Future<void> _submit(AuthProvider auth) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final phone = _phoneController.text.trim();
    final password = _passwordController.text;
    final shopName = _shopNameController.text.trim();

    final ok = await auth.openShop(phone: phone, password: password, shopName: shopName);
    if (!mounted) return;
    setState(() => _submitting = false);

    if (ok) {
      context.goNamed(RouteNames.home);
      return;
    }

    // «أكّد رقم جوالك أولاً» / «أدخل رمز التحقق الذي وصلك.» — the account (or
    // the number's proof) is one code away from complete, not a dead end.
    if (auth.errorReason == 'unverified' || auth.errorReason == 'otp_required') {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => VerifyPhoneScreen(phone: phone, password: password, shopName: shopName),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(
        backgroundColor: AppColors.surface0,
        elevation: 0,
        title: const Text('فتح محل جديد', style: AppTextStyles.headlineSmall),
      ),
      body: SafeArea(
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: Consumer<AuthProvider>(
            builder: (context, auth, _) => SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(height: AppSpacing.sm),
                  // THE WORDMARK, THE ONLY MARK — same source as the web console's
                  // apps/console/src/brand/Mark.tsx (`Wordmark`): no icon, no box,
                  // no glyph. راجِع, set in type, IS the logo. Cairo, weight 800,
                  // the brand accent colour, the kasra always written. One edit to
                  // the brand (the name, the accent colour) changes this and the
                  // website together, since both read from the same real sources.
                  const Text(
                    'راجِع',
                    style: TextStyle(
                      fontFamily: AppTextStyles.arabicFont,
                      fontWeight: FontWeight.w800,
                      fontSize: 40,
                      color: AppColors.accent,
                      height: 1,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  const Text('ثلاث خطوات فقط لفتح محلك', style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
                  const SizedBox(height: AppSpacing.xl),
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    decoration: AppCardDecorations.elevated,
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (auth.error != null &&
                              auth.errorReason != 'unverified' &&
                              auth.errorReason != 'otp_required') ...[
                            _buildErrorBanner(auth),
                          ],
                          TextFormField(
                            controller: _shopNameController,
                            textInputAction: TextInputAction.next,
                            style: AppTextStyles.bodyMedium,
                            decoration: AppInputDecorations.standard.copyWith(
                              labelText: 'اسم المحل',
                              prefixIcon: const Icon(Icons.storefront_outlined, color: AppColors.textMuted),
                            ),
                            validator: (v) => Validators.validateRequired(v, fieldName: 'اسم المحل'),
                          ),
                          const SizedBox(height: AppSpacing.md),
                          TextFormField(
                            controller: _phoneController,
                            keyboardType: TextInputType.phone,
                            textInputAction: TextInputAction.next,
                            textDirection: TextDirection.ltr,
                            textAlign: TextAlign.left,
                            style: AppTextStyles.bodyMedium.copyWith(fontFamily: AppTextStyles.englishFont),
                            decoration: AppInputDecorations.standard.copyWith(
                              labelText: 'رقم الجوال',
                              hintText: '05XXXXXXXX',
                              prefixIcon: const Icon(Icons.phone_android_rounded, color: AppColors.textMuted),
                            ),
                            validator: Validators.validatePhone,
                          ),
                          const SizedBox(height: AppSpacing.md),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscure,
                            textInputAction: TextInputAction.next,
                            style: AppTextStyles.bodyMedium.copyWith(fontFamily: AppTextStyles.englishFont),
                            decoration: AppInputDecorations.standard.copyWith(
                              labelText: 'كلمة المرور',
                              prefixIcon: const Icon(Icons.lock_outline_rounded, color: AppColors.textMuted),
                              suffixIcon: IconButton(
                                icon: Icon(_obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                                    color: AppColors.textMuted),
                                onPressed: () => setState(() => _obscure = !_obscure),
                              ),
                            ),
                            validator: Validators.validatePassword,
                          ),
                          const SizedBox(height: AppSpacing.md),
                          TextFormField(
                            controller: _confirmController,
                            obscureText: _obscure,
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submit(auth),
                            style: AppTextStyles.bodyMedium.copyWith(fontFamily: AppTextStyles.englishFont),
                            decoration: AppInputDecorations.standard.copyWith(
                              labelText: 'تأكيد كلمة المرور',
                              prefixIcon: const Icon(Icons.lock_outline_rounded, color: AppColors.textMuted),
                            ),
                            validator: (v) => Validators.validateConfirmPassword(v, _passwordController.text),
                          ),
                          const SizedBox(height: AppSpacing.lg),
                          _buildSubmitButton(auth),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  TextButton(
                    onPressed: auth.isLoading ? null : () => context.goNamed(RouteNames.login),
                    child: Text('لديك محل بالفعل؟ سجّل الدخول',
                        style: AppTextStyles.labelMedium.copyWith(color: AppColors.accent)),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildErrorBanner(AuthProvider auth) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
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
    );
  }

  Widget _buildSubmitButton(AuthProvider auth) {
    final busy = _submitting || auth.isLoading;
    return Container(
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
                      const Icon(Icons.storefront_rounded, color: AppColors.accentContrast, size: 20),
                      const SizedBox(width: AppSpacing.sm),
                      Text('فتح المحل',
                          style: AppTextStyles.button.copyWith(color: AppColors.accentContrast, fontSize: 16)),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}
