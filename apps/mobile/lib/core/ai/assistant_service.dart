import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Wires [AiModel] to [KbService] AND [ActionRegistry] — one model doing both jobs the owner
/// asked for: a text answer grounded in what this app actually is, and (per [AiTool]/[AiEvent])
/// a proposed action it wants considered. Never a guess, never an execution — see below.
///
/// THE SAME "NO GAMES" DISCIPLINE THE OWNER HOLDS FOR MONEY, APPLIED HERE TO INFORMATION AND TO
/// ACTIONS. The system prompt built by [_systemPrompt] explicitly tells the model to answer ONLY
/// from the knowledge handed to it and to say it does not know otherwise — the model never sees
/// the whole app, only [KbService.buildKnowledgeText]'s output for entries THIS session's real,
/// already capability-filtered [Catalog] may see. The SAME catalog is what [ActionRegistry]
/// filters its own tool list by — an action the session's capability doesn't hold is never even
/// DECLARED to the model, the same "invisible, not just refused" posture [KbService] already
/// holds to (see both classes' own doc comments on why that source, never a role guessed
/// client-side).
///
/// AN [AiActionProposed] EVENT IS EXACTLY THAT — A PROPOSAL. This class never executes one
/// itself; it is the caller's job (per [AppAction.requiresConfirmation]) to validate against the
/// real, current [Catalog] again — a capability held when the tool list was built could have
/// changed by the time the model actually proposes calling it — and to decide whether a real tap
/// from the operator is what carries it out. That executor does not exist yet; this class only
/// carries the event through unchanged.
///
/// STAYS A THIN WIRE, NOT A SECOND POLICY LAYER. Visibility is decided once, by
/// [KbService.visibleEntries]/[ActionRegistry.visibleActions]; this class never re-derives who
/// sees what.
class AssistantService {
  AssistantService({required this.aiModel, required this.kbService, required this.actionRegistry});

  final AiModel aiModel;
  final KbService kbService;
  final ActionRegistry actionRegistry;

  AiModelStatus get status => aiModel.status;
  Stream<AiModelStatus> get statusStream => aiModel.statusStream;
  Stream<int> get downloadProgress => aiModel.downloadProgress;

  /// [catalog] IS FIXED FOR THE SESSION ONCE THIS RESOLVES — see [AiModel.ensureReady]'s own doc
  /// comment on why tools cannot change per question. A no-op call (model already ready) keeps
  /// whatever tool list the FIRST real call declared.
  Future<void> ensureReady(Catalog catalog) => aiModel.ensureReady(tools: actionRegistry.toolsFor(catalog));

  /// Ask the assistant [question] in [lang], grounded in the KB entries [catalog] makes visible
  /// AND that [question] is actually about (see [KbService.buildKnowledgeText] on why it is not
  /// simply every entry). The caller must check [status] is [AiModelStatus.ready] first — same
  /// rule [AiModel.generate] itself holds to.
  Stream<AiEvent> ask(String question, {required String lang, required Catalog catalog}) {
    final knowledge = kbService.buildKnowledgeText(lang, catalog, question: question);
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
