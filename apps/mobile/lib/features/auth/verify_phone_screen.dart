// Proving a phone number with a WhatsApp/SMS code.
//
// REACHABLE FROM BOTH DOORS. `AuthProvider.login` and `AuthProvider.openShop`
// both land here whenever the server refuses with reason `unverified`,
// `otp_required` or `unverified_hold` — see AuthProvider's own docstring on
// why the reason code exists (a screen cannot route on Arabic sentence text
// that somebody will improve one day).
//
// A NO-OP TODAY, HONESTLY SO. The real deployment ships with
// SIGNUP_REQUIRE_OTP=false (deploy/services/operations.values.yaml), so
// neither door currently refuses with these reasons — this screen exists for
// when that flag is turned on, and for the `unverified_hold` state a stray
// incomplete signup can already leave behind. It is not a stub: every call
// here hits the real `/api/v1/signup/code` and `/api/v1/signup/verify`
// routes, which already work end to end.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/kb_hint_button.dart';

class VerifyPhoneScreen extends StatefulWidget {
  /// The phone number to verify, and the password to retry sign-in with once
  /// it is proven. Both are required — this screen's only job is to unblock
  /// the sign-in the caller already attempted.
  final String phone;
  final String password;
  /// When set, a verified number should retry [AuthProvider.openShop] with
  /// this shop name instead of [AuthProvider.login] — the signup flow's own
  /// unverified refusal happens mid-saga, after the shop already exists.
  final String? shopName;

  const VerifyPhoneScreen({
    super.key,
    required this.phone,
    required this.password,
    this.shopName,
  });

  @override
  State<VerifyPhoneScreen> createState() => _VerifyPhoneScreenState();
}

class _VerifyPhoneScreenState extends State<VerifyPhoneScreen> {
  final _codeController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _busy = false;
  bool _codeRequested = false;
  String? _localError;

  @override
  void initState() {
    super.initState();
    _sendCode();
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    setState(() => _busy = true);
    final auth = context.read<AuthProvider>();
    final ok = await auth.requestCode(widget.phone);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _codeRequested = ok;
      _localError = ok ? null : (auth.error ?? S.of(context)!.authCodeSendFailedFallback);
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _localError = null;
    });

    final auth = context.read<AuthProvider>();
    final verified = await auth.verifyCode(widget.phone, _codeController.text.trim());
    if (!mounted) return;
    if (!verified) {
      setState(() {
        _busy = false;
        _localError = auth.error ?? S.of(context)!.authOtpIncorrectFallback;
      });
      return;
    }

    // NUMBER PROVEN — retry whichever door sent us here.
    final ok = widget.shopName != null
        ? await auth.openShop(
            phone: widget.phone,
            password: widget.password,
            shopName: widget.shopName!,
          )
        : await auth.login(widget.phone, widget.password);

    if (!mounted) return;
    setState(() => _busy = false);
    if (!ok) {
      setState(() => _localError = auth.error);
      return;
    }
    context.goNamed(RouteNames.home);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(
        title: Text(S.of(context)!.authVerifyPhoneTitle),
        actions: const [KbHintButton(anchor: 'auth.verify_phone')],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  S.of(context)!.authVerifyCodeSentTo(widget.phone),
                  style: AppTextStyles.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.lg),
                TextFormField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  maxLength: 6,
                  style: AppTextStyles.headlineSmall,
                  decoration: const InputDecoration(
                    counterText: '',
                    hintText: '000000',
                    border: OutlineInputBorder(),
                  ),
                  validator: (v) => Validators.validateOtp(v)?.text(context),
                ),
                if (_localError != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    _localError!,
                    style: const TextStyle(color: AppColors.danger),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: AppSpacing.lg),
                ElevatedButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? S.of(context)!.authVerifying : S.of(context)!.authConfirmCta),
                ),
                const SizedBox(height: AppSpacing.md),
                TextButton(
                  onPressed: _busy ? null : _sendCode,
                  child: Text(_codeRequested ? S.of(context)!.authResendCodeCta : S.of(context)!.authSendCodeCta),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
