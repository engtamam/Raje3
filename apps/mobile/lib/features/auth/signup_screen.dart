// Opening a new shop — phone + password + shop name, and nothing else.
//
// THE THREE-FIELD FORM IS NOT A SIMPLIFICATION — it is the REAL contract.
// See services/operations/app/core/signup.py's own module docstring: the
// commercial register, the address, the VAT number and even the trade type
// are all asked later from a screen where it is obvious why, and a shop now
// opens with an empty catalogue rather than a wrong guess. There is no email
// field here because the real `POST /api/v1/signup` route
// (services/operations/app/api/v1/signup.py::OpenShopIn) has never had one.
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

    final phone = _phoneController.text.trim();
    final password = _passwordController.text;
    final shopName = _shopNameController.text.trim();

    final ok = await auth.openShop(
      phone: phone,
      password: password,
      shopName: shopName,
    );
    if (!mounted) return;

    if (ok) {
      context.goNamed(RouteNames.home);
      return;
    }

    // «أكّد رقم جوالك أولاً» / «أدخل رمز التحقق الذي وصلك.» — the account (or
    // the number's proof) is one code away from complete, not a dead end.
    if (auth.errorReason == 'unverified' || auth.errorReason == 'otp_required') {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => VerifyPhoneScreen(
            phone: phone,
            password: password,
            shopName: shopName,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('فتح محل جديد')),
      body: SafeArea(
        child: Consumer<AuthProvider>(
          builder: (context, auth, _) => SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('راجِع', style: AppTextStyles.headlineMedium, textAlign: TextAlign.center),
                  const SizedBox(height: AppSpacing.xs),
                  const Text(
                    'ثلاث خطوات فقط لفتح محلك',
                    style: AppTextStyles.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  TextFormField(
                    controller: _shopNameController,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'اسم المحل',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) => Validators.validateRequired(v, fieldName: 'اسم المحل'),
                  ),
                  const SizedBox(height: AppSpacing.md),
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
                    textInputAction: TextInputAction.next,
                    decoration: InputDecoration(
                      labelText: 'كلمة المرور',
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
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
                    decoration: const InputDecoration(
                      labelText: 'تأكيد كلمة المرور',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) => Validators.validateConfirmPassword(v, _passwordController.text),
                  ),
                  if (auth.error != null && auth.errorReason != 'unverified' && auth.errorReason != 'otp_required') ...[
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
                    child: Text(auth.isLoading ? 'جارٍ الإنشاء...' : 'فتح المحل'),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextButton(
                    onPressed: auth.isLoading ? null : () => context.goNamed(RouteNames.login),
                    child: const Text('لديك محل بالفعل؟ سجّل الدخول'),
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
