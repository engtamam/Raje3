import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/models/app_store_model.dart' show Owned;
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_style.dart';
import 'package:raje3_mobile/features/campaigns/whatsapp_bubble.dart';

/// Launching a campaign — a full-screen, step-by-step wizard (Launch.tsx's own job, rebuilt for
/// a phone instead of a wide rail+canvas+phone triptych). Three steps, and the middle one is the
/// product: goal, then a real message + real reach count, then one press to send.
///
/// THE PREVIEW-BEFORE-SEND STEP IS NON-NEGOTIABLE — this pass's own brief: a shop owner must see
/// exactly what real customers will receive, and how many, before any button that actually sends
/// anything. There is no path through this screen that reaches `createCampaign` without first
/// showing a successful `previewCampaign` answer.
///
/// DEFERRED THIS PASS (documented, not silently dropped — see this feature's own build report):
/// weekly recurring send-window, live loyalty threshold sliders (fixed 90 days / 3 visits),
/// scheduling a later launch, multi-service/package selection (single item only), and the
/// gift/points reward types (every campaign here sends its discount, same as every goal's own
/// default). `occasion` (هنّئ في مناسبة) is EXCLUDED from the goal picker entirely: it is the one
/// goal whose trigger is a scheduled future moment rather than "now", and launching it without
/// that date field would create a campaign that silently never fires (dispatch.py's own
/// `fire_at == 0` guard treats a bare `occasion` campaign as "skip forever") — a correctness risk,
/// not a UX one, so it stays off until its own scheduling step is built.
class LaunchWizardScreen extends StatefulWidget {
  const LaunchWizardScreen({super.key, required this.owned, this.initialGoal});

  /// Read once by the caller (`MessagesScreen`'s own `_loadAll`) rather than re-fetched here —
  /// this screen is reached only ever from that one place, and re-asking would just cost a
  /// second round trip for an answer the caller already has.
  final Owned? owned;

  /// ARRIVING WITH THE DECISION ALREADY MADE — a templates-tab cross-link names its own goal
  /// here so the owner never has to find it again on the goal grid (Messages.tsx's own
  /// `?launch=` note). Only pre-selects when the goal is actually AVAILABLE — an unreachable
  /// goal falls through to the normal picker instead of a dead pre-selection.
  final String? initialGoal;

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

  final _ownerTextController = TextEditingController();
  final _offerAmountController = TextEditingController();
  // `pct`/`sar` — TYPED, never folded into the free line the owner types (core/preview.py's own
  // `_OFFER` regex: `20%` or `50 ريال`, nothing else). A composed string is built from this and
  // the amount at the one point it is actually sent, never held as the source of truth itself.
  String _discountKind = 'pct';
  String _serviceId = '';
  String _serviceName = '';
  DateTime? _endsOn;

  CampaignPreview? _preview;
  bool _loadingPreview = false;
  bool _sending = false;
  String _error = '';

  static const _goalIcons = {
    'win_back': Icons.replay_circle_filled_rounded,
    'reward_loyal': Icons.workspace_premium_rounded,
    'announce': Icons.campaign_rounded,
    'service_offer': Icons.local_offer_rounded,
    'package_offer': Icons.card_giftcard_rounded,
  };

  @override
  void initState() {
    super.initState();
    final apiClient = context.read<AuthProvider>().apiClient;
    _service = MessagesService(apiClient: apiClient);
    _catalogueService = ServicesCatalogueService(apiClient: apiClient);
    _loadGoals();
  }

  @override
  void dispose() {
    _ownerTextController.dispose();
    _offerAmountController.dispose();
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

  Future<void> _loadGoals() async {
    final goals = await _service.goals();
    final services = await _catalogueService.list(includeRetired: false);
    if (!mounted) return;
    final filtered = (goals ?? const []).where((g) => g.goal != 'occasion').toList();
    setState(() {
      // `occasion` DELIBERATELY EXCLUDED — see this file's own header comment.
      _goals = filtered;
      _services = services ?? const [];
      if (widget.initialGoal != null) {
        final match = filtered.where((g) => g.goal == widget.initialGoal && g.available).firstOrNull;
        if (match != null) {
          _picked = match;
          _step = _Step.fields;
        }
      }
    });
  }

  bool get _rewardEnabled =>
      const {'occasion', 'win_back', 'service_offer', 'package_offer'}.contains(_picked?.goal);

  bool get _fieldsValid {
    if (_picked == null) return false;
    if (_picked!.hasBlank('amount') && _offerAmountController.text.trim().isEmpty) return false;
    if (_picked!.hasBlank('date') && _endsOn == null) return false;
    if (_picked!.goal == 'service_offer' && _serviceId.isEmpty) return false;
    return true;
  }

  Map<String, dynamic> _buildBody() {
    final expiresAt = _endsOn == null
        ? 0
        : DateTime(_endsOn!.year, _endsOn!.month, _endsOn!.day, 23, 59, 59)
            .millisecondsSinceEpoch ~/
            1000;
    return {
      'goal': _picked!.goal,
      'owner_text': _ownerTextController.text.trim(),
      'service_ids': _serviceId.isNotEmpty ? [_serviceId] : <String>[],
      'package_ids': <String>[],
      'loyalty_window_days': 90,
      'loyalty_min_visits': 3,
      'branch_id': '',
      'offer_value': _offerValue,
      'service_names': _serviceId.isNotEmpty ? [_serviceName] : <String>[],
      'package_names': <String>[],
      'expires_at': expiresAt,
      'fire_at': 0,
      'window_start_hour': 0,
      'window_end_hour': 24,
      'window_weekdays': <int>[],
      'reward_type': 'discount',
      'reward_points': 0,
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
        leading: IconButton(
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
      body: SafeArea(
        child: switch (_step) {
          _Step.goal => _GoalStep(
              goals: _goals,
              icons: _goalIcons,
              onPick: (g) => setState(() {
                _picked = g;
                _step = _Step.fields;
              }),
            ),
          _Step.fields => _FieldsStep(
              goal: _picked!,
              services: _services,
              ownerTextController: _ownerTextController,
              offerAmountController: _offerAmountController,
              discountKind: _discountKind,
              onDiscountKindChanged: (k) => setState(() => _discountKind = k),
              rewardEnabled: _rewardEnabled,
              serviceId: _serviceId,
              endsOn: _endsOn,
              onServicePicked: (id, name) => setState(() {
                _serviceId = id;
                _serviceName = name;
              }),
              onDatePicked: (d) => setState(() => _endsOn = d),
              canContinue: _fieldsValid,
              onContinue: _goToPreview,
            ),
          _Step.preview => _PreviewStep(
              loading: _loadingPreview,
              preview: _preview,
              error: _error,
              sending: _sending,
              onSend: _send,
            ),
        },
      ),
    );
  }
}

class _GoalStep extends StatelessWidget {
  const _GoalStep({required this.goals, required this.icons, required this.onPick});
  final List<GoalRow>? goals;
  final Map<String, IconData> icons;
  final ValueChanged<GoalRow> onPick;

  @override
  Widget build(BuildContext context) {
    if (goals == null) return const Center(child: CircularProgressIndicator());
    if (goals!.isEmpty) {
      return EmptyState(icon: Icons.campaign_outlined, title: ct(context, 'noGoalsAvailable'));
    }
    return GridView.builder(
      padding: const EdgeInsets.all(AppSpacing.md),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: AppSpacing.sm,
        mainAxisSpacing: AppSpacing.sm,
        childAspectRatio: 0.95,
      ),
      itemCount: goals!.length,
      itemBuilder: (context, i) {
        final g = goals![i];
        final style = msgClassStyle(g.goal == 'announce' ? 'marketing' : 'offers', context.isDark);
        return AppCard(
          onTap: g.available ? () => onPick(g) : null,
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
    );
  }
}

class _FieldsStep extends StatelessWidget {
  const _FieldsStep({
    required this.goal,
    required this.services,
    required this.ownerTextController,
    required this.offerAmountController,
    required this.discountKind,
    required this.onDiscountKindChanged,
    required this.rewardEnabled,
    required this.serviceId,
    required this.endsOn,
    required this.onServicePicked,
    required this.onDatePicked,
    required this.canContinue,
    required this.onContinue,
  });

  final GoalRow goal;
  final List<ServiceItem> services;
  final TextEditingController ownerTextController;
  final TextEditingController offerAmountController;
  final String discountKind;
  final ValueChanged<String> onDiscountKindChanged;
  final bool rewardEnabled;
  final String serviceId;
  final DateTime? endsOn;
  final void Function(String id, String name) onServicePicked;
  final ValueChanged<DateTime> onDatePicked;
  final bool canContinue;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              if (goal.goal == 'service_offer') ...[
                Text(ct(context, 'whichService'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                for (final s in services)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(s.name),
                    leading: Icon(
                      s.id == serviceId ? Icons.check_circle_rounded : Icons.circle_outlined,
                      color: s.id == serviceId
                          ? (context.isDark ? AppDarkColors.accent : AppColors.accent)
                          : context.appColors.textMuted,
                    ),
                    onTap: () => onServicePicked(s.id, s.name),
                  ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (rewardEnabled) ...[
                Text(ct(context, 'discountAmount'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                // TYPED, NOT FREE TEXT — the server's own shape (core/preview.py's `_OFFER`
                // regex) is exactly "20%" or "50 ريال": a percent 1-99 with no decimals, or an
                // amount with up to 2. Composing it from a number + a real toggle means a shop
                // can never type something the server refuses at the very last step.
                Row(children: [
                  Expanded(
                    child: AppTextField(
                      controller: offerAmountController,
                      hintText: discountKind == 'pct' ? '20' : '50',
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
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
              if (goal.hasBlank('date')) ...[
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
              if (goal.hasBlank('owner')) ...[
                Text(ct(context, 'whatsNew'), style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(controller: ownerTextController, maxLines: 2, hintText: ct(context, 'ownerTextHint')),
                const SizedBox(height: AppSpacing.md),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: PrimaryButton(text: ct(context, 'nextPreview'), onPressed: canContinue ? onContinue : null),
        ),
      ],
    );
  }
}

class _PreviewStep extends StatelessWidget {
  const _PreviewStep({
    required this.loading,
    required this.preview,
    required this.error,
    required this.sending,
    required this.onSend,
  });

  final bool loading;
  final CampaignPreview? preview;
  final String error;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    if (preview == null) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Text(error.isNotEmpty ? error : ct(context, 'previewGenericFailed'), style: AppTextStyles.bodyMedium),
      );
    }
    final p = preview!;
    final blocked = p.spreadRefused.isNotEmpty || !p.templateActive;
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              WhatsAppPhoneFrame(child: WhatsAppBubble(text: p.message)),
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
              if (error.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Text(error, style: AppTextStyles.bodySmall.copyWith(color: context.isDark ? AppDarkColors.danger : AppColors.danger)),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: PrimaryButton(
            text: ct(context, 'launchNowButton'),
            isLoading: sending,
            onPressed: blocked ? null : onSend,
          ),
        ),
      ],
    );
  }
}
