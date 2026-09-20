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

class AppAction {
  /// This registry's own key — also what `ci/check_mobile_actions_are_covered.py` reports by.
  final String id;

  /// The name the model is given and returns in a function call — must be a valid identifier;
  /// never the same string as [id] by requirement, but conventionally similar.
  final String name;

  /// What the model reads to decide whether THIS action matches the user's intent. Written for
  /// the model, not for a person — plain, unambiguous, one sentence.
  final String description;

  /// The GoRouter route NAME this action navigates to (`context.goNamed(route)`), never a path —
  /// verified against the real router by the CI gate, so this can never point at a route that
  /// was renamed or removed out from under it.
  final String route;

  /// The `mobile_kb.json` entry id this action is paired with — verified to actually exist by
  /// the same gate.
  final String kbEntryId;

  /// Capability ids this session must hold for the action to exist at all — checked against
  /// [Catalog.hasAll], same rule [KbEntry.requires] already holds to.
  final List<String> requires;

  const AppAction({
    required this.id,
    required this.name,
    required this.description,
    required this.route,
    required this.kbEntryId,
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
    final route = json['route'];
    if (route is! String || route.trim().isEmpty) {
      throw ActionError('$id: missing required field "route"');
    }
    final kbEntryId = json['kb_entry'];
    if (kbEntryId is! String || kbEntryId.trim().isEmpty) {
      throw ActionError('$id: missing required field "kb_entry"');
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
      route: route,
      kbEntryId: kbEntryId,
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
