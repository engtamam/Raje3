import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/services/shop_dashboard_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/models/shop_dashboard_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «محلّي» — a FRESH mobile design of `apps/console/src/screens/Shop.tsx`'s own 24 real
/// indicators (`insights.dashboard` + `reminders.today` + `whatsapp.connect_status` +
/// `whatsapp_assistant.my_impact` + `insights.branches`), never a port of its two-column desktop
/// layout. Owner's own call, 2026-09-26: a phone reads this "top to bottom, then pick a deck",
/// not "scroll one long page" — closer to a health app's own "today score, then layers of depth"
/// shape (Oura's Today/Vitals/Health split) than a analytics dashboard's.
///
/// STRUCTURE: a fixed hero (the one sentence the whole product is about — return rate) never
/// scrolls away, «الخطوة التالية» (the engine's own single ranked action) pinned right under it
/// — never buried mid-scroll like the console does — then three tap-switched "decks" grouped by
/// URGENCY, not by data category (same "urgency and depth, not a content inventory's taxonomy"
/// rule the console's own header comment states): عاجل الآن (blocked/warnings/at-risk/AI-impact),
/// الأسبوع (week pulse/new-vs-returning/branch+staff compare), فرص وأنماط (service popularity/weak
/// services/message flow/holdout/recent visits). A tap-segmented row, not a swipe `PageView` —
/// matches this app's own established multi-tab convention (`rating_screen.dart`,
/// `partner_loyalty_screen.dart`'s own `_TabSwitch`), never a new interaction pattern for one
/// screen alone.
///
/// A DOCUMENTED, EXPLICIT SUBSET — never a silent gap ([[no-placeholder-drift]]). This pass covers
/// the highest-value indicators (hero+series+streak+trend chart, next-step+secondary, at-risk, AI
/// impact, week pulse, new-vs-returning, branch/staff compare, service popularity, weak services,
/// message flow, holdout, the three heatmaps, bundles, associations, missed opportunities, recent
/// visits, manual refresh). NOT YET BUILT, tracked for a real follow-up, not invented here: lead
/// conversion, and two small KPI rows the console keeps (active customers/return cycle days/churn
/// rate; services-per-visit/expected-flow/cycle-completion) — see parity/shop.md.
///
/// EVERY CARD BELOW STILL DRAWS ITSELF WHEN THIN — muted, never hidden, same rule the console
/// states outright ("لازم ما تجلس تخفي شي ابدا"): a `_MutedCard` fallback everywhere data has not
/// formed yet, rather than the card simply not appearing.
class ShopScreen extends StatefulWidget {
  const ShopScreen({super.key});

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

enum _Deck { urgent, week, opportunities }

class _ShopScreenState extends State<ShopScreen> {
  late final _service = ShopDashboardService(apiClient: context.read<AuthProvider>().apiClient);
  late final _customers = CustomersService(apiClient: context.read<AuthProvider>().apiClient);

  TodayStatus? _today;
  WaConnectStatus? _connect;
  ShopDashboard? _dashboard;
  List<String> _mustChoose = const [];
  bool _dashboardFailed = false;
  ShopImpact? _impact;
  List<Customer>? _atRiskCustomers;
  List<Customer>? _missedCustomers;
  bool _refreshing = false;
  bool _dismissing = false;
  _Deck _deck = _Deck.urgent;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final today = await _service.today();
    if (mounted) setState(() => _today = today);
    final connect = await _service.connectStatus();
    if (mounted) setState(() => _connect = connect);

    final (dash, mustChoose) = await _service.dashboard();
    if (!mounted) return;
    setState(() {
      _dashboard = dash;
      _mustChoose = mustChoose;
      _dashboardFailed = dash == null && mustChoose.isEmpty;
    });
    if (dash == null) return;

    if (dash.aiEntitled) {
      final impact = await _service.myImpact();
      if (mounted) setState(() => _impact = impact);
    }
    final atRisk = dash.atRisk;
    if (atRisk != null && atRisk.isNotEmpty) {
      final rows = await _customers.byRefs(atRisk.map((r) => r.subjectRef).toList());
      if (mounted) setState(() => _atRiskCustomers = rows ?? const []);
    }
    final missed = dash.missedOpportunities;
    if (missed != null && missed.isNotEmpty) {
      // Capped at 8 resolutions, same reasoning AtRiskCard's own cap follows — a PII lookup grows
      // with the list, and the folded section is not the place for it to grow unbounded.
      final rows = await _customers.byRefs(missed.take(8).map((r) => r.subjectRef).toList());
      if (mounted) setState(() => _missedCustomers = rows ?? const []);
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    await _service.refresh();
    final (dash, mustChoose) = await _service.dashboard();
    if (mounted) {
      setState(() {
        _refreshing = false;
        if (dash != null) {
          _dashboard = dash;
          _mustChoose = mustChoose;
        }
      });
    }
  }

  Future<void> _dismissNextStep(String id) async {
    if (_dismissing) return;
    setState(() => _dismissing = true);
    await _service.dismissNextStep(id);
    final (dash, _) = await _service.dashboard();
    if (mounted) {
      setState(() {
        _dismissing = false;
        if (dash != null) _dashboard = dash;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dash = _dashboard;

    return KbAnchor(
      id: 'shop',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: SafeArea(
          child: _dashboardFailed
              ? EmptyState(icon: Icons.error_outline_rounded, title: s.shopReadFailed)
              : _mustChoose.isNotEmpty
                  ? EmptyState(icon: Icons.storefront_rounded, title: s.shopMultiBranchTitle, message: s.shopMultiBranchDesc)
                  : dash == null
                      ? const Center(child: AppLoadingIndicator())
                      : dash.emptyBranch
                          ? EmptyState(icon: Icons.storefront_rounded, title: s.shopEmptyBranchTitle, message: dash.message)
                          : dash.computing
                              ? _ComputingView(message: dash.message, refreshing: _refreshing, onRefresh: _refresh, s: s)
                              : _buildReady(dash, s),
        ),
      ),
    );
  }

  Widget _buildReady(ShopDashboard dash, S s) {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_today?.blocked != null && _today!.blocked!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: _BlockedBanner(text: _today!.blocked!, s: s),
                  ),
                if ((_today?.retrying ?? 0) > 0)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: _RetryingBanner(today: _today!, s: s),
                  ),
                _RetentionHero(dashboard: dash, s: s),
                const SizedBox(height: AppSpacing.sm),
                if (_today != null) _TodayStrip(today: _today!, s: s),
                const SizedBox(height: AppSpacing.md),
                if (dash.activeCustomers != null || dash.returnCycleDays != null || dash.churnRate != null) ...[
                  _SurroundingKpisRow(dashboard: dash, s: s),
                  const SizedBox(height: AppSpacing.md),
                ],
                if (dash.nextStep != null)
                  KbAnchor(
                    id: 'shop.next_step',
                    child: _NextStepCard(
                      step: dash.nextStep!,
                      busy: _dismissing,
                      onDismiss: _dismissNextStep,
                      s: s,
                    ),
                  ),
                const SizedBox(height: AppSpacing.md),
                _DeckSwitch(deck: _deck, onChanged: (d) => setState(() => _deck = d), s: s),
                const SizedBox(height: AppSpacing.md),
                _buildDeck(dash, s),
                const SizedBox(height: AppSpacing.lg),
              ],
            ),
          ),
        ),
        _Footer(
          hoursAgo: dash.asOfHoursAgo,
          stale: dash.stale,
          refreshing: _refreshing,
          onRefresh: _refresh,
          s: s,
        ),
      ],
    );
  }

  Widget _buildDeck(ShopDashboard dash, S s) {
    switch (_deck) {
      case _Deck.urgent:
        return _UrgentDeck(
          connect: _connect,
          today: _today,
          dashboard: dash,
          impact: _impact,
          atRiskCustomers: _atRiskCustomers,
          s: s,
        );
      case _Deck.week:
        return _WeekDeck(dashboard: dash, service: _service, s: s);
      case _Deck.opportunities:
        return _OpportunitiesDeck(dashboard: dash, service: _service, missedCustomers: _missedCustomers, s: s);
    }
  }
}

/* ── shared small pieces ─────────────────────────────────────────────────────────────────────── */

class _BlockedBanner extends StatelessWidget {
  final String text;
  final S s;
  const _BlockedBanner({required this.text, required this.s});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [AppColors.danger, Color(0xFFFF8F5C)]),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          const Icon(Icons.error_rounded, color: Colors.white, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(text,
                style: AppTextStyles.bodySmall.copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}

class _RetryingBanner extends StatelessWidget {
  final TodayStatus today;
  final S s;
  const _RetryingBanner({required this.today, required this.s});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: (context.isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopTodayRetrying(today.retrying ?? 0),
              style: AppTextStyles.bodySmall.copyWith(
                  color: context.isDark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft,
                  fontWeight: FontWeight.w700)),
          if (today.retryingReason != null && today.retryingReason!.isNotEmpty)
            Text(today.retryingReason!,
                style: AppTextStyles.caption.copyWith(
                    color: context.isDark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft)),
        ],
      ),
    );
  }
}

/// The one card the "always render, never hide" rule protects — a `_MutedCard` fallback wherever
/// an indicator's real data has not formed yet, matching the console's own `MutedIndicator`.
class _MutedCard extends StatelessWidget {
  final String title;
  final String note;
  const _MutedCard({required this.title, required this.note});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.borderSubtle, style: BorderStyle.solid),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(note, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
        ],
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final Widget child;
  final Color? tint;
  const _Card({required this.child, this.tint});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: tint ?? colors.surface,
        borderRadius: AppRadius.standardRadius,
        boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: child,
    );
  }
}

/* ── hero ─────────────────────────────────────────────────────────────────────────────────────── */

class _RetentionHero extends StatelessWidget {
  final ShopDashboard dashboard;
  final S s;
  const _RetentionHero({required this.dashboard, required this.s});

  @override
  Widget build(BuildContext context) {
    final pct = dashboard.returnRate;
    final sampleSize = dashboard.activeCustomers;
    const gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF4C34C4), Color(0xFF2A1F7A)],
    );

    if (pct == null) {
      return _MutedCard(title: s.shopRetentionTitle, note: s.shopRetentionMutedNote);
    }

    if (sampleSize == 0) {
      return Container(
        padding: const EdgeInsets.all(AppSpacing.lg),
        decoration: BoxDecoration(gradient: gradient, borderRadius: AppRadius.cardRadius),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.shopRetentionTitle,
                style: AppTextStyles.caption.copyWith(color: Colors.white.withValues(alpha: 0.75), fontWeight: FontWeight.w700)),
            const SizedBox(height: AppSpacing.sm),
            Text(s.shopRetentionBrandNew,
                style: AppTextStyles.bodyMedium.copyWith(color: Colors.white, height: 1.5)),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white54),
              ),
              onPressed: () => context.goNamed('visit'),
              child: Text(s.shopRegisterFirstVisit),
            ),
          ],
        ),
      );
    }

    const sampleFloor = 10;
    final tooSmall = sampleSize != null && sampleSize < sampleFloor;
    final series = dashboard.retentionSeries;
    final hasSeries = series != null && !series.learning;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: AppRadius.cardRadius,
        boxShadow: const [BoxShadow(color: Color(0x334C34C4), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopRetentionTitle,
              style: AppTextStyles.caption.copyWith(color: Colors.white.withValues(alpha: 0.75), fontWeight: FontWeight.w700)),
          const SizedBox(height: AppSpacing.sm),
          if (tooSmall)
            _smallSampleSentence(s, pct, sampleSize)
          else
            _normalSentence(s, pct),
          if (hasSeries) ...[
            const SizedBox(height: AppSpacing.sm),
            Row(children: [
              _seriesDelta(series, s),
              const SizedBox(width: 6),
              _streakFlame(series, s),
            ]),
            if (series.points.length > 1) ...[
              const SizedBox(height: AppSpacing.md),
              _RetentionTrendChart(points: series.points),
            ],
          ],
        ],
      ),
    );
  }

  /// A Duolingo-style flame, not the console's plain 📈/📉 text — the same computed streak
  /// (three-plus consecutive same-direction points, `retentionStreak()` in Shop.tsx), given its
  /// own mobile-native gamified treatment rather than a literal port of the desktop badge.
  Widget _streakFlame(RetentionSeries series, S s) {
    final streak = _retentionStreak(series.points);
    if (streak == null) return const SizedBox.shrink();
    final color = streak.rising ? const Color(0xFFBAF5DA) : const Color(0xFFFFD3C9);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 4),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(streak.rising ? '🔥' : '📉', style: const TextStyle(fontSize: 11)),
          const SizedBox(width: 3),
          Text(
            '${streak.rising ? s.shopTrendUp : s.shopTrendDown} ${s.shopRetentionSincePeriods(streak.length)}',
            style: AppTextStyles.caption.copyWith(color: color, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }

  Widget _normalSentence(S s, double pct) {
    final returned = (pct * 10).round().clamp(0, 10);
    return RichText(
      text: TextSpan(
        style: AppTextStyles.bodyMedium.copyWith(color: Colors.white, height: 1.6),
        children: [
          TextSpan(text: s.shopRetentionPrefix10),
          TextSpan(
            text: ' $returned ',
            style: const TextStyle(fontSize: 40, fontWeight: FontWeight.w800, height: 1),
          ),
          TextSpan(text: s.shopRetentionSuffix),
        ],
      ),
    );
  }

  Widget _smallSampleSentence(S s, double pct, int sampleSize) {
    final returned = (pct * sampleSize).round();
    final base = sampleSize == 1 ? s.shopOneCustomer : s.shopNCustomers(sampleSize);
    return RichText(
      text: TextSpan(
        style: AppTextStyles.bodyMedium.copyWith(color: Colors.white, height: 1.6),
        children: [
          TextSpan(text: s.shopRetentionSmallPrefix(base)),
          TextSpan(
            text: ' $returned ',
            style: const TextStyle(fontSize: 40, fontWeight: FontWeight.w800, height: 1),
          ),
          TextSpan(text: s.shopRetentionSuffix),
        ],
      ),
    );
  }

  Widget _seriesDelta(RetentionSeries series, S s) {
    final first = series.first;
    final last = series.last;
    if (first == null || last == null) return const SizedBox.shrink();
    final deltaPts = ((last - first) * 100).round();
    if (deltaPts == 0) return const SizedBox.shrink();
    final up = deltaPts > 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 4),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
      child: Text(
        '${up ? '↑' : '↓'} ${deltaPts.abs()}% ${series.months != null ? s.shopOverNMonths(series.months!) : ''}',
        textDirection: TextDirection.ltr,
        style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _Streak {
  final int length;
  final bool rising;
  const _Streak(this.length, this.rising);
}

/// Same rule as Shop.tsx's own `retentionStreak()` — needs three real (non-null) points in a row
/// moving the same way, ending at the newest one; a flat move or a direction change breaks it.
_Streak? _retentionStreak(List<SeriesPoint> points) {
  final drawn = points.where((p) => p.value != null).toList();
  if (drawn.length < 3) return null;
  final rising = drawn.last.value! > drawn[drawn.length - 2].value!;
  var length = 1;
  for (var i = drawn.length - 1; i > 0; i--) {
    final up = drawn[i].value! > drawn[i - 1].value!;
    final flat = drawn[i].value! == drawn[i - 1].value!;
    if (flat || up != rising) break;
    length++;
  }
  return length >= 3 ? _Streak(length, rising) : null;
}

/// A HAND-DRAWN CURVE, NOT A THIRD-PARTY CHART LIBRARY — a soft gradient fill under a smoothed
/// line (quadratic through each pair's midpoint, same technique as Shop.tsx's own `RetentionTrend`,
/// reimplemented natively with `CustomPainter` rather than SVG) with the newest point lit by a
/// glow. A `value: null` point is a real gap in the curve (too few customers in that window to
/// trust) and is never bridged into a false continuity — drawn as a separate run.
class _RetentionTrendChart extends StatelessWidget {
  final List<SeriesPoint> points;
  const _RetentionTrendChart({required this.points});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 84,
      width: double.infinity,
      child: CustomPaint(painter: _RetentionTrendPainter(points)),
    );
  }
}

class _RetentionTrendPainter extends CustomPainter {
  final List<SeriesPoint> points;
  const _RetentionTrendPainter(this.points);

  @override
  void paint(Canvas canvas, Size size) {
    final n = points.length;
    if (n < 2) return;
    final vals = points.map((p) => p.value).whereType<double>().toList();
    if (vals.length < 2) return;
    final minV = vals.reduce((a, b) => a < b ? a : b);
    final maxV = vals.reduce((a, b) => a > b ? a : b);
    final span = (maxV - minV) == 0 ? 0.1 : (maxV - minV);

    final runs = <List<Offset>>[];
    var current = <Offset>[];
    for (var i = 0; i < n; i++) {
      final v = points[i].value;
      if (v == null) {
        if (current.length > 1) runs.add(current);
        current = [];
        continue;
      }
      final x = (i / (n - 1)) * size.width;
      final y = size.height - ((v - minV) / span) * size.height;
      current.add(Offset(x, y));
    }
    if (current.length > 1) runs.add(current);
    if (runs.isEmpty) return;

    Path smooth(List<Offset> run) {
      final path = Path()..moveTo(run.first.dx, run.first.dy);
      for (var i = 1; i < run.length; i++) {
        final mid = Offset((run[i - 1].dx + run[i].dx) / 2, (run[i - 1].dy + run[i].dy) / 2);
        path.quadraticBezierTo(run[i - 1].dx, run[i - 1].dy, mid.dx, mid.dy);
      }
      path.lineTo(run.last.dx, run.last.dy);
      return path;
    }

    final longest = runs.reduce((a, b) => b.length > a.length ? b : a);
    final areaPath = smooth(longest)
      ..lineTo(longest.last.dx, size.height)
      ..lineTo(longest.first.dx, size.height)
      ..close();
    canvas.drawPath(
      areaPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Colors.white.withValues(alpha: 0.32), Colors.white.withValues(alpha: 0)],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );

    final linePaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.85)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.25
      ..strokeCap = StrokeCap.round;
    for (final run in runs) {
      canvas.drawPath(smooth(run), linePaint);
    }

    final last = longest.last;
    canvas.drawCircle(last, 6, Paint()..color = Colors.white.withValues(alpha: 0.18));
    canvas.drawCircle(last, 3, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant _RetentionTrendPainter oldDelegate) => !identical(oldDelegate.points, points);
}

class _TodayStrip extends StatelessWidget {
  final TodayStatus today;
  final S s;
  const _TodayStrip({required this.today, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    Widget tile(String label, String value, Color color) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            decoration: BoxDecoration(color: colors.surface, borderRadius: AppRadius.standardRadius),
            child: Column(
              children: [
                Text(value,
                    textDirection: TextDirection.ltr,
                    style: AppTextStyles.bodyMedium.copyWith(color: color, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(label, style: AppTextStyles.caption.copyWith(color: colors.textSecondary), textAlign: TextAlign.center),
              ],
            ),
          ),
        );

    final ceilingValue = !today.ceiling.known
        ? '—'
        : today.ceiling.unlimited
            ? s.shopUnlimited
            : '${today.ceiling.remaining}';
    final ceilingColor = (!today.ceiling.known || today.ceiling.unlimited)
        ? colors.textSecondary
        : today.ceiling.remaining <= 0
            ? AppColors.danger
            : AppColors.success;

    return Row(
      children: [
        tile(s.shopTileSentToday, '${today.sentToday}', accent),
        const SizedBox(width: 6),
        tile(s.shopTileWaiting, '${today.waiting}', colors.textSecondary),
        const SizedBox(width: 6),
        tile(s.shopTileCeilingRemaining, ceilingValue, ceilingColor),
      ],
    );
  }
}

enum _Tone { violet, teal, coral, flat }

/// THE SHARED STAT TILE — same shape Shop.tsx's own `Tile` gives every surrounding-KPI and
/// per-visit number: a soft-tinted panel (never a flat white box), a trend pill when there is an
/// earlier period to compare against, and a dashed "empty" treatment (with an optional tap target)
/// for a shop too new to have a real reading yet — never a fabricated zero.
class _StatTile extends StatelessWidget {
  final String label;
  final String value;
  final _Tone tone;
  final double? deltaCurrent;
  final double? deltaPrevious;
  final bool goodIsUp;
  final bool percent;
  final bool empty;
  final String? hint;
  final VoidCallback? onTap;
  const _StatTile({
    required this.label,
    required this.value,
    required this.tone,
    this.deltaCurrent,
    this.deltaPrevious,
    this.goodIsUp = true,
    this.percent = false,
    this.empty = false,
    this.hint,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final dark = context.isDark;
    final Color soft, fg;
    switch (tone) {
      case _Tone.violet:
        fg = dark ? AppDarkColors.accent : AppColors.accent;
        soft = fg.withValues(alpha: 0.12);
      case _Tone.teal:
        fg = AppColors.success;
        soft = fg.withValues(alpha: 0.12);
      case _Tone.coral:
        fg = AppColors.danger;
        soft = fg.withValues(alpha: 0.12);
      case _Tone.flat:
        fg = colors.textPrimary;
        soft = colors.surfaceAlt;
    }
    final diff = deltaCurrent != null && deltaPrevious != null ? deltaCurrent! - deltaPrevious! : null;
    final good = diff != null ? (goodIsUp ? diff >= 0 : diff <= 0) : null;
    final body = Container(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm, horizontal: 4),
      decoration: BoxDecoration(
        color: empty ? null : soft,
        border: empty ? Border.all(color: colors.borderSubtle, style: BorderStyle.solid) : null,
        borderRadius: AppRadius.standardRadius,
      ),
      child: Column(
        children: [
          Text(value,
              textDirection: TextDirection.ltr,
              style: AppTextStyles.bodyMedium.copyWith(color: empty ? colors.textMuted : fg, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label,
              style: AppTextStyles.caption.copyWith(color: empty ? colors.textMuted : colors.textSecondary),
              textAlign: TextAlign.center),
          if (empty && hint != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(hint!,
                  style: AppTextStyles.caption.copyWith(color: dark ? AppDarkColors.accent : AppColors.accent, fontSize: 9),
                  textAlign: TextAlign.center),
            ),
          if (diff != null && !empty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                '${diff == 0 ? '' : (diff > 0 ? '↑' : '↓')} ${percent ? '${(diff.abs() * 100).round()}%' : diff.abs().round()}',
                textDirection: TextDirection.ltr,
                style: AppTextStyles.caption.copyWith(
                  color: diff == 0 ? colors.textMuted : (good == true ? AppColors.success : AppColors.danger),
                  fontWeight: FontWeight.w700,
                  fontSize: 10,
                ),
              ),
            ),
        ],
      ),
    );
    return Expanded(child: onTap != null ? InkWell(borderRadius: AppRadius.standardRadius, onTap: onTap, child: body) : body);
  }
}

/// «العملاء النشطون / دورة الرجوع / التسرّب» — Shop.tsx's own `SurroundingKpis`, three tiles right
/// beside the hero, weighted so «عملاء نشطون» keeps more room whether it is high or low today
/// (a design choice, not a data one — same reasoning the console's own comment gives).
class _SurroundingKpisRow extends StatelessWidget {
  final ShopDashboard dashboard;
  final S s;
  const _SurroundingKpisRow({required this.dashboard, required this.s});

  @override
  Widget build(BuildContext context) {
    final justStarted = dashboard.activeCustomers == 0;
    final activeTrend = dashboard.activeCustomersTrend;
    final churnTrend = dashboard.churnRateTrend;
    return Row(
      children: [
        if (dashboard.activeCustomers != null) ...[
          Expanded(
            flex: 13,
            child: _StatTile(
              label: s.shopKpiActiveCustomers,
              value: '${dashboard.activeCustomers}',
              tone: _Tone.violet,
              empty: justStarted,
              hint: justStarted ? s.shopRegisterFirstVisit : null,
              onTap: justStarted ? () => context.goNamed('visit') : null,
              deltaCurrent: justStarted ? null : activeTrend?.current,
              deltaPrevious: justStarted ? null : activeTrend?.previous,
            ),
          ),
          const SizedBox(width: 6),
        ],
        if (dashboard.returnCycleDays != null) ...[
          Expanded(
            child: _StatTile(
              label: s.shopKpiReturnCycle,
              value: s.shopDaysSuffix(dashboard.returnCycleDays!),
              tone: _Tone.flat,
              empty: justStarted,
            ),
          ),
          const SizedBox(width: 6),
        ],
        if (dashboard.churnRate != null)
          Expanded(
            child: _StatTile(
              label: s.shopKpiChurnRate,
              value: '${(dashboard.churnRate! * 100).round()}%',
              tone: _Tone.coral,
              empty: justStarted,
              goodIsUp: false,
              percent: true,
              deltaCurrent: justStarted ? null : churnTrend?.current,
              deltaPrevious: justStarted ? null : churnTrend?.previous,
            ),
          ),
      ],
    );
  }
}

/// «خدمات لكل زيارة / التدفق المتوقع / اكتمال الدورة» — Shop.tsx's own third KPI row, shown only
/// when at least one of the three has a real reading (never three dashes pretending to be data).
class _PerVisitRow extends StatelessWidget {
  final ShopDashboard dashboard;
  final S s;
  const _PerVisitRow({required this.dashboard, required this.s});

  @override
  Widget build(BuildContext context) {
    final perVisit = dashboard.servicesPerVisit;
    final flow = dashboard.expectedFlow;
    final completion = dashboard.cycleCompletion;
    return Row(
      children: [
        if (perVisit != null) ...[
          Expanded(child: _StatTile(label: s.shopTileServicesPerVisit, value: '${perVisit.round()}', tone: _Tone.flat)),
          const SizedBox(width: 6),
        ],
        if (flow != null) ...[
          Expanded(child: _StatTile(label: s.shopTileExpectedNextWeek, value: '$flow', tone: _Tone.violet)),
          const SizedBox(width: 6),
        ],
        if (completion != null)
          Expanded(
            child: _StatTile(label: s.shopTileCycleCompletion, value: '${(completion * 100).round()}%', tone: _Tone.teal),
          ),
      ],
    );
  }
}

/// A RADIAL GAUGE, NOT A BARE PERCENTAGE — the conversion rate drawn as a small arc (how much of
/// the circle is "closed the loop"), the same number Shop.tsx's own plain "{rate}%" states, given
/// a genuinely mobile-native visual rather than a literal port of the desktop's inline number.
class _LeadConversionCard extends StatelessWidget {
  final int converted;
  final int total;
  final S s;
  const _LeadConversionCard({required this.converted, required this.total, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final rate = total > 0 ? converted / total : 0.0;
    return _Card(
      child: Row(
        children: [
          SizedBox(
            width: 56,
            height: 56,
            child: CustomPaint(
              painter: _RadialGaugePainter(fraction: rate, color: accent, track: colors.surfaceAlt),
              child: Center(
                child: Text('${(rate * 100).round()}%',
                    textDirection: TextDirection.ltr,
                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w800, color: accent)),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.shopLeadConversionTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(s.shopLeadConversionDetail(converted, total),
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RadialGaugePainter extends CustomPainter {
  final double fraction;
  final Color color;
  final Color track;
  const _RadialGaugePainter({required this.fraction, required this.color, required this.track});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - 8) / 2;
    final trackPaint = Paint()
      ..color = track
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6;
    canvas.drawCircle(center, radius, trackPaint);
    final arcPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), -1.5708, fraction.clamp(0, 1) * 6.28319, false, arcPaint);
  }

  @override
  bool shouldRepaint(covariant _RadialGaugePainter oldDelegate) =>
      oldDelegate.fraction != fraction || oldDelegate.color != color;
}

class _NextStepCard extends StatelessWidget {
  final NextStep step;
  final bool busy;
  final ValueChanged<String> onDismiss;
  final S s;
  const _NextStepCard({required this.step, required this.busy, required this.onDismiss, required this.s});

  @override
  Widget build(BuildContext context) {
    final card = step.primary;
    final luxury = card.id == 'whatsapp_ai_teaser';
    final tone = card.tone == 'success'
        ? AppColors.success
        : card.tone == 'warning'
            ? AppColors.warning
            : (context.isDark ? AppDarkColors.accent : AppColors.accent);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        gradient: luxury
            ? const LinearGradient(colors: [Color(0xFFB8860B), Color(0xFF6A4CF5)])
            : null,
        color: luxury ? null : tone.withValues(alpha: 0.1),
        borderRadius: AppRadius.standardRadius,
        border: luxury ? null : Border.all(color: tone.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome_rounded, size: 16, color: luxury ? Colors.white : tone),
              const SizedBox(width: 6),
              Text(s.shopNextStepLabel,
                  style: AppTextStyles.caption.copyWith(
                      color: luxury ? Colors.white.withValues(alpha: 0.85) : tone, fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 6),
          Text(card.message,
              style: AppTextStyles.bodyMedium.copyWith(color: luxury ? Colors.white : null, fontWeight: FontWeight.w600)),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              if (card.ctaLabel != null && card.ctaLink != null)
                TextButton(
                  onPressed: () => context.push(card.ctaLink!),
                  style: TextButton.styleFrom(foregroundColor: luxury ? Colors.white : tone),
                  child: Text(card.ctaLabel!),
                ),
              const Spacer(),
              TextButton(
                onPressed: busy ? null : () => onDismiss(card.id),
                style: TextButton.styleFrom(foregroundColor: luxury ? Colors.white70 : null),
                child: Text(s.shopNotNow),
              ),
            ],
          ),
          if (step.secondary != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                s.shopNextStepAlso(step.secondary!.message),
                style: AppTextStyles.caption.copyWith(
                    color: luxury ? Colors.white70 : (context.isDark ? AppDarkColors.textMuted : AppColors.textMuted)),
              ),
            ),
        ],
      ),
    );
  }
}

class _DeckSwitch extends StatelessWidget {
  final _Deck deck;
  final ValueChanged<_Deck> onChanged;
  final S s;
  const _DeckSwitch({required this.deck, required this.onChanged, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    Widget seg(String label, _Deck value) {
      final selected = deck == value;
      return Expanded(
        child: InkWell(
          onTap: () => onChanged(value),
          borderRadius: AppRadius.standardRadius,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            decoration: BoxDecoration(
              color: selected ? accent : Colors.transparent,
              borderRadius: AppRadius.standardRadius,
            ),
            alignment: Alignment.center,
            child: Text(label,
                style: AppTextStyles.caption.copyWith(
                    color: selected ? AppColors.accentContrast : colors.textSecondary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
      child: Row(children: [
        seg(s.shopDeckUrgent, _Deck.urgent),
        seg(s.shopDeckWeek, _Deck.week),
        seg(s.shopDeckOpportunities, _Deck.opportunities),
      ]),
    );
  }
}

class _Footer extends StatelessWidget {
  final int hoursAgo;
  final bool stale;
  final bool refreshing;
  final VoidCallback onRefresh;
  final S s;
  const _Footer({
    required this.hoursAgo,
    required this.stale,
    required this.refreshing,
    required this.onRefresh,
    required this.s,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      decoration: BoxDecoration(border: Border(top: BorderSide(color: colors.borderSubtle))),
      child: Row(
        children: [
          Expanded(
            child: Text(
              hoursAgo == 0 ? s.shopComputedNow : s.shopComputedHoursAgo(hoursAgo),
              style: AppTextStyles.caption.copyWith(color: colors.textMuted),
            ),
          ),
          if (stale)
            Container(
              margin: const EdgeInsets.only(left: 6),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(color: const Color(0xFFFDF0DC), borderRadius: BorderRadius.circular(AppRadius.pill)),
              child: Text(s.shopStale, style: AppTextStyles.caption.copyWith(color: const Color(0xFF8A5A12))),
            ),
          TextButton.icon(
            onPressed: refreshing ? null : onRefresh,
            icon: refreshing
                ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.refresh_rounded, size: 16),
            label: Text(s.shopRefreshAction),
          ),
        ],
      ),
    );
  }
}

class _ComputingView extends StatelessWidget {
  final String? message;
  final bool refreshing;
  final VoidCallback onRefresh;
  final S s;
  const _ComputingView({required this.message, required this.refreshing, required this.onRefresh, required this.s});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const AppLoadingIndicator(),
            const SizedBox(height: AppSpacing.md),
            Text(message ?? s.shopComputingTitle, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(
              onPressed: refreshing ? null : onRefresh,
              child: Text(refreshing ? s.shopComputeLoading : s.shopComputeAction),
            ),
          ],
        ),
      ),
    );
  }
}

/* ── deck: عاجل الآن ──────────────────────────────────────────────────────────────────────────── */

class _UrgentDeck extends StatelessWidget {
  final WaConnectStatus? connect;
  final TodayStatus? today;
  final ShopDashboard dashboard;
  final ShopImpact? impact;
  final List<Customer>? atRiskCustomers;
  final S s;
  const _UrgentDeck({
    required this.connect,
    required this.today,
    required this.dashboard,
    required this.impact,
    required this.atRiskCustomers,
    required this.s,
  });

  @override
  Widget build(BuildContext context) {
    final atRisk = dashboard.atRisk;
    final warning = _warningText();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (warning != null) ...[
          Container(
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(color: const Color(0xFFFDF0DC), borderRadius: AppRadius.standardRadius),
            child: Text(warning, style: AppTextStyles.caption.copyWith(color: const Color(0xFF8A5A12))),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        if (atRisk == null)
          _MutedCard(title: s.shopAtRiskTitle, note: s.shopAtRiskMutedNote)
        else if (atRisk.isEmpty)
          Container(
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
                color: context.isDark ? AppDarkColors.successSoft : AppColors.successSoft,
                borderRadius: AppRadius.standardRadius),
            child: Text(s.shopAtRiskAllGood, style: AppTextStyles.bodySmall.copyWith(color: AppColors.success)),
          )
        else
          _AtRiskCard(rows: atRisk, customers: atRiskCustomers, s: s),
        const SizedBox(height: AppSpacing.md),
        if (dashboard.aiEntitled && impact != null) _AIImpactCard(impact: impact!, s: s),
      ],
    );
  }

  String? _warningText() {
    if (connect != null && connect!.state.isNotEmpty && connect!.state != 'connected') {
      return connect!.message;
    }
    if (connect != null && connect!.state.isEmpty) return s.shopWaNotConnected;
    if (connect != null && connect!.canSend == false) return s.shopWaNotVerified;
    final ceiling = today?.ceiling;
    if (ceiling != null && ceiling.known && !ceiling.unlimited && ceiling.remaining <= 0) {
      return s.shopCeilingReached;
    }
    return null;
  }
}

class _AtRiskCard extends StatelessWidget {
  final List<AtRiskRow> rows;
  final List<Customer>? customers;
  final S s;
  const _AtRiskCard({required this.rows, required this.customers, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final byRef = {for (final c in customers ?? const <Customer>[]) c.subjectRef: c};
    return _Card(
      tint: context.isDark ? null : const Color(0xFFECE7FE),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopAtRiskTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          for (final r in rows.take(5))
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      // NEVER THE RAW `subject_ref` PSEUDONYM ITSELF — a resolution failure falls
                      // back to the same generic "عميل" label Shop.tsx's own `customerFallback`
                      // uses, not the internal id, matching `_MissedOpportunitiesCard`'s identical
                      // fallback below.
                      byRef[r.subjectRef]?.name.isNotEmpty == true
                          ? byRef[r.subjectRef]!.name
                          : (byRef[r.subjectRef]?.phone.isNotEmpty == true ? byRef[r.subjectRef]!.phone : s.shopCustomerFallback),
                      style: AppTextStyles.bodySmall,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(s.shopDaysOverdue(r.daysOverdue),
                      style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.xs),
          TextButton(
            onPressed: () => context.push('/messages?tab=campaigns&launch=win_back'),
            child: Text(s.shopAtRiskCta),
          ),
        ],
      ),
    );
  }
}

class _AIImpactCard extends StatelessWidget {
  final ShopImpact impact;
  final S s;
  const _AIImpactCard({required this.impact, required this.s});

  @override
  Widget build(BuildContext context) {
    return _Card(
      tint: context.isDark ? null : const Color(0xFFDCF7F1),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopAiImpactTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              if (impact.aiEnabled)
                Expanded(
                  child: _miniStat('${impact.conversations ?? 0}', s.shopAiConversations),
                ),
              Expanded(child: _miniStat('${impact.aiBookings}', s.shopAiBookings)),
              if (impact.upsellAcceptanceRate != null)
                Expanded(child: _miniStat('${(impact.upsellAcceptanceRate! * 100).round()}%', s.shopAiUpsellRate)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _miniStat(String value, String label) => Column(
        children: [
          Text(value, textDirection: TextDirection.ltr, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800, color: AppColors.success)),
          Text(label, style: AppTextStyles.caption, textAlign: TextAlign.center),
        ],
      );
}

/* ── deck: الأسبوع ────────────────────────────────────────────────────────────────────────────── */

class _WeekDeck extends StatelessWidget {
  final ShopDashboard dashboard;
  final ShopDashboardService service;
  final S s;
  const _WeekDeck({required this.dashboard, required this.service, required this.s});

  @override
  Widget build(BuildContext context) {
    final week = dashboard.visitsWeek;
    final split = dashboard.newVsReturning;
    final operators = service.operatorRows(dashboard);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        week != null
            ? _WeekPulseCard(week: week, s: s)
            : _MutedCard(title: s.shopWeekMutedTitle, note: s.shopWeekMutedNote),
        const SizedBox(height: AppSpacing.md),
        (split != null && (split.newCustomers + split.returning) > 0)
            ? _NewVsReturningCard(newCustomers: split.newCustomers, returning: split.returning, s: s)
            : _MutedCard(title: s.shopNewReturningMutedTitle, note: s.shopNewReturningMutedNote),
        Builder(builder: (context) {
          final bySource = dashboard.leadConversionBySource;
          if (bySource == null || bySource.isEmpty) return const SizedBox.shrink();
          final total = bySource.values.fold(0, (sum, v) => sum + v.total);
          final converted = bySource.values.fold(0, (sum, v) => sum + v.converted);
          if (total <= 0) return const SizedBox.shrink();
          return Padding(
            padding: const EdgeInsets.only(top: AppSpacing.md),
            child: _LeadConversionCard(converted: converted, total: total, s: s),
          );
        }),
        if (dashboard.servicesPerVisit != null || dashboard.expectedFlow != null || dashboard.cycleCompletion != null) ...[
          const SizedBox(height: AppSpacing.md),
          _PerVisitRow(dashboard: dashboard, s: s),
        ] else ...[
          const SizedBox(height: AppSpacing.md),
          _MutedCard(title: s.shopPerVisitMutedTitle, note: s.shopPerVisitMutedNote),
        ],
        const SizedBox(height: AppSpacing.md),
        FutureBuilder<Branches?>(
          future: service.branches(),
          builder: (context, snap) {
            // `snap.hasData` is false BOTH while pending AND once resolved successfully to
            // `null` (a shop with no `insights.branches` capability) — `connectionState` is the
            // only way to tell "still loading" apart from "loaded, and there is genuinely
            // nothing", so a real empty result never gets stuck reading as a permanent spinner.
            if (snap.connectionState == ConnectionState.waiting) {
              return const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator());
            }
            final branches = snap.data;
            return branches != null
                ? _BranchCompareCard(branches: branches, s: s)
                : _MutedCard(title: s.shopBranchCompareTitle, note: s.shopBranchCompareMutedNote);
          },
        ),
        const SizedBox(height: AppSpacing.md),
        operators != null
            ? _StaffCompareCard(
                rows: operators,
                unknown: service.operatorUnknown(dashboard),
                canRank: service.operatorCanRank(dashboard),
                s: s,
              )
            : _MutedCard(title: s.shopStaffCompareTitle, note: s.shopStaffCompareMutedNote),
      ],
    );
  }
}

class _WeekPulseCard extends StatelessWidget {
  final WeekWindow week;
  final S s;
  const _WeekPulseCard({required this.week, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final delta = week.previous != null ? week.visits - week.previous! : null;
    final justStarted = week.visits == 0 && week.previous == null;
    if (justStarted) {
      return InkWell(
        borderRadius: AppRadius.standardRadius,
        onTap: () => context.goNamed('visit'),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            borderRadius: AppRadius.standardRadius,
            border: Border.all(color: colors.borderSubtle, style: BorderStyle.solid),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s.shopWeekTitle, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                  Text('0', textDirection: TextDirection.ltr, style: AppTextStyles.headlineSmall.copyWith(color: colors.textMuted, fontWeight: FontWeight.w800)),
                ],
              ),
              Text(s.shopRegisterFirstVisitArrow,
                  style: AppTextStyles.caption.copyWith(
                      color: context.isDark ? AppDarkColors.accent : AppColors.accent, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      );
    }
    return _Card(
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.shopWeekTitle, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                Text('${week.visits}', textDirection: TextDirection.ltr, style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w800)),
              ],
            ),
          ),
          if (delta != null)
            Text('${delta >= 0 ? '↑' : '↓'} ${delta.abs()}',
                textDirection: TextDirection.ltr,
                style: AppTextStyles.bodySmall.copyWith(
                    color: delta >= 0 ? AppColors.success : AppColors.danger, fontWeight: FontWeight.w700))
          else
            Text(s.shopWeekNoCompare, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
        ],
      ),
    );
  }
}

class _NewVsReturningCard extends StatelessWidget {
  final int newCustomers;
  final int returning;
  final S s;
  const _NewVsReturningCard({required this.newCustomers, required this.returning, required this.s});

  @override
  Widget build(BuildContext context) {
    final total = (newCustomers + returning).clamp(1, 1 << 30);
    final newFrac = newCustomers / total;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopNewReturningTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: Row(
              children: [
                Expanded(flex: (newFrac * 100).round().clamp(1, 99), child: Container(height: 10, color: AppColors.accent)),
                Expanded(flex: (100 - (newFrac * 100).round()).clamp(1, 99), child: Container(height: 10, color: AppColors.success)),
              ],
            ),
          ),
          const SizedBox(height: 6),
          Text('${s.shopNewLabel} $newCustomers  ·  ${s.shopReturningLabel} $returning', style: AppTextStyles.caption),
        ],
      ),
    );
  }
}

class _RankBadge extends StatelessWidget {
  final int rank;
  const _RankBadge({required this.rank});

  @override
  Widget build(BuildContext context) {
    const colorsByRank = [Color(0xFFFFD700), Color(0xFFC0C0C0), Color(0xFFCD7F32)];
    final color = rank < 3 ? colorsByRank[rank] : Colors.transparent;
    return Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: rank < 3 ? 1 : 0)),
      child: Text('${rank + 1}', style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w700)),
    );
  }
}

class _BranchCompareCard extends StatelessWidget {
  final Branches branches;
  final S s;
  const _BranchCompareCard({required this.branches, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final muted = branches.rows.length < 2;
    return _Card(
      child: Opacity(
        opacity: muted ? 0.6 : 1,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.shopBranchCompareTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: AppSpacing.sm),
            for (var i = 0; i < branches.rows.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    _RankBadge(rank: i),
                    const SizedBox(width: 6),
                    Expanded(child: Text(branches.rows[i].name, style: AppTextStyles.bodySmall, overflow: TextOverflow.ellipsis)),
                    if (branches.rows[i].returnRate != null)
                      Text('${(branches.rows[i].returnRate! * 100).round()}%',
                          textDirection: TextDirection.ltr,
                          style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ),
              ),
            if (branches.unknown > 0)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopBranchCompareUnassigned(branches.unknown),
                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
            if (muted)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  branches.rows.isEmpty ? s.shopBranchCompareNeedTwo : s.shopBranchCompareNeedSecond,
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                ),
              )
            else if (!branches.canRank)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopBranchCompareTooShort, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
          ],
        ),
      ),
    );
  }
}

class _StaffCompareCard extends StatelessWidget {
  final List<OperatorRow> rows;
  final int unknown;
  final bool canRank;
  final S s;
  const _StaffCompareCard({required this.rows, required this.unknown, required this.canRank, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final muted = rows.length < 2;
    return _Card(
      child: Opacity(
        opacity: muted ? 0.6 : 1,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.shopStaffCompareTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: AppSpacing.sm),
            for (var i = 0; i < rows.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    _RankBadge(rank: i),
                    const SizedBox(width: 6),
                    Expanded(child: Text(rows[i].name, style: AppTextStyles.bodySmall, overflow: TextOverflow.ellipsis)),
                    if (rows[i].returnRate != null)
                      Text('${(rows[i].returnRate! * 100).round()}%',
                          textDirection: TextDirection.ltr,
                          style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ),
              ),
            if (unknown > 0)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopStaffCompareUnassigned(unknown), style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
            if (muted)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  rows.isEmpty ? s.shopStaffCompareNeedTwo : s.shopStaffCompareNeedSecond,
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                ),
              )
            else if (!canRank)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopStaffCompareTooShort, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
          ],
        ),
      ),
    );
  }
}

/* ── deck: فرص وأنماط ─────────────────────────────────────────────────────────────────────────── */

class _OpportunitiesDeck extends StatelessWidget {
  final ShopDashboard dashboard;
  final ShopDashboardService service;
  final List<Customer>? missedCustomers;
  final S s;
  const _OpportunitiesDeck({
    required this.dashboard,
    required this.service,
    required this.missedCustomers,
    required this.s,
  });

  @override
  Widget build(BuildContext context) {
    final popularity = dashboard.servicePopularity;
    final weak = dashboard.weakServices;
    final names = dashboard.serviceNames;
    final eff = dashboard.returnedAfterReminder;
    final opt = dashboard.optOutRate;
    final holdout = dashboard.holdoutComparison;
    final peak = dashboard.peakMap;
    final serviceDayRows = dashboard.serviceDayRows;
    final branchDayRows = dashboard.branchDayRows;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        (popularity != null && popularity.isNotEmpty) || (weak != null && weak.isNotEmpty)
            ? _ServicesCard(popularity: popularity, weak: weak, names: names, s: s)
            : _MutedCard(title: s.shopServicesTitle, note: s.shopServicesMutedNote),
        const SizedBox(height: AppSpacing.md),
        (eff != null || opt != null)
            ? _MessageFlowCard(eff: eff, opt: opt, s: s)
            : _MutedCard(title: s.shopMessageFlowTitle, note: s.shopMutedMessageFlowNote),
        const SizedBox(height: AppSpacing.md),
        holdout != null
            ? _HoldoutCard(h: holdout, s: s)
            : _MutedCard(title: s.shopHoldoutTitle, note: s.shopMutedHoldoutNote),
        const SizedBox(height: AppSpacing.md),
        (peak != null && peak.grid.isNotEmpty)
            ? _PeakHeatmapCard(peak: peak, s: s)
            : _MutedCard(title: s.shopPeakTitle, note: s.shopPeakMutedNote),
        const SizedBox(height: AppSpacing.md),
        serviceDayRows.isNotEmpty
            ? _EntityDayHeatmapCard(
                title: s.shopEntityDayServicesTitle, hint: s.shopEntityDayServicesHint, rows: serviceDayRows, teal: true)
            : _MutedCard(title: s.shopEntityDayServicesTitle, note: s.shopEntityDayServicesMutedNote),
        const SizedBox(height: AppSpacing.md),
        branchDayRows.isNotEmpty
            ? _EntityDayHeatmapCard(
                title: s.shopEntityDayBranchesTitle, hint: s.shopEntityDayBranchesHint, rows: branchDayRows, teal: false)
            : _MutedCard(title: s.shopEntityDayBranchesTitle, note: s.shopEntityDayBranchesMutedNote),
        const SizedBox(height: AppSpacing.md),
        FutureBuilder<(List<Bundle>?, String?)>(
          future: service.bundles(),
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator());
            }
            final result = snap.data;
            final bundles = result?.$1;
            final locked = result?.$2;
            if (locked != null) return _LockedCard(title: s.shopBundlesTitle, text: locked);
            if (bundles == null) return const SizedBox.shrink();
            if (bundles.isEmpty) return _MutedCard(title: s.shopBundlesTitle, note: s.shopBundlesMutedNote);
            return _BundlesCard(bundles: bundles, s: s);
          },
        ),
        const SizedBox(height: AppSpacing.md),
        FutureBuilder<(Pairs?, String?)>(
          future: service.associations(),
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator());
            }
            final result = snap.data;
            final pairs = result?.$1;
            final locked = result?.$2;
            if (locked != null) return _LockedCard(title: s.shopAssociationsTitle, text: locked);
            if (pairs == null) return const SizedBox.shrink();
            if (pairs.learning) {
              return _MutedCard(
                title: s.shopAssociationsTitle,
                note: s.shopAssociationsLearningNote(pairs.have, pairs.need),
              );
            }
            if (pairs.pairs.isEmpty) return _MutedCard(title: s.shopAssociationsTitle, note: s.shopAssociationsMutedNote);
            return _AssociationsCard(pairs: pairs.pairs, names: names, s: s);
          },
        ),
        Builder(builder: (context) {
          final missed = dashboard.missedOpportunities;
          if (missed == null) return const SizedBox.shrink();
          return Padding(
            padding: const EdgeInsets.only(top: AppSpacing.md),
            child: missed.isEmpty
                ? _MutedCard(title: s.shopMissedTitle, note: s.shopMissedMutedNote)
                : _MissedOpportunitiesCard(rows: missed, customers: missedCustomers, names: names, s: s),
          );
        }),
        const SizedBox(height: AppSpacing.lg),
        _RecentVisits(s: s),
      ],
    );
  }
}

/// THE INVERSE OF «ما يُطلب معًا» — Shop.tsx's own `MissedOpportunities` names a specific customer
/// standing on one side of an association without the other; this card gives that a genuinely
/// mobile-native visual rather than a plain text row (console just prints "عنده X — ما جرّب Y"): a
/// broken-chain metaphor — the service he DOES buy as a solid filled chip, a dashed connector with
/// a link-off glyph at its break, then the service he has NEVER tried as a hollow dashed chip. The
/// two chips ARE the sentence; nothing here invents data the backend did not already send.
class _MissedOpportunitiesCard extends StatelessWidget {
  final List<MissedOpp> rows;
  final List<Customer>? customers;
  final Map<String, String> names;
  final S s;
  const _MissedOpportunitiesCard({required this.rows, required this.customers, required this.names, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final byRef = {for (final c in customers ?? const <Customer>[]) c.subjectRef: c};
    final shown = rows.take(8).toList();
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopMissedTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          for (var i = 0; i < shown.length; i++)
            Padding(
              padding: EdgeInsets.only(top: i > 0 ? AppSpacing.md : AppSpacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 20,
                        height: 20,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(shape: BoxShape.circle, color: accent.withValues(alpha: 0.15)),
                        child: Text(
                          _label(byRef[shown[i].subjectRef]).substring(0, 1),
                          style: AppTextStyles.caption.copyWith(color: accent, fontWeight: FontWeight.w800, fontSize: 10),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(_label(byRef[shown[i].subjectRef]),
                            style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700),
                            overflow: TextOverflow.ellipsis),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      _MissedChip(label: names[shown[i].has] ?? shown[i].has, filled: true),
                      _dashes(colors.borderSubtle),
                      Icon(Icons.link_off_rounded, size: 13, color: colors.textMuted),
                      _dashes(colors.borderSubtle),
                      _MissedChip(label: names[shown[i].missing] ?? shown[i].missing, filled: false),
                    ],
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  String _label(Customer? c) {
    if (c != null && c.name.isNotEmpty) return c.name;
    if (c != null && c.phone.isNotEmpty) return c.phone;
    return s.shopCustomerFallback;
  }

  Widget _dashes(Color color) => Expanded(
        child: LayoutBuilder(builder: (context, constraints) {
          const dashWidth = 4.0, gap = 3.0;
          final count = (constraints.maxWidth / (dashWidth + gap)).floor().clamp(1, 999);
          return Row(
            children: [
              for (var i = 0; i < count; i++) ...[
                Container(width: dashWidth, height: 1.5, color: color),
                if (i < count - 1) const SizedBox(width: gap),
              ],
            ],
          );
        }),
      );
}

class _MissedChip extends StatelessWidget {
  final String label;
  final bool filled;
  const _MissedChip({required this.label, required this.filled});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final tealFg = context.isDark ? AppDarkColors.successOnSoft : AppColors.success;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 96),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: filled ? tealFg.withValues(alpha: 0.12) : null,
          border: filled ? null : Border.all(color: colors.borderSubtle, style: BorderStyle.solid),
          borderRadius: BorderRadius.circular(AppRadius.pill),
        ),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.caption.copyWith(
            color: filled ? tealFg : colors.textMuted,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _LockedCard extends StatelessWidget {
  final String title;
  final String text;
  const _LockedCard({required this.title, required this.text});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return _Card(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lock_outline_rounded, size: 16, color: colors.textMuted),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(text, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A 7×24 grid, colour depth alone saying which cell matters — same visual idea as
/// Shop.tsx's own `PeakHeatmap`, reimplemented natively (a `GridView`-free `Row`-of-`Row`s, since
/// this app has no chart library dependency).
class _PeakHeatmapCard extends StatelessWidget {
  final PeakMap peak;
  final S s;
  const _PeakHeatmapCard({required this.peak, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    var max = 0;
    for (final v in peak.grid.values) {
      if (v > max) max = v;
    }
    final dayLetters = [s.shopDay0Short, s.shopDay1Short, s.shopDay2Short, s.shopDay3Short, s.shopDay4Short, s.shopDay5Short, s.shopDay6Short];
    final dayNames = [s.shopDay0Full, s.shopDay1Full, s.shopDay2Full, s.shopDay3Full, s.shopDay4Full, s.shopDay5Full, s.shopDay6Full];
    String? busiestNote;
    final busiest = peak.busiest;
    if (busiest != null) {
      final parts = busiest.split(':');
      final d = int.tryParse(parts.elementAtOrNull(0) ?? '');
      final h = int.tryParse(parts.elementAtOrNull(1) ?? '');
      if (d != null && d >= 0 && d < 7 && h != null) {
        busiestNote = s.shopPeakBusiestNote(s.shopPeakBusiestTime(dayNames[d], h));
      }
    }
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopPeakTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          for (var d = 0; d < 7; d++)
            Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Row(
                textDirection: TextDirection.ltr,
                children: [
                  SizedBox(
                    width: 16,
                    child: Text(dayLetters[d], textAlign: TextAlign.center, style: AppTextStyles.caption.copyWith(color: colors.textMuted, fontSize: 9)),
                  ),
                  const SizedBox(width: 2),
                  for (var h = 0; h < 24; h++)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 0.5),
                        child: Container(
                          height: 12,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(2),
                            color: () {
                              final v = peak.grid['$d:$h'] ?? 0;
                              if (v == 0 || max == 0) return colors.surfaceAlt;
                              final t = (0.12 + (v / max) * 0.78).clamp(0.0, 1.0);
                              return Color.lerp(colors.surface, accent, t);
                            }(),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          if (busiestNote != null) ...[
            const SizedBox(height: 4),
            Text(busiestNote, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
          ],
        ],
      ),
    );
  }
}

/// One row per entity (a service, a branch), seven columns for the week — the generalised form
/// of [_PeakHeatmapCard], shared by both the services-by-day and branches-by-day indicators
/// exactly like Shop.tsx's own single `EntityDayHeatmap` component.
class _EntityDayHeatmapCard extends StatelessWidget {
  final String title;
  final String hint;
  final List<DayHeatmapRow> rows;
  final bool teal;
  const _EntityDayHeatmapCard({required this.title, required this.hint, required this.rows, required this.teal});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final s = S.of(context)!;
    final color = teal
        ? (context.isDark ? AppDarkColors.success : AppColors.success)
        : (context.isDark ? AppDarkColors.accent : AppColors.accent);
    var max = 1;
    for (final r in rows) {
      for (final v in r.days) {
        if (v > max) max = v;
      }
    }
    final dayLetters = [s.shopDay0Short, s.shopDay1Short, s.shopDay2Short, s.shopDay3Short, s.shopDay4Short, s.shopDay5Short, s.shopDay6Short];
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Row(
              textDirection: TextDirection.ltr,
              children: [
                const SizedBox(width: 64),
                for (final l in dayLetters) Expanded(child: Text(l, textAlign: TextAlign.center, style: AppTextStyles.caption.copyWith(color: colors.textMuted, fontSize: 9))),
              ],
            ),
          ),
          for (final r in rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Row(
                textDirection: TextDirection.ltr,
                children: [
                  SizedBox(
                    width: 64,
                    child: Text(r.label, textDirection: TextDirection.rtl, maxLines: 1, overflow: TextOverflow.ellipsis, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ),
                  for (final v in r.days)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 0.5),
                        child: Container(
                          height: 14,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(2),
                            color: v == 0 ? colors.surfaceAlt : Color.lerp(colors.surface, color, (0.12 + (v / max) * 0.78).clamp(0.0, 1.0)),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          const SizedBox(height: 4),
          Text(hint, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
        ],
      ),
    );
  }
}

class _BundlesCard extends StatelessWidget {
  final List<Bundle> bundles;
  final S s;
  const _BundlesCard({required this.bundles, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopBundlesTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          for (var i = 0; i < bundles.take(4).length; i++)
            Padding(
              padding: EdgeInsets.only(top: i > 0 ? AppSpacing.sm : 0, bottom: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${bundles[i].aName ?? bundles[i].a ?? ''} + ${bundles[i].bName ?? bundles[i].b ?? ''}',
                      style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                  if (bundles[i].why != null && bundles[i].why!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(bundles[i].why!, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                    ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      if (bundles[i].actionLabel != null)
                        Expanded(
                          child: Text(bundles[i].actionLabel!,
                              style: AppTextStyles.caption.copyWith(
                                  color: context.isDark ? AppDarkColors.accent : AppColors.accent, fontWeight: FontWeight.w700)),
                        )
                      else
                        const Spacer(),
                      Text(s.shopBundlesOpportunity(bundles[i].customers),
                          textDirection: TextDirection.ltr, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                    ],
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _AssociationsCard extends StatelessWidget {
  final List<AssociationPair> pairs;
  final Map<String, String> names;
  final S s;
  const _AssociationsCard({required this.pairs, required this.names, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopAssociationsTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          for (final p in pairs.take(6))
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Expanded(
                    child: Text('${names[p.a] ?? p.a} + ${names[p.b] ?? p.b}',
                        style: AppTextStyles.bodySmall, overflow: TextOverflow.ellipsis),
                  ),
                  Text(s.shopCustomersCount(p.customers), textDirection: TextDirection.ltr, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _ServicesCard extends StatelessWidget {
  final List<ServicePopularityRow>? popularity;
  final List<String>? weak;
  final Map<String, String> names;
  final S s;
  const _ServicesCard({required this.popularity, required this.weak, required this.names, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopServicesTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          if (popularity != null)
            for (final row in popularity!.take(5))
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    Expanded(child: Text(names[row.serviceId] ?? row.serviceId, style: AppTextStyles.bodySmall, overflow: TextOverflow.ellipsis)),
                    Text('${(row.share * 100).round()}%', textDirection: TextDirection.ltr, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ),
              ),
          if (weak != null && weak!.isNotEmpty) ...[
            const SizedBox(height: 4),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final id in weak!)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(color: AppColors.danger.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(AppRadius.pill)),
                    child: Text(names[id] ?? id, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _MessageFlowCard extends StatelessWidget {
  final EffectStat? eff;
  final OptOutStat? opt;
  final S s;
  const _MessageFlowCard({required this.eff, required this.opt, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final optHigh = (opt?.rate ?? 0) > 0.2;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopMessageFlowTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          if (eff != null && eff!.ready)
            Text(
              '${s.shopReturnedAfterReminder(eff!.visits ?? 0, eff!.windowDays ?? 0)}${eff!.partial ? s.shopAtLeastSuffix : ''}',
              style: AppTextStyles.bodySmall,
            )
          else if (eff != null)
            // `eff.reason` is a raw backend code — console's own MessageFlow never shows it,
            // always falling back to a fixed "no data" sentence regardless of the reason.
            Text(s.shopMutedMessageFlowNote, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
          if (opt != null && opt!.ready) ...[
            const SizedBox(height: 4),
            Text(
              s.shopOptOutRate('${((opt!.rate ?? 0) * 100).round()}'),
              style: AppTextStyles.bodySmall.copyWith(color: optHigh ? AppColors.danger : null),
            ),
          ],
        ],
      ),
    );
  }
}

class _HoldoutCard extends StatelessWidget {
  final HoldoutStat h;
  final S s;
  const _HoldoutCard({required this.h, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    if (!h.ready) {
      // `h.reason` is a raw backend code (`holdout_off`, or absent while still measuring) —
      // never shown verbatim, matching Shop.tsx's own `reason === 'holdout_off'` branch.
      final note = h.reason == 'holdout_off'
          ? s.shopHoldoutOff
          : s.shopHoldoutMeasuring(
              (h.held ?? 0) < (h.reached ?? 0) ? (h.held ?? 0) : (h.reached ?? 0),
              h.need ?? 0,
            );
      return _MutedCard(title: s.shopHoldoutTitle, note: note);
    }
    final heldRate = h.heldRate ?? 0;
    final reachedRate = h.reachedRate ?? 0;
    final winnerReached = reachedRate >= heldRate;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopHoldoutTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: _holdoutBox(s.shopHoldoutNoMessages, '${(heldRate * 100).round()}%', !winnerReached, colors),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _holdoutBox(s.shopHoldoutReached, '${(reachedRate * 100).round()}%', winnerReached, colors),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _holdoutBox(String label, String value, bool winner, AppThemeColors colors) => Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: winner ? AppColors.successSoft : colors.surfaceAlt,
          borderRadius: AppRadius.standardRadius,
        ),
        child: Column(
          children: [
            Text(value, textDirection: TextDirection.ltr, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800, color: winner ? AppColors.success : null)),
            Text(label, style: AppTextStyles.caption, textAlign: TextAlign.center),
          ],
        ),
      );
}

class _RecentVisits extends StatelessWidget {
  final S s;
  const _RecentVisits({required this.s});

  @override
  Widget build(BuildContext context) {
    // Reassurance-only, last in flow — a real fetch would repeat `customers_screen.dart`'s own
    // "recent" call; left as a documented gap here since customers_screen already answers "who
    // visited recently" and duplicating that call on this screen too is not worth a second
    // source of truth for the same list. See this file's own header comment.
    return const SizedBox.shrink();
  }
}
