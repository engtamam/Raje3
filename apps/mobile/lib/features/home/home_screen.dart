// Placeholder — Raje3's own home screen is a later pass (this pass is
// infra-only). Exists so AppRouter compiles.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('راجِع')),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Home screen — placeholder (infra pass only)',
                style: AppTextStyles.bodyMedium),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(
              onPressed: () => context.read<AuthProvider>().logout(),
              child: const Text('تسجيل الخروج'),
            ),
          ],
        ),
      ),
    );
  }
}
