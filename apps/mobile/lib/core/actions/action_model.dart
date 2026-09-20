/// One thing the assistant may DO, never merely explain — the mobile mirror of [KbEntry]'s own
/// shape (lib/core/knowledge/kb_model.dart), same reasons for existing:
///
///   - A registry entry, not a hardcoded switch, so adding an action is "add a JSON entry",
///     the same "a first KB is a map of ids to a title and some text" ease [KbEntry]'s own doc
///     comment argues for.
///   - [requires] is checked against the real, already capability-filtered [Catalog] — never a
///     role guessed client-side — the same [KbService] rule this file's own gate reuses.
///
/// TIED TO A KB ENTRY, DELIBERATELY. [kbEntryId] must name a REAL `mobile_kb.json` id —
/// enforced by `ci/check_mobile_actions_are_covered.py`, never assumed — so an action can never
/// exist for a screen the assistant has no explanation for, and (the same gate, the other
/// direction) a screen's own KB entry forces a real decision about whether it should be
/// voice-reachable at all, not a silent gap nobody noticed.
library;

class ActionError extends FormatException {
  ActionError(super.message);
}

/// The three tiers the owner's own structure asks for — every action belongs to exactly one:
///
///   [system]     — platform-level, outside any single "app" (تطبيق)'s own concept: حسابي
///                  (account), الفوترة (billing), متجر التطبيقات (the app store) — shell
///                  features every operator has regardless of which apps they've installed.
///   [navigation] — opens a specific "app" (تطبيق) — this file's own `open_visit_app` is the
///                  first of these. Always a real [AppAction.route].
///   [app]        — acts INSIDE the app that is already open (pick a service, save a form) —
///                  never navigates itself, so [AppAction.route] is usually absent; tied to a
///                  KB entry scoped to that same app (e.g. `visit.register.services_grid`).
enum ActionScope {
  system,
  navigation,
  app;

  static ActionScope parse(String id, dynamic raw) {
    if (raw is! String) {
      throw ActionError('$id: missing required field "scope" '
          '("system" | "navigation" | "app", no default)');
    }
    for (final scope in ActionScope.values) {
      if (scope.name == raw) return scope;
    }
    throw ActionError('$id: "scope" must be one of ${ActionScope.values.map((s) => s.name)}, '
        'got "$raw"');
  }
}

class AppAction {
  /// This registry's own key — also what `ci/check_mobile_actions_are_covered.py` reports by.
  final String id;

  /// The name the model is given and returns in a function call — must be a valid identifier;
  /// never the same string as [id] by requirement, but conventionally similar.
  final String name;

  /// What the model reads to decide whether THIS action matches the user's intent. Written for
  /// the model, not for a person — plain, unambiguous, one sentence.
  final String description;

  /// Which tier this action belongs to — see [ActionScope] itself for what each means.
  final ActionScope scope;

  /// The GoRouter route NAME this action navigates to (`context.goNamed(route)`), never a path —
  /// verified against the real router by the CI gate, so this can never point at a route that
  /// was renamed or removed out from under it. REQUIRED when [scope] is [ActionScope.navigation]
  /// (there is nothing to navigate to otherwise); absent for most [ActionScope.system]/[app]
  /// actions, which act in place rather than opening a different app.
  final String? route;

  /// The `mobile_kb.json` entry id this action is paired with — verified to actually exist by
  /// the same gate.
  final String kbEntryId;

  /// Capability ids this session must hold for the action to exist at all — checked against
  /// [Catalog.hasAll], same rule [KbEntry.requires] already holds to.
  final List<String> requires;

  /// A hard kill switch, independent of [requires] — a capability describes WHO may use an
  /// action; this describes whether the action exists AT ALL in this build, for every session,
  /// regardless of capability. Set to `false` to pull a misbehaving action without touching its
  /// registry entry or the model's own tool list shape.
  final bool enabled;

  /// Whether a real tap from the OPERATOR, not the model's own output, is what actually carries
  /// out this action. REQUIRED, never defaulted: the owner's own rule — "تأكيده هو التنفيذ
  /// الفعلي مو الذكاء الاصطناعي" (the operator's own confirmation is the real execution, never
  /// the model) — means every action author must consciously decide this, the same way a KB
  /// entry cannot omit its title. `true` for anything that changes data or has a real-world
  /// effect (a booking, a cancellation); `false` only for actions with no side effect at all —
  /// reading data, or navigating, exactly like this file's own `open_visit_app`.
  final bool requiresConfirmation;

  const AppAction({
    required this.id,
    required this.name,
    required this.description,
    required this.scope,
    this.route,
    required this.kbEntryId,
    required this.enabled,
    required this.requiresConfirmation,
    this.requires = const [],
  });

  factory AppAction.fromJson(String id, Map<String, dynamic> json) {
    final name = json['name'];
    if (name is! String || name.trim().isEmpty) {
      throw ActionError('$id: missing required field "name"');
    }
    final description = json['description'];
    if (description is! String || description.trim().isEmpty) {
      throw ActionError('$id: missing required field "description"');
    }
    final scope = ActionScope.parse(id, json['scope']);

    final routeRaw = json['route'];
    if (routeRaw != null && (routeRaw is! String || routeRaw.trim().isEmpty)) {
      throw ActionError('$id: "route" must be a non-empty string when present');
    }
    final route = routeRaw as String?;
    if (scope == ActionScope.navigation && route == null) {
      throw ActionError('$id: scope "navigation" requires a "route" — nothing to navigate to '
          'otherwise');
    }
    final kbEntryId = json['kb_entry'];
    if (kbEntryId is! String || kbEntryId.trim().isEmpty) {
      throw ActionError('$id: missing required field "kb_entry"');
    }
    final enabled = json['enabled'];
    if (enabled is! bool) {
      throw ActionError('$id: missing required field "enabled" (true/false, no default)');
    }
    final requiresConfirmation = json['requires_confirmation'];
    if (requiresConfirmation is! bool) {
      throw ActionError('$id: missing required field "requires_confirmation" (true/false, no '
          'default — every action must state whether a real tap, not the model, carries it out)');
    }

    final requiresRaw = json['requires'];
    final requires = requiresRaw == null
        ? const <String>[]
        : (requiresRaw is List
            ? requiresRaw.map((e) => e.toString()).toList(growable: false)
            : throw ActionError('$id: "requires" must be a list of capability ids'));

    return AppAction(
      id: id,
      name: name,
      description: description,
      scope: scope,
      route: route,
      kbEntryId: kbEntryId,
      enabled: enabled,
      requiresConfirmation: requiresConfirmation,
      requires: requires,
    );
  }
}

/// Parse a whole action registry document: `{id: entry}`. One bad entry fails the whole load —
/// the same [parseKb] rule, for the same reason: a registry silently missing an action someone
/// wrote is worse than a build that refuses to ship at all.
List<AppAction> parseActions(Map<String, dynamic> raw) {
  final actions = <AppAction>[];
  final seenIds = <String>{};
  final seenNames = <String>{};
  raw.forEach((id, value) {
    if (id.trim().isEmpty) throw ActionError('action id must be a non-empty string');
    if (value is! Map<String, dynamic>) {
      throw ActionError('$id: entry must be an object');
    }
    if (!seenIds.add(id)) throw ActionError('$id: duplicate id — one of them would silently win');
    final action = AppAction.fromJson(id, value);
    if (!seenNames.add(action.name)) {
      throw ActionError('${action.name}: duplicate action name — the model could not tell these '
          'two actions apart');
    }
    actions.add(action);
  });
  return actions;
}
