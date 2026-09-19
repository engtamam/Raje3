// Signing back into an existing shop — phone + password, and nothing else.
//
// WIRED TO THE REAL DOOR: POST /api/v1/signup/signin
// (services/operations/app/api/v1/signup.py -> core/signup.py::sign_in),
// which resolves the shop from the phone number and forwards to identity's
// own membership mint. No email field exists on this route, so none exists
// here either.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/auth/verify_phone_screen.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit(AuthProvider auth) async {
    if (!_formKey.currentState!.validate()) return;

    final phone = _phoneController.text.trim();
    final password = _passwordController.text;

    final ok = await auth.login(phone, password);
    if (!mounted) return;

    if (ok) {
      // Router's own redirect takes over from here once AuthState flips to
      // authenticated — see app_router.dart's `_globalRedirect`. No manual
      // navigation needed for the success path.
      return;
    }

    // «أكّد رقم جوالك أولاً» — a step, not a wall. See AuthProvider's own
    // docstring on `errorReason`.
    if (auth.errorReason == 'unverified') {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => VerifyPhoneScreen(phone: phone, password: password),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        child: Consumer<AuthProvider>(
          builder: (context, auth, _) => Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'راجِع',
                      style: AppTextStyles.headlineMedium,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    TextFormField(
                      controller: _phoneController,
                      keyboardType: TextInputType.phone,
                      textInputAction: TextInputAction.next,
                      textDirection: TextDirection.ltr,
                      decoration: const InputDecoration(
                        labelText: 'رقم الجوال',
                        hintText: '05xxxxxxxx',
                        border: OutlineInputBorder(),
                      ),
                      validator: Validators.validatePhone,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscure,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _submit(auth),
                      decoration: InputDecoration(
                        labelText: 'كلمة المرور',
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                      ),
                      validator: (v) => Validators.validateRequired(v, fieldName: 'كلمة المرور'),
                    ),
                    if (auth.error != null && auth.errorReason != 'unverified') ...[
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        auth.error!,
                        style: const TextStyle(color: AppColors.danger),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: AppSpacing.lg),
                    ElevatedButton(
                      onPressed: auth.isLoading ? null : () => _submit(auth),
                      child: Text(auth.isLoading ? 'جارٍ الدخول...' : 'تسجيل الدخول'),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    TextButton(
                      onPressed: auth.isLoading
                          ? null
                          : () => context.pushNamed(RouteNames.signup),
                      child: const Text('ليس لديك محل؟ افتح محلاً جديداً'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
