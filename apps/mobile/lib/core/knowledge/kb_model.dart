/// One explainable thing about THIS APP — not the shop's business data (prices, services,
/// bookings), which lives in the shop's own catalogue and is never guessed here. This is product
/// knowledge: what a screen/label/action does and, later, how the assistant can act on it.
///
/// LEARNED FROM TWO PLACES, KEPT AS ONE SHAPE.
///
///   - The reference project's `assets/knowledge/app_guides.json` / `AppGuideService`: a single
///     JSON file shipped INSIDE the app (not fetched from a server), loaded once, that serves
///     both a UI "؟" sheet AND the AI's own context — one source, never two copies to drift.
///
///   - This platform's own `platform/services/assistant-service/app/core/kb.py`: the richer
///     record shape (`kind`, `anchor`, `requires`, `related`, a language MAP rather than
///     `title_ar`/`title_en` fields) already proven server-side for the exact same console "؟"
///     icon (see AssistantHint.tsx / Hint.tsx) — reused here rather than invented twice.
///
/// `requires` iS CHECKED AGAINST THE REAL, ALREADY-CAPABILITY-FILTERED CATALOGUE
/// ([Catalog.hasAll]) — the same source [NavProvider.visibleSections] trusts. An entry naming a
/// capability the signed-in operator does not hold is invisible to BOTH the "؟" button and the AI
/// context builder — describing what a role cannot do teaches the wrong door, exactly kb.py's own
/// `visible_to` reasoning.
library;

class KbError extends FormatException {
  KbError(super.message);
}

const String _defaultLang = 'ar';

Map<String, String> _textMap(dynamic value, {required String entryId, required String field}) {
  if (value is String) {
    if (value.trim().isEmpty) throw KbError('$entryId: $field is empty');
    return {_defaultLang: value};
  }
  if (value is! Map || value.isEmpty) {
    throw KbError('$entryId: $field must be a non-empty string or {lang: text} map');
  }
  final out = <String, String>{};
  value.forEach((lang, text) {
    if (lang is! String || lang.trim().isEmpty) {
      throw KbError('$entryId: $field has a non-string language key');
    }
    if (text is! String || text.trim().isEmpty) {
      throw KbError('$entryId: $field[$lang] is empty — omit the language instead');
    }
    out[lang.trim().toLowerCase()] = text;
  });
  return out;
}

String _pick(Map<String, String> m, String lang) {
  final key = lang.trim().toLowerCase();
  if (m.containsKey(key)) return m[key]!;
  final base = key.split('-').first;
  if (m.containsKey(base)) return m[base]!;
  if (m.containsKey(_defaultLang)) return m[_defaultLang]!;
  return m.values.isEmpty ? '' : m.values.first;
}

/// An optional "take me there" action attached to an entry — the reference project's `cta`
/// field. A route the router already knows, never a guessed path.
class KbCta {
  final String label;
  final String route;
  const KbCta({required this.label, required this.route});
}

class KbEntry {
  final String id;
  final Map<String, String> title;
  final Map<String, String> body;

  /// Free-form, same as kb.py: 'screen' | 'field' | 'howto' | 'action' | ''.
  final String kind;

  /// Ties this entry to one UI element, for a direct "؟" lookup with no search.
  final String anchor;

  /// Capability ids this session must hold for this entry to exist at all — checked against
  /// [Catalog.hasAll], never a role name guessed client-side.
  final List<String> requires;

  final List<String> related;
  final KbCta? cta;

  const KbEntry({
    required this.id,
    required this.title,
    required this.body,
    this.kind = '',
    this.anchor = '',
    this.requires = const [],
    this.related = const [],
    this.cta,
  });

  (String, String) text(String lang) => (_pick(title, lang), _pick(body, lang));

  factory KbEntry.fromJson(String id, Map<String, dynamic> json) {
    if (!json.containsKey('title')) throw KbError('$id: missing required field "title"');
    if (!json.containsKey('body')) throw KbError('$id: missing required field "body"');

    final requiresRaw = json['requires'];
    final requires = requiresRaw == null
        ? const <String>[]
        : (requiresRaw is List
            ? requiresRaw.map((e) => e.toString()).toList(growable: false)
            : throw KbError('$id: "requires" must be a list of capability ids'));

    final relatedRaw = json['related'];
    final related = relatedRaw == null
        ? const <String>[]
        : (relatedRaw is List
            ? relatedRaw.map((e) => e.toString()).toList(growable: false)
            : throw KbError('$id: "related" must be a list of entry ids'));

    final ctaRaw = json['cta'];
    KbCta? cta;
    if (ctaRaw != null) {
      if (ctaRaw is! Map || ctaRaw['label'] == null || ctaRaw['route'] == null) {
        throw KbError('$id: "cta" must be an object with "label" and "route"');
      }
      cta = KbCta(label: ctaRaw['label'].toString(), route: ctaRaw['route'].toString());
    }

    return KbEntry(
      id: id,
      title: _textMap(json['title'], entryId: id, field: 'title'),
      body: _textMap(json['body'], entryId: id, field: 'body'),
      kind: (json['kind'] ?? '').toString().trim().toLowerCase(),
      anchor: (json['anchor'] ?? '').toString().trim(),
      requires: requires,
      related: related,
      cta: cta,
    );
  }
}

/// Parse a whole KB document: `{id: entry}`. Every entry is validated, and one bad entry fails
/// the whole load — the same kb.py rule: a KB that ships silently missing an entry someone wrote
/// is worse than a build that refuses to ship at all.
List<KbEntry> parseKb(Map<String, dynamic> raw) {
  final entries = <KbEntry>[];
  final seen = <String>{};
  raw.forEach((id, value) {
    if (id.trim().isEmpty) throw KbError('entry id must be a non-empty string');
    if (value is! Map<String, dynamic>) {
      throw KbError('$id: entry must be an object');
    }
    if (!seen.add(id)) throw KbError('$id: duplicate id — one of them would silently win');
    entries.add(KbEntry.fromJson(id, value));
  });
  return entries;
}
