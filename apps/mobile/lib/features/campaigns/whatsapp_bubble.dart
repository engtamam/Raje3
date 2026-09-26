import 'package:flutter/material.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// A real WhatsApp message bubble — the ONE thing this pass must never simplify away (this
/// feature's own brief: a shop owner sending a real marketing message must see exactly what the
/// customer receives). Fixed WhatsApp green (`#DCF8C6`) on purpose, same literal colour the
/// console's own `MessagePreview.tsx::Bubble` uses — a brand colour, never the app's own themed
/// surface, so what renders here matches what actually arrives on a real phone regardless of
/// which theme the shop picked for itself.
class WhatsAppBubble extends StatelessWidget {
  const WhatsAppBubble({super.key, required this.text, this.caption, this.buttons = const []});

  final String text;
  final String? caption;
  /// Drawn OUTSIDE the bubble, exactly where Meta actually renders them — never inside the
  /// message text. Static labels only this pass: opening a Flow for real stays deferred (see
  /// this feature's own build notes) — a shop owner still sees exactly which button ships with
  /// the message, just cannot walk through its screens here yet.
  final List<MessageButton> buttons;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFDCF8C6),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(2),
              bottomRight: Radius.circular(16),
            ),
            boxShadow: [
              BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 6, offset: const Offset(0, 2)),
            ],
          ),
          child: Text(
            text.isEmpty ? '…' : text,
            style: const TextStyle(color: Color(0xFF111B21), fontSize: 14, height: 1.5, fontFamily: 'Cairo'),
          ),
        ),
        if (buttons.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 1),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: Colors.black12),
            ),
            child: Column(
              children: [
                for (final b in buttons)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    decoration: const BoxDecoration(
                      border: Border(top: BorderSide(color: Colors.black12)),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(b.kind == 'flow' ? Icons.auto_awesome_outlined : Icons.open_in_new,
                            size: 14, color: const Color(0xFF0091FF)),
                        const SizedBox(width: 6),
                        Text(b.label, style: const TextStyle(color: Color(0xFF0091FF), fontSize: 13, fontFamily: 'Cairo')),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (caption != null) ...[
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Text(caption!, style: AppTextStyles.caption),
          ),
        ],
      ],
    );
  }
}

/// The "phone" frame around a bubble, used by the wizard's full-screen preview step — a dark
/// chat-wallpaper backdrop so the bubble reads as "this is inside WhatsApp", not "this is inside
/// our app". Deliberately plain (no status bar / header chrome) — that extra realism is the
/// console's own `WhatsAppTemplatePreview`'s job on a wide screen with room for it; on a phone,
/// the bubble itself IS the phone, and drawing a phone-inside-a-phone reads as a toy, not a preview.
class WhatsAppPhoneFrame extends StatelessWidget {
  const WhatsAppPhoneFrame({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0B141A),
        borderRadius: AppRadius.cardRadius,
      ),
      child: Align(alignment: Alignment.centerLeft, child: child),
    );
  }
}
