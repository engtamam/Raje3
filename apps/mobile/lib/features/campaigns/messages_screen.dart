import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_style.dart';
import 'package:raje3_mobile/features/campaigns/launch_wizard_screen.dart';
import 'package:raje3_mobile/features/campaigns/message_preview_sheet.dart';

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
  final Map<String, Customer> _who = {};
  String _logFilter = '';

  @override
  void initState() {
    super.initState();
    final apiClient = context.read<AuthProvider>().apiClient;
    _service = MessagesService(apiClient: apiClient);
    _customersService = CustomersService(apiClient: apiClient);
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(() {
      if (_tabController.indexIsChanging) return;
      if (_tabController.index == 3 && _log == null) _loadLog();
    });
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    final results = await Future.wait([
      _service.today(),
      _service.reasons(),
      _service.goals(),
      _service.schedule(),
      _service.campaigns(),
    ]);
    if (!mounted) return;
    setState(() {
      _today = results[0] as TodayStatus?;
      _todayFailed = _today == null;
      _reasons = results[1] as List<ReasonRow>?;
      _goals = results[2] as List<GoalRow>?;
      _schedule = results[3] as List<ScheduleRow>?;
      _campaigns = results[4] as List<Campaign>?;
    });
    _resolveWho();
  }

  Future<void> _loadLog() async {
    final rows = await _service.log(outcome: _logFilter);
    if (!mounted) return;
    setState(() => _log = rows);
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

  Future<void> _openWizard() async {
    final launched = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const LaunchWizardScreen()),
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
      appBar: AppBar(title: const Text('الحملات')),
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
                      text: 'أطلق رسالة جديدة',
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
                  tabs: const [
                    Tab(text: 'القوالب'),
                    Tab(text: 'القادمة'),
                    Tab(text: 'الحملات'),
                    Tab(text: 'السجل'),
                  ],
                ),
              ),
            ),
            SliverFillRemaining(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _TemplatesTab(reasons: _reasons, goals: _goals, service: _service, onChanged: _loadAll),
                  _QueueTab(schedule: _schedule, who: _who, service: _service, onChanged: _loadAll),
                  _CampaignsTab(campaigns: _campaigns, service: _service, onChanged: _loadAll),
                  _LogTab(
                    log: _log,
                    who: _who,
                    filter: _logFilter,
                    onFilterChanged: (f) {
                      setState(() {
                        _logFilter = f;
                        _log = null;
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
            ? const Center(child: Text('تعذّرت قراءة حالة اليوم.'))
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
                  const Text('الإرسال متوقف اليوم', style: AppTextStyles.labelMedium),
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
          const Text('هل كل شيء يعمل اليوم؟',
              style: TextStyle(color: Colors.white70, fontSize: 13, fontFamily: 'Cairo')),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(child: _HeroStat(value: s.sentToday, label: 'أُرسل')),
              Expanded(child: _HeroStat(value: s.waiting, label: 'بالانتظار')),
              Expanded(child: _HeroStat(value: s.retrying, label: 'يُعاد المحاولة', warn: s.retrying > 0)),
            ],
          ),
          if (s.ceilingKnown && !s.ceilingUnlimited) ...[
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                const Icon(Icons.speed_rounded, color: Colors.white70, size: 14),
                const SizedBox(width: 6),
                Text('المتبقي اليوم لدى واتساب: ${s.ceilingRemaining} من ${s.ceilingLimit}',
                    style: const TextStyle(color: Colors.white70, fontSize: 12, fontFamily: 'Cairo')),
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
class _TemplatesTab extends StatelessWidget {
  const _TemplatesTab({required this.reasons, required this.goals, required this.service, required this.onChanged});

  final List<ReasonRow>? reasons;
  final List<GoalRow>? goals;
  final MessagesService service;
  final VoidCallback onChanged;

  static const _order = ['service', 'personal', 'marketing', 'offers'];
  static const _sectionLabel = {
    'service': 'خدمية', 'personal': 'شخصية', 'marketing': 'تسويقية', 'offers': 'عروض',
  };

  @override
  Widget build(BuildContext context) {
    if (reasons == null) return const Center(child: CircularProgressIndicator());
    final cards = mergeTemplateCards(reasons!, goals ?? const []);
    if (cards.isEmpty) {
      return const EmptyState(icon: Icons.forum_outlined, title: 'لا رسائل مُعرَّفة بعد');
    }
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        for (final section in _order)
          if (cards.any((c) => c.cls == section)) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
              child: Text(_sectionLabel[section]!, style: AppTextStyles.labelMedium),
            ),
            for (final c in cards.where((c) => c.cls == section))
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: _TemplateCardTile(card: c, service: service, onChanged: onChanged),
              ),
          ],
      ],
    );
  }
}

class _TemplateCardTile extends StatefulWidget {
  const _TemplateCardTile({required this.card, required this.service, required this.onChanged});
  final TemplateCard card;
  final MessagesService service;
  final VoidCallback onChanged;

  @override
  State<_TemplateCardTile> createState() => _TemplateCardTileState();
}

class _TemplateCardTileState extends State<_TemplateCardTile> {
  bool _busy = false;

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
    return AppCard(
      hasShadow: false,
      onTap: () => showMessagePreviewSheet(context,
          label: c.label, when: c.when, reasonId: c.reason?.id, templateType: c.reason == null ? c.goal : null),
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
                  AppBadge(text: c.auto && c.manual ? 'آلي ويدوي' : c.auto ? 'آلي' : 'يدوي',
                      backgroundColor: style.soft, textColor: style.onSoft),
                ]),
                Text(c.when, style: AppTextStyles.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
          if (c.reason != null) ...[
            const SizedBox(width: AppSpacing.sm),
            if (c.reason!.canSwitch)
              Switch(value: c.reason!.on, onChanged: _busy ? null : _flip, activeThumbColor: style.solid)
            else
              const Icon(Icons.lock_outline, size: 18),
          ],
        ],
      ),
    );
  }
}

/// «القادمة» — real people, by name, waiting for a message; swipe to cancel ONE of them, never
/// the rule behind it.
class _QueueTab extends StatelessWidget {
  const _QueueTab({required this.schedule, required this.who, required this.service, required this.onChanged});

  final List<ScheduleRow>? schedule;
  final Map<String, Customer> who;
  final MessagesService service;
  final VoidCallback onChanged;

  String _dueIn(int at) {
    final secondsLeft = at - DateTime.now().millisecondsSinceEpoch / 1000;
    if (secondsLeft <= 0) return 'متأخّرة';
    final days = (secondsLeft / 86400).round();
    if (days <= 0) return 'اليوم';
    if (days == 1) return 'غدًا';
    return 'خلال $days أيام';
  }

  String _occasion(String kind) {
    switch (kind) {
      case 'reminder':
        return 'تذكير موعد';
      case 'follow_up':
        return 'متابعة بعد الزيارة';
      case 'review_request':
        return 'طلب تقييم';
      case 'campaign':
        return 'حملة';
      default:
        return 'رسالة';
    }
  }

  @override
  Widget build(BuildContext context) {
    if (schedule == null) return const Center(child: CircularProgressIndicator());
    if (schedule!.isEmpty) {
      return const EmptyState(icon: Icons.schedule_outlined, title: 'لا رسائل بانتظار الخروج الآن');
    }
    final rows = [...schedule!]..sort((a, b) => a.dueAt.compareTo(b.dueAt));
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: rows.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, i) {
        final r = rows[i];
        final person = who[r.subjectRef];
        final title = person?.name.isNotEmpty == true ? person!.name : (person?.phone ?? 'عميل');
        final urgent = r.dueAt - DateTime.now().millisecondsSinceEpoch / 1000 <= 3600;
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
            final ok = await service.cancelSchedule(r.id);
            if (ok) onChanged();
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
                      Text('${_occasion(r.kind)} · ${_dueIn(r.dueAt)}', style: AppTextStyles.caption),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// «الحملات» — launched campaigns as swipeable cards, never a dense table. Tap opens its own
/// send-history detail; the "launch" action lives in the hero above, not duplicated here.
class _CampaignsTab extends StatelessWidget {
  const _CampaignsTab({required this.campaigns, required this.service, required this.onChanged});

  final List<Campaign>? campaigns;
  final MessagesService service;
  final VoidCallback onChanged;

  static const _goalTitle = {
    'win_back': 'رجّع اللي غابوا', 'reward_loyal': 'كافئ المخلصين', 'announce': 'أعلن جديدك',
    'occasion': 'هنّئ في مناسبة', 'service_offer': 'عرض على خدمة', 'package_offer': 'عرض على باقة',
  };

  @override
  Widget build(BuildContext context) {
    if (campaigns == null) {
      return const CapabilityGate(
        requires: ['campaigns.list'],
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (campaigns!.isEmpty) {
      return const EmptyState(icon: Icons.campaign_outlined, title: 'لم تُطلق حملة بعد',
          message: 'اضغط «أطلق رسالة جديدة» بالأعلى للبدء');
    }
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: campaigns!.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, i) {
        final c = campaigns![i];
        final state = msgStateStyle(c.state, c.isScheduled, context.isDark);
        const stateLabels = {
          'active': 'نشطة', 'paused': 'متوقفة', 'scheduled': 'مجدولة', 'done': 'انتهت',
        };
        return AppCard(
          hasShadow: false,
          onTap: () => _openDetail(context, c),
          child: Row(
            children: [
              Container(width: 8, height: 40,
                  decoration: BoxDecoration(color: state.solid, borderRadius: BorderRadius.circular(4))),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_goalTitle[c.goal] ?? c.goal, style: AppTextStyles.bodyMedium),
                    Text('وصلت ${c.sent} عميلاً', style: AppTextStyles.caption),
                  ],
                ),
              ),
              AppBadge(text: stateLabels[c.isScheduled ? 'scheduled' : c.state] ?? c.state,
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
      },
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

class _CampaignDetailSheet extends StatefulWidget {
  const _CampaignDetailSheet({required this.campaign, required this.service});
  final Campaign campaign;
  final MessagesService service;

  @override
  State<_CampaignDetailSheet> createState() => _CampaignDetailSheetState();
}

class _CampaignDetailSheetState extends State<_CampaignDetailSheet> {
  (List<CampaignRun>, Map<String, int>)? _data;

  @override
  void initState() {
    super.initState();
    widget.service.runs(widget.campaign.id).then((d) {
      if (mounted) setState(() => _data = d);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
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
                const Text('ماذا حدث', style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.sm),
                if ((_data!.$2).isNotEmpty)
                  Wrap(spacing: AppSpacing.sm, runSpacing: AppSpacing.sm, children: [
                    for (final key in ['matched', 'sent', 'suppressed', 'redeemed'])
                      if (_data!.$2.containsKey(key))
                        KpiTile(icon: Icons.numbers, label: key, value: '${_data!.$2[key]}'),
                  ]),
                const SizedBox(height: AppSpacing.md),
                for (final r in _data!.$1)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('أُرسل ${r.sent} · امتنع ${r.suppressed}', style: AppTextStyles.bodySmall),
                      ],
                    ),
                  ),
                if (_data!.$1.isEmpty)
                  const Text('لا سجل إرسال بعد', style: AppTextStyles.bodySmall),
              ],
            ),
    );
  }
}

/// «السجل» — every send, with the real three-state receipt (قرأها/وصلت/خرجت) never a single
/// ambiguous "sent" colour.
class _LogTab extends StatelessWidget {
  const _LogTab({required this.log, required this.who, required this.filter, required this.onFilterChanged});

  final List<MessageLogRow>? log;
  final Map<String, Customer> who;
  final String filter;
  final ValueChanged<String> onFilterChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: SegmentedFilter<String>(
            value: filter,
            onChanged: onFilterChanged,
            options: const [
              SegmentedFilterOption(value: '', label: 'الكل'),
              SegmentedFilterOption(value: 'sent', label: 'أُرسل'),
              SegmentedFilterOption(value: 'suppressed', label: 'امتنع'),
            ],
          ),
        ),
        Expanded(
          child: log == null
              ? const Center(child: CircularProgressIndicator())
              : log!.isEmpty
                  ? const EmptyState(icon: Icons.receipt_long_outlined, title: 'لا سجل إرسال بعد')
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
                      itemCount: log!.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (context, i) {
                        final r = log![i];
                        final person = who[r.subjectRef];
                        final title = person?.name.isNotEmpty == true ? person!.name : (person?.phone ?? 'عميل');
                        final color = msgOutcomeColor(r.outcome, r.deliveredAt > 0, r.readAt > 0, context.isDark);
                        final outcomeLabel = r.outcome != 'sent'
                            ? 'امتنعت'
                            : r.readAt > 0
                                ? 'قرأها'
                                : r.deliveredAt > 0
                                    ? 'وصلت'
                                    : 'خرجت';
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
