import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show Branch;
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/app_store_model.dart' show Owned;
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_style.dart';
import 'package:raje3_mobile/features/campaigns/launch_wizard_screen.dart';
import 'package:raje3_mobile/features/campaigns/message_preview_sheet.dart';
import 'package:raje3_mobile/features/campaigns/whatsapp_bubble.dart';

/// «الحملات» — every message the shop sends in its own name: what fires automatically, what is
/// about to go, what the owner launches by hand, and what already happened. See
/// parity/messages.md for the full console-vs-mobile feature catalogue this screen is built
/// against.
///
/// THE HOME CONTENT IS THE STATUS ANSWER, NOT A LIST — opening this feature answers "is
/// everything working" in about a second (this pass's own explicit design decision, distinct
/// from the console where the same card sits small at the top of a dense desktop page). A shop
/// owner checking this mid-shift wants the answer before he wants a list to scroll.
class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> with SingleTickerProviderStateMixin {
  late final MessagesService _service;
  late final CustomersService _customersService;
  late final TabController _tabController;

  TodayStatus? _today;
  bool _todayFailed = false;
  List<ReasonRow>? _reasons;
  List<GoalRow>? _goals;
  List<ScheduleRow>? _schedule;
  List<Campaign>? _campaigns;
  List<MessageLogRow>? _log;
  bool _logDenied = false;
  bool _logLoaded = false;
  Owned? _owned;
  final Map<String, Customer> _who = {};
  String _logFilter = '';
  List<Branch> _branches = const [];
  String _logBranch = '';

  @override
  void initState() {
    super.initState();
    final auth = context.read<AuthProvider>();
    final apiClient = auth.apiClient;
    _service = MessagesService(apiClient: apiClient);
    _customersService = CustomersService(apiClient: apiClient);
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(() {
      if (_tabController.indexIsChanging) return;
      if (_tabController.index == 3 && _log == null) _loadLog();
    });
    _loadAll();
    auth.fetchBranches().then((r) {
      if (mounted && r != null) setState(() => _branches = r.branches);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    final auth = context.read<AuthProvider>();
    final results = await Future.wait([
      _service.today(),
      _service.reasons(),
      _service.goals(),
      _service.schedule(),
      _service.campaigns(),
      auth.fetchOwnership(),
    ]);
    if (!mounted) return;
    setState(() {
      _today = results[0] as TodayStatus?;
      _todayFailed = _today == null;
      _reasons = results[1] as List<ReasonRow>?;
      _goals = results[2] as List<GoalRow>?;
      _schedule = results[3] as List<ScheduleRow>?;
      _campaigns = results[4] as List<Campaign>?;
      _owned = results[5] as Owned?;
    });
    _resolveWho();
  }

  Future<void> _loadLog() async {
    final (rows, denied) = await _service.log(outcome: _logFilter, branchId: _logBranch);
    if (!mounted) return;
    setState(() {
      _log = rows;
      _logDenied = denied;
      _logLoaded = true;
    });
    _resolveWho();
  }

  Future<void> _resolveWho() async {
    final refs = <String>{
      ...((_schedule ?? const []).map((r) => r.subjectRef)),
      ...((_log ?? const []).map((r) => r.subjectRef)),
    }.where((r) => r.isNotEmpty && !_who.containsKey(r)).toList();
    if (refs.isEmpty) return;
    final rows = await _customersService.byRefs(refs);
    if (!mounted || rows == null) return;
    setState(() {
      for (final c in rows) {
        if (c.subjectRef.isNotEmpty) _who[c.subjectRef] = c;
      }
    });
  }

  /// ARRIVING WITH THE DECISION ALREADY MADE — a shared card's cross-link jumps straight into
  /// the wizard with its goal pre-picked (Messages.tsx's own `?launch=` note: a plain link that
  /// still makes him find the goal again is the same ask twice).
  Future<void> _openWizard({String? initialGoal}) async {
    final launched = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => LaunchWizardScreen(owned: _owned, initialGoal: initialGoal, branches: _branches)),
    );
    if (launched == true) {
      _loadAll();
      _tabController.animateTo(2);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.surface == AppColors.surface1
          ? AppColors.surface0
          : AppDarkColors.surface0,
      appBar: AppBar(title: Text(ct(context, 'title'))),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _log = null);
          await _loadAll();
          if (_tabController.index == 3) await _loadLog();
        },
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
                child: Column(
                  children: [
                    _TodayHero(status: _today, failed: _todayFailed),
                    const SizedBox(height: AppSpacing.md),
                    PrimaryButton(
                      text: ct(context, 'launchNew'),
                      icon: Icons.add_circle_outline,
                      onPressed: _openWizard,
                    ),
                    const SizedBox(height: AppSpacing.md),
                  ],
                ),
              ),
            ),
            SliverPersistentHeader(
              pinned: true,
              delegate: _TabBarDelegate(
                TabBar(
                  controller: _tabController,
                  isScrollable: false,
                  labelStyle: AppTextStyles.labelMedium,
                  tabs: [
                    Tab(text: ct(context, 'tabTemplates')),
                    Tab(text: ct(context, 'tabQueue')),
                    Tab(text: ct(context, 'title')),
                    Tab(text: ct(context, 'tabLog')),
                  ],
                ),
              ),
            ),
            SliverFillRemaining(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _TemplatesTab(
                    reasons: _reasons,
                    goals: _goals,
                    service: _service,
                    owned: _owned,
                    onChanged: _loadAll,
                    onCrossLink: (goal) => _openWizard(initialGoal: goal),
                  ),
                  _QueueTab(schedule: _schedule, who: _who, service: _service, onChanged: _loadAll),
                  _CampaignsTab(
                    campaigns: _campaigns,
                    goals: _goals,
                    service: _service,
                    owned: _owned,
                    onChanged: _loadAll,
                    onSubscribe: () => GoRouter.of(context).go('/apps'),
                  ),
                  _LogTab(
                    log: _log,
                    denied: _logDenied,
                    loaded: _logLoaded,
                    who: _who,
                    filter: _logFilter,
                    branches: _branches,
                    branchFilter: _logBranch,
                    onFilterChanged: (f) {
                      setState(() {
                        _logFilter = f;
                        _log = null;
                        _logLoaded = false;
                      });
                      _loadLog();
                    },
                    onBranchFilterChanged: (b) {
                      setState(() {
                        _logBranch = b;
                        _log = null;
                        _logLoaded = false;
                      });
                      _loadLog();
                    },
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

class _TabBarDelegate extends SliverPersistentHeaderDelegate {
  _TabBarDelegate(this.tabBar);
  final TabBar tabBar;

  @override
  double get minExtent => tabBar.preferredSize.height;
  @override
  double get maxExtent => tabBar.preferredSize.height;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(color: context.appColors.surface, child: tabBar);
  }

  @override
  bool shouldRebuild(covariant _TabBarDelegate oldDelegate) => oldDelegate.tabBar != tabBar;
}

/// THE ACTUAL LANDING CONTENT — a status hero, not a small card lost above a list. Blocked reads
/// as a real alert; healthy reads as a calm, confident gradient — the two states must never look
/// like the same widget with different text, or an owner scanning fast misses which one he's in.
/// GREEN | YELLOW | RED — Meta's own scale, mirrored from `reminders/core/ceiling.py`. Every
/// other value (NA/UNKNOWN) is deliberately unmapped: a quality we could not read is not
/// "متوسطة", it is nothing to say at all.
String? _qualityLabel(BuildContext context, String quality) {
  switch (quality) {
    case 'GREEN':
      return ct(context, 'qualityGreen');
    case 'YELLOW':
      return ct(context, 'qualityYellow');
    case 'RED':
      return ct(context, 'qualityRed');
    default:
      return null;
  }
}

/// When something already happened, in the words an owner uses — "today"/"yesterday"/"N days
/// ago" — same habit `_QueueTab`'s own future-facing `_dueIn` already keeps, just the past side.
String _whenPast(BuildContext context, int at) {
  if (at <= 0) return '';
  final days = ((DateTime.now().millisecondsSinceEpoch / 1000 - at) / 86400).floor();
  if (days <= 0) return ct(context, 'dueToday');
  if (days == 1) return ct(context, 'yesterday');
  return ct(context, 'daysAgo', {'n': '$days'});
}

class _TodayHero extends StatelessWidget {
  const _TodayHero({required this.status, required this.failed});

  final TodayStatus? status;
  final bool failed;

  @override
  Widget build(BuildContext context) {
    if (status == null) {
      return Container(
        height: 110,
        decoration: BoxDecoration(
          color: context.appColors.surfaceAlt,
          borderRadius: AppRadius.cardRadius,
        ),
        child: failed
            ? Center(child: Text(ct(context, 'todayReadFailed')))
            : const Center(child: CircularProgressIndicator()),
      );
    }
    final s = status!;
    if (s.blocked.isNotEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: context.isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: context.isDark ? AppDarkColors.danger : AppColors.danger),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.error_outline_rounded, color: context.isDark ? AppDarkColors.danger : AppColors.danger),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(ct(context, 'blockedTitle'), style: AppTextStyles.labelMedium),
                  const SizedBox(height: 4),
                  Text(s.blocked, style: AppTextStyles.bodySmall),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: context.isDark
              ? const [Color(0xFF241C4D), Color(0xFF0F332F)]
              : const [Color(0xFF7C3AED), Color(0xFF0C9C8D)],
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
        ),
        borderRadius: AppRadius.cardRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(ct(context, 'heroQuestion'),
              style: const TextStyle(color: Colors.white70, fontSize: 13, fontFamily: 'Cairo')),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(child: _HeroStat(value: s.sentToday, label: ct(context, 'statSent'))),
              Expanded(child: _HeroStat(value: s.waiting, label: ct(context, 'statWaiting'))),
              Expanded(child: _HeroStat(
                  value: s.retrying, label: ct(context, 'statRetrying'), warn: s.retrying > 0)),
            ],
          ),
          if (s.retryingReason.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(s.retryingReason,
                style: const TextStyle(color: Colors.white70, fontSize: 11, fontFamily: 'Cairo')),
          ],
          if (s.ceilingKnown && !s.ceilingUnlimited) ...[
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                const Icon(Icons.speed_rounded, color: Colors.white70, size: 14),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                      ct(context, 'ceilingLine', {
                        'remaining': '${s.ceilingRemaining}',
                        'limit': '${s.ceilingLimit}',
                      }) + (_qualityLabel(context, s.ceilingQuality) != null
                          ? ' · ${_qualityLabel(context, s.ceilingQuality)}'
                          : ''),
                      style: const TextStyle(color: Colors.white70, fontSize: 12, fontFamily: 'Cairo')),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _HeroStat extends StatelessWidget {
  const _HeroStat({required this.value, required this.label, this.warn = false});
  final int value;
  final String label;
  final bool warn;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('$value',
            style: TextStyle(
              color: warn ? const Color(0xFFFFE066) : Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              fontFamily: 'Cairo',
            )),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12, fontFamily: 'Cairo')),
      ],
    );
  }
}

/// «القوالب» — every message the system CAN send, once, grouped by class with a colour-coded
/// accent per Messages.tsx's own class taxonomy (service/personal/marketing) plus `offers` for
/// goal-only cards. Console's dense filterable table becomes swipeable/scrollable grouped cards —
/// this pass's own mobile-native brief.
class _TemplatesTab extends StatefulWidget {
  const _TemplatesTab({
    required this.reasons,
    required this.goals,
    required this.service,
    required this.owned,
    required this.onChanged,
    required this.onCrossLink,
  });

  final List<ReasonRow>? reasons;
  final List<GoalRow>? goals;
  final MessagesService service;
  final Owned? owned;
  final VoidCallback onChanged;
  final ValueChanged<String> onCrossLink;

  @override
  State<_TemplatesTab> createState() => _TemplatesTabState();
}

class _TemplatesTabState extends State<_TemplatesTab> {
  static const _order = ['service', 'personal', 'marketing', 'offers'];
  static const _sectionLabelKey = {
    'service': 'sectionService', 'personal': 'sectionPersonal',
    'marketing': 'sectionMarketing', 'offers': 'sectionOffers',
  };
  String _classFilter = '';
  // STACKABLE, NOT SINGLE-SELECT — both together means "automatic AND interactive", the same
  // Messages.tsx's own smart filter promises. On top of the class rail above, never instead of it.
  final Set<String> _tagFilters = {};

  @override
  Widget build(BuildContext context) {
    if (widget.reasons == null) return const Center(child: CircularProgressIndicator());
    final allCards = mergeTemplateCards(widget.reasons!, widget.goals ?? const []);
    if (allCards.isEmpty) {
      return EmptyState(icon: Icons.forum_outlined, title: ct(context, 'templatesEmpty'));
    }
    final cards = allCards
        .where((c) => !_tagFilters.contains('auto') || c.auto)
        .where((c) => !_tagFilters.contains('interactive') || c.interactive)
        .toList();
    // THE RAIL AS A HORIZONTAL CHIP BAR (Google Maps' own category-filter pattern: one
    // horizontally-scrollable row, each chip toggled, counted so a shop can see what's worth
    // opening before tapping it — never a hidden count that could go stale) — a phone has no
    // room for the console's own side-by-side rail-and-canvas layout.
    final sections = _order.where((s) => cards.any((c) => c.cls == s)).toList();
    final visible = _classFilter.isEmpty ? cards : cards.where((c) => c.cls == _classFilter).toList();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
          child: Wrap(spacing: AppSpacing.sm, children: [
            FilterChip(
              label: Text(ct(context, 'filterAutoOnly')),
              selected: _tagFilters.contains('auto'),
              onSelected: (v) => setState(() => v ? _tagFilters.add('auto') : _tagFilters.remove('auto')),
            ),
            FilterChip(
              label: Text(ct(context, 'filterInteractive')),
              selected: _tagFilters.contains('interactive'),
              onSelected: (v) => setState(() => v ? _tagFilters.add('interactive') : _tagFilters.remove('interactive')),
            ),
          ]),
        ),
        if (sections.length > 1)
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
            child: SegmentedFilter<String>(
              value: _classFilter,
              onChanged: (v) => setState(() => _classFilter = v),
              options: [
                SegmentedFilterOption(value: '', label: ct(context, 'classAll'), badge: cards.length),
                for (final s in sections)
                  SegmentedFilterOption(
                    value: s, label: ct(context, _sectionLabelKey[s]!),
                    badge: cards.where((c) => c.cls == s).length,
                  ),
              ],
            ),
          ),
        Expanded(
          child: cards.isEmpty
              ? EmptyState(icon: Icons.filter_alt_off_outlined, title: ct(context, 'templatesEmpty'))
              : ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              for (final section in (_classFilter.isEmpty ? sections : [_classFilter]))
                if (visible.any((c) => c.cls == section)) ...[
                  if (_classFilter.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                      child: Text(ct(context, _sectionLabelKey[section]!), style: AppTextStyles.labelMedium),
                    ),
                  for (final c in visible.where((c) => c.cls == section))
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: _TemplateCardTile(
                        card: c, service: widget.service, owned: widget.owned,
                        onChanged: widget.onChanged, onCrossLink: widget.onCrossLink,
                      ),
                    ),
                ],
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                child: Text(ct(context, 'templatesFootnote'), style: AppTextStyles.caption),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _TemplateCardTile extends StatefulWidget {
  const _TemplateCardTile({
    required this.card,
    required this.service,
    required this.owned,
    required this.onChanged,
    required this.onCrossLink,
  });
  final TemplateCard card;
  final MessagesService service;
  final Owned? owned;
  final VoidCallback onChanged;
  final ValueChanged<String> onCrossLink;

  @override
  State<_TemplateCardTile> createState() => _TemplateCardTileState();
}

class _TemplateCardTileState extends State<_TemplateCardTile> {
  bool _busy = false;

  static const _tplStatusKey = {
    'approved': 'tplApproved', 'pending': 'tplPending', 'paused': 'tplPaused',
    'disabled': 'tplDisabled', 'rejected': 'tplRejected', 'not_registered': 'tplNotRegistered',
  };

  Future<void> _flip(bool on) async {
    setState(() => _busy = true);
    await widget.service.setReason(widget.card.reason!.id, on);
    if (!mounted) return;
    setState(() => _busy = false);
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.card;
    final style = msgClassStyle(c.cls, context.isDark);
    // THE APP THIS REASON DEPENDS ON, IF ANY — never hides the card, only replaces the switch
    // with a lock, same rule the console's own `apps_store_screen.dart` paywall-bypass fix
    // established: a locked feature must still be reachable and explainable, never invisible.
    final appKey = kReasonApp[c.reason?.id ?? ''];
    final appLocked = appKey != null && widget.owned?.owns(appKey) == false;
    return AppCard(
      hasShadow: false,
      onTap: () => showMessagePreviewSheet(context,
          label: c.label, when: c.when, reasonId: c.reason?.id, templateType: c.reason == null ? c.goal : null,
          canRetext: c.reason?.canRetext ?? false),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: style.gradient, begin: Alignment.topLeft, end: Alignment.bottomRight),
              shape: BoxShape.circle,
            ),
            child: Icon(style.icon, color: Colors.white, size: 18),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Expanded(child: Text(c.label, style: AppTextStyles.bodyMedium, maxLines: 1, overflow: TextOverflow.ellipsis)),
                ]),
                Text(c.when, style: AppTextStyles.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
                Wrap(spacing: 4, runSpacing: 4, children: [
                  AppBadge(text: c.auto && c.manual
                      ? ct(context, 'tagBoth')
                      : c.auto ? ct(context, 'tagAuto') : ct(context, 'tagManual'),
                      backgroundColor: style.soft, textColor: style.onSoft),
                  if (_tplStatusKey.containsKey(c.templateStatus))
                    AppBadge(text: ct(context, _tplStatusKey[c.templateStatus]!)),
                  if (c.reason?.template.isNotEmpty == true)
                    AppBadge(text: ct(context, 'yourText')),
                  if (c.interactive)
                    AppBadge(
                      icon: Icons.touch_app_outlined,
                      text: ct(context, 'interactive'),
                      backgroundColor: context.isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
                      textColor: context.isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft,
                    ),
                  if (c.goal != null)
                    GestureDetector(
                      onTap: () => widget.onCrossLink(c.goal!),
                      child: AppBadge(
                        icon: Icons.arrow_outward_rounded,
                        text: ct(context, 'crossLink', {'goal': c.label}),
                      ),
                    ),
                ]),
              ],
            ),
          ),
          if (c.reason != null) ...[
            const SizedBox(width: AppSpacing.sm),
            if (appLocked)
              Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.lock_outline, size: 18),
                Text(ct(context, 'afterPurchase'), style: AppTextStyles.caption),
              ])
            else if (c.reason!.canSwitch)
              Switch(value: c.reason!.on, onChanged: _busy ? null : _flip, activeThumbColor: style.solid)
            else
              Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.lock_outline, size: 18),
                Text(ct(context, 'customerRight'), style: AppTextStyles.caption),
              ]),
          ],
        ],
      ),
    );
  }
}

/// «القادمة» — real people, by name, waiting for a message; swipe to cancel ONE of them, never
/// the rule behind it.
class _QueueTab extends StatefulWidget {
  const _QueueTab({required this.schedule, required this.who, required this.service, required this.onChanged});

  final List<ScheduleRow>? schedule;
  final Map<String, Customer> who;
  final MessagesService service;
  final VoidCallback onChanged;

  @override
  State<_QueueTab> createState() => _QueueTabState();
}

enum _Urgency { soon, today, later }

class _QueueTabState extends State<_QueueTab> {
  String _urgencyFilter = '';

  _Urgency _urgencyOf(int dueAt) {
    final secondsLeft = dueAt - DateTime.now().millisecondsSinceEpoch / 1000;
    if (secondsLeft <= 3600) return _Urgency.soon;
    if (secondsLeft <= 86400) return _Urgency.today;
    return _Urgency.later;
  }

  String _dueIn(BuildContext context, int at) {
    final secondsLeft = at - DateTime.now().millisecondsSinceEpoch / 1000;
    if (secondsLeft <= 0) return ct(context, 'queueOverdue');
    final days = (secondsLeft / 86400).round();
    if (days <= 0) return ct(context, 'dueToday');
    if (days == 1) return ct(context, 'dueTomorrow');
    return ct(context, 'dueInDays', {'n': '$days'});
  }

  String _occasion(BuildContext context, String kind) {
    switch (kind) {
      case 'reminder':
        return ct(context, 'occasionReminder');
      case 'follow_up':
        return ct(context, 'occasionFollowUp');
      case 'review_request':
        return ct(context, 'occasionReview');
      case 'campaign':
        return ct(context, 'occasionCampaign');
      default:
        return ct(context, 'occasionFallback');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.schedule == null) return const Center(child: CircularProgressIndicator());
    if (widget.schedule!.isEmpty) {
      return EmptyState(icon: Icons.schedule_outlined, title: ct(context, 'queueEmpty'));
    }
    final allRows = [...widget.schedule!]..sort((a, b) => a.dueAt.compareTo(b.dueAt));
    final rows = _urgencyFilter.isEmpty
        ? allRows
        : allRows.where((r) => _urgencyOf(r.dueAt).name == _urgencyFilter).toList();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: SegmentedFilter<String>(
            value: _urgencyFilter,
            onChanged: (v) => setState(() => _urgencyFilter = v),
            options: [
              SegmentedFilterOption(value: '', label: ct(context, 'classAll'), badge: allRows.length),
              for (final u in _Urgency.values)
                SegmentedFilterOption(
                  value: u.name,
                  label: ct(context, 'urgency${u.name[0].toUpperCase()}${u.name.substring(1)}'),
                  badge: allRows.where((r) => _urgencyOf(r.dueAt) == u).length,
                ),
            ],
          ),
        ),
        Expanded(
          child: rows.isEmpty
              ? EmptyState(icon: Icons.filter_alt_off_outlined, title: ct(context, 'queueEmpty'))
              : ListView.separated(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
            itemCount: rows.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) {
              final r = rows[i];
              final person = widget.who[r.subjectRef];
              final title = person?.name.isNotEmpty == true ? person!.name : (person?.phone ?? ct(context, 'customerFallback'));
              final urgent = _urgencyOf(r.dueAt) == _Urgency.soon;
              return Dismissible(
                key: ValueKey(r.id),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  decoration: BoxDecoration(
                      color: context.isDark ? AppDarkColors.danger : AppColors.danger,
                      borderRadius: AppRadius.cardRadius),
                  child: const Icon(Icons.close, color: Colors.white),
                ),
                confirmDismiss: (_) async {
                  final ok = await widget.service.cancelSchedule(r.id);
                  if (ok) widget.onChanged();
                  return ok;
                },
                child: AppCard(
                  hasShadow: false,
                  child: Row(
                    children: [
                      Container(
                        width: 8,
                        height: 40,
                        decoration: BoxDecoration(
                          color: urgent
                              ? (context.isDark ? AppDarkColors.danger : AppColors.danger)
                              : (context.isDark ? AppDarkColors.warning : AppColors.warning),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(title, style: AppTextStyles.bodyMedium),
                            Text('${_occasion(context, r.kind)} · ${_dueIn(context, r.dueAt)}', style: AppTextStyles.caption),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// «الحملات» — launched campaigns as swipeable cards, never a dense table. Tap opens its own
/// send-history detail; the "launch" action lives in the hero above, not duplicated here.
class _CampaignsTab extends StatelessWidget {
  const _CampaignsTab({
    required this.campaigns,
    required this.goals,
    required this.service,
    required this.owned,
    required this.onChanged,
    required this.onSubscribe,
  });

  final List<Campaign>? campaigns;
  final List<GoalRow>? goals;
  final MessagesService service;
  final Owned? owned;
  final VoidCallback onChanged;
  final VoidCallback onSubscribe;

  @override
  Widget build(BuildContext context) {
    // LOCKED ON THE ENTITLEMENT, NOT THE CAPABILITY — the app itself may not be owned even when
    // the operator's own role can see every `campaigns.*` action id (an owner always holds the
    // capability, regardless of which apps the shop has bought). The card stays visible with a
    // real way to buy it, same lesson `apps_store_screen.dart`'s own paywall-bypass fix already
    // taught this app: never hide a feature nobody can then discover, and never let a locked
    // feature be reached silently either.
    final ownsIt = owned?.owns('feature.campaigns');
    if (ownsIt == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (ownsIt == false) {
      return _LockedCampaigns(onSubscribe: onSubscribe);
    }
    if (campaigns == null) {
      return const CapabilityGate(
        requires: ['campaigns.list'],
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (campaigns!.isEmpty) {
      return EmptyState(icon: Icons.campaign_outlined, title: ct(context, 'campaignsEmptyTitle'),
          message: ct(context, 'campaignsEmptyMsg'));
    }
    final reach = (goals ?? const []).fold<int>(0, (sum, g) => sum + g.reach);
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        // THE THREE NUMBERS AN OWNER ACTUALLY WANTS AT A GLANCE — every one real: active count
        // and total from this same list, reach summed from the goals' own side counter
        // (`campaigns.goals`'s own `reach` field, already fetched for the templates tab — no
        // second network call). Messages.tsx's own note on why a redemption-rate tile is
        // deliberately left out applies here too: it needs every campaign's own `/runs` totals,
        // one call each, which does not belong on a screen that opens on every visit.
        Row(children: [
          Expanded(child: KpiTile(icon: Icons.play_circle_outline, tone: KpiTone.success,
              label: ct(context, 'stateActive'), value: '${campaigns!.where((c) => c.state == 'active').length}')),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: KpiTile(icon: Icons.bar_chart_rounded, tone: KpiTone.info,
              label: ct(context, 'title'), value: '${campaigns!.length}')),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: KpiTile(icon: Icons.people_outline_rounded, tone: KpiTone.neutral,
              label: ct(context, 'kpiReach'), value: '$reach')),
        ]),
        const SizedBox(height: AppSpacing.md),
        for (final c in campaigns!) ...[
          _CampaignCard(campaign: c, service: service, onChanged: onChanged, onTap: () => _openDetail(context, c)),
          const SizedBox(height: AppSpacing.sm),
        ],
      ],
    );
  }

  void _openDetail(BuildContext context, Campaign c) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _CampaignDetailSheet(campaign: c, service: service),
    );
  }
}

class _CampaignCard extends StatelessWidget {
  const _CampaignCard({required this.campaign, required this.service, required this.onChanged, required this.onTap});
  final Campaign campaign;
  final MessagesService service;
  final VoidCallback onChanged;
  final VoidCallback onTap;

  static const _goalTitleKey = {
    'win_back': 'goalWinBack', 'reward_loyal': 'goalRewardLoyal', 'announce': 'goalAnnounce',
    'occasion': 'goalOccasion', 'service_offer': 'goalServiceOffer', 'package_offer': 'goalPackageOffer',
  };
  static const _stateLabelKeys = {
    'active': 'stateActive', 'paused': 'statePaused', 'scheduled': 'stateScheduled', 'done': 'stateDone',
  };

  @override
  Widget build(BuildContext context) {
    final c = campaign;
    final state = msgStateStyle(c.state, c.isScheduled, context.isDark);
    final window = c.windowChip;
    return AppCard(
      hasShadow: false,
      onTap: onTap,
      child: Row(
        children: [
          Container(width: 8, height: 40,
              decoration: BoxDecoration(color: state.solid, borderRadius: BorderRadius.circular(4))),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_goalTitleKey.containsKey(c.goal) ? ct(context, _goalTitleKey[c.goal]!) : c.goal,
                    style: AppTextStyles.bodyMedium),
                Row(children: [
                  Flexible(child: Text(ct(context, 'reachedCount', {'n': '${c.sent}'}),
                      style: AppTextStyles.caption, overflow: TextOverflow.ellipsis)),
                  if (window != null) ...[
                    const SizedBox(width: 6),
                    const Icon(Icons.repeat_rounded, size: 11),
                    const SizedBox(width: 2),
                    Text(window, style: AppTextStyles.caption),
                  ],
                ]),
              ],
            ),
          ),
          AppBadge(
              text: ct(context, _stateLabelKeys[c.isScheduled ? 'scheduled' : c.state] ?? c.state),
              backgroundColor: state.soft, textColor: state.onSoft),
          if (c.state == 'active') ...[
            const SizedBox(width: 4),
            CapabilityGate(
              requires: const ['campaigns.pause'],
              child: IconButton(
                icon: const Icon(Icons.pause_circle_outline, size: 20),
                onPressed: () async {
                  await service.pauseCampaign(c.id);
                  onChanged();
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// THE TAB'S OWN LOCK STATE — always a real reason plus a real way to buy, never a blank/empty
/// list that reads as "you have no campaigns" when the true answer is "you don't own this yet".
class _LockedCampaigns extends StatelessWidget {
  const _LockedCampaigns({required this.onSubscribe});
  final VoidCallback onSubscribe;

  @override
  Widget build(BuildContext context) {
    final style = msgClassStyle('offers', context.isDark);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: style.gradient),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.lock_outline_rounded, color: Colors.white, size: 28),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(ct(context, 'lockedTitle'), style: AppTextStyles.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.sm),
            Text(
              ct(context, 'lockedDesc'),
              style: AppTextStyles.bodySmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            PrimaryButton(text: ct(context, 'subscribeNow'), icon: Icons.storefront_outlined, onPressed: onSubscribe),
          ],
        ),
      ),
    );
  }
}

class _CampaignDetailSheet extends StatefulWidget {
  const _CampaignDetailSheet({required this.campaign, required this.service});
  final Campaign campaign;
  final MessagesService service;

  @override
  State<_CampaignDetailSheet> createState() => _CampaignDetailSheetState();
}

class _CampaignDetailSheetState extends State<_CampaignDetailSheet> {
  (List<CampaignRun>, Map<String, int>)? _data;
  CampaignPreview? _preview;

  @override
  void initState() {
    super.initState();
    widget.service.runs(widget.campaign.id).then((d) {
      if (mounted) setState(() => _data = d);
    });
    // THE MESSAGE ITSELF — re-rendered from THIS campaign's own stored settings, the same
    // `campaigns.preview` call the wizard already makes, never a client-composed guess
    // (Messages.tsx's own `openRuns()` does the identical re-fetch).
    final c = widget.campaign;
    widget.service.previewCampaign({
      'goal': c.goal,
      'owner_text': c.ownerText,
      'service_ids': c.scopeServiceIds.isNotEmpty ? c.scopeServiceIds : (c.serviceId.isNotEmpty ? [c.serviceId] : <String>[]),
      'package_ids': c.packageId.isNotEmpty ? [c.packageId] : <String>[],
      'loyalty_window_days': c.loyaltyWindowDays,
      'loyalty_min_visits': c.loyaltyMinVisits,
      'branch_id': c.branchId,
      'offer_value': c.offerValue,
      'service_names': c.scopeServiceNames,
      'package_names': <String>[],
      'expires_at': c.expiresAt,
      'fire_at': c.fireAt,
      'window_start_hour': c.windowStartHour,
      'window_end_hour': c.windowEndHour,
      'window_weekdays': c.windowWeekdays,
      'reward_type': c.rewardType,
      'reward_points': c.rewardPoints,
    }).then((p) {
      if (mounted) setState(() => _preview = p);
    });
  }

  /// One bar per calendar day this campaign actually sent something, oldest first — real numbers
  /// only, never estimated (Messages.tsx's own `runsByDay()`).
  List<MapEntry<String, int>> _byDay() {
    final byDay = <String, int>{};
    final order = <String>[];
    for (final r in (_data?.$1 ?? const <CampaignRun>[]).reversed) {
      if (r.at <= 0) continue;
      final d = DateTime.fromMillisecondsSinceEpoch(r.at * 1000);
      final label = '${d.day}/${d.month}';
      if (!byDay.containsKey(label)) order.add(label);
      byDay[label] = (byDay[label] ?? 0) + r.sent;
    }
    return [for (final label in order) MapEntry(label, byDay[label]!)];
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final byDay = _byDay();
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: _data == null
          ? const Center(child: Padding(padding: EdgeInsets.all(AppSpacing.xl), child: CircularProgressIndicator()))
          : ListView(
              shrinkWrap: true,
              children: [
                Text(ct(context, 'whatHappened'), style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.sm),
                if (_preview?.message.isNotEmpty == true)
                  WhatsAppPhoneFrame(child: WhatsAppBubble(text: _preview!.message)),
                const SizedBox(height: AppSpacing.sm),
                if ((_data!.$2).isNotEmpty)
                  Wrap(spacing: AppSpacing.sm, runSpacing: AppSpacing.sm, children: [
                    for (final key in ['matched', 'sent', 'suppressed', 'redeemed'])
                      if (_data!.$2.containsKey(key))
                        KpiTile(icon: Icons.numbers, label: key, value: '${_data!.$2[key]}'),
                  ]),
                if (byDay.length > 1) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(ct(context, 'trendLabel'), style: AppTextStyles.labelMedium),
                  const SizedBox(height: AppSpacing.sm),
                  _TrendBars(days: byDay),
                ],
                const SizedBox(height: AppSpacing.md),
                for (final r in _data!.$1)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                                ct(context, 'runSummary', {'sent': '${r.sent}', 'suppressed': '${r.suppressed}'}),
                                style: AppTextStyles.bodySmall),
                            Text(_whenPast(context, r.at), style: AppTextStyles.caption),
                          ],
                        ),
                        if (r.reason.isNotEmpty)
                          Text(r.reason, style: AppTextStyles.caption),
                      ],
                    ),
                  ),
                if (_data!.$1.isEmpty)
                  Text(ct(context, 'noRunsYet'), style: AppTextStyles.bodySmall),
              ],
            ),
    );
  }
}

/// A plain bar-per-day trend — real sums only, no chart library: this feature's own bars, sized
/// relative to the busiest day.
class _TrendBars extends StatelessWidget {
  const _TrendBars({required this.days});
  final List<MapEntry<String, int>> days;

  @override
  Widget build(BuildContext context) {
    final maxV = days.map((e) => e.value).fold(1, (a, b) => a > b ? a : b);
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    return SizedBox(
      height: 80,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (final d in days)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('${d.value}', style: AppTextStyles.caption),
                    const SizedBox(height: 2),
                    Container(
                      height: 4 + 44 * (d.value / maxV),
                      decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(3)),
                    ),
                    const SizedBox(height: 2),
                    Text(d.key, style: AppTextStyles.caption),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// «السجل» — every send, with the real three-state receipt (قرأها/وصلت/خرجت) never a single
/// ambiguous "sent" colour.
class _LogTab extends StatelessWidget {
  const _LogTab({
    required this.log,
    required this.denied,
    required this.loaded,
    required this.who,
    required this.filter,
    required this.branches,
    required this.branchFilter,
    required this.onFilterChanged,
    required this.onBranchFilterChanged,
  });

  final List<MessageLogRow>? log;
  final bool denied;
  /// `false` is "still asking" (never confuse with a real failure); `true` with `log == null`
  /// and `!denied` is a real read failure — three states, three sentences, never one collapsed
  /// into another (MessagePreview.tsx's own header note applies here too).
  final bool loaded;
  final Map<String, Customer> who;
  final String filter;
  final List<Branch> branches;
  final String branchFilter;
  final ValueChanged<String> onFilterChanged;
  final ValueChanged<String> onBranchFilterChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(children: [
            SegmentedFilter<String>(
              value: filter,
              onChanged: onFilterChanged,
              options: [
                SegmentedFilterOption(value: '', label: ct(context, 'filterAll')),
                SegmentedFilterOption(value: 'sent', label: ct(context, 'statSent')),
                SegmentedFilterOption(value: 'suppressed', label: ct(context, 'filterSuppressed')),
              ],
            ),
            // SHOWN ONLY FOR A SHOP WITH MORE THAN ONE PLACE — "filter by your only branch" is a
            // control that does nothing (Messages.tsx's own note on the identical console field).
            if (branches.length > 1) ...[
              const SizedBox(height: AppSpacing.sm),
              SegmentedFilter<String>(
                value: branchFilter,
                onChanged: onBranchFilterChanged,
                options: [
                  SegmentedFilterOption(value: '', label: ct(context, 'allBranches')),
                  for (final b in branches) SegmentedFilterOption(value: b.id, label: b.name),
                  SegmentedFilterOption(value: '_none', label: ct(context, 'noBranch')),
                ],
              ),
            ],
          ]),
        ),
        Expanded(
          child: log == null
              ? (denied
                  ? EmptyState(icon: Icons.lock_outline, title: ct(context, 'logDenied'))
                  : loaded
                      ? EmptyState(icon: Icons.error_outline, title: ct(context, 'logFailed'))
                      : const Center(child: CircularProgressIndicator()))
              : log!.isEmpty
                  ? EmptyState(icon: Icons.receipt_long_outlined, title: ct(context, 'noRunsYet'))
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
                      itemCount: log!.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (context, i) {
                        final r = log![i];
                        final person = who[r.subjectRef];
                        final title = person?.name.isNotEmpty == true ? person!.name : (person?.phone ?? ct(context, 'customerFallback'));
                        final color = msgOutcomeColor(r.outcome, r.deliveredAt > 0, r.readAt > 0, context.isDark);
                        final outcomeLabel = r.outcome != 'sent'
                            ? ct(context, 'outcomeSuppressed')
                            : r.readAt > 0
                                ? ct(context, 'outcomeRead')
                                : r.deliveredAt > 0
                                    ? ct(context, 'outcomeDelivered')
                                    : ct(context, 'outcomeSent');
                        return AppCard(
                          hasShadow: false,
                          child: Row(
                            children: [
                              Container(width: 8, height: 36,
                                  decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4))),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(title, style: AppTextStyles.bodyMedium),
                                    if (r.reason.isNotEmpty)
                                      Text(r.reason, style: AppTextStyles.caption, maxLines: 2, overflow: TextOverflow.ellipsis),
                                  ],
                                ),
                              ),
                              AppBadge(text: outcomeLabel),
                            ],
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
