// Placeholder — Raje3's own login screen is a later pass (this pass is
// infra-only). Exists so AppRouter compiles and the auth redirect is
// exercisable end to end.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('راجِع', style: AppTextStyles.headlineMedium),
              const SizedBox(height: AppSpacing.md),
              const Text(
                'Login screen — placeholder (infra pass only)',
                style: AppTextStyles.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.lg),
              Consumer<AuthProvider>(
                builder: (context, auth, _) => ElevatedButton(
                  onPressed: auth.isLoading
                      ? null
                      : () => auth.login('0500000000', 'placeholder'),
                  child: Text(auth.isLoading ? 'جارٍ الدخول...' : 'دخول تجريبي'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
