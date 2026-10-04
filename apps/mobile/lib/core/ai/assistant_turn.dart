import 'package:raje3_mobile/core/actions/action_model.dart';

/// One question/answer pair in an assistant conversation — shared between
/// [AssistantChatSheet]'s own scrollback and [FloatingMicButton]'s hand-off
/// into it (see [AssistantChatSheet.new]'s `seed` parameter), so a voice
/// question answered in text mode shows up exactly like one typed there.
class AssistantTurn {
  final String question;
  String answer;
  AppAction? pendingAction;
  AssistantTurn({required this.question, this.answer = ''});
}
