// BM25 relevance selection — the piece that keeps buildKnowledgeText() from dumping the whole
// KB into every question as the KB grows past today's 4 screens. Uses the REAL shipped
// assets/knowledge/mobile_kb.json, the same way assistant_service_test.dart does.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

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
    expect(text, contains('تسجيل زيارة'));
    expect(text, isNot(contains('فتح محل جديد')));
  });

  test('a question about opening a shop selects the signup entry, not the visit one', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: 'كيف أفتح محل جديد؟');
    expect(text, contains('فتح محل جديد'));
    expect(text, isNot(contains('تسجيل زيارة')));
  });

  test('a bare "؟" with no recognizable words falls back to every visible entry', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: '؟');
    expect(text, contains('تسجيل الدخول'));
    expect(text, contains('فتح محل جديد'));
    expect(text, contains('تأكيد رقم الجوال'));
    expect(text, contains('تسجيل زيارة'));
  });

  test('no question at all still returns every visible entry (old behaviour preserved)', () {
    final text = kb.buildKnowledgeText('ar', fullCatalog);
    expect(text, contains('تسجيل الدخول'));
    expect(text, contains('تسجيل زيارة'));
  });

  test('a diacritic- and clitic-mismatched question still matches the visit entry', () {
    // "والزيارة" (with the conjunction "و" glued on) and full tashkeel on "سُجِّل" —
    // neither should stop the match, per _normalizeArabic/_stripArabicClitic.
    final text = kb.buildKnowledgeText('ar', fullCatalog, question: 'وَالزِّيَارَة كيف أُسَجِّل؟');
    expect(text, contains('تسجيل زيارة'));
  });

  test('an entry gated by a capability the session lacks never surfaces, even when the '
      'question is clearly about it', () {
    final text = kb.buildKnowledgeText('ar', Catalog.empty, question: 'كيف أسجل زيارة للعميل؟');
    expect(text, isNot(contains('تسجيل زيارة')));
  });
}
