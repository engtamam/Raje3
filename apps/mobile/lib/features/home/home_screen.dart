import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «محلّي» — copied from the reference project's
/// `lib/features/business/business_dashboard_screen.dart` (gradient sliver
/// header, stat-circle overview card, section cards), then adapted:
/// its many CRM/credits/banners sections are gone because we only have two
/// real endpoints today — the same ones apps/console/src/screens/Shop.tsx
/// reads for its own dashboard cards:
///   - GET /api/v1/reminders/today    (services/reminders/app/api/v1/owner.py::today)
///   - GET /api/v1/insights/dashboard (services/insights/app/api/v1/insights.py::dashboard)
/// Both are shared, cross-client-type routes (not under /api/v1/mobile), so this
/// calls [ApiClient.dio] directly rather than [ApiClient.get]'s envelope — same
/// reasoning as catalog_service.dart's own doc comment.
///
/// ONLY REACHABLE WHEN NavProvider SAYS THE 'shop' SECTION IS VISIBLE for this
/// session (wired in app_router.dart's redirect) — this screen never assumes
/// it is the landing screen; it just renders what it is given.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entryController;
  late final CurvedAnimation _entryAnimation = CurvedAnimation(
    parent: _entryController,
    curve: Curves.easeOut,
  );

  bool _loading = true;
  Map<String, dynamic>? _today;
  Map<String, dynamic>? _dashboard;
  String? _error;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      vsync: this,
      duration: AppMotion.slow,
      value: 1.0, // content is already visible; no blank-screen entry animation
    );
    _load();
  }

  @override
  void dispose() {
    _entryAnimation.dispose();
    _entryController.dispose();
    super.dispose();
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
      body: RefreshIndicator(
        onRefresh: _load,
        color: AppColors.accent,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            _buildSliverHeader(),
            SliverToBoxAdapter(
              child: AnimatedBuilder(
                animation: _entryController,
                builder: (context, _) {
                  final anim = _entryAnimation.value;
                  return Opacity(
                    opacity: anim,
                    child: Transform.translate(
                      offset: Offset(0, 20 * (1 - anim)),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SizedBox(height: AppSpacing.md),
                            if (_loading)
                              const Center(
                                child: Padding(
                                  padding: EdgeInsets.all(AppSpacing.xl),
                                  child: CircularProgressIndicator(),
                                ),
                              )
                            else if (_error != null)
                              _ErrorCard(message: _error!, onRetry: _load)
                            else ...[
                              if (_today != null) _buildTodayOverview(_today!),
                              if (_dashboard != null) ...[
                                const SizedBox(height: AppSpacing.md),
                                _buildDashboardCard(_dashboard!),
                              ],
                            ],
                            const SizedBox(height: AppSpacing.xxl),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Header ──────────────────────────────────────────────────────────────

  Widget _buildSliverHeader() {
    return SliverToBoxAdapter(
      child: Container(
        padding: EdgeInsets.only(
          top: MediaQuery.of(context).padding.top + AppSpacing.md,
          left: AppSpacing.md,
          right: AppSpacing.md,
          bottom: AppSpacing.md,
        ),
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppColors.accent, AppColors.accentHover, AppColors.accent],
          ),
          borderRadius: BorderRadius.only(
            bottomLeft: Radius.circular(28),
            bottomRight: Radius.circular(28),
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'لوحة التحكم',
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.accentContrast.withValues(alpha: 0.85),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'محلّي',
                    style: AppTextStyles.headlineMedium.copyWith(
                      color: AppColors.accentContrast,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.accentContrast.withValues(alpha: 0.15),
                borderRadius: AppRadius.standardRadius,
              ),
              child: const Icon(
                Icons.today_rounded,
                color: AppColors.accentContrast,
                size: 22,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Today overview (GET /api/v1/reminders/today) ─────────────────────────

  Widget _buildTodayOverview(Map<String, dynamic> today) {
    final messages = today['messages'] as Map<String, dynamic>? ?? {};
    final blocked = (today['blocked'] as String? ?? '').trim();
    final retrying = (messages['retrying'] as num? ?? 0);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: AppColors.borderSubtle),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.accentSoft,
                  borderRadius: AppRadius.standardRadius,
                ),
                child: const Icon(Icons.today_rounded, color: AppColors.accent, size: 18),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'اليوم',
                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (blocked.isNotEmpty) ...[
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: AppColors.warningSoft,
                borderRadius: AppRadius.standardRadius,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.warning_amber_rounded, size: 14, color: AppColors.warningOnSoft),
                  const SizedBox(width: AppSpacing.xs),
                  Flexible(
                    child: Text(
                      blocked,
                      style: AppTextStyles.bodySmall.copyWith(color: AppColors.warningOnSoft),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          Row(
            children: [
              _buildOverviewStat(
                icon: Icons.send_rounded,
                value: '${messages['sent_today'] ?? 0}',
                label: 'أُرسلت',
                color: AppColors.info,
              ),
              const SizedBox(width: AppSpacing.md),
              _buildOverviewStat(
                icon: Icons.hourglass_top_rounded,
                value: '${messages['waiting'] ?? 0}',
                label: 'في الانتظار',
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: AppSpacing.md),
              _buildOverviewStat(
                icon: Icons.replay_rounded,
                value: '$retrying',
                label: 'تعيد المحاولة',
                color: retrying > 0 ? AppColors.danger : AppColors.success,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildOverviewStat({
    required IconData icon,
    required String value,
    required String label,
    required Color color,
  }) {
    return Expanded(
      child: Column(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            value,
            style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: AppTextStyles.bodySmall,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  // ── Dashboard card (GET /api/v1/insights/dashboard) ──────────────────────

  Widget _buildDashboardCard(Map<String, dynamic> dashboard) {
    if (dashboard['computing'] == true) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: AppColors.borderSubtle),
        ),
        child: Text(
          dashboard['message'] as String? ?? 'أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل',
          style: AppTextStyles.bodyMedium,
        ),
      );
    }
    final values = dashboard['values'] as Map<String, dynamic>? ?? {};
    final numericEntries = values.entries.where((e) => e.value is num).toList(growable: false);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: AppColors.borderSubtle),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.accentSoft,
                  borderRadius: AppRadius.standardRadius,
                ),
                child: const Icon(Icons.insights_rounded, color: AppColors.accent, size: 18),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'مؤشرات المحل',
                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (numericEntries.isEmpty)
            const Text('لا توجد بيانات كافية بعد.', style: AppTextStyles.bodySmall)
          else
            Wrap(
              spacing: AppSpacing.md,
              runSpacing: AppSpacing.md,
              children: [
                for (final entry in numericEntries)
                  SizedBox(
                    width: 90,
                    child: Column(
                      children: [
                        Text(
                          '${entry.value}',
                          style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          entry.key,
                          style: AppTextStyles.bodySmall,
                          textAlign: TextAlign.center,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
              ],
            ),
        ],
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorCard({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Column(
        children: [
          Text(message, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}
