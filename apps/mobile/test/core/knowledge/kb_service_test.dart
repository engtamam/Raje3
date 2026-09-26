// BM25 relevance selection — the piece that keeps buildKnowledgeText() from dumping the whole
// KB into every question as the KB grows past today's 4 screens. Uses the REAL shipped
// assets/knowledge/mobile_kb.json, the same way assistant_service_test.dart does.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // The "visit.register" entry's OWN heading, never a bare 'تسجيل زيارة' — that phrase also
  // appears inside OTHER, ungated entries' own body prose (adding a customer "بدون تسجيل زيارة",
  // the vehicle-tracking switch's own description), which made every assertion below pass or
  // fail for the wrong reason: a bare substring check cannot tell "the gated entry is present"
  // apart from "an unrelated entry happened to mention the same two words in passing".
  const visitHeading = '## تسجيل زيارة\n';

  late KbService kb;
  const fullCatalog = Catalog(
    services: [
      CatalogServiceEntry(
        service: 'operations',
        actions: [
          CatalogAction(
            id: 'operations.record_visit',
            label: 'x',
            method: 'GET',
            path: '/x',
            capability: 'operations.record_visit',
          ),
        ],
      ),
    ],
    unreachable: [],
  );

  setUpAll(() async {
    kb = KbService();
    await kb.init();
  });

  test('a question about visits selects the visit entry, not an unrelated one', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: 'كيف أسجل زيارة للعميل؟');
    expect(text, contains(visitHeading));
    expect(text, isNot(contains('فتح محل جديد')));
  });

  test('a question about opening a shop selects the signup entry, not the visit one', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: 'كيف أفتح محل جديد؟');
    expect(text, contains('فتح محل جديد'));
    expect(text, isNot(contains(visitHeading)));
  });

  test('a bare "؟" with no recognizable words falls back to every visible entry', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: '؟');
    expect(text, contains('تسجيل الدخول'));
    expect(text, contains('فتح محل جديد'));
    expect(text, contains('تأكيد رقم الجوال'));
    expect(text, contains(visitHeading));
  });

  test('no question at all still returns every visible entry (old behaviour preserved)', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog);
    expect(text, contains('تسجيل الدخول'));
    expect(text, contains(visitHeading));
  });

  test('a diacritic- and clitic-mismatched question still matches the visit entry', () {
    // "والزيارة" (with the conjunction "و" glued on) and full tashkeel on "سُجِّل" —
    // neither should stop the match, per _normalizeArabic/_stripArabicClitic.
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: 'وَالزِّيَارَة كيف أُسَجِّل؟');
    expect(text, contains(visitHeading));
  });

  test('an entry gated by a capability the session lacks never surfaces, even when the '
      'question is clearly about it', () {
    final text = kb.buildKnowledgeText('ar', Catalog.empty, question: 'كيف أسجل زيارة للعميل؟');
    expect(text, isNot(contains(visitHeading)));
  });
}
