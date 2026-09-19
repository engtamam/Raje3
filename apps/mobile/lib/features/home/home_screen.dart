import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «محلّي» — the mobile mirror of apps/console/src/screens/Shop.tsx's own dashboard cards.
///
/// ONLY REACHABLE WHEN NavProvider SAYS THE 'shop' SECTION IS VISIBLE for this session (wired
/// in app_router.dart's redirect) — this screen never assumes it is the landing screen; it just
/// renders what it is given, same discipline Shop.tsx itself follows (no `if (role === …)`).
///
/// Reads the SAME two real endpoints Shop.tsx reads for its own top cards:
///   - GET /api/v1/reminders/today   (services/reminders/app/api/v1/owner.py::today)
///   - GET /api/v1/insights/dashboard (services/insights/app/api/v1/insights.py::dashboard)
/// Both are shared, cross-client-type routes (not under /api/v1/mobile), so this calls
/// [ApiClient.dio] directly rather than [ApiClient.get]'s `{success, data}` envelope — same
/// reasoning as catalog_service.dart's own doc comment.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loading = true;
  Map<String, dynamic>? _today;
  Map<String, dynamic>? _dashboard;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final apiClient = context.read<AuthProvider>().apiClient;
    try {
      final results = await Future.wait([
        apiClient.dio.get<dynamic>('/api/v1/reminders/today'),
        apiClient.dio.get<dynamic>('/api/v1/insights/dashboard'),
      ]);
      if (!mounted) return;
      setState(() {
        _today = results[0].data is Map<String, dynamic>
            ? results[0].data as Map<String, dynamic>
            : null;
        _dashboard = results[1].data is Map<String, dynamic>
            ? results[1].data as Map<String, dynamic>
            : null;
        _loading = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _error = 'تعذّر تحميل بيانات اليوم. حاول مرة أخرى.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('محلّي')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(children: [_ErrorCard(message: _error!, onRetry: _load)])
                : ListView(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    children: [
                      if (_today != null) _TodayCard(today: _today!),
                      const SizedBox(height: AppSpacing.md),
                      if (_dashboard != null) _DashboardCard(dashboard: _dashboard!),
                    ],
                  ),
      ),
    );
  }
}

class _TodayCard extends StatelessWidget {
  final Map<String, dynamic> today;
  const _TodayCard({required this.today});

  @override
  Widget build(BuildContext context) {
    final messages = today['messages'] as Map<String, dynamic>? ?? {};
    final blocked = (today['blocked'] as String? ?? '').trim();
    return Card(
      color: AppColors.surface1,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('اليوم', style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: AppSpacing.md),
            if (blocked.isNotEmpty)
              Text(blocked, style: AppTextStyles.bodyMedium.copyWith(color: AppColors.warning)),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _Stat(label: 'أُرسلت', value: '${messages['sent_today'] ?? 0}'),
                _Stat(label: 'في الانتظار', value: '${messages['waiting'] ?? 0}'),
                _Stat(
                  label: 'تعيد المحاولة',
                  value: '${messages['retrying'] ?? 0}',
                  isWarning: (messages['retrying'] as num? ?? 0) > 0,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  final Map<String, dynamic> dashboard;
  const _DashboardCard({required this.dashboard});

  @override
  Widget build(BuildContext context) {
    if (dashboard['computing'] == true) {
      return Card(
        color: AppColors.surface1,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Text(
            dashboard['message'] as String? ?? 'أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل',
            style: AppTextStyles.bodyMedium,
          ),
        ),
      );
    }
    final values = dashboard['values'] as Map<String, dynamic>? ?? {};
    final numericEntries = values.entries
        .where((e) => e.value is num)
        .toList(growable: false);
    return Card(
      color: AppColors.surface1,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('مؤشرات المحل',
                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: AppSpacing.md),
            if (numericEntries.isEmpty)
              Text('لا توجد بيانات كافية بعد.', style: AppTextStyles.bodyMedium)
            else
              Wrap(
                spacing: AppSpacing.md,
                runSpacing: AppSpacing.md,
                children: [
                  for (final entry in numericEntries)
                    _Stat(label: entry.key, value: '${entry.value}'),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final bool isWarning;
  const _Stat({required this.label, required this.value, this.isWarning = false});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: AppTextStyles.bodyMedium.copyWith(
            fontWeight: FontWeight.bold,
            fontSize: 20,
            color: isWarning ? AppColors.warning : AppColors.textPrimary,
          ),
        ),
        Text(label, style: AppTextStyles.bodyMedium.copyWith(color: AppColors.textSecondary)),
      ],
    );
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorCard({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        children: [
          Text(message, style: AppTextStyles.bodyMedium),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}
