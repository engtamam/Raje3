import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Loads `assets/knowledge/mobile_actions.json` once — the mobile mirror of [KbService]
/// (lib/core/knowledge/kb_service.dart), same "shipped inside the app, never fetched" rule.
class ActionRegistry {
  Map<String, AppAction> _actions = {};
  bool _loaded = false;

  static const _assetPath = 'assets/knowledge/mobile_actions.json';

  Future<void> init() async {
    if (_loaded) return;
    final raw = await rootBundle.loadString(_assetPath);
    final json = jsonDecode(raw) as Map<String, dynamic>;
    final actions = parseActions(json);
    _actions = {for (final a in actions) a.id: a};
    _loaded = true;
  }

  bool _visible(AppAction a, Catalog catalog) {
    if (a.requires.isEmpty) return true;
    return catalog.hasAll(a.requires);
  }

  /// Every action THIS session's real, already capability-filtered [catalog] allows — never a
  /// role guessed client-side. What actually gets declared to the model as its tool list.
  Iterable<AppAction> visibleActions(Catalog catalog) => _actions.values.where((a) => _visible(a, catalog));

  /// The action named [name] (as the model returned it in a function call), IF this session may
  /// still use it — checked again at execution time, never trusted from when the tool list was
  /// built, since a subscription/role could have changed mid-conversation.
  AppAction? byName(String name, Catalog catalog) {
    for (final a in _actions.values) {
      if (a.name == name && _visible(a, catalog)) return a;
    }
    return null;
  }
}
