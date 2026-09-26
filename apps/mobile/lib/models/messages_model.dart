/// «الحملات» — mirrors apps/console/src/screens/Messages.tsx's own data contracts exactly
/// (`reminders.today/reasons/set_reason/list_schedule/cancel/log`,
/// `campaigns.goals/preview/create/list/runs/pause`). See parity/messages.md for the full
/// feature catalogue this mobile pass is built against.
library;

/// "هل كل شيء يعمل اليوم؟" — one call, `reminders.today`, answers the question this whole
/// feature opens on. Every field defensive: a malformed/partial answer must draw the parts that
/// did arrive, never crash the screen it feeds.
class TodayStatus {
  final bool canSend;
  final String blocked;
  final int sentToday;
  final int waiting;
  final int retrying;
  final String retryingReason;
  final bool ceilingKnown;
  final bool ceilingUnlimited;
  final int ceilingLimit;
  final int ceilingRemaining;
  final String ceilingQuality;

  const TodayStatus({
    required this.canSend,
    required this.blocked,
    required this.sentToday,
    required this.waiting,
    required this.retrying,
    required this.retryingReason,
    required this.ceilingKnown,
    required this.ceilingUnlimited,
    required this.ceilingLimit,
    required this.ceilingRemaining,
    required this.ceilingQuality,
  });

  factory TodayStatus.fromJson(Map<String, dynamic> json) {
    final messages = (json['messages'] as Map?) ?? const {};
    final ceiling = (json['ceiling'] as Map?) ?? const {};
    return TodayStatus(
      canSend: json['can_send'] != false,
      blocked: (json['blocked'] as String?) ?? '',
      sentToday: (messages['sent_today'] as num?)?.toInt() ?? 0,
      waiting: (messages['waiting'] as num?)?.toInt() ?? 0,
      retrying: (messages['retrying'] as num?)?.toInt() ?? 0,
      retryingReason: (messages['retrying_reason'] as String?) ?? '',
      ceilingKnown: ceiling['known'] == true,
      ceilingUnlimited: ceiling['unlimited'] == true,
      ceilingLimit: (ceiling['limit'] as num?)?.toInt() ?? 0,
      ceilingRemaining: (ceiling['remaining'] as num?)?.toInt() ?? 0,
      ceilingQuality: (ceiling['quality'] as String?) ?? '',
    );
  }
}

/// One of the 13 automatic reasons «متى نرسل» tracks — `reminders.reasons`.
class ReasonRow {
  final String id;
  final String label;
  final String when;
  final bool on;
  final bool canSwitch;
  final bool canRetext;
  final String cls;
  final String clsLabel;
  final String templateStatus;
  /// The name of the owner's own approved text for this reason, when he has pointed it at one
  /// (`reason_choices.py`'s own `row["template"]`) — empty means "sending ours". Drives the
  /// «نصّك أنت» badge, same signal `MessagePreview.tsx`'s own `customTextBadge` reads.
  final String template;

  const ReasonRow({
    required this.id,
    required this.label,
    required this.when,
    required this.on,
    required this.canSwitch,
    required this.canRetext,
    required this.cls,
    required this.clsLabel,
    required this.templateStatus,
    this.template = '',
  });

  factory ReasonRow.fromJson(Map<String, dynamic> json) => ReasonRow(
        id: (json['id'] as String?) ?? '',
        label: (json['label'] as String?) ?? '',
        when: (json['when'] as String?) ?? '',
        on: json['on'] == true,
        canSwitch: json['can_switch'] == true,
        canRetext: json['can_retext'] == true,
        cls: (json['cls'] as String?) ?? '',
        clsLabel: (json['cls_label'] as String?) ?? '',
        templateStatus: (json['template_status'] as String?) ?? 'unknown',
        template: (json['template'] as String?) ?? '',
      );

  ReasonRow copyWith({bool? on}) => ReasonRow(
        id: id,
        label: label,
        when: when,
        on: on ?? this.on,
        canSwitch: canSwitch,
        canRetext: canRetext,
        cls: cls,
        clsLabel: clsLabel,
        templateStatus: templateStatus,
        template: template,
      );
}

/// Which app a reason's message depends on, when it does — `booking_confirmed`/`rating_requested`
/// are the only two (Messages.tsx's own hand-mapped `REASON_APP`, kept in sync by hand: this table
/// is small and rarely changes, not worth a network round trip for exactly one screen).
const Map<String, String> kReasonApp = {
  'booking_confirmed': 'feature.bookings',
  'rating_requested': 'feature.rating',
};

/// One of the 5 manual goals with no automatic reason of its own — `campaigns.goals`.
class GoalRow {
  final String goal;
  final String title;
  final String line;
  final String templateStatus;
  final int uses;
  final int reach;
  final bool available;
  final String unavailableReason;
  final String icon;
  /// The blanks THIS goal's message actually has, by kind — `amount`/`date`/`owner`/`catalogue`
  /// (Launch.tsx's own `hasBlank()`). Drives which fields the wizard shows: a goal with no
  /// `date` blank must never ask for an end date it cannot use.
  final List<String> blanks;

  const GoalRow({
    required this.goal,
    required this.title,
    required this.line,
    required this.templateStatus,
    required this.uses,
    required this.reach,
    required this.available,
    required this.unavailableReason,
    required this.icon,
    required this.blanks,
  });

  bool hasBlank(String kind) => blanks.contains(kind);

  factory GoalRow.fromJson(Map<String, dynamic> json) => GoalRow(
        goal: (json['goal'] as String?) ?? '',
        title: (json['title'] as String?) ?? '',
        line: (json['line'] as String?) ?? '',
        templateStatus: (json['template_status'] as String?) ?? 'unknown',
        uses: (json['uses'] as num?)?.toInt() ?? 0,
        reach: (json['reach'] as num?)?.toInt() ?? 0,
        available: json['available'] != false,
        unavailableReason: (json['unavailable_reason'] as String?) ?? '',
        icon: (json['icon'] as String?) ?? '',
        blanks: ((json['blanks'] as List?) ?? const []).map((e) => e.toString()).toList(),
      );
}

/// «متى نرسل» + «حملاتي» MERGED INTO ONE LIST — the console's own rename (Messages.tsx's own
/// `templateCards()`). Three goals (win_back/occasion/reward_loyal) share a card with their
/// reason; the rest of `reasons` stay automatic-only and the remaining goals stay manual-only.
/// Ported as a plain function, not a class method, so the merge rule is one thing a test can hold
/// without building a screen — same posture the console's own source keeps.
class TemplateCard {
  final String key;
  final String label;
  final String when;
  final String cls;
  final String clsLabel;
  final bool auto;
  final bool manual;
  final ReasonRow? reason;
  final String? goal;
  final String templateStatus;
  /// Opens real Flow screens inside WhatsApp (booking a slot, a loyalty activation button…),
  /// not just text to read — Messages.tsx's own `INTERACTIVE_TEMPLATE_TYPES` lookup.
  final bool interactive;

  const TemplateCard({
    required this.key,
    required this.label,
    required this.when,
    required this.cls,
    required this.clsLabel,
    required this.auto,
    required this.manual,
    required this.reason,
    required this.goal,
    required this.templateStatus,
    this.interactive = false,
  });
}

/// EVERY REASON'S OWN `template_type` — reminders' own `reasons.py` REASONS tuple, mirrored by
/// hand (Messages.tsx's own `REASON_TEMPLATE_TYPE`: a table this small drifting is a one-line
/// fix, not worth a network round trip for exactly one screen).
const Map<String, String> kReasonTemplateType = {
  'visit_recorded': 'svc_visit_confirmation',
  'rating_requested': 'svc_visit_confirmation_rating',
  'booking_confirmed': 'svc_booking_confirmation',
  'visit_redeemed': 'svc_visit_redeemed',
  'service_due': 'svc_service_reminder',
  'after_visit': 'svc_follow_up',
  'no_response': 'svc_service_reminder',
  'balance_changed': 'per_account_notice',
  'points_expiring': 'per_points_expiring',
  'reward_within_reach': 'mkt_loyalty_activation',
  'gone_missing': 'mkt_winback',
  'loyal_customer': 'mkt_loyalty_activation',
  'personal_occasion': 'mkt_personal_occasion',
};

/// THE TEMPLATE TYPE EACH GOAL SENDS — campaigns' own `GOAL_TEMPLATE`, mirrored the same way.
const Map<String, String> kGoalTemplateType = {
  'announce': 'mkt_announcement',
  'service_offer': 'mkt_offer',
  'package_offer': 'mkt_offer',
};

/// تفاعلي = يفتح شاشات حقيقية داخل واتساب (Flow)، لا مجرد نص — Messages.tsx's own set.
const Set<String> kInteractiveTemplateTypes = {
  'mkt_offer', 'mkt_personal_occasion', 'mkt_winback', 'svc_visit_confirmation_rating',
};

/// `REASON_GOAL` — Messages.tsx's own hand-matched table (reasons.py vs. GOAL_TEMPLATE), kept in
/// sync by hand on purpose: a table this small drifting is a one-line fix, not worth a network
/// round trip for exactly one screen.
const Map<String, String> kReasonGoal = {
  'gone_missing': 'win_back',
  'personal_occasion': 'occasion',
  'loyal_customer': 'reward_loyal',
};

List<TemplateCard> mergeTemplateCards(List<ReasonRow> reasons, List<GoalRow> goals) {
  final out = <TemplateCard>[];
  final goalHasReason = kReasonGoal.values.toSet();
  for (final r in reasons) {
    final linkedGoal = kReasonGoal[r.id];
    final templateType = kReasonTemplateType[r.id];
    out.add(TemplateCard(
      key: 'reason:${r.id}',
      label: r.label,
      when: r.when,
      cls: r.cls,
      clsLabel: r.clsLabel,
      auto: true,
      manual: linkedGoal != null,
      reason: r,
      goal: linkedGoal,
      templateStatus: r.templateStatus,
      interactive: templateType != null && kInteractiveTemplateTypes.contains(templateType),
    ));
  }
  for (final g in goals) {
    if (goalHasReason.contains(g.goal)) continue; // already carried by its reason card, above
    final templateType = kGoalTemplateType[g.goal];
    out.add(TemplateCard(
      key: 'goal:${g.goal}',
      label: g.title,
      when: g.line,
      cls: g.goal == 'announce' ? 'marketing' : 'offers',
      clsLabel: g.goal == 'announce' ? 'تسويقية' : 'عروض',
      auto: false,
      manual: true,
      reason: null,
      goal: g.goal,
      templateStatus: g.templateStatus,
      interactive: templateType != null && kInteractiveTemplateTypes.contains(templateType),
    ));
  }
  return out;
}

/// One queued, not-yet-sent message — `reminders.list_schedule`.
class ScheduleRow {
  final String id;
  final String kind;
  final int dueAt;
  final String subjectRef;
  final String branchId;

  const ScheduleRow({
    required this.id,
    required this.kind,
    required this.dueAt,
    required this.subjectRef,
    required this.branchId,
  });

  factory ScheduleRow.fromJson(Map<String, dynamic> json) => ScheduleRow(
        id: (json['id'] as String?) ?? '',
        kind: (json['kind'] as String?) ?? '',
        dueAt: (json['due_at'] as num?)?.toInt() ?? 0,
        subjectRef: (json['subject_ref'] as String?) ?? '',
        branchId: (json['branch_id'] as String?) ?? '',
      );
}

/// One line of the delivery log — `reminders.log`.
class MessageLogRow {
  final String id;
  final String branchId;
  final int at;
  final String outcome;
  final int deliveredAt;
  final int readAt;
  final String reason;
  final String templateName;
  final String cls;
  final String subjectRef;

  const MessageLogRow({
    required this.id,
    required this.branchId,
    required this.at,
    required this.outcome,
    required this.deliveredAt,
    required this.readAt,
    required this.reason,
    required this.templateName,
    required this.cls,
    required this.subjectRef,
  });

  factory MessageLogRow.fromJson(Map<String, dynamic> json) => MessageLogRow(
        id: (json['id'] as String?) ?? '',
        branchId: (json['branch_id'] as String?) ?? '',
        at: (json['at'] as num?)?.toInt() ?? 0,
        outcome: (json['outcome'] as String?) ?? '',
        deliveredAt: (json['delivered_at'] as num?)?.toInt() ?? 0,
        readAt: (json['read_at'] as num?)?.toInt() ?? 0,
        reason: (json['reason'] as String?) ?? '',
        templateName: (json['template_name'] as String?) ?? '',
        cls: (json['cls'] as String?) ?? '',
        subjectRef: (json['subject_ref'] as String?) ?? '',
      );
}

/// A launched campaign — `campaigns.list`/`campaigns.create`.
class Campaign {
  final String id;
  final String goal;
  final String state;
  final int sent;
  final int fireAt;
  final int lastEvaluated;
  final int windowStartHour;
  final int windowEndHour;
  final List<int> windowWeekdays;
  // THE REST OF THE STORED ROW — needed to re-preview an ALREADY-LAUNCHED campaign's real
  // message on the detail sheet, the same way the wizard already can before it launches
  // (Messages.tsx's own `openRuns()` does this exact re-fetch).
  final String ownerText;
  final String offerValue;
  final int expiresAt;
  final String serviceId;
  final String packageId;
  final List<String> scopeServiceIds;
  final List<String> scopeServiceNames;
  final String branchId;
  final int loyaltyWindowDays;
  final int loyaltyMinVisits;
  final String rewardType;
  final int rewardPoints;

  const Campaign({
    required this.id,
    required this.goal,
    required this.state,
    required this.sent,
    required this.fireAt,
    required this.lastEvaluated,
    required this.windowStartHour,
    required this.windowEndHour,
    required this.windowWeekdays,
    this.ownerText = '',
    this.offerValue = '',
    this.expiresAt = 0,
    this.serviceId = '',
    this.packageId = '',
    this.scopeServiceIds = const [],
    this.scopeServiceNames = const [],
    this.branchId = '',
    this.loyaltyWindowDays = 90,
    this.loyaltyMinVisits = 3,
    this.rewardType = 'discount',
    this.rewardPoints = 0,
  });

  /// Job-service is holding this campaign for a future moment it has not fired even once —
  /// mirrors Messages.tsx's own `isScheduled()` exactly.
  bool get isScheduled => fireAt > 0 && fireAt > DateTime.now().millisecondsSinceEpoch / 1000 && lastEvaluated == 0;

  /// A short chip for the campaign's own recurring window, or `null` when it carries none — the
  /// `(0, 24, [])` defaults `window_*` itself uses to mean "no window". Mirrors Messages.tsx's
  /// own `windowChip()` at a glance rather than the full sentence.
  String? get windowChip {
    final start = windowStartHour;
    final end = windowEndHour;
    if (start == 0 && end == 24 && windowWeekdays.isEmpty) return null;
    final hours = '$start–$end';
    if (windowWeekdays.isEmpty) return hours;
    return '$hours · ${windowWeekdays.length}';
  }

  factory Campaign.fromJson(Map<String, dynamic> json) => Campaign(
        id: (json['id'] as String?) ?? '',
        goal: (json['goal'] as String?) ?? '',
        state: (json['state'] as String?) ?? '',
        sent: (json['sent'] as num?)?.toInt() ?? 0,
        fireAt: (json['fire_at'] as num?)?.toInt() ?? 0,
        lastEvaluated: (json['last_evaluated'] as num?)?.toInt() ?? 0,
        windowStartHour: (json['window_start_hour'] as num?)?.toInt() ?? 0,
        windowEndHour: (json['window_end_hour'] as num?)?.toInt() ?? 24,
        windowWeekdays: ((json['window_weekdays'] as List?) ?? const [])
            .map((e) => (e as num).toInt())
            .toList(),
        ownerText: (json['owner_text'] as String?) ?? '',
        offerValue: (json['offer_value'] as String?) ?? '',
        expiresAt: (json['expires_at'] as num?)?.toInt() ?? 0,
        serviceId: (json['service_id'] as String?) ?? '',
        packageId: (json['package_id'] as String?) ?? '',
        scopeServiceIds: ((json['scope_service_ids'] as List?) ?? const []).map((e) => e.toString()).toList(),
        scopeServiceNames: ((json['scope_service_names'] as List?) ?? const []).map((e) => e.toString()).toList(),
        branchId: (json['branch_id'] as String?) ?? '',
        loyaltyWindowDays: (json['loyalty_window_days'] as num?)?.toInt() ?? 90,
        loyaltyMinVisits: (json['loyalty_min_visits'] as num?)?.toInt() ?? 3,
        rewardType: (json['reward_type'] as String?) ?? 'discount',
        rewardPoints: (json['reward_points'] as num?)?.toInt() ?? 0,
      );
}

/// One send pass of a campaign — `campaigns.runs`.
class CampaignRun {
  final int at;
  final int sent;
  final int suppressed;
  final String reason;

  const CampaignRun({required this.at, required this.sent, required this.suppressed, required this.reason});

  factory CampaignRun.fromJson(Map<String, dynamic> json) => CampaignRun(
        at: (json['at'] as num?)?.toInt() ?? 0,
        sent: (json['sent'] as num?)?.toInt() ?? 0,
        suppressed: (json['suppressed'] as num?)?.toInt() ?? 0,
        reason: (json['reason'] as String?) ?? '',
      );
}

/// The reach/refusal answer `campaigns.preview` gives BEFORE any send button is reachable —
/// non-negotiable per this pass's own brief: never simplified away.
class CampaignPreview {
  final String message;
  final String when;
  final int reaches;
  final int excluded;
  final int tooRecent;
  final String spreadRefused;
  final String spreadSays;
  final List<String> why;
  final bool templateActive;
  final String templateInactiveReason;

  const CampaignPreview({
    required this.message,
    required this.when,
    required this.reaches,
    required this.excluded,
    required this.tooRecent,
    required this.spreadRefused,
    required this.spreadSays,
    required this.why,
    required this.templateActive,
    required this.templateInactiveReason,
  });

  factory CampaignPreview.fromJson(Map<String, dynamic> json) {
    final spread = (json['spread'] as Map?) ?? const {};
    return CampaignPreview(
      message: (json['message'] as String?) ?? '',
      when: (json['when'] as String?) ?? '',
      reaches: (json['reaches'] as num?)?.toInt() ?? 0,
      excluded: (json['excluded'] as num?)?.toInt() ?? 0,
      tooRecent: (json['too_recent'] as num?)?.toInt() ?? 0,
      spreadRefused: (spread['refused'] as String?) ?? '',
      spreadSays: (json['spread_says'] as String?) ?? '',
      why: ((json['why'] as List?) ?? const []).map((e) => e.toString()).toList(),
      templateActive: json['template_active'] != false,
      templateInactiveReason: (json['template_inactive_reason'] as String?) ?? '',
    );
  }
}

/// The whole answer `reminders.preview_reason`/`preview_by_type` gives — not just the options list,
/// which used to be all this app read. `chosen`/`tone` decide which option carries the "sending
/// now" badge; `emptyBecause` is the SERVER'S OWN REASON for an empty list (never guessed here —
/// MessagePreview.tsx's own header note: conflating "under review" with "never submitted" sends an
/// owner to wait on Meta for a refusal that was ours).
class PreviewAnswer {
  final List<MessageOption> options;
  final String chosen;
  final String tone;
  final String emptyBecause;

  const PreviewAnswer({
    required this.options,
    required this.chosen,
    required this.tone,
    required this.emptyBecause,
  });

  factory PreviewAnswer.fromJson(Map<String, dynamic> json) {
    final rows = (json['options'] as List?) ?? const [];
    return PreviewAnswer(
      options: rows.whereType<Map>().map((m) => MessageOption.fromJson(Map<String, dynamic>.from(m))).toList(),
      chosen: (json['chosen'] as String?) ?? '',
      tone: (json['tone'] as String?) ?? 'masculine',
      emptyBecause: (json['empty_because'] as String?) ?? '',
    );
  }
}

/// One wording option in the message-preview sheet — `reminders.preview_reason`/`preview_by_type`.
class MessageOption {
  final String name;
  final String tone;
  final String text;
  final bool mine;
  final bool? approved;
  final String status;
  final String reason;
  /// The template AS WRITTEN, with named blanks — «[اسم العميل]» where a blank is. Shown only
  /// when it differs from [text] (the filled example), same rule MessagePreview.tsx's own
  /// `o.template && o.template !== o.text` guard keeps.
  final String template;
  final List<MessageButton> buttons;

  const MessageOption({
    required this.name,
    required this.tone,
    required this.text,
    required this.mine,
    required this.approved,
    required this.status,
    required this.reason,
    this.template = '',
    this.buttons = const [],
  });

  factory MessageOption.fromJson(Map<String, dynamic> json) => MessageOption(
        name: (json['name'] as String?) ?? '',
        tone: (json['tone'] as String?) ?? '',
        text: (json['text'] as String?) ?? '',
        mine: json['mine'] == true,
        approved: json['approved'] is bool ? json['approved'] as bool : null,
        status: (json['status'] as String?) ?? '',
        reason: (json['reason'] as String?) ?? '',
        template: (json['template'] as String?) ?? '',
        buttons: ((json['buttons'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) => MessageButton.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
      );
}

/// One button Meta draws OUTSIDE the message bubble — never rendered as if it were inside the
/// text. `flowName` present only for `kind: 'flow'`; absent means "show the label, cannot open it
/// here yet" (Flow-opening itself stays deferred this pass — see this feature's own build notes).
class MessageButton {
  final String label;
  final String kind;
  final String flowName;

  const MessageButton({required this.label, required this.kind, required this.flowName});

  factory MessageButton.fromJson(Map<String, dynamic> json) => MessageButton(
        label: (json['label'] as String?) ?? '',
        kind: (json['kind'] as String?) ?? '',
        flowName: (json['flow_name'] as String?) ?? '',
      );
}
