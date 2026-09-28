import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show Branch;
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/models/app_store_model.dart' show Owned;
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_style.dart';
import 'package:raje3_mobile/features/campaigns/message_preview_sheet.dart';
import 'package:raje3_mobile/features/campaigns/wa_flow_screens.dart';
import 'package:raje3_mobile/features/campaigns/whatsapp_bubble.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// THE OTHER DIRECTION FROM `kReasonGoal` (messages_model.dart) — goal → its shared reason id,
/// so the wizard can open the SAME preview/retext screen «القوالب» itself uses for the three
/// goals that share one, instead of building a second, smaller preview just for this screen.
const Map<String, String> _kGoalReasonId = {
  'win_back': 'gone_missing', 'occasion': 'personal_occasion', 'reward_loyal': 'loyal_customer',
};

/// Which goal gives which of three rewards — `models.py::REWARD_ENABLED_GOALS`.
const Set<String> _kRewardEnabledGoals = {
  'occasion', 'win_back', 'service_offer', 'package_offer', 'community_milestone',
};

/// Launching a campaign — a full-screen, step-by-step wizard (Launch.tsx's own job, rebuilt for
/// a phone instead of a wide rail+canvas+phone triptych). Three steps, and the middle one is the
/// product: goal, then a real message + real reach count, then one press to send.
///
/// THE PREVIEW-BEFORE-SEND STEP IS NON-NEGOTIABLE — this pass's own brief: a shop owner must see
/// exactly what real customers will receive, and how many, before any button that actually sends
/// anything. There is no path through this screen that reaches `createCampaign` without first
/// showing a successful `previewCampaign` answer.
///
/// STILL DEFERRED (documented, not silently dropped — see this feature's own build report): the
/// custom-text-editor + submit-to-WhatsApp + help-request flow (a slow human review cycle that
/// stays on the console for its first mobile pass), and opening a real interactive Flow from a
/// message button (the label renders; walking through its actual screens needs the
/// `WaFlowScreens`-equivalent renderer this pass does not build).
class LaunchWizardScreen extends StatefulWidget {
  const LaunchWizardScreen({super.key, required this.owned, this.initialGoal, this.branches = const []});

  /// Read once by the caller (`MessagesScreen`'s own `_loadAll`) rather than re-fetched here —
  /// this screen is reached only ever from that one place, and re-asking would just cost a
  /// second round trip for an answer the caller already has.
  final Owned? owned;

  /// ARRIVING WITH THE DECISION ALREADY MADE — a templates-tab cross-link names its own goal
  /// here so the owner never has to find it again on the goal grid (Messages.tsx's own
  /// `?launch=` note). Only pre-selects when the goal is actually AVAILABLE — an unreachable
  /// goal falls through to the normal picker instead of a dead pre-selection.
  final String? initialGoal;

  /// Same list `MessagesScreen`'s own log-tab branch filter already fetched once — passed
  /// through rather than asked for a second time.
  final List<Branch> branches;

  @override
  State<LaunchWizardScreen> createState() => _LaunchWizardScreenState();
}

enum _Step { goal, fields, preview }

class _LaunchWizardScreenState extends State<LaunchWizardScreen> {
  late final MessagesService _service;
  late final ServicesCatalogueService _catalogueService;

  _Step _step = _Step.goal;
  List<GoalRow>? _goals;
  GoalRow? _picked;
  List<ServiceItem> _services = const [];
  List<ServicePackage> _packages = const [];
  // ONLY TO LEARN which of the three shared goals has a real reason to cross-link to — never
  // read for anything else here, «القوالب» itself owns switching/retexting a reason.
  List<ReasonRow>? _reasons;

  final _ownerTextController = TextEditingController();
  final _offerAmountController = TextEditingController();
  final _rewardPointsController = TextEditingController();
  // `pct`/`sar` — TYPED, never folded into the free line the owner types (core/preview.py's own
  // `_OFFER` regex: `20%` or `50 ريال`, nothing else). A composed string is built from this and
  // the amount at the one point it is actually sent, never held as the source of truth itself.
  String _discountKind = 'pct';
  // SEVERAL SERVICES/PACKAGES, ONE OFFER — every one selected, in the order picked; the merged
  // message names all of them together (reminders' own `merged_service_text`).
  final List<String> _serviceIds = [];
  final List<String> _packageIds = [];
  DateTime? _endsOn;
  String _rewardType = 'discount';

  // «الهدف الجماعي» ONLY — the shared target the whole cohort is revealed at together
  // (services/campaigns/app/core/milestone.py). Meaningless for every other goal.
  final _milestoneThresholdController = TextEditingController();
  bool _milestoneRecurring = false;

  // «كافئ المخلصين»'s OWN THRESHOLDS — meaningless for every other goal.
  double _loyaltyWindowDays = 90;
  double _loyaltyMinVisits = 3;

  // THE OWNER'S OWN RECURRING WINDOW — collapsed by default; most campaigns need no window at all.
  bool _windowOn = false;
  double _windowStartHour = 9;
  double _windowEndHour = 21;
  final Set<int> _windowWeekdays = {};

  // WHEN IT LAUNCHES — every goal but `occasion`, which answers this with its own day below.
  bool _launchLater = false;
  DateTime? _launchDate;
  TimeOfDay _launchTime = const TimeOfDay(hour: 8, minute: 0);
  // THE DAY «هنّئ في مناسبة» IS ABOUT — the one goal whose trigger is a scheduled moment rather
  // than "now"; launching it with no day at all would create a campaign that silently never
  // fires (dispatch.py's own `fire_at == 0` guard treats it as "skip forever").
  DateTime? _occasionOn;

  String _branchId = '';

  CampaignPreview? _preview;
  bool _loadingPreview = false;
  bool _sending = false;
  String _error = '';

  // THE FIELDS STEP'S OWN LIVE PREVIEW — a small always-current answer shown WHILE he is still
  // filling the form, never waiting for the separate "next" press. Debounced: a slider or a
  // rapid string of taps fires many changes, and re-asking the server on every one of them would
  // flood the preview endpoint the same way a live-updating text field would. Additive only —
  // the explicit preview STEP (`_goToPreview`) is still the one gate before a real send, and
  // still calls the server itself rather than trusting this cached answer.
  CampaignPreview? _livePreview;
  Timer? _liveDebounce;

  void _mutate(VoidCallback fn) {
    setState(fn);
    _scheduleLivePreview();
  }

  void _scheduleLivePreview() {
    _liveDebounce?.cancel();
    _liveDebounce = Timer(const Duration(milliseconds: 350), () async {
      if (_picked == null) return;
      final p = await _service.previewCampaign(_buildBody());
      if (mounted) setState(() => _livePreview = p);
    });
  }

  static const _goalIcons = {
    'win_back': Icons.replay_circle_filled_rounded,
    'reward_loyal': Icons.workspace_premium_rounded,
    'announce': Icons.campaign_rounded,
    'service_offer': Icons.local_offer_rounded,
    'package_offer': Icons.card_giftcard_rounded,
    'occasion': Icons.cake_outlined,
    'community_milestone': Icons.track_changes_rounded,
  };

  @override
  void initState() {
    super.initState();
    final apiClient = context.read<AuthProvider>().apiClient;
    _service = MessagesService(apiClient: apiClient);
    _catalogueService = ServicesCatalogueService(apiClient: apiClient);
    _loadGoals();
    _service.reasons().then((r) {
      if (mounted) setState(() => _reasons = r);
    });
    _offerAmountController.addListener(_scheduleLivePreview);
    _rewardPointsController.addListener(_scheduleLivePreview);
    _ownerTextController.addListener(_scheduleLivePreview);
    _milestoneThresholdController.addListener(_scheduleLivePreview);
  }

  @override
  void dispose() {
    _liveDebounce?.cancel();
    _ownerTextController.dispose();
    _offerAmountController.dispose();
    _rewardPointsController.dispose();
    _milestoneThresholdController.dispose();
    super.dispose();
  }

  /// The composed, server-shaped offer value — built ONLY here, at the point it is actually
  /// read, never stored as its own piece of state (a single source of truth: the digits the
  /// owner typed, and the toggle he set).
  String get _offerValue {
    final n = _offerAmountController.text.trim();
    if (n.isEmpty) return '';
    return _discountKind == 'pct' ? '$n%' : '$n ريال';
  }

  bool get _rewardEnabled => _kRewardEnabledGoals.contains(_picked?.goal);

  bool get _isMilestone => _picked?.goal == 'community_milestone';

  int get _milestoneThreshold {
    final digits = _milestoneThresholdController.text.replaceAll(RegExp('[^0-9]'), '');
    return int.tryParse(digits) ?? 0;
  }

  /// THE MORNING OF HIS DAY, not its last minute — a greeting belongs at the start of the day.
  int get _occasionFireAt {
    if (_occasionOn == null) return 0;
    final d = _occasionOn!;
    final at = DateTime(d.year, d.month, d.day, 8).millisecondsSinceEpoch;
    return at ~/ 1000;
  }

  int get _generalFireAt {
    if (!_launchLater || _launchDate == null) return 0;
    final d = _launchDate!;
    final at = DateTime(d.year, d.month, d.day, _launchTime.hour, _launchTime.minute).millisecondsSinceEpoch;
    return at ~/ 1000;
  }

  int get _combinedFireAt => _picked?.goal == 'occasion' ? _occasionFireAt : _generalFireAt;

  int get _rewardPoints {
    if (_rewardType != 'points') return 0;
    final digits = _rewardPointsController.text.replaceAll(RegExp('[^0-9]'), '');
    return int.tryParse(digits) ?? 0;
  }

  Future<void> _loadGoals() async {
    final goals = await _service.goals();
    final services = await _catalogueService.list(includeRetired: false);
    final packages = await _catalogueService.listPackages();
    if (!mounted) return;
    final list = goals ?? const [];
    setState(() {
      _goals = list;
      _services = services ?? const [];
      _packages = (packages ?? const []).where((p) => p.active).toList();
      if (widget.initialGoal != null) {
        final match = list.where((g) => g.goal == widget.initialGoal && g.available).firstOrNull;
        if (match != null) {
          _picked = match;
          _step = _Step.fields;
        }
      }
    });
  }

  bool get _fieldsValid {
    final picked = _picked;
    if (picked == null) return false;
    if (picked.hasBlank('amount') && _offerAmountController.text.trim().isEmpty) return false;
    if (picked.hasBlank('date') && _endsOn == null) return false;
    if (picked.goal == 'service_offer' && _serviceIds.isEmpty) return false;
    if (picked.goal == 'package_offer' && _packageIds.isEmpty) return false;
    if (picked.goal == 'occasion' && _occasionOn == null) return false;
    if (_isMilestone) {
      // «الهدف الجماعي»'S OWN TWO REQUIREMENTS — a shared target under 2 is not a milestone
      // (`MIN_MILESTONE_THRESHOLD`, backend), it carries an end date even though its message has
      // no textual "date" blank, and a RECURRING round needs an explicit start too
      // (`validate_milestone_recurrence`) — answered by turning on «متى تُطلق: لاحقاً» below.
      if (_milestoneThreshold < 2) return false;
      if (_endsOn == null) return false;
      if (_milestoneRecurring && _combinedFireAt == 0) return false;
    }
    if (_rewardEnabled) {
      if (_rewardType == 'gift') {
        final needed = picked.goal == 'package_offer' ? _packageIds : _serviceIds;
        if (needed.isEmpty) return false;
      }
      if (_rewardType == 'points' && _rewardPoints <= 0) return false;
      if (_rewardType == 'discount' && picked.hasBlank('amount') && _offerAmountController.text.trim().isEmpty) return false;
    }
    return true;
  }

  Map<String, dynamic> _buildBody() {
    final expiresAt = _endsOn == null
        ? 0
        : DateTime(_endsOn!.year, _endsOn!.month, _endsOn!.day, 23, 59, 59)
            .millisecondsSinceEpoch ~/
            1000;
    final isPackage = _picked?.goal == 'package_offer';
    return {
      'goal': _picked!.goal,
      'owner_text': _ownerTextController.text.trim(),
      'service_ids': isPackage ? <String>[] : _serviceIds,
      'package_ids': isPackage ? _packageIds : <String>[],
      'loyalty_window_days': _loyaltyWindowDays.round(),
      'loyalty_min_visits': _loyaltyMinVisits.round(),
      'branch_id': _branchId,
      'offer_value': _offerValue,
      'service_names': isPackage ? <String>[] : _serviceIds.map((id) => _services.where((s) => s.id == id).firstOrNull?.name ?? '').toList(),
      'package_names': isPackage ? _packageIds.map((id) => _packages.where((p) => p.id == id).firstOrNull?.name ?? '').toList() : <String>[],
      'expires_at': expiresAt,
      'fire_at': _combinedFireAt,
      'window_start_hour': _windowOn ? _windowStartHour.round() : 0,
      'window_end_hour': _windowOn ? _windowEndHour.round() : 24,
      'window_weekdays': _windowOn ? _windowWeekdays.toList() : <int>[],
      'reward_type': _rewardEnabled ? _rewardType : 'discount',
      'reward_points': _rewardPoints,
      'milestone_threshold': _isMilestone ? _milestoneThreshold : 0,
      'milestone_recurring': _isMilestone && _milestoneRecurring,
    };
  }

  Future<void> _goToPreview() async {
    setState(() {
      _step = _Step.preview;
      _loadingPreview = true;
      _preview = null;
      _error = '';
    });
    final preview = await _service.previewCampaign(_buildBody());
    if (!mounted) return;
    setState(() {
      _loadingPreview = false;
      _preview = preview;
      if (preview == null) _error = ct(context, 'previewFailed');
    });
  }

  Future<void> _send() async {
    setState(() {
      _sending = true;
      _error = '';
    });
    final refusal = await _service.createCampaign(_buildBody());
    if (!mounted) return;
    if (refusal == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _sending = false;
      _error = refusal;
    });
  }

  @override
  Widget build(BuildContext context) {
    // SAME LOCK, SAME REASON as MessagesScreen's own campaigns tab (this screen is reached from
    // there, but a deep link or a stale nav stack could still land here directly) — never a
    // wizard that lets an unowned shop preview and press "launch" only to be refused by the
    // server at the very last step.
    if (widget.owned?.owns('feature.campaigns') == false) {
      return Scaffold(
        appBar: AppBar(title: Text(ct(context, 'title'))),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Text(ct(context, 'lockedWizardMsg'), textAlign: TextAlign.center),
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(switch (_step) {
          _Step.goal => ct(context, 'stepGoalTitle'),
          _Step.fields => _picked?.title ?? '',
          _Step.preview => ct(context, 'stepPreviewTitle'),
        }),
        leading: KbAnchor(
          id: 'campaigns.launch_wizard.back_button',
          child: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () {
              if (_step == _Step.fields) {
                setState(() => _step = _Step.goal);
              } else if (_step == _Step.preview) {
                setState(() => _step = _Step.fields);
              } else {
                Navigator.of(context).pop();
              }
            },
          ),
        ),
      ),
      body: SafeArea(
        child: switch (_step) {
          _Step.goal => _GoalStep(
              goals: _goals,
              icons: _goalIcons,
              onPick: (g) => setState(() {
                _picked = g;
                _step = _Step.fields;
                _livePreview = null;
                _milestoneThresholdController.clear();
                _milestoneRecurring = false;
              }),
            ),
          _Step.fields => _FieldsStep(
              goal: _picked!,
              linkedReason: (_reasons ?? const []).where((r) => r.id == _kGoalReasonId[_picked!.goal]).firstOrNull,
              services: _services,
              packages: _packages,
              ownerTextController: _ownerTextController,
              offerAmountController: _offerAmountController,
              discountKind: _discountKind,
              onDiscountKindChanged: (k) => _mutate(() => _discountKind = k),
              rewardEnabled: _rewardEnabled,
              rewardType: _rewardType,
              onRewardTypeChanged: (t) => _mutate(() => _rewardType = t),
              rewardPointsController: _rewardPointsController,
              milestoneThresholdController: _milestoneThresholdController,
              milestoneRecurring: _milestoneRecurring,
              onMilestoneRecurringChanged: (v) => _mutate(() => _milestoneRecurring = v),
              serviceIds: _serviceIds,
              packageIds: _packageIds,
              onServiceToggled: (id) => _mutate(() {
                _serviceIds.contains(id) ? _serviceIds.remove(id) : _serviceIds.add(id);
              }),
              onPackageToggled: (id) => _mutate(() {
                _packageIds.contains(id) ? _packageIds.remove(id) : _packageIds.add(id);
              }),
              endsOn: _endsOn,
              onDatePicked: (d) => _mutate(() => _endsOn = d),
              occasionOn: _occasionOn,
              onOccasionPicked: (d) => _mutate(() => _occasionOn = d),
              launchLater: _launchLater,
              onLaunchLaterChanged: (v) => _mutate(() => _launchLater = v),
              launchDate: _launchDate,
              onLaunchDatePicked: (d) => _mutate(() => _launchDate = d),
              launchTime: _launchTime,
              onLaunchTimePicked: (t) => _mutate(() => _launchTime = t),
              loyaltyWindowDays: _loyaltyWindowDays,
              loyaltyMinVisits: _loyaltyMinVisits,
              onLoyaltyWindowChanged: (v) => _mutate(() => _loyaltyWindowDays = v),
              onLoyaltyMinVisitsChanged: (v) => _mutate(() => _loyaltyMinVisits = v),
              windowOn: _windowOn,
              onWindowOnChanged: (v) => _mutate(() => _windowOn = v),
              windowStartHour: _windowStartHour,
              windowEndHour: _windowEndHour,
              onWindowStartChanged: (v) => _mutate(() => _windowStartHour = v),
              onWindowEndChanged: (v) => _mutate(() => _windowEndHour = v),
              windowWeekdays: _windowWeekdays,
              onWeekdayToggled: (d) => _mutate(() {
                _windowWeekdays.contains(d) ? _windowWeekdays.remove(d) : _windowWeekdays.add(d);
              }),
              branches: widget.branches,
              branchId: _branchId,
              onBranchChanged: (b) => _mutate(() => _branchId = b),
              livePreview: _livePreview,
              canContinue: _fieldsValid,
              onContinue: _goToPreview,
            ),
          _Step.preview => _PreviewStep(
              loading: _loadingPreview,
              preview: _preview,
              error: _error,
              sending: _sending,
              onSend: _send,
              service: _service,
              goal: _picked?.goal ?? '',
              owned: widget.owned,
              scopedCount: _picked?.goal == 'package_offer' ? _packageIds.length : _serviceIds.length,
            ),
        },
      ),
    );
  }
}

class _GoalStep extends StatefulWidget {
  const _GoalStep({required this.goals, required this.icons, required this.onPick});
  final List<GoalRow>? goals;
  final Map<String, IconData> icons;
  final ValueChanged<GoalRow> onPick;

  @override
  State<_GoalStep> createState() => _GoalStepState();
}

/// A search box for a handful of goals is a step that saves nothing — this is real code, not a
/// hardcoded skip: both thresholds are read from the goal list itself, so the search box and the
/// category rail appear on their own the day `campaigns.goals` ever grows past what a glance can
/// already scan, with zero further work here.
const int _kGoalSearchThreshold = 8;
const int _kGoalCategoryMinDistinct = 2;

class _GoalStepState extends State<_GoalStep> {
  String _search = '';
  String _category = '';

  @override
  Widget build(BuildContext context) {
    final goals = widget.goals;
    final icons = widget.icons;
    if (goals == null) return const Center(child: CircularProgressIndicator());
    if (goals.isEmpty) {
      return EmptyState(icon: Icons.campaign_outlined, title: ct(context, 'noGoalsAvailable'));
    }
    final categories = goals.map((g) => g.category).where((c) => c.isNotEmpty).toSet().toList();
    final showSearch = goals.length > _kGoalSearchThreshold;
    final showCategories = categories.length >= _kGoalCategoryMinDistinct;
    final q = _search.trim();
    final visible = goals
        .where((g) => _category.isEmpty || g.category == _category)
        .where((g) => q.isEmpty || g.title.contains(q) || g.line.contains(q))
        .toList();
    return Column(
      children: [
        if (showSearch)
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
            child: KbAnchor(
              id: 'campaigns.launch_wizard.goal_search_field',
              child: AppTextField(
                hintText: ct(context, 'goalSearchHint'),
                prefixIcon: Icons.search,
                onChanged: (v) => setState(() => _search = v),
              ),
            ),
          ),
        if (showCategories)
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
            child: SegmentedFilter<String>(
              value: _category,
              onChanged: (v) => setState(() => _category = v),
              options: [
                SegmentedFilterOption(value: '', label: ct(context, 'classAll'), badge: goals.length),
                for (final c in categories)
                  SegmentedFilterOption(value: c, label: c, badge: goals.where((g) => g.category == c).length),
              ],
            ),
          ),
        Expanded(
          child: visible.isEmpty
              ? EmptyState(icon: Icons.search_off_outlined, title: ct(context, 'noGoalsAvailable'))
              : GridView.builder(
      padding: const EdgeInsets.all(AppSpacing.md),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: AppSpacing.sm,
        mainAxisSpacing: AppSpacing.sm,
        childAspectRatio: 0.95,
      ),
      itemCount: visible.length,
      itemBuilder: (context, i) {
        final g = visible[i];
        final style = msgClassStyle(g.goal == 'announce' ? 'marketing' : 'offers', context.isDark);
        return AppCard(
          onTap: g.available ? () => widget.onPick(g) : null,
          child: Opacity(
            opacity: g.available ? 1 : 0.5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: style.gradient),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icons[g.goal] ?? Icons.campaign_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(g.title, style: AppTextStyles.labelMedium, maxLines: 2, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text(g.line, style: AppTextStyles.caption, maxLines: 2, overflow: TextOverflow.ellipsis),
                if (!g.available) ...[
                  const SizedBox(height: 4),
                  Row(children: [
                    const Icon(Icons.lock_outline, size: 12),
                    const SizedBox(width: 4),
                    Expanded(child: Text(g.unavailableReason, style: AppTextStyles.caption, maxLines: 1, overflow: TextOverflow.ellipsis)),
                  ]),
                ],
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

class _FieldsStep extends StatelessWidget {
  const _FieldsStep({
    required this.goal,
    required this.linkedReason,
    required this.services,
    required this.packages,
    required this.ownerTextController,
    required this.offerAmountController,
    required this.discountKind,
    required this.onDiscountKindChanged,
    required this.rewardEnabled,
    required this.rewardType,
    required this.onRewardTypeChanged,
    required this.rewardPointsController,
    required this.milestoneThresholdController,
    required this.milestoneRecurring,
    required this.onMilestoneRecurringChanged,
    required this.serviceIds,
    required this.packageIds,
    required this.onServiceToggled,
    required this.onPackageToggled,
    required this.endsOn,
    required this.onDatePicked,
    required this.occasionOn,
    required this.onOccasionPicked,
    required this.launchLater,
    required this.onLaunchLaterChanged,
    required this.launchDate,
    required this.onLaunchDatePicked,
    required this.launchTime,
    required this.onLaunchTimePicked,
    required this.loyaltyWindowDays,
    required this.loyaltyMinVisits,
    required this.onLoyaltyWindowChanged,
    required this.onLoyaltyMinVisitsChanged,
    required this.windowOn,
    required this.onWindowOnChanged,
    required this.windowStartHour,
    required this.windowEndHour,
    required this.onWindowStartChanged,
    required this.onWindowEndChanged,
    required this.windowWeekdays,
    required this.onWeekdayToggled,
    required this.branches,
    required this.branchId,
    required this.onBranchChanged,
    required this.livePreview,
    required this.canContinue,
    required this.onContinue,
  });

  final GoalRow goal;
  final ReasonRow? linkedReason;
  final List<ServiceItem> services;
  final List<ServicePackage> packages;
  final TextEditingController ownerTextController;
  final TextEditingController offerAmountController;
  final String discountKind;
  final ValueChanged<String> onDiscountKindChanged;
  final bool rewardEnabled;
  final String rewardType;
  final ValueChanged<String> onRewardTypeChanged;
  final TextEditingController rewardPointsController;
  final TextEditingController milestoneThresholdController;
  final bool milestoneRecurring;
  final ValueChanged<bool> onMilestoneRecurringChanged;
  final List<String> serviceIds;
  final List<String> packageIds;
  final ValueChanged<String> onServiceToggled;
  final ValueChanged<String> onPackageToggled;
  final DateTime? endsOn;
  final ValueChanged<DateTime> onDatePicked;
  final DateTime? occasionOn;
  final ValueChanged<DateTime> onOccasionPicked;
  final bool launchLater;
  final ValueChanged<bool> onLaunchLaterChanged;
  final DateTime? launchDate;
  final ValueChanged<DateTime> onLaunchDatePicked;
  final TimeOfDay launchTime;
  final ValueChanged<TimeOfDay> onLaunchTimePicked;
  final double loyaltyWindowDays;
  final double loyaltyMinVisits;
  final ValueChanged<double> onLoyaltyWindowChanged;
  final ValueChanged<double> onLoyaltyMinVisitsChanged;
  final bool windowOn;
  final ValueChanged<bool> onWindowOnChanged;
  final double windowStartHour;
  final double windowEndHour;
  final ValueChanged<double> onWindowStartChanged;
  final ValueChanged<double> onWindowEndChanged;
  final Set<int> windowWeekdays;
  final ValueChanged<int> onWeekdayToggled;
  final List<Branch> branches;
  final String branchId;
  final ValueChanged<String> onBranchChanged;
  /// THE FIELDS STEP'S OWN LIVE ANSWER — updates as he types/picks, debounced (see the state's
  /// own `_mutate`). Additive only: the explicit preview step ahead of this one is still the one
  /// real gate before `createCampaign`, and re-asks the server itself rather than trusting this.
  final CampaignPreview? livePreview;
  final bool canContinue;
  final VoidCallback onContinue;

  static const _weekdayKeys = ['weekdayMon', 'weekdayTue', 'weekdayWed', 'weekdayThu', 'weekdayFri', 'weekdaySat', 'weekdaySun'];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              // THE CROSS-LINK, THE OTHER DIRECTION — «القوالب»'s own card for this exact
              // shared template opens with a link into this wizard (Messages.tsx's own
              // `REASON_GOAL`); this is the same door from this side, reusing the identical
              // preview/retext sheet whole rather than a second, smaller one built just here.
              if (linkedReason != null) ...[
                SecondaryButton(
                  text: ct(context, 'viewOrEditMessage'),
                  icon: Icons.visibility_outlined,
                  onPressed: () => showMessagePreviewSheet(
                    context, label: linkedReason!.label, when: linkedReason!.when, reasonId: linkedReason!.id,
                    canRetext: linkedReason!.canRetext,
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.goal == 'service_offer') ...[
                Text(ct(context, 'whichService'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                for (final s in services)
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: Text(s.name),
                    value: serviceIds.contains(s.id),
                    onChanged: (_) => onServiceToggled(s.id),
                  ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.goal == 'package_offer') ...[
                Text(ct(context, 'whichPackage'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                for (final p in packages)
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: Text(p.name),
                    value: packageIds.contains(p.id),
                    onChanged: (_) => onPackageToggled(p.id),
                  ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (rewardEnabled) ...[
                Text(ct(context, 'rewardTitle'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                SegmentedFilter<String>(
                  value: rewardType,
                  onChanged: onRewardTypeChanged,
                  options: [
                    SegmentedFilterOption(value: 'discount', label: ct(context, 'rewardDiscount')),
                    SegmentedFilterOption(value: 'gift', label: ct(context, 'rewardGift')),
                    SegmentedFilterOption(value: 'points', label: ct(context, 'rewardPoints')),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                if (rewardType == 'discount')
                  // TYPED, NOT FREE TEXT — the server's own shape (core/preview.py's `_OFFER`
                  // regex) is exactly "20%" or "50 ريال": a percent 1-99 with no decimals, or an
                  // amount with up to 2. Composing it from a number + a real toggle means a shop
                  // can never type something the server refuses at the very last step.
                  Row(children: [
                    Expanded(
                      child: KbAnchor(
                        id: 'campaigns.launch_wizard.offer_amount_field',
                        child: AppTextField(
                          controller: offerAmountController,
                          hintText: discountKind == 'pct' ? '20' : '50',
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    SegmentedFilter<String>(
                      value: discountKind,
                      onChanged: onDiscountKindChanged,
                      options: [
                        const SegmentedFilterOption(value: 'pct', label: '%'),
                        SegmentedFilterOption(value: 'sar', label: ct(context, 'sar')),
                      ],
                    ),
                  ])
                else if (rewardType == 'points')
                  KbAnchor(
                    id: 'campaigns.launch_wizard.reward_points_field',
                    child: AppTextField(
                      controller: rewardPointsController,
                      hintText: ct(context, 'rewardPointsHint'),
                      keyboardType: TextInputType.number,
                    ),
                  )
                else
                  Text(ct(context, 'rewardGiftHint'), style: AppTextStyles.caption),
                const SizedBox(height: AppSpacing.md),
              ] else if (goal.hasBlank('amount'))
                ...[
                  Text(ct(context, 'discountAmount'), style: AppTextStyles.labelMedium),
                  const SizedBox(height: AppSpacing.sm),
                  Row(children: [
                    Expanded(
                      child: KbAnchor(
                        id: 'campaigns.launch_wizard.offer_amount_field',
                        child: AppTextField(
                          controller: offerAmountController,
                          hintText: discountKind == 'pct' ? '20' : '50',
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    SegmentedFilter<String>(
                      value: discountKind,
                      onChanged: onDiscountKindChanged,
                      options: [
                        const SegmentedFilterOption(value: 'pct', label: '%'),
                        SegmentedFilterOption(value: 'sar', label: ct(context, 'sar')),
                      ],
                    ),
                  ]),
                  const SizedBox(height: AppSpacing.md),
                ],
              if (goal.goal == 'reward_loyal') ...[
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: context.appColors.surfaceAlt,
                    borderRadius: AppRadius.standardRadius,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(ct(context, 'loyaltyTitle'), style: AppTextStyles.labelMedium),
                      Text(ct(context, 'loyaltyWindowLabel', {'n': '${loyaltyWindowDays.round()}'}), style: AppTextStyles.caption),
                      Slider(value: loyaltyWindowDays, min: 7, max: 365, onChanged: onLoyaltyWindowChanged),
                      Text(ct(context, 'loyaltyMinVisitsLabel', {'n': '${loyaltyMinVisits.round()}'}), style: AppTextStyles.caption),
                      Slider(value: loyaltyMinVisits, min: 1, max: 50, onChanged: onLoyaltyMinVisitsChanged),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.goal == 'community_milestone') ...[
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: context.appColors.surfaceAlt,
                    borderRadius: AppRadius.standardRadius,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(ct(context, 'milestoneTitle'), style: AppTextStyles.labelMedium),
                      const SizedBox(height: AppSpacing.sm),
                      Text(ct(context, 'milestoneThresholdLabel'), style: AppTextStyles.caption),
                      const SizedBox(height: 4),
                      KbAnchor(
                        id: 'campaigns.launch_wizard.milestone_threshold_field',
                        child: AppTextField(
                          controller: milestoneThresholdController,
                          hintText: '10',
                          keyboardType: TextInputType.number,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(ct(context, 'milestoneThresholdHint'), style: AppTextStyles.caption),
                      const SizedBox(height: AppSpacing.sm),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(ct(context, 'milestoneRecurringLabel'), style: AppTextStyles.labelMedium),
                        value: milestoneRecurring,
                        onChanged: onMilestoneRecurringChanged,
                      ),
                      if (milestoneRecurring)
                        Text(ct(context, 'milestoneRecurringHint'), style: AppTextStyles.caption),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.hasBlank('date') || goal.goal == 'community_milestone') ...[
                Text(ct(context, 'endsOnLabel'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                SecondaryButton(
                  text: endsOn == null
                      ? ct(context, 'pickEndDate')
                      : '${endsOn!.year}-${endsOn!.month.toString().padLeft(2, '0')}-${endsOn!.day.toString().padLeft(2, '0')}',
                  icon: Icons.calendar_today_outlined,
                  onPressed: () async {
                    final picked = await showDatePicker(
                      context: context,
                      initialDate: DateTime.now().add(const Duration(days: 7)),
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 365)),
                    );
                    if (picked != null) onDatePicked(picked);
                  },
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.goal == 'occasion') ...[
                Text(ct(context, 'occasionDayLabel'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                SecondaryButton(
                  text: occasionOn == null
                      ? ct(context, 'pickEndDate')
                      : '${occasionOn!.year}-${occasionOn!.month.toString().padLeft(2, '0')}-${occasionOn!.day.toString().padLeft(2, '0')}',
                  icon: Icons.cake_outlined,
                  onPressed: () async {
                    final picked = await showDatePicker(
                      context: context,
                      initialDate: DateTime.now().add(const Duration(days: 1)),
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 365)),
                    );
                    if (picked != null) onOccasionPicked(picked);
                  },
                ),
                const SizedBox(height: AppSpacing.md),
              ] else ...[
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(color: context.appColors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(ct(context, 'whenTitle'), style: AppTextStyles.labelMedium),
                      const SizedBox(height: AppSpacing.sm),
                      SegmentedFilter<bool>(
                        value: launchLater,
                        onChanged: onLaunchLaterChanged,
                        options: [
                          SegmentedFilterOption(value: false, label: ct(context, 'whenNow')),
                          SegmentedFilterOption(value: true, label: ct(context, 'whenLater')),
                        ],
                      ),
                      if (launchLater) ...[
                        const SizedBox(height: AppSpacing.sm),
                        Row(children: [
                          Expanded(
                            child: SecondaryButton(
                              text: launchDate == null
                                  ? ct(context, 'pickEndDate')
                                  : '${launchDate!.year}-${launchDate!.month.toString().padLeft(2, '0')}-${launchDate!.day.toString().padLeft(2, '0')}',
                              icon: Icons.calendar_today_outlined,
                              onPressed: () async {
                                final picked = await showDatePicker(
                                  context: context,
                                  initialDate: DateTime.now(),
                                  firstDate: DateTime.now(),
                                  lastDate: DateTime.now().add(const Duration(days: 365)),
                                );
                                if (picked != null) onLaunchDatePicked(picked);
                              },
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          SecondaryButton(
                            text: launchTime.format(context),
                            icon: Icons.access_time,
                            onPressed: () async {
                              final picked = await showTimePicker(context: context, initialTime: launchTime);
                              if (picked != null) onLaunchTimePicked(picked);
                            },
                          ),
                        ]),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (goal.hasBlank('owner')) ...[
                Text(ct(context, 'whatsNew'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                KbAnchor(
                  id: 'campaigns.launch_wizard.owner_text_field',
                  child: AppTextField(controller: ownerTextController, maxLines: 2, hintText: ct(context, 'ownerTextHint')),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              // THE RECURRING WINDOW — collapsed by default (this pass's own posture, same as
              // the console: most campaigns need no window, and a form opening with every
              // optional field expanded reads as more decisions than it is).
              Container(
                padding: const EdgeInsets.all(AppSpacing.sm),
                decoration: BoxDecoration(color: context.appColors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(ct(context, 'windowTitle'), style: AppTextStyles.labelMedium),
                      value: windowOn,
                      onChanged: onWindowOnChanged,
                    ),
                    if (windowOn) ...[
                      Text(ct(context, 'windowHoursLabel', {
                        'start': '${windowStartHour.round()}', 'end': '${windowEndHour.round()}',
                      }), style: AppTextStyles.caption),
                      RangeSlider(
                        values: RangeValues(windowStartHour, windowEndHour),
                        min: 0, max: 24, divisions: 24,
                        onChanged: (v) {
                          onWindowStartChanged(v.start);
                          onWindowEndChanged(v.end);
                        },
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Wrap(spacing: 6, children: [
                        for (var d = 0; d < 7; d++)
                          FilterChip(
                            label: Text(ct(context, _weekdayKeys[d])),
                            selected: windowWeekdays.contains(d),
                            onSelected: (_) => onWeekdayToggled(d),
                          ),
                      ]),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              // ESTIMATED FOR A SHOP WITH MORE THAN ONE PLACE — "target your only branch" is a
              // control that does nothing.
              if (branches.length > 1) ...[
                Text(ct(context, 'branchLabel'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                DropdownButtonFormField<String>(
                  initialValue: branchId,
                  items: [
                    DropdownMenuItem(value: '', child: Text(ct(context, 'allBranches'))),
                    for (final b in branches) DropdownMenuItem(value: b.id, child: Text(b.name)),
                  ],
                  onChanged: (v) => onBranchChanged(v ?? ''),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
            ],
          ),
        ),
        if (livePreview != null)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(color: context.appColors.surfaceAlt, borderRadius: AppRadius.standardRadius),
            child: Row(children: [
              const Icon(Icons.people_outline_rounded, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  ct(context, 'reachesLine', {'n': '${livePreview!.reaches}'}),
                  style: AppTextStyles.caption,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ]),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
          child: PrimaryButton(text: ct(context, 'nextPreview'), onPressed: canContinue ? onContinue : null),
        ),
      ],
    );
  }
}

/// Which Meta button (if any) the real send would attach — computed client-side, same as
/// Launch.tsx's own `flowEligible`/`singleItemButtonShown` logic: a booking Flow for the four
/// goals that end in "come back" when Bookings is owned, else a single-item quick-reply button
/// when exactly one service/package is scoped and both Bookings and the AI assistant are owned.
const Set<String> _kFlowEligibleGoals = {'win_back', 'occasion', 'service_offer', 'package_offer'};
const Set<String> _kButtonEligibleGoals = {
  'win_back', 'occasion', 'service_offer', 'package_offer', 'reward_loyal', 'announce',
};

List<MessageButton> _computeMessageButtons({
  required String goal,
  required Owned? owned,
  required int scopedCount,
}) {
  final hasBookings = owned?.owns('feature.bookings') == true;
  final hasAssistant = owned?.owns('feature.whatsapp') == true;
  final flowEligible = _kFlowEligibleGoals.contains(goal) && hasBookings;
  if (flowEligible) {
    return const [MessageButton(label: 'احجز الآن', kind: 'flow', flowName: 'booking')];
  }
  final singleItem = _kButtonEligibleGoals.contains(goal) && hasBookings && hasAssistant && scopedCount == 1;
  if (singleItem) {
    return const [MessageButton(label: 'تواصل معنا', kind: 'reply', flowName: '')];
  }
  return const [];
}

class _PreviewStep extends StatefulWidget {
  const _PreviewStep({
    required this.loading,
    required this.preview,
    required this.error,
    required this.sending,
    required this.onSend,
    required this.service,
    required this.goal,
    required this.owned,
    required this.scopedCount,
  });

  final bool loading;
  final CampaignPreview? preview;
  final String error;
  final bool sending;
  final VoidCallback onSend;
  final MessagesService service;
  final String goal;
  final Owned? owned;
  final int scopedCount;

  @override
  State<_PreviewStep> createState() => _PreviewStepState();
}

class _PreviewStepState extends State<_PreviewStep> {
  FlowJson? _openFlow;
  bool _flowLoading = false;
  String _flowError = '';

  Future<void> _pressButton(MessageButton b) async {
    if (b.kind != 'flow' || b.flowName.isEmpty) return;
    setState(() {
      _flowLoading = true;
      _flowError = '';
    });
    final flow = await widget.service.fetchFlowJson(b.flowName);
    if (!mounted) return;
    setState(() {
      _flowLoading = false;
      _openFlow = flow;
      if (flow == null) _flowError = ct(context, 'flowFetchFailed');
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.loading) return const Center(child: CircularProgressIndicator());
    if (widget.preview == null) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Text(widget.error.isNotEmpty ? widget.error : ct(context, 'previewGenericFailed'), style: AppTextStyles.bodyMedium),
      );
    }
    final p = widget.preview!;
    final blocked = p.spreadRefused.isNotEmpty || !p.templateActive;
    final buttons = _computeMessageButtons(goal: widget.goal, owned: widget.owned, scopedCount: widget.scopedCount);
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              WhatsAppPhoneFrame(
                child: _openFlow != null || _flowLoading || _flowError.isNotEmpty
                    ? (_flowLoading
                        ? const SizedBox(width: 300, height: 160, child: Center(child: CircularProgressIndicator(color: Colors.white)))
                        : _flowError.isNotEmpty
                            ? SizedBox(
                                width: 300,
                                child: Container(
                                  padding: const EdgeInsets.all(AppSpacing.md),
                                  decoration: BoxDecoration(color: Colors.white, borderRadius: AppRadius.cardRadius),
                                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                                    Text(_flowError, style: const TextStyle(color: Color(0xFFB7412F), fontSize: 13)),
                                    KbAnchor(
                                      id: 'campaigns.launch_wizard.flow_error_back',
                                      child: TextButton(onPressed: () => setState(() { _openFlow = null; _flowError = ''; }), child: Text(ct(context, 'backToMessage'))),
                                    ),
                                  ]),
                                ),
                              )
                            : WaFlowScreens(flow: _openFlow!, onDone: () => setState(() => _openFlow = null)))
                    : WhatsAppBubble(text: p.message, buttons: buttons, onPressButton: _pressButton),
              ),
              const SizedBox(height: AppSpacing.md),
              Row(children: [
                const Icon(Icons.people_outline_rounded, size: 18),
                const SizedBox(width: 6),
                Text(ct(context, 'reachesLine', {'n': '${p.reaches}'}), style: AppTextStyles.labelMedium),
              ]),
              if (p.when.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(p.when, style: AppTextStyles.bodySmall),
              ],
              if (p.excluded > 0) ...[
                const SizedBox(height: 4),
                Text(ct(context, 'excludedLine', {'n': '${p.excluded}'}), style: AppTextStyles.caption),
              ],
              if (p.tooRecent > 0) ...[
                const SizedBox(height: 4),
                Text(ct(context, 'tooRecentLine', {'n': '${p.tooRecent}'}), style: AppTextStyles.caption),
              ],
              if (!p.templateActive) ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(type: AlertType.warning, message: p.templateInactiveReason),
              ] else if (p.spreadRefused.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(type: AlertType.error, message: p.spreadRefused),
              ] else if (p.spreadSays.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(type: AlertType.success, message: p.spreadSays),
              ],
              for (final line in p.why) ...[
                const SizedBox(height: 4),
                Text(line, style: AppTextStyles.caption),
              ],
              if (widget.error.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Text(widget.error, style: AppTextStyles.bodySmall.copyWith(color: context.isDark ? AppDarkColors.danger : AppColors.danger)),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: PrimaryButton(
            text: ct(context, 'launchNowButton'),
            isLoading: widget.sending,
            onPressed: blocked ? null : widget.onSend,
          ),
        ),
      ],
    );
  }
}
