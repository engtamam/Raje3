import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Wires [AiModel] to [KbService] — Phase 1 of the on-device assistant: a text answer grounded in
/// what this app actually is, never a guess.
///
/// THE SAME "NO GAMES" DISCIPLINE THE OWNER HOLDS FOR MONEY, APPLIED HERE TO INFORMATION. The
/// system prompt built by [_systemPrompt] explicitly tells the model to answer ONLY from the
/// knowledge handed to it and to say it does not know otherwise — the model never sees the whole
/// app, only [KbService.buildKnowledgeText]'s output for entries THIS session's real, already
/// capability-filtered [Catalog] may see (see KbService's own doc comment on why that source, not
/// a role guessed client-side).
///
/// STAYS A THIN WIRE, NOT A SECOND POLICY LAYER. Visibility is decided once, by
/// [KbService.visibleEntries]; this class never re-derives who sees what.
class AssistantService {
  AssistantService({required this.aiModel, required this.kbService});

  final AiModel aiModel;
  final KbService kbService;

  AiModelStatus get status => aiModel.status;
  Stream<AiModelStatus> get statusStream => aiModel.statusStream;
  Stream<int> get downloadProgress => aiModel.downloadProgress;

  Future<void> ensureReady() => aiModel.ensureReady();

  /// Ask the assistant [question] in [lang], grounded in every KB entry [catalog] makes visible.
  /// The caller must check [status] is [AiModelStatus.ready] first — same rule [AiModel.generate]
  /// itself holds to.
  Stream<String> ask(String question, {required String lang, required Catalog catalog}) {
    final knowledge = kbService.buildKnowledgeText(lang, catalog);
    return aiModel.generate(question, systemInstruction: _systemPrompt(knowledge, lang));
  }

  String _systemPrompt(String knowledge, String lang) {
    final rule = lang == 'ar'
        ? 'جاوب فقط من المعلومات التالية عن هذا التطبيق. إذا كان السؤال خارج هذي المعلومات، قل إنك ما تعرف — لا تختلق إجابة أبداً.'
        : 'Answer only from the following information about this app. If the question falls '
            'outside it, say you do not know — never invent an answer.';
    if (knowledge.trim().isEmpty) return rule;
    return '$rule\n\n$knowledge';
  }
}
