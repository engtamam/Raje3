import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

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
        _error = S.of(context)!.homeLoadErrorMessage;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final surface0 = isDark ? AppDarkColors.surface0 : AppColors.surface0;

    return Scaffold(
      backgroundColor: surface0,
      body: RefreshIndicator(
        onRefresh: _load,
        color: accent,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            _buildSliverHeader(context),
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
                              const AppLoadingIndicator()
                            else if (_error != null)
                              EmptyState(
                                icon: Icons.wifi_off_rounded,
                                title: S.of(context)!.homeLoadErrorTitle,
                                message: _error,
                                actionText: S.of(context)!.retry,
                                onAction: _load,
                              )
                            else ...[
                              if (_today != null) _buildTodayOverview(context, _today!),
                              if (_dashboard != null) ...[
                                const SizedBox(height: AppSpacing.md),
                                _buildDashboardCard(context, _dashboard!),
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

  Widget _buildSliverHeader(BuildContext context) {
    final isDark = context.isDark;
    final onAccent = isDark ? AppDarkColors.accentContrast : AppColors.accentContrast;
    final s = S.of(context)!;

    return SliverToBoxAdapter(
      child: Container(
        padding: EdgeInsets.only(
          top: MediaQuery.of(context).padding.top + AppSpacing.md,
          left: AppSpacing.md,
          right: AppSpacing.md,
          bottom: AppSpacing.md,
        ),
        decoration: BoxDecoration(
          gradient: primaryGradient(dark: isDark),
          borderRadius: const BorderRadius.only(
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
                    s.homeDashboardTitle,
                    style: AppTextStyles.bodySmall.copyWith(
                      color: onAccent.withValues(alpha: 0.85),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    s.homeShopSectionLabel,
                    style: AppTextStyles.headlineMedium.copyWith(
                      color: onAccent,
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
                color: onAccent.withValues(alpha: 0.15),
                borderRadius: AppRadius.standardRadius,
              ),
              child: Icon(Icons.today_rounded, color: onAccent, size: 22),
            ),
          ],
        ),
      ),
    );
  }

  // ── Today overview (GET /api/v1/reminders/today) ─────────────────────────

  Widget _buildTodayOverview(BuildContext context, Map<String, dynamic> today) {
    final colors = context.appColors;
    final isDark = context.isDark;
    final s = S.of(context)!;
    final messages = today['messages'] as Map<String, dynamic>? ?? {};
    final blocked = (today['blocked'] as String? ?? '').trim();
    final retrying = (messages['retrying'] as num? ?? 0);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _buildSectionIcon(context, Icons.today_rounded),
              const SizedBox(width: AppSpacing.sm),
              Text(
                s.homeTodaySectionTitle,
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (blocked.isNotEmpty) ...[
            AppAlert(type: AlertType.warning, message: blocked),
            const SizedBox(height: AppSpacing.md),
          ],
          Row(
            children: [
              _buildOverviewStat(
                context,
                icon: Icons.send_rounded,
                value: '${messages['sent_today'] ?? 0}',
                label: s.homeStatSent,
                color: isDark ? AppDarkColors.info : AppColors.info,
              ),
              const SizedBox(width: AppSpacing.md),
              _buildOverviewStat(
                context,
                icon: Icons.hourglass_top_rounded,
                value: '${messages['waiting'] ?? 0}',
                label: s.homeStatWaiting,
                color: colors.textSecondary,
              ),
              const SizedBox(width: AppSpacing.md),
              _buildOverviewStat(
                context,
                icon: Icons.replay_rounded,
                value: '$retrying',
                label: s.homeStatRetrying,
                color: retrying > 0
                    ? (isDark ? AppDarkColors.danger : AppColors.danger)
                    : (isDark ? AppDarkColors.success : AppColors.success),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildOverviewStat(
    BuildContext context, {
    required IconData icon,
    required String value,
    required String label,
    required Color color,
  }) {
    final colors = context.appColors;
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
            style: AppTextStyles.headlineSmall.copyWith(
              fontWeight: FontWeight.w700,
              color: colors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildSectionIcon(BuildContext context, IconData icon) {
    final isDark = context.isDark;
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
        borderRadius: AppRadius.standardRadius,
      ),
      child: Icon(
        icon,
        color: isDark ? AppDarkColors.accent : AppColors.accent,
        size: 18,
      ),
    );
  }

  // ── Dashboard card (GET /api/v1/insights/dashboard) ──────────────────────

  Widget _buildDashboardCard(BuildContext context, Map<String, dynamic> dashboard) {
    final colors = context.appColors;
    final s = S.of(context)!;

    if (dashboard['computing'] == true) {
      return AppCard(
        child: Text(
          dashboard['message'] as String? ?? s.homeDashboardComputing,
          style: AppTextStyles.bodyMedium.copyWith(color: colors.textPrimary),
        ),
      );
    }
    final values = dashboard['values'] as Map<String, dynamic>? ?? {};
    final numericEntries = values.entries.where((e) => e.value is num).toList(growable: false);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _buildSectionIcon(context, Icons.insights_rounded),
              const SizedBox(width: AppSpacing.sm),
              Text(
                s.homeDashboardSectionTitle,
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (numericEntries.isEmpty)
            Text(
              s.homeDashboardEmpty,
              style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
            )
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
                          style: AppTextStyles.headlineSmall.copyWith(
                            fontWeight: FontWeight.w700,
                            color: colors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          entry.key,
                          style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
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
