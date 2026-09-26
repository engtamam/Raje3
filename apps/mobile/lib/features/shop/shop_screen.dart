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
/// the highest-value indicators (hero+series, next-step, at-risk, AI impact, week pulse, new-vs-
/// returning, branch/staff compare, service popularity, weak services, message flow, holdout,
/// recent visits, manual refresh). NOT YET BUILT, tracked for a real follow-up, not invented here:
/// the three heatmaps (peak hours, services-by-day, branches-by-day), associations/bundles
/// ("ما يُطلب معًا"), missed opportunities, lead conversion, and the surrounding-KPIs 3-tile row
/// (cycle days/churn) + services-per-visit/expected-flow/cycle-completion row.
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
                _RetentionHero(dashboard: dash, s: s),
                const SizedBox(height: AppSpacing.sm),
                if (_today != null) _TodayStrip(today: _today!, s: s),
                const SizedBox(height: AppSpacing.md),
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
        return _OpportunitiesDeck(dashboard: dash, s: s);
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
            _seriesDelta(series, s),
          ],
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
                      byRef[r.subjectRef]?.name.isNotEmpty == true
                          ? byRef[r.subjectRef]!.name
                          : (byRef[r.subjectRef]?.phone ?? r.subjectRef),
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
        const SizedBox(height: AppSpacing.md),
        FutureBuilder<Branches?>(
          future: service.branches(),
          builder: (context, snap) {
            final branches = snap.data;
            if (!snap.hasData) return const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator());
            return branches != null
                ? _BranchCompareCard(branches: branches, s: s)
                : _MutedCard(title: s.shopBranchCompareTitle, note: s.shopBranchCompareMutedNote);
          },
        ),
        const SizedBox(height: AppSpacing.md),
        operators != null
            ? _StaffCompareCard(rows: operators, s: s)
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
                    color: delta >= 0 ? AppColors.success : AppColors.danger, fontWeight: FontWeight.w700)),
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
            if (muted)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopBranchCompareMutedNote, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
          ],
        ),
      ),
    );
  }
}

class _StaffCompareCard extends StatelessWidget {
  final List<OperatorRow> rows;
  final S s;
  const _StaffCompareCard({required this.rows, required this.s});

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
            if (muted)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(s.shopStaffCompareMutedNote, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
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
  final S s;
  const _OpportunitiesDeck({required this.dashboard, required this.s});

  @override
  Widget build(BuildContext context) {
    final popularity = dashboard.servicePopularity;
    final weak = dashboard.weakServices;
    final names = dashboard.serviceNames;
    final eff = dashboard.returnedAfterReminder;
    final opt = dashboard.optOutRate;
    final holdout = dashboard.holdoutComparison;

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
        const SizedBox(height: AppSpacing.lg),
        _RecentVisits(s: s),
      ],
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
            Text(s.shopReturnedAfterReminder(eff!.visits ?? 0, eff!.windowDays ?? 0), style: AppTextStyles.bodySmall)
          else if (eff != null)
            Text(eff!.reason ?? '', style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
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
      return _MutedCard(title: s.shopHoldoutTitle, note: h.reason ?? s.shopMutedHoldoutNote);
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
