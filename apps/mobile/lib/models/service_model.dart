int _toInt(dynamic v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

/// «خدماتي ومنتجاتي» — mirrors services/operations/app/core/models.py's own `Service.public()`
/// shape exactly, the same contract apps/console/src/screens/Services.tsx already reads.
/// Scope note: the separate reminders/loyalty per-service settings TREE (cycle/points groups
/// and overrides, distinct from this row's own plain `cycle_days`) is a real, richer part of
/// this same screen on console that is NOT built here yet — not stubbed, simply absent, same
/// "no placeholder drift" rule every other screen in this pass holds to.
class ServiceItem {
  final String id;
  final String name;
  final int cycleDays;
  final int priceMinor;
  final int durationMinutes;
  final bool active;
  final String description;
  final bool hasImage;
  final List<String> eligibleStaffIds; // [] = every active field operator, not "none"
  final String assignmentMode; // "named" | "auto"
  final List<String> procedureStepIds; // ordered

  const ServiceItem({
    required this.id,
    required this.name,
    required this.cycleDays,
    required this.priceMinor,
    required this.durationMinutes,
    required this.active,
    required this.description,
    required this.hasImage,
    required this.eligibleStaffIds,
    required this.assignmentMode,
    required this.procedureStepIds,
  });

  factory ServiceItem.fromJson(Map<String, dynamic> json) {
    return ServiceItem(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      cycleDays: _toInt(json['cycle_days']),
      priceMinor: _toInt(json['price_minor']),
      durationMinutes: _toInt(json['duration_minutes']),
      // ABSENT MUST READ AS ACTIVE — the console's own documented regression trap
      // (Services.tsx's own note): a missing `active` field is not the same as `false`.
      active: json['active'] as bool? ?? true,
      description: json['description'] as String? ?? '',
      hasImage: json['has_image'] as bool? ?? false,
      eligibleStaffIds: ((json['eligible_staff_ids'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList(growable: false),
      assignmentMode: json['assignment_mode'] as String? ?? 'auto',
      procedureStepIds: ((json['procedure_step_ids'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList(growable: false),
    );
  }
}

/// `services/operations/app/core/models.py::ProcedureStep.public()` — one shared protocol line,
/// referenced by id from any service's own `procedure_step_ids`. Editing a step's text here
/// changes it everywhere it is used, by design — never per-service duplicated text.
class ProcedureStep {
  final String id;
  final String text;
  final String severity; // "normal" | "critical"
  final bool active;

  const ProcedureStep({
    required this.id,
    required this.text,
    required this.severity,
    required this.active,
  });

  factory ProcedureStep.fromJson(Map<String, dynamic> json) {
    return ProcedureStep(
      id: json['id'] as String? ?? '',
      text: json['text'] as String? ?? '',
      severity: json['severity'] as String? ?? 'normal',
      active: json['active'] as bool? ?? true,
    );
  }
}

/// `services/operations/app/core/models.py::Package.public()` — several ACTIVE services sold as
/// one unit at one owner-set price (never derived from the components' own prices). Mobile builds
/// only the "manual" half of this: name, member services, price, description — the scheduling
/// fields (`starts_at`/`recurrence`/...) are real on the server but not exposed here, so every
/// package this screen creates is simply always-offerable, which is the ordinary case.
class ServicePackage {
  final String id;
  final String name;
  final List<String> serviceIds;
  final int priceMinor;
  final String description;
  final bool active;

  const ServicePackage({
    required this.id,
    required this.name,
    required this.serviceIds,
    required this.priceMinor,
    required this.description,
    required this.active,
  });

  factory ServicePackage.fromJson(Map<String, dynamic> json) {
    return ServicePackage(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      serviceIds: ((json['service_ids'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList(growable: false),
      priceMinor: _toInt(json['price_minor']),
      description: json['description'] as String? ?? '',
      active: json['active'] as bool? ?? true,
    );
  }
}

/// `services/reminders/app/api/v1/owner.py::SettingsIn` — one level of the reminder settings
/// tree (general, one group, or one service's own override). `intervalDays`/`followUpDays` are
/// `null` when that level does not set them at all (`SettingsIn.values()`'s own `exclude_none`).
class ReminderSetting {
  final int? intervalDays;
  final int? followUpDays;

  const ReminderSetting({this.intervalDays, this.followUpDays});

  factory ReminderSetting.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ReminderSetting();
    return ReminderSetting(
      intervalDays: (json['interval_days'] as num?)?.round(),
      followUpDays: (json['follow_up_days'] as num?)?.round(),
    );
  }
}

/// The full reminder settings tree — `GET /api/v1/reminders/settings` — general, named groups,
/// which group each service belongs to, and each service's own override. Mirrors
/// apps/console/src/screens/Services.tsx's own `Settings` interface exactly: a service resolves
/// by checking its own override, then its group, then general, in that order.
class ReminderSettingsTree {
  final ReminderSetting general;
  final Map<String, ReminderSetting> groups;
  final Map<String, String> serviceGroup;
  final Map<String, ReminderSetting> services;

  const ReminderSettingsTree({
    required this.general,
    required this.groups,
    required this.serviceGroup,
    required this.services,
  });

  factory ReminderSettingsTree.fromJson(Map<String, dynamic> json) {
    Map<String, ReminderSetting> mapOf(dynamic v) => {
          for (final e in ((v as Map?) ?? const {}).entries)
            e.key.toString(): ReminderSetting.fromJson(Map<String, dynamic>.from(e.value as Map)),
        };
    return ReminderSettingsTree(
      general: ReminderSetting.fromJson(json['general'] as Map<String, dynamic>?),
      groups: mapOf(json['groups']),
      serviceGroup: {
        for (final e in ((json['service_group'] as Map?) ?? const {}).entries)
          e.key.toString(): e.value.toString(),
      },
      services: mapOf(json['services']),
    );
  }

  /// The effective value for one service, and whether it holds its own override — the exact
  /// three-level resolution order `settingFor` in Services.tsx already implements.
  (ReminderSetting, bool) resolve(String serviceId) {
    final own = services[serviceId];
    if (own != null) return (own, true);
    final group = serviceGroup[serviceId];
    final fromGroup = group != null ? groups[group] : null;
    return (fromGroup ?? general, false);
  }
}

/// `services/loyalty/app/api/v1/loyalty.py`'s own earning tree — `GET /api/v1/loyalty/settings`.
/// Four levels: a service's own points, its group, the tenant general, then the platform default
/// (the platform floor is never editable here, only ever read).
class EarnSettingsTree {
  final int? generalPoints;
  final int? defaultPoints;
  final Map<String, int> groupPoints;
  final Map<String, String> serviceGroup;
  final Map<String, int> servicePoints;
  // «طريقة الاحتساب» (spec §9.3) — the loyalty program's own earning switch, read from the SAME
  // `GET /api/v1/loyalty/settings` response this whole tree already comes from (never a second
  // call): "services" (each service carries its own point value) or "invoice" (one point per
  // riyal actually charged). `servicesPriced` is the LAST live check, taken at the mode switch
  // itself — never read pre-emptively as a standing fact, since a service can be re-priced the
  // moment after.
  final String mode;
  final int pointsPerRiyal;
  final bool servicesPriced;

  const EarnSettingsTree({
    required this.generalPoints,
    required this.defaultPoints,
    required this.groupPoints,
    required this.serviceGroup,
    required this.servicePoints,
    this.mode = 'services',
    this.pointsPerRiyal = 1,
    this.servicesPriced = true,
  });

  factory EarnSettingsTree.fromJson(Map<String, dynamic> json) {
    int? pts(dynamic m) => m is Map ? (m['points'] as num?)?.toInt() : null;
    final config = json['config'];
    return EarnSettingsTree(
      generalPoints: pts(json['general']),
      defaultPoints: pts(json['defaults']),
      groupPoints: {
        for (final e in ((json['groups'] as Map?) ?? const {}).entries)
          e.key.toString(): pts(e.value) ?? 0,
      },
      serviceGroup: {
        for (final e in ((json['service_group'] as Map?) ?? const {}).entries)
          e.key.toString(): e.value.toString(),
      },
      servicePoints: {
        for (final e in ((json['services'] as Map?) ?? const {}).entries)
          e.key.toString(): pts(e.value) ?? 0,
      },
      mode: config is Map ? (config['mode'] as String? ?? 'services') : 'services',
      pointsPerRiyal: config is Map ? ((config['points_per_riyal'] as num?)?.toInt() ?? 1) : 1,
      servicesPriced: config is Map ? (config['services_priced'] as bool? ?? true) : true,
    );
  }

  /// The effective points for one service, and whether it holds its own override — the same
  /// four-level `earnFor` resolution Services.tsx already implements.
  (int, bool) resolve(String serviceId) {
    final own = servicePoints[serviceId];
    if (own != null) return (own, true);
    final group = serviceGroup[serviceId];
    final fromGroup = group != null ? groupPoints[group] : null;
    return (fromGroup ?? generalPoints ?? defaultPoints ?? 0, false);
  }
}

/// `GET /api/v1/reminders/settings/suggest-group` — a proposal only, never acted on unless the
/// owner agrees: several services already share the same value on one field.
class GroupSuggestion {
  final String field;
  final num value;
  final List<String> serviceIds;

  const GroupSuggestion({required this.field, required this.value, required this.serviceIds});

  static GroupSuggestion? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final field = json['field'] as String?;
    final value = json['value'];
    final ids = (json['services'] as List?) ?? const [];
    if (field == null || value is! num || ids.isEmpty) return null;
    return GroupSuggestion(
      field: field,
      value: value,
      serviceIds: ids.map((e) => e.toString()).toList(growable: false),
    );
  }
}
