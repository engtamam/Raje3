import 'package:flutter/widgets.dart';

/// Marks one UI element as a KB anchor — declares "this widget IS explained by KB entry [id]",
/// nothing else. Renders its [child] unchanged.
///
/// WHY THIS EXISTS AT ALL. `ci/check_mobile_kb_anchors_are_covered.py` greps every mobile screen
/// for `KbAnchor(id: '...')` and cross-checks the result against `assets/knowledge/mobile_kb.json`
/// in BOTH directions: a widget wired to an anchor with no KB entry, or a KB entry whose anchor no
/// widget references any more, both fail the build. Without this marker there is nothing for that
/// gate to grep — "does every label/action have an explanation the assistant can give when asked"
/// would be unverifiable, exactly the drift the owner asked to close permanently.
///
/// NEVER A VISIBLE "؟" BUTTON — the owner's own standing rule for this app: help is entirely
/// through the AI assistant a session can ask directly, never a separate help icon on any screen.
/// This marker is invisible on purpose (`build()` returns [child] unchanged); a screen's own
/// root is wrapped in one purely so its KB entry stays anchored to something real in code.
class KbAnchor extends StatelessWidget {
  final String id;
  final Widget child;

  const KbAnchor({super.key, required this.id, required this.child});

  @override
  Widget build(BuildContext context) => child;
}
