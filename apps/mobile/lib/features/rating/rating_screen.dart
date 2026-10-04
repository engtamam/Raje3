import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/ratings_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/rating_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:go_router/go_router.dart';

import 'staff_quadrant.dart';
import 'package:raje3_mobile/widgets/date_time_picker_sheet.dart';

/// The three fixed windows Rating.tsx's own `rangeFor` offers, plus a custom pick — same days-back
/// counts (7/30/90), same "extend `until` to the end of that calendar day" rule for a custom range.
enum _Period { week, month, quarter, custom }

/// Which number ranks the podium/rest-of-staff list — never blended into one score, same
/// `METRICS` map Rating.tsx itself reads from (visits/ratings/avg), so "الأكثر زيارات" never
/// reads as "الأفضل تقييماً".
enum _Metric { visits, ratings, avg }

/// «التقييم» — mobile mirror of apps/console/src/screens/Rating.tsx's own DATA and BEHAVIOR
/// contract, EVERY piece of it (podium, quadrant, per-operator training drill-down, PDF/Word
/// export), built with an entirely different mobile-native STRUCTURE: two real tabs
/// («نظرة عامة» — insights a manager glances at; «كل التقييمات» — the raw filterable feed) instead
/// of the console's one long dashboard, never a single scroll that just restacks the console's
/// own sections in a different order.
class RatingScreen extends StatefulWidget {
  const RatingScreen({super.key});

  @override
  State<RatingScreen> createState() => _RatingScreenState();
}

enum _HandledFilter { unhandled, all, handled }

enum _MainTab { overview, feed }

class _RatingScreenState extends State<RatingScreen> {
  late final RatingsService _service;

  List<StaffPerformance>? _staff;
  bool _staffFailed = false;
  List<RatingRow>? _rows;
  String? _nextCursor;
  bool _loadingMore = false;
  bool _rowsFailed = false;
  bool _exporting = false;

  int _starFilter = 0;
  _HandledFilter _handledFilter = _HandledFilter.unhandled;
  String _stepFilter = '';
  String _stepFilterLabel = '';
  _MainTab _tab = _MainTab.overview;

  _Period _period = _Period.month;
  DateTime _customSince = DateTime.now().subtract(const Duration(days: 30));
  DateTime _customUntil = DateTime.now();
  _Metric _metric = _Metric.avg;
  String _exportLocale = 'ar';

  bool _localeInit = false;

  @override
  void initState() {
    super.initState();
    _service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    _loadStaff();
    _loadRows(reset: true);
    // A BRANCH SWITCH ELSEWHERE (the home hero's own chip) MUST REACH THIS SCREEN TOO — same
    // pattern visit_screen.dart's own today's-bookings card already holds to.
    context.read<BranchProvider>().addListener(_onBranchChanged);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // `Localizations.localeOf` reads an inherited widget — illegal in initState itself (found
    // live: "dependOnInheritedWidgetOfExactType... called before initState() completed"), so the
    // one-time default read happens here instead, guarded to run only once.
    if (!_localeInit) {
      _localeInit = true;
      _exportLocale = Localizations.localeOf(context).languageCode;
    }
  }

  @override
  void dispose() {
    context.read<BranchProvider>().removeListener(_onBranchChanged);
    super.dispose();
  }

  void _onBranchChanged() {
    if (!mounted) return;
    _loadStaff();
    _loadRows(reset: true);
  }

  String get _branchId => context.read<BranchProvider>().selectedId ?? '';

  /// `[since, until]`, unix seconds — Rating.tsx's own `rangeFor`, verbatim: the three fixed
  /// windows are just "N days back from now"; a custom range is exactly the two calendar days
  /// picked, `until` extended to the end of that day. `null` means the custom range is not usable
  /// yet (reversed), the caller's own signal never to fetch on it.
  ({int since, int until})? _range() {
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    if (_period == _Period.custom) {
      final since = DateTime(_customSince.year, _customSince.month, _customSince.day)
              .millisecondsSinceEpoch ~/
          1000;
      final until = DateTime(_customUntil.year, _customUntil.month, _customUntil.day)
                  .millisecondsSinceEpoch ~/
              1000 +
          86400 -
          1;
      if (until < since) return null;
      return (since: since, until: until);
    }
    final days = switch (_period) {
      _Period.week => 7,
      _Period.month => 30,
      _Period.quarter => 90,
      _Period.custom => 30,
    };
    return (since: now - days * 86400, until: now);
  }

  void _onPeriodChanged(_Period p) {
    setState(() => _period = p);
    _loadStaff();
  }

  Future<void> _loadStaff() async {
    final catalog = context.read<NavProvider>().catalog;
    // NEVER LEAVE `_staff` null FOREVER — a capability-less session or a failed fetch both
    // resolve into an empty list, the same "fail into nothing visible, not a spinner that never
    // ends" rule every other list load in this app already holds to (found live, 2026-09-22: the
    // Overview tab spun forever for a session without `operations.staff_performance`, since
    // nothing here ever set `_staff` at all).
    if (!catalog.hasAll(['operations.staff_performance'])) {
      if (mounted) setState(() => _staff = const []);
      return;
    }
    final range = _range();
    if (range == null) return; // an incomplete/reversed custom pick — leave _staff as it was
    setState(() {
      _staff = null;
      _staffFailed = false;
    });
    final staff = await _service.staffPerformance(
        since: range.since, until: range.until, branchId: _branchId);
    if (!mounted) return;
    setState(() {
      _staffFailed = staff == null;
      _staff = staff ?? const [];
    });
  }

  String get _handledParam => switch (_handledFilter) {
        _HandledFilter.unhandled => 'false',
        _HandledFilter.handled => 'true',
        _HandledFilter.all => '',
      };

  Future<void> _loadRows({required bool reset}) async {
    if (reset) {
      setState(() {
        _rows = null;
        _nextCursor = null;
        _rowsFailed = false;
      });
    } else {
      setState(() => _loadingMore = true);
    }
    final result = await _service.list(
      stars: _starFilter,
      handled: _handledParam,
      stepId: _stepFilter,
      cursor: reset ? '' : (_nextCursor ?? ''),
      branchId: _branchId,
    );
    if (!mounted) return;
    if (result == null) {
      setState(() {
        _rowsFailed = reset;
        _loadingMore = false;
        if (reset) _rows = [];
      });
      return;
    }
    setState(() {
      _rows = reset ? result.rows : [...?_rows, ...result.rows];
      _nextCursor = result.nextCursor;
      _loadingMore = false;
    });
  }

  Future<void> _markHandled(RatingRow r, String note) async {
    final s = S.of(context)!;
    final reason = await _service.markHandled(r.id, note: note);
    if (!mounted) return;
    if (reason == null) {
      if (_handledFilter == _HandledFilter.unhandled) {
        setState(() => _rows = _rows!.where((x) => x.id != r.id).toList());
      } else {
        _loadRows(reset: true);
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(reason.isNotEmpty ? reason : s.ratingActionFailed)),
      );
    }
  }

  void _setStepFilter(String id, String label) {
    setState(() {
      _tab = _MainTab.feed;
      _stepFilter = id;
      _stepFilterLabel = label;
    });
    _loadRows(reset: true);
  }

  Future<void> _openExportSheet() async {
    final s = S.of(context)!;
    var pickedLocale = _exportLocale;
    final format = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => StatefulBuilder(
        builder: (context, setSheetState) => Container(
          padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
          decoration: const BoxDecoration(
            color: AppColors.surface1,
            borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.ratingExportTitle, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.sm),
              Text(s.ratingExportHint,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
              const SizedBox(height: AppSpacing.md),
              _ExportLocaleField(
                value: pickedLocale,
                onChanged: (v) => setSheetState(() => pickedLocale = v),
              ),
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => Navigator.of(context).pop('pdf'),
                      icon: const Icon(Icons.picture_as_pdf_outlined),
                      label: const Text('PDF'),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => Navigator.of(context).pop('docx'),
                      icon: const Icon(Icons.description_outlined),
                      label: const Text('Word'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    if (format == null || !mounted) return;
    _exportLocale = pickedLocale;
    await _export(format);
  }

  Future<void> _export(String format) async {
    final s = S.of(context)!;
    final range = _range();
    if (range == null) return;
    setState(() => _exporting = true);
    final now = DateTime.now();
    final bytes = await _service.exportStaffPerformance(
        since: range.since,
        until: range.until,
        fileFormat: format,
        locale: _exportLocale,
        branchId: _branchId);
    if (!mounted) return;
    setState(() => _exporting = false);
    if (bytes == null || bytes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.ratingExportFailed)));
      return;
    }
    try {
      final dir = await getTemporaryDirectory();
      final ext = format == 'docx' ? 'docx' : 'pdf';
      final file = File('${dir.path}/rating_report_${now.millisecondsSinceEpoch}.$ext');
      await file.writeAsBytes(bytes);
      await SharePlus.instance.share(
        ShareParams(files: [XFile(file.path)], text: s.ratingExportTitle),
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.ratingExportFailed)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final totalRatings = _staff?.fold<int>(0, (a, b) => a + b.ratings) ?? 0;
    final weightedAvg = totalRatings > 0
        ? (_staff!.fold<double>(0, (a, b) => a + b.averageRating * b.ratings) / totalRatings)
        : 0.0;
    final unhandledCount = (_rows ?? const [])
        .where((r) => !r.isHandled)
        .length; // only reflects the currently-loaded page, an honest partial count

    final topIssues = _computeTopIssues(_rows ?? const []);

    return KbAnchor(
      id: 'rating',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: RefreshIndicator(
          onRefresh: () async {
            await Future.wait([_loadStaff(), _loadRows(reset: true)]);
          },
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: _RatingHero(
                  weightedAvg: weightedAvg,
                  totalRatings: totalRatings,
                  staffCount: _staff?.length ?? 0,
                  unhandledCount: unhandledCount,
                  exporting: _exporting,
                  onExport: _openExportSheet,
                ),
              ),
              if (_tab == _MainTab.overview)
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
                  sliver: SliverToBoxAdapter(
                    child: KbAnchor(
                      id: 'rating.period',
                      child: _PeriodSelector(
                        period: _period,
                        onChanged: _onPeriodChanged,
                        customSince: _customSince,
                        customUntil: _customUntil,
                        rangeInvalid: _period == _Period.custom && _range() == null,
                        onPickSince: () async {
                          final picked = await pickDaySheet(context,
                              initial: _customSince,
                              firstDate: DateTime(2020),
                              lastDate: _customUntil);
                          if (picked != null) {
                            setState(() => _customSince = picked);
                            _loadStaff();
                          }
                        },
                        onPickUntil: () async {
                          final picked = await pickDaySheet(context,
                              initial: _customUntil,
                              firstDate: _customSince,
                              lastDate: DateTime.now());
                          if (picked != null) {
                            setState(() => _customUntil = picked);
                            _loadStaff();
                          }
                        },
                      ),
                    ),
                  ),
                ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: KbAnchor(
                    id: 'rating.main_tabs',
                    child: SegmentedFilter<_MainTab>(
                      value: _tab,
                      onChanged: (v) => setState(() => _tab = v),
                      options: [
                        SegmentedFilterOption(value: _MainTab.overview, label: s.ratingTabOverview),
                        SegmentedFilterOption(
                            value: _MainTab.feed,
                            label: s.ratingTabFeed,
                            badge: (_rows ?? const []).length),
                      ],
                    ),
                  ),
                ),
              ),
              if (_tab == _MainTab.overview)
                ..._overviewSlivers(topIssues)
              else
                ..._feedSlivers(s),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _overviewSlivers(List<_TopIssue> topIssues) {
    final s = S.of(context)!;
    if (_staff == null) {
      return [const SliverPadding(padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator()))];
    }
    if (_staff!.isEmpty) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: _staffFailed
                ? EmptyState(
                    icon: Icons.cloud_off_rounded,
                    title: s.ratingLoadFailedTitle,
                    actionText: s.mobileRequestsRetry,
                    onAction: _loadStaff,
                  )
                : EmptyState(icon: Icons.insights_outlined, title: s.ratingOverviewEmpty),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, 0),
        sliver: SliverToBoxAdapter(
          child: _PodiumCard(
            staff: _staff!,
            metric: _metric,
            onMetricChanged: (m) => setState(() => _metric = m),
          ),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
        sliver: SliverToBoxAdapter(child: StaffQuadrantCard(staff: _staff!, service: _service)),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
        sliver: SliverToBoxAdapter(child: _StaffTableCard(staff: _staff!)),
      ),
      if (topIssues.isNotEmpty)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: _TopIssuesRow(issues: topIssues, onTap: _setStepFilter),
          ),
        )
      else
        const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),
    ];
  }

  List<Widget> _feedSlivers(S s) {
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
        sliver: SliverToBoxAdapter(
          child: KbAnchor(
            id: 'rating.filters',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_stepFilter.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: InputChip(
                      label: Text(s.ratingIssueFilterLabel(_stepFilterLabel)),
                      onDeleted: () {
                        setState(() {
                          _stepFilter = '';
                          _stepFilterLabel = '';
                        });
                        _loadRows(reset: true);
                      },
                    ),
                  ),
                SegmentedFilter<_HandledFilter>(
                  value: _handledFilter,
                  onChanged: (v) {
                    setState(() => _handledFilter = v);
                    _loadRows(reset: true);
                  },
                  options: [
                    SegmentedFilterOption(value: _HandledFilter.unhandled, label: s.ratingFilterUnhandled),
                    SegmentedFilterOption(value: _HandledFilter.all, label: s.ratingFilterAll),
                    SegmentedFilterOption(value: _HandledFilter.handled, label: s.ratingFilterHandled),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                SegmentedFilter<int>(
                  value: _starFilter,
                  onChanged: (v) {
                    setState(() => _starFilter = v);
                    _loadRows(reset: true);
                  },
                  options: [
                    SegmentedFilterOption(value: 0, label: s.ratingStarsAll),
                    for (final n in [5, 4, 3, 2, 1]) SegmentedFilterOption(value: n, label: '$n ★'),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      if (_rows == null)
        const SliverFillRemaining(hasScrollBody: false, child: BrandLoadingIndicator())
      else if (_rowsFailed)
        SliverFillRemaining(
          hasScrollBody: false,
          child: EmptyState(
            icon: Icons.cloud_off_rounded,
            title: s.ratingLoadFailedTitle,
            actionText: s.mobileRequestsRetry,
            onAction: () => _loadRows(reset: true),
          ),
        )
      else if (_rows!.isEmpty)
        SliverFillRemaining(
          hasScrollBody: false,
          child: EmptyState(icon: Icons.star_outline_rounded, title: s.ratingEmptyTitle),
        )
      else
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
          sliver: SliverList.separated(
            itemCount: _rows!.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) => _RatingCard(
              r: _rows![i],
              onMarkHandled: (note) => _markHandled(_rows![i], note),
              onOpenCustomer: _rows![i].customerId.isEmpty
                  ? null
                  : () => context.pushNamed(RouteNames.customerDetail,
                      pathParameters: {'customerId': _rows![i].customerId}),
            ),
          ),
        ),
      if (_rows != null && _rows!.isNotEmpty && _nextCursor != null)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: Center(
              child: _loadingMore
                  ? const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator(size: 24))
                  : TextButton(onPressed: () => _loadRows(reset: false), child: Text(s.ratingLoadMore)),
            ),
          ),
        )
      else
        const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),
    ];
  }
}

/// The export report's own language — separate from the app's UI language, the same `OperatorLocale`
/// set Rating.tsx's own `PrintLocalePicker` offers (rj-ui/PrintLocalePicker.tsx): ar/en/ur/ha/fil/bn.
class _ExportLocaleField extends StatelessWidget {
  const _ExportLocaleField({required this.value, required this.onChanged});
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final labels = {
      'ar': s.localeNameAr,
      'en': s.localeNameEn,
      'ur': s.localeNameUr,
      'ha': s.localeNameHa,
      'fil': s.localeNameFil,
      'bn': s.localeNameBn,
    };
    return Row(
      children: [
        Expanded(
          child: Text(s.ratingExportLocaleLabel, style: AppTextStyles.bodySmall),
        ),
        DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            value: value,
            isDense: true,
            items: [
              for (final entry in labels.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: (v) {
              if (v != null) onChanged(v);
            },
          ),
        ),
      ],
    );
  }
}

class _TopIssue {
  final String id;
  final String text;
  final String severity;
  final int count;
  const _TopIssue({required this.id, required this.text, required this.severity, required this.count});
}

List<_TopIssue> _computeTopIssues(List<RatingRow> rows) {
  final counts = <String, _TopIssue>{};
  for (final r in rows) {
    for (final step in r.issueSteps) {
      final existing = counts[step.id];
      counts[step.id] = _TopIssue(
        id: step.id,
        text: step.text,
        severity: step.severity,
        count: (existing?.count ?? 0) + 1,
      );
    }
  }
  final list = counts.values.toList()..sort((a, b) => b.count.compareTo(a.count));
  return list.take(5).toList();
}

/// Amber/gold gradient hero — «التقييم»'s own tone (features/home/app_tone.dart's real
/// `AppTone.warning` assignment for `'rating'`), deliberately NOT the brand-purple hero every
/// other screen's own header wears, so this app keeps its own visual identity at a glance.
class _RatingHero extends StatelessWidget {
  const _RatingHero({
    required this.weightedAvg,
    required this.totalRatings,
    required this.staffCount,
    required this.unhandledCount,
    required this.exporting,
    required this.onExport,
  });
  final double weightedAvg;
  final int totalRatings;
  final int staffCount;
  final int unhandledCount;
  final bool exporting;
  final VoidCallback onExport;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: dark
          ? [const Color(0xFFB8860B), const Color(0xFF8A6108)]
          : [const Color(0xFFF6B93B), const Color(0xFFE08E0B)],
    );

    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        child: Stack(
          children: [
            Positioned.directional(
              textDirection: Directionality.of(context),
              top: -30,
              end: -24,
              child: Container(
                width: 130,
                height: 130,
                decoration:
                    BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.10)),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(s.ratingTitle,
                              style: AppTextStyles.displaySmall.copyWith(color: Colors.white)),
                        ),
                        CapabilityGate(
                          requires: const ['operations.staff_performance_export'],
                          child: KbAnchor(
                            id: 'rating.export_button',
                            child: Material(
                              color: Colors.white.withValues(alpha: 0.18),
                              shape: const CircleBorder(),
                              clipBehavior: Clip.antiAlias,
                              child: InkWell(
                                onTap: exporting ? null : onExport,
                                child: SizedBox(
                                  width: 38,
                                  height: 38,
                                  child: exporting
                                      ? const Padding(
                                          padding: EdgeInsets.all(9),
                                          child: CircularProgressIndicator(
                                              color: Colors.white, strokeWidth: 2),
                                        )
                                      : const Icon(Icons.ios_share_rounded, size: 18, color: Colors.white),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          totalRatings > 0 ? weightedAvg.toStringAsFixed(1) : '—',
                          style: AppTextStyles.displaySmall
                              .copyWith(color: Colors.white, fontSize: 40, height: 1),
                        ),
                        const SizedBox(width: 6),
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            children: List.generate(
                              5,
                              (i) => Icon(
                                i < weightedAvg.round() ? Icons.star_rounded : Icons.star_border_rounded,
                                size: 16,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(s.ratingWeightedAvgHint(totalRatings),
                            style: AppTextStyles.bodySmall
                                .copyWith(color: Colors.white.withValues(alpha: 0.85))),
                        if (staffCount > 0) ...[
                          const SizedBox(width: 6),
                          const Icon(Icons.circle, size: 3, color: Colors.white54),
                          const SizedBox(width: 6),
                          Text(s.ratingStaffCount(staffCount),
                              style: AppTextStyles.bodySmall
                                  .copyWith(color: Colors.white.withValues(alpha: 0.85))),
                        ],
                      ],
                    ),
                    if (unhandledCount > 0) ...[
                      const SizedBox(height: AppSpacing.md),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.priority_high_rounded, size: 14, color: Colors.white),
                            const SizedBox(width: 4),
                            Text(s.ratingUnhandledCount(unhandledCount),
                                style: AppTextStyles.caption
                                    .copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A real podium — 1st place raised and centered with a crown, 2nd/3rd flanking it lower, medal-
/// toned bases — the mobile-native shape this ranking actually deserves, never a plain numbered
/// list (which is what the console itself renders as a table row).
/// The number each metric ranks by — visits/ratings/average, never blended into one score, same
/// `METRICS` map Rating.tsx's own leaderboard reads from.
num _metricValue(_Metric m, StaffPerformance s) => switch (m) {
      _Metric.visits => s.visits,
      _Metric.ratings => s.ratings,
      _Metric.avg => s.averageRating,
    };

class _PodiumCard extends StatelessWidget {
  const _PodiumCard({required this.staff, required this.metric, required this.onMetricChanged});
  final List<StaffPerformance> staff;
  final _Metric metric;
  final ValueChanged<_Metric> onMetricChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final eligible = metric == _Metric.avg ? staff.where((x) => x.ratings > 0).toList() : staff;
    final ranked = [...eligible]
      ..sort((a, b) => _metricValue(metric, b).compareTo(_metricValue(metric, a)));
    if (ranked.isEmpty) return const SizedBox.shrink();
    final top = ranked.take(3).toList();
    final rest = ranked.skip(3).toList();

    final first = top[0];
    final second = top.length > 1 ? top[1] : null;
    final third = top.length > 2 ? top[2] : null;

    return KbAnchor(
      id: 'rating.leaderboard',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.ratingLeaderboardTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: AppSpacing.sm),
            SegmentedFilter<_Metric>(
              value: metric,
              onChanged: onMetricChanged,
              options: [
                SegmentedFilterOption(value: _Metric.visits, label: s.ratingMetricVisits),
                SegmentedFilterOption(value: _Metric.ratings, label: s.ratingMetricRatings),
                SegmentedFilterOption(value: _Metric.avg, label: s.ratingMetricAvg),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                    child: second != null
                        ? _PodiumSlot(p: second, place: 2, metric: metric)
                        : const SizedBox()),
                const SizedBox(width: 6),
                Expanded(
                    flex: 0,
                    child: SizedBox(
                        width: 96, child: _PodiumSlot(p: first, place: 1, metric: metric))),
                const SizedBox(width: 6),
                Expanded(
                    child: third != null
                        ? _PodiumSlot(p: third, place: 3, metric: metric)
                        : const SizedBox()),
              ],
            ),
            if (rest.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              for (var i = 0; i < rest.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 20,
                        child: Text('${i + 4}',
                            textAlign: TextAlign.center,
                            style: AppTextStyles.caption.copyWith(
                                color: context.appColors.textMuted, fontWeight: FontWeight.w700)),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        width: 26,
                        height: 26,
                        decoration: BoxDecoration(
                          color: context.appColors.surfaceAlt,
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text(
                            rest[i].operatorName.isNotEmpty
                                ? rest[i].operatorName.substring(0, 1).toUpperCase()
                                : '?',
                            style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(rest[i].operatorName.isNotEmpty ? rest[i].operatorName : s.ratingCardNoName,
                            style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
                      ),
                      Text(
                        metric == _Metric.avg
                            ? rest[i].averageRating.toStringAsFixed(1)
                            : '${_metricValue(metric, rest[i])}',
                        style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary),
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PodiumSlot extends StatelessWidget {
  const _PodiumSlot({required this.p, required this.place, required this.metric});
  final StaffPerformance p;
  final int place;
  final _Metric metric;

  static const _medalColors = {
    1: Color(0xFFF6B93B),
    2: Color(0xFFB8C0CC),
    3: Color(0xFFCD8B5C),
  };

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final medal = _medalColors[place]!;
    final barHeight = place == 1 ? 64.0 : (place == 2 ? 44.0 : 32.0);
    final avatarSize = place == 1 ? 52.0 : 40.0;

    return Column(
      children: [
        if (place == 1) const Icon(Icons.emoji_events_rounded, color: Color(0xFFF6B93B), size: 20),
        const SizedBox(height: 4),
        Container(
          width: avatarSize,
          height: avatarSize,
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [medal, medal.withValues(alpha: 0.75)]),
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(color: medal.withValues(alpha: 0.4), blurRadius: 8, offset: const Offset(0, 3))],
          ),
          child: Center(
            child: Text(p.operatorName.isNotEmpty ? p.operatorName.substring(0, 1).toUpperCase() : '?',
                style: AppTextStyles.bodyMedium.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
          ),
        ),
        const SizedBox(height: 6),
        Text(p.operatorName, maxLines: 1, overflow: TextOverflow.ellipsis, style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w700)),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.star_rounded, size: 11, color: Color(0xFFF6B93B)),
            const SizedBox(width: 2),
            Text(p.averageRating.toStringAsFixed(1), style: AppTextStyles.caption),
          ],
        ),
        Text(s.ratingVisitsShort(p.visits),
            style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted, fontSize: 10)),
        const SizedBox(height: 6),
        Container(
          height: barHeight,
          decoration: BoxDecoration(
            color: medal.withValues(alpha: 0.18),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.sm)),
            border: Border(top: BorderSide(color: medal, width: 3)),
          ),
          alignment: Alignment.topCenter,
          padding: const EdgeInsets.only(top: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('$place',
                  style: AppTextStyles.labelMedium.copyWith(color: medal, fontWeight: FontWeight.w900)),
              if (place == 1)
                Text(
                  switch (metric) {
                    _Metric.visits => s.ratingMetricVisits,
                    _Metric.ratings => s.ratingMetricRatings,
                    _Metric.avg => s.ratingMetricAvg,
                  },
                  style: AppTextStyles.caption.copyWith(color: medal, fontSize: 9),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// The full per-operator table — every column Rating.tsx's own table has (visits, ratings,
/// engagement %, average, no-show %) — a stacked list of rows here, never a horizontally-scrolled
/// table (the mobile-native shape a phone-width table always needs).
class _StaffTableCard extends StatelessWidget {
  const _StaffTableCard({required this.staff});
  final List<StaffPerformance> staff;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return KbAnchor(
      id: 'rating.staff_table',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.ratingTableTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: AppSpacing.sm),
            for (final row in staff)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  children: [
                    Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(color: colors.surfaceAlt, shape: BoxShape.circle),
                      child: Center(
                        child: Text(
                          row.operatorName.isNotEmpty ? row.operatorName.substring(0, 1).toUpperCase() : '?',
                          style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(row.operatorName.isNotEmpty ? row.operatorName : s.ratingCardNoName,
                              style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                          Wrap(
                            spacing: 8,
                            children: [
                              Text(s.ratingTableVisitsValue(row.visits),
                                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                              Text(s.ratingTableRatingsValue(row.ratings),
                                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                              Text(
                                s.ratingTableEngagementValue(
                                    row.visits > 0 ? ((row.ratings / row.visits) * 100).round() : 0),
                                style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.star_rounded, size: 12, color: Color(0xFFF6B93B)),
                            const SizedBox(width: 2),
                            Text(row.averageRating.toStringAsFixed(1), style: AppTextStyles.caption),
                          ],
                        ),
                        Text(
                          s.ratingTableNoShowValue((row.noShowRate * 100).round()),
                          style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// The period switch — week/month/quarter/custom, same `Period` union Rating.tsx's own header
/// control offers. Custom shows two date fields under it, never a range picker widget (the app's
/// own `pickDaySheet` is the single day-only picker this codebase uses everywhere, per its own
/// doc comment on the Eastern-Arabic-digit bug it sidesteps).
class _PeriodSelector extends StatelessWidget {
  const _PeriodSelector({
    required this.period,
    required this.onChanged,
    required this.customSince,
    required this.customUntil,
    required this.rangeInvalid,
    required this.onPickSince,
    required this.onPickUntil,
  });
  final _Period period;
  final ValueChanged<_Period> onChanged;
  final DateTime customSince;
  final DateTime customUntil;
  final bool rangeInvalid;
  final VoidCallback onPickSince;
  final VoidCallback onPickUntil;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SegmentedFilter<_Period>(
          value: period,
          onChanged: onChanged,
          options: [
            SegmentedFilterOption(value: _Period.week, label: s.ratingPeriodWeek),
            SegmentedFilterOption(value: _Period.month, label: s.ratingPeriodMonth),
            SegmentedFilterOption(value: _Period.quarter, label: s.ratingPeriodQuarter),
            SegmentedFilterOption(value: _Period.custom, label: s.ratingPeriodCustom),
          ],
        ),
        if (period == _Period.custom) ...[
          const SizedBox(height: AppSpacing.sm),
          KbAnchor(
            id: 'rating.custom_range_pickers',
            child: Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onPickSince,
                  child: Text(
                      s.ratingCustomSince(Formatters.formatDateShort(customSince, locale: locale))),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: OutlinedButton(
                  onPressed: onPickUntil,
                  child: Text(
                      s.ratingCustomUntil(Formatters.formatDateShort(customUntil, locale: locale))),
                ),
              ),
            ],
            ),
          ),
          if (rangeInvalid) ...[
            const SizedBox(height: 4),
            Text(s.ratingCustomRangeInvalid,
                style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
          ],
        ],
      ],
    );
  }
}

class _TopIssuesRow extends StatelessWidget {
  const _TopIssuesRow({required this.issues, required this.onTap});
  final List<_TopIssue> issues;
  final void Function(String id, String label) onTap;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'rating.top_issues',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.ratingTopIssuesTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.xs),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final issue in issues) ...[
                  Material(
                    color: issue.severity == 'critical'
                        ? (context.isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft)
                        : context.appColors.surfaceAlt,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                    child: InkWell(
                      onTap: () => onTap(issue.id, issue.text),
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        child: Text('${issue.text} (${issue.count})',
                            style: AppTextStyles.caption.copyWith(
                              color: issue.severity == 'critical'
                                  ? (context.isDark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft)
                                  : context.appColors.textSecondary,
                              fontWeight: FontWeight.w600,
                            )),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xs),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RatingCard extends StatelessWidget {
  const _RatingCard({
    required this.r,
    required this.onMarkHandled,
    required this.onOpenCustomer,
  });
  final RatingRow r;
  final ValueChanged<String> onMarkHandled;
  final VoidCallback? onOpenCustomer;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final colors = context.appColors;
    final dark = context.isDark;
    final low = r.rating <= 2;

    return KbAnchor(
      id: 'rating.rating_card',
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(
            color: low && !r.isHandled
                ? AppColors.danger.withValues(alpha: 0.35)
                : colors.borderSubtle,
          ),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Row(
                  children: List.generate(
                    5,
                    (i) => Icon(
                      i < r.rating ? Icons.star_rounded : Icons.star_border_rounded,
                      size: 16,
                      color: const Color(0xFFF6B93B),
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  Formatters.formatTimeAgo(
                      DateTime.fromMillisecondsSinceEpoch(r.ratedAt * 1000), locale: locale),
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                ),
              ],
            ),
            const SizedBox(height: 6),
            InkWell(
              onTap: onOpenCustomer,
              child: Text(
                r.customerName.isNotEmpty ? r.customerName : s.customersUnnamed,
                style: AppTextStyles.bodyMedium.copyWith(
                  fontWeight: FontWeight.w700,
                  color: colors.textPrimary,
                  decoration: onOpenCustomer != null ? TextDecoration.underline : null,
                  decorationColor: colors.borderSubtle,
                ),
              ),
            ),
            if (r.operatorName.isNotEmpty)
              Text(s.ratingByOperator(r.operatorName),
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            if (r.feedbackText.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(r.feedbackText, style: AppTextStyles.bodySmall),
            ],
            if (r.issueSteps.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final step in r.issueSteps)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: step.severity == 'critical'
                            ? (dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft)
                            : (dark ? AppDarkColors.warningSoft : AppColors.warningSoft),
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                      ),
                      child: Text(step.text,
                          style: AppTextStyles.caption.copyWith(
                            color: step.severity == 'critical'
                                ? (dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft)
                                : (dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
                            fontWeight: FontWeight.w600,
                          )),
                    ),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            if (r.isHandled)
              Row(
                children: [
                  Icon(Icons.check_circle_rounded,
                      size: 14, color: dark ? AppDarkColors.successOnSoft : AppColors.successOnSoft),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      r.ratingHandledNote.isNotEmpty
                          ? s.ratingHandledWithNote(r.ratingHandledNote)
                          : s.ratingHandledPlain,
                      style: AppTextStyles.caption.copyWith(
                          color: dark ? AppDarkColors.successOnSoft : AppColors.successOnSoft),
                    ),
                  ),
                ],
              )
            else
              CapabilityGate(
                requires: const ['operations.mark_rating_handled'],
                child: KbAnchor(
                  id: 'rating.mark_handled_button',
                  child: SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => _openHandleSheet(context, s),
                      icon: const Icon(Icons.check_rounded, size: 16),
                      label: Text(s.ratingMarkHandled),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _openHandleSheet(BuildContext context, S s) async {
    final controller = TextEditingController();
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: Container(
          padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
          decoration: const BoxDecoration(
            color: AppColors.surface1,
            borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.ratingMarkHandled, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.sm),
              Text(s.ratingMarkHandledHint,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'rating.handled_note_field',
                child: AppTextField(labelText: s.ratingHandledNoteLabel, controller: controller, maxLines: 3),
              ),
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(
                text: s.ratingMarkHandledConfirm,
                onPressed: () => Navigator.of(context).pop(true),
              ),
            ],
          ),
        ),
      ),
    );
    if (confirmed == true) onMarkHandled(controller.text.trim());
  }
}
