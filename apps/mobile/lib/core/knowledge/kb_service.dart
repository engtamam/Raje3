import 'dart:convert';
import 'dart:math' as math;

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

  /// Every visible entry, or — when [question] is given — only the entries actually relevant to
  /// it, flattened to plain text in [lang] for the model's system prompt.
  ///
  /// WHY THIS EXISTS AT ALL. Today's KB is 4 screens, small enough to hand the model whole. It
  /// will not stay that way — every future screen adds its own entries — and a model has a real,
  /// finite context limit (GemmaAiModel.ensureReady() itself asks for `maxTokens: 2048`). Dumping
  /// the entire KB into every question would silently stop fitting the moment the KB outgrows
  /// that budget, the exact scaling gap flagged when this assistant was first wired up. Selecting
  /// only what the question is actually about is what keeps "add a screen, add its KB entries"
  /// working forever, instead of needing a second pass once the KB is large.
  ///
  /// BM25, NOT AN EMBEDDING MODEL. Running a second on-device model just to rank a few dozen
  /// short entries would cost far more (another multi-hundred-MB download, more RAM, more
  /// battery) than it could ever save — the KB entries are short, human-written sentences, and
  /// classic lexical scoring is the well-understood, right-sized tool at this scale. A plain
  /// keyword-overlap count (an earlier pass of this file) has one real defect: it can't tell a
  /// common word every entry shares (e.g. "شاشة", "screen") from the one specific word that
  /// actually identifies the right entry. BM25 fixes exactly that, at the same O(entries) cost.
  String buildKnowledgeText(String lang, Catalog catalog, {String? question, int limit = 5}) {
    final entries = question == null || question.trim().isEmpty
        ? visibleEntries(catalog)
        : _relevantEntries(question, catalog, limit: limit);
    final buf = StringBuffer();
    for (final e in entries) {
      final (title, body) = e.text(lang);
      buf.writeln('## $title');
      buf.writeln(body);
      buf.writeln();
    }
    return buf.toString();
  }

  /// The [limit] visible entries BM25-ranked against [question], most-relevant first. A question
  /// with no recognizable words (e.g. a bare "؟") falls back to every visible entry — the same
  /// behaviour as calling [buildKnowledgeText] with no question at all, since there is nothing to
  /// rank against.
  Iterable<KbEntry> _relevantEntries(String question, Catalog catalog, {required int limit}) {
    final qTokens = _tokenize(question).toSet();
    if (qTokens.isEmpty) return visibleEntries(catalog);

    final visible = visibleEntries(catalog).toList();
    if (visible.isEmpty) return const [];
    final docTokens = <KbEntry, List<String>>{
      for (final e in visible) e: _tokenize(_entryText(e)).toList(),
    };

    // Classic BM25: idf per query term across THIS session's visible entries (never a role's
    // full KB — an entry a caller can't see must not even shape another entry's ranking), then
    // a length-normalized term-frequency score per entry, k1/b at their standard textbook values.
    const k1 = 1.5;
    const b = 0.75;
    final n = visible.length;
    final avgDocLen = docTokens.values.map((t) => t.length).reduce((a, c) => a + c) / n;

    final df = <String, int>{};
    for (final tokens in docTokens.values) {
      for (final term in tokens.toSet()) {
        df[term] = (df[term] ?? 0) + 1;
      }
    }
    double idf(String term) {
      final f = df[term] ?? 0;
      if (f == 0) return 0;
      return _ln((n - f + 0.5) / (f + 0.5) + 1);
    }

    final scored = <MapEntry<KbEntry, double>>[];
    for (final e in visible) {
      final tokens = docTokens[e]!;
      if (tokens.isEmpty) continue;
      final tf = <String, int>{};
      for (final t in tokens) {
        tf[t] = (tf[t] ?? 0) + 1;
      }
      var score = 0.0;
      for (final term in qTokens) {
        final freq = tf[term];
        if (freq == null) continue;
        final norm = 1 - b + b * (tokens.length / avgDocLen);
        score += idf(term) * (freq * (k1 + 1)) / (freq + k1 * norm);
      }
      if (score > 0) scored.add(MapEntry(e, score));
    }
    scored.sort((a, b) => b.value.compareTo(a.value));
    return scored.take(limit).map((entry) => entry.key);
  }

  String _entryText(KbEntry e) {
    final (titleAr, bodyAr) = e.text('ar');
    final (titleEn, bodyEn) = e.text('en');
    return '$titleAr $bodyAr $titleEn $bodyEn ${e.id}';
  }

  static final _wordPattern = RegExp(r'[^\p{L}\p{N}]+', unicode: true);
  // Tashkeel (diacritics) + tatweel — present in carefully-typed KB body text far more often
  // than in what someone actually types as a question, so leaving them in would silently break
  // matching on the KB side only. Stripped before tokenizing, on both the question and the KB.
  static final _arabicDiacritics = RegExp('[ؐ-ًؚ-ٰٟـ]');

  List<String> _tokenize(String text) {
    final normalized = _normalizeArabic(text.toLowerCase());
    return normalized
        .split(_wordPattern)
        .map(_stripArabicClitic)
        .where((t) => t.length > 1)
        .toList();
  }

  /// Folds the alef/ya/ta-marbuta variants a real user routinely mixes up (أ/إ/آ vs ا, ى vs ي,
  /// ة vs ه) to one canonical form, and drops diacritics/tatweel — matters more here than
  /// stemming, since these are typos a lexical matcher would otherwise treat as different words.
  String _normalizeArabic(String text) {
    return text
        .replaceAll(_arabicDiacritics, '')
        .replaceAll(RegExp('[إأآ]'), 'ا')
        .replaceAll('ى', 'ي')
        .replaceAll('ة', 'ه');
  }

  static final _arabicCliticPrefix = RegExp(r'^(?:وال|فال|بال|كال|لل|ال|و|ف|ب|ل|ك)');

  /// Strips a leading definite article (ال) or single-letter conjunction/preposition (و ف ب ل ك)
  /// — Arabic attaches these directly to the next word with no space, so "والحجز" and "الحجز"
  /// tokenize as unrelated words without this, even though they share the same root. Only
  /// applied when enough of the word survives, so short real words are never gutted.
  String _stripArabicClitic(String token) {
    if (token.length < 5) return token;
    final stripped = token.replaceFirst(_arabicCliticPrefix, '');
    return stripped.length >= 3 ? stripped : token;
  }
}

double _ln(double x) => x <= 0 ? 0 : math.log(x);
