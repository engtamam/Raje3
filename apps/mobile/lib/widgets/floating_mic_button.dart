import 'package:flutter/material.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// The always-reachable "talk to the assistant" button — a floating, draggable circle the
/// operator can park anywhere on screen, the fallback for whoever called the wake word and got
/// no response, or who never wants to rely on it at all.
///
/// DEFAULTS TO THE LEFT SIDE, mid-height — never the right, where an RTL app's own back/forward
/// gestures and the bottom bar's rightmost tabs already live. Every drag is persisted through
/// [LocalStorage.setMicButtonPosition] as a screen-fraction (not raw pixels), so it reopens where
/// it was left even after a rotation or on a different device.
///
/// WIRED TO [AssistantChatSheet] BY THE CALLER (MainShell) — this widget never imports the
/// assistant itself, it only fires [onTap]. Showing this button at all is already gated by the
/// caller (only when the AI driver is actually built in), so there is no second "is this feature
/// even on" check inside the widget itself.
class FloatingMicButton extends StatefulWidget {
  final LocalStorage localStorage;
  final VoidCallback? onTap;

  const FloatingMicButton({super.key, required this.localStorage, this.onTap});

  @override
  State<FloatingMicButton> createState() => _FloatingMicButtonState();
}

class _FloatingMicButtonState extends State<FloatingMicButton> {
  static const double _size = 56;
  static const double _defaultDx = 0.06;
  static const double _defaultDy = 0.62;

  Offset? _fraction;

  @override
  void initState() {
    super.initState();
    _fraction = widget.localStorage.getMicButtonPosition();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final height = constraints.maxHeight;
        final fraction = _fraction ?? const Offset(_defaultDx, _defaultDy);
        final left = (fraction.dx * width).clamp(0.0, width - _size);
        final top = (fraction.dy * height).clamp(0.0, height - _size);

        return Positioned(
          left: left,
          top: top,
          child: GestureDetector(
            onPanUpdate: (details) {
              setState(() {
                final newLeft = (left + details.delta.dx).clamp(0.0, width - _size);
                final newTop = (top + details.delta.dy).clamp(0.0, height - _size);
                _fraction = Offset(newLeft / width, newTop / height);
              });
            },
            onPanEnd: (_) {
              if (_fraction != null) {
                widget.localStorage.setMicButtonPosition(_fraction!);
              }
            },
            onTap: widget.onTap,
            child: Container(
              width: _size,
              height: _size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: appPrimaryGradient,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.accent.withValues(alpha: 0.35),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: const Icon(Icons.mic_rounded, color: AppColors.accentContrast, size: 26),
            ),
          ),
        );
      },
    );
  }
}
