import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:raje3_mobile/core/knowledge/kb_model.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Loads `assets/knowledge/mobile_kb.json` once and serves both consumers this app's own KB
/// needs — the same split `AppGuideService` (reference project) already proved works:
///
///   1. A "؟" button reading one entry by [anchor] — no model, no retrieval, a dictionary lookup.
///   2. The on-device assistant's own context — [buildKnowledgeText] flattens every entry this
///      session is allowed to see into plain text for the model's prompt.
///
/// SHIPPED INSIDE THE APP, NEVER FETCHED. Per the owner's own rule for the on-device assistant —
/// nothing about it may reach our servers — this file is a build asset, updated by shipping a new
/// app version, not a request this app ever makes.
class KbService {
  Map<String, KbEntry> _entries = {};
  bool _loaded = false;

  static const _assetPath = 'assets/knowledge/mobile_kb.json';

  Future<void> init() async {
    if (_loaded) return;
    final raw = await rootBundle.loadString(_assetPath);
    final json = jsonDecode(raw) as Map<String, dynamic>;
    final entries = parseKb(json);
    _entries = {for (final e in entries) e.id: e};
    _loaded = true;
  }

  KbEntry? entry(String id) => _entries[id];

  /// The entry tied to this UI [anchor], if any and if this session may see it.
  KbEntry? byAnchor(String anchor, Catalog catalog) {
    for (final e in _entries.values) {
      if (e.anchor == anchor && _visible(e, catalog)) return e;
    }
    return null;
  }

  bool _visible(KbEntry e, Catalog catalog) {
    if (e.requires.isEmpty) return true;
    return catalog.hasAll(e.requires);
  }

  Iterable<KbEntry> visibleEntries(Catalog catalog) => _entries.values.where((e) => _visible(e, catalog));

  /// Every visible entry, flattened to plain text in [lang] — fed into the on-device model's
  /// system prompt so it answers from what this app actually is, never a guess.
  String buildKnowledgeText(String lang, Catalog catalog) {
    final buf = StringBuffer();
    for (final e in visibleEntries(catalog)) {
      final (title, body) = e.text(lang);
      buf.writeln('## $title');
      buf.writeln(body);
      buf.writeln();
    }
    return buf.toString();
  }
}
