import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/actions/action_executor.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/ai/assistant_service.dart';
import 'package:raje3_mobile/core/ai/assistant_turn.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';
import 'package:raje3_mobile/core/voice/speech_input_model.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/assistant_chat_sheet.dart';

/// The always-reachable "talk to the assistant" button — a floating, draggable circle the
/// operator can park anywhere on screen, the fallback for whoever called the wake word and got
/// no response, or who never wants to rely on it at all.
///
/// ONE BUTTON, NO EXTRA SCREENS — the owner's own explicit call. A single tap drives its own
/// state machine (idle → listening → thinking → speaking) and the SAME tap cancels whatever is
/// currently happening: mid-listening cancels the microphone outright (never treats a partial
/// utterance as final), mid-thinking cancels the pending answer, mid-speaking stops the voice.
/// There is no separate "mute" — cancelling always fully stops, exactly as asked.
///
/// FALLS BACK TO THE TEXT SHEET WHEN VOICE ISN'T AVAILABLE. A device with no speech recognizer,
/// no microphone permission, or the 'null' [SpeechInputModel] driver still gets Phase 1 (typed
/// chat, [AssistantChatSheet]) rather than a dead button — the SpeechInputModel port's own
/// `isAvailable()` decides this per tap, never assumed once and cached forever.
///
/// DEFAULTS TO THE LEFT SIDE, mid-height — never the right, where an RTL app's own back/forward
/// gestures and the bottom bar's rightmost tabs already live. Every drag is persisted through
/// [LocalStorage.setMicButtonPosition] as a screen-fraction (not raw pixels), so it reopens where
/// it was left even after a rotation or on a different device.
class FloatingMicButton extends StatefulWidget {
  final LocalStorage localStorage;

  const FloatingMicButton({super.key, required this.localStorage});

  @override
  State<FloatingMicButton> createState() => _FloatingMicButtonState();
}

enum _VoiceState { idle, listening, thinking, speaking }

class _FloatingMicButtonState extends State<FloatingMicButton>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  static const double _size = 56;
  static const double _defaultDx = 0.06;
  static const double _defaultDy = 0.62;

  Offset? _fraction;
  _VoiceState _state = _VoiceState.idle;
  // MIRRORS AssistantService'S OWN STATE, PURELY FOR THE SMALL DOWNLOAD RING BELOW — the app
  // itself never blocks on this: the model downloads in the background the moment this button
  // first mounts (see initState), and every screen underneath keeps working exactly as if the
  // assistant weren't there at all. Only the button's own decoration reacts to it.
  AiModelStatus _modelStatus = AiModelStatus.unavailable;
  int _downloadPercent = 0;
  StreamSubscription<AiModelStatus>? _modelStatusSubscription;
  StreamSubscription<int>? _downloadProgressSubscription;
  StreamSubscription<AiEvent>? _answerSubscription;
  // GUARDS AGAINST A DOUBLE-TAP RACE: _startOrFallBack awaits isAvailable() before _state
  // leaves idle, so a second tap landing inside that window would otherwise start listening
  // twice concurrently. Reset in the same method's finally block, never left stuck true.
  bool _starting = false;

  late final AssistantService _assistant;
  late final TtsModel _tts;
  late final SpeechInputModel _speech;
  late final WakeWordModel _wakeWord;
  late final ActionExecutor _executor;
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _fraction = widget.localStorage.getMicButtonPosition();
    _assistant = context.read<AssistantService>();
    _tts = context.read<TtsModel>();
    _speech = context.read<SpeechInputModel>();
    _wakeWord = context.read<WakeWordModel>();
    _executor = ActionExecutor(registry: context.read<ActionRegistry>());
    _pulseController = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
    unawaited(_maybeStartWakeWord());

    // STARTS THE MODEL DOWNLOAD THE MOMENT THIS BUTTON MOUNTS, NEVER WAITING FOR A FIRST TAP —
    // the owner's own call (2026-09-28): the app stays fully usable the whole time; this button
    // is the only thing that shows anything is happening, via the small ring below. A no-op if
    // the model is already downloaded/ready (AiModel.ensureReady's own contract).
    _modelStatus = _assistant.status;
    _modelStatusSubscription = _assistant.statusStream.listen((s) {
      if (mounted) setState(() => _modelStatus = s);
    });
    _downloadProgressSubscription = _assistant.downloadProgress.listen((p) {
      if (mounted) setState(() => _downloadPercent = p);
    });
    if (_modelStatus != AiModelStatus.ready) {
      unawaited(_assistant.ensureReady(context.read<NavProvider>().catalog));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _wakeWord.dispose();
    _modelStatusSubscription?.cancel();
    _downloadProgressSubscription?.cancel();
    _answerSubscription?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // NEVER LISTEN IN THE BACKGROUND — a battery and privacy requirement, not just a nicety:
    // the wake word is only ever active while this screen is actually visible and foregrounded.
    if (state == AppLifecycleState.resumed) {
      unawaited(_maybeStartWakeWord());
    } else {
      unawaited(_wakeWord.stop());
    }
  }

  /// Starts passive wake-word listening when idle — never while [_speech] or [_tts] already
  /// owns the microphone/audio session (mid-listening/thinking/speaking), and never when the
  /// device can't run the trained model at all ([WakeWordModel.isAvailable] fails closed on a
  /// missing asset or denied permission, same contract every other port here holds).
  Future<void> _maybeStartWakeWord() async {
    if (_state != _VoiceState.idle || _wakeWord.isListening) return;
    if (!await _wakeWord.isAvailable()) return;
    if (!mounted || _state != _VoiceState.idle) return; // still true after the async gap
    await _wakeWord.start(onDetected: _onWakeWordDetected);
  }

  void _onWakeWordDetected() {
    if (!mounted || _state != _VoiceState.idle) return;
    unawaited(_startOrFallBack());
  }

  Future<void> _onTap() async {
    // EVERY NON-FINAL CASE ENDS IN AN EXPLICIT `return` — clearer than relying on Dart's own
    // "no implicit fallthrough" rule to keep these four branches independent.
    switch (_state) {
      case _VoiceState.idle:
        if (_modelStatus == AiModelStatus.error) {
          // RETRY, NOT A DEAD BUTTON — a lost connection mid-download previously left the
          // assistant stuck in AiModelStatus.error forever (found live, 2026-09-28: nothing
          // anywhere retried it). A tap here re-fires the exact same ensureReady() the button's
          // own initState already tried once.
          setState(() => _modelStatus = AiModelStatus.downloading);
          unawaited(_assistant.ensureReady(context.read<NavProvider>().catalog));
          return;
        }
        await _startOrFallBack();
        return;
      case _VoiceState.listening:
        await _speech.cancel();
        _goIdle();
        return;
      case _VoiceState.thinking:
        // NOT AWAITED, DELIBERATELY. cancel()'s own returned Future only signals when a
        // StreamController's own onCancel resource-cleanup finishes — irrelevant here, since
        // we never set one, and the subscription stops delivering events the instant cancel()
        // is called, not when that Future resolves. Awaiting it would block the button's own
        // "cancel" responsiveness on Dart's internal bookkeeping for no real benefit.
        _answerSubscription?.cancel();
        _answerSubscription = null;
        // DEFENSIVE, NOT REDUNDANT: onDone can already be queued as a microtask the instant
        // before cancel() runs, so _deliverAnswer may have started speaking a beat before this
        // branch finishes — stop() is a harmless no-op if nothing is speaking yet.
        await _tts.stop();
        _goIdle();
        return;
      case _VoiceState.speaking:
        await _tts.stop();
        _goIdle();
        return;
    }
  }

  void _showLastError() {
    final error = _assistant.aiModel.lastError;
    if (!mounted || error == null) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error), duration: const Duration(seconds: 8)),
    );
  }

  /// The one place `_state` moves back to idle — always re-arms passive wake-word listening
  /// alongside it (a no-op if the mic session it just gave up is unrelated, or if wake-word
  /// listening isn't available on this device at all).
  void _goIdle() {
    if (!mounted) return;
    setState(() => _state = _VoiceState.idle);
    unawaited(_maybeStartWakeWord());
  }

  Future<void> _startOrFallBack() async {
    if (_starting) return;
    _starting = true;
    try {
      // NEVER TWO MIC SESSIONS AT ONCE — the passive wake-word listener and the real speech
      // recognizer both want the platform's own audio input; stopping the former before the
      // latter opens avoids a real device rejecting the second concurrent AudioRecord session.
      await _wakeWord.stop();
      final available = await _speech.isAvailable();
      if (!mounted) return;
      if (!available) {
        AssistantChatSheet.show(context);
        unawaited(_maybeStartWakeWord());
        return;
      }
      // BEST-EFFORT WARM-UP, NOT AWAITED — a real model load can take a while; firing it here
      // lets it happen while the operator is still talking, instead of only starting once
      // _handleRecognized needs it. _handleRecognized itself still checks status before asking,
      // so a still-loading model degrades to idle rather than crashing on a not-ready ask().
      unawaited(_assistant.ensureReady(context.read<NavProvider>().catalog));
      final lang = Localizations.localeOf(context).languageCode;
      setState(() => _state = _VoiceState.listening);
      await _speech.startListening(
        languageCode: lang,
        onResult: (text, {required isFinal}) {
          if (isFinal) _handleRecognized(text, lang);
        },
      );
    } finally {
      _starting = false;
    }
  }

  void _handleRecognized(String text, String lang) {
    if (!mounted || _state != _VoiceState.listening) return;
    final question = text.trim();
    if (question.isEmpty) {
      _goIdle();
      return;
    }
    if (_assistant.status != AiModelStatus.ready) {
      // The warm-up fired in _startOrFallBack hasn't finished yet — degrade to idle rather
      // than crash on AiModel.generate()'s own "caller must check status first" contract.
      _goIdle();
      return;
    }
    setState(() => _state = _VoiceState.thinking);
    final catalog = context.read<NavProvider>().catalog;
    final buffer = StringBuffer();
    _answerSubscription = _assistant.ask(question, lang: lang, catalog: catalog).listen(
      (event) {
        switch (event) {
          case AiTextToken(:final text):
            buffer.write(text);
          case AiActionProposed():
            _handleProposedAction(event, lang, question);
        }
      },
      onDone: () {
        // Guarded the same way _deliverAnswer guards itself below — a proposed action already
        // resolved to idle (or to opening the chat sheet) must not also deliver whatever text,
        // if any, arrived alongside it.
        if (_state == _VoiceState.thinking) _deliverAnswer(question, buffer.toString(), lang);
      },
    );
  }

  /// Resolves [event] against the REAL, CURRENT catalog — never the snapshot [_handleRecognized]
  /// captured when the question was first asked, since a capability can change mid-turn.
  void _handleProposedAction(AiActionProposed event, String lang, String question) {
    if (!mounted || _state != _VoiceState.thinking) return; // cancelled meanwhile
    final catalog = context.read<NavProvider>().catalog;
    final decision = _executor.resolve(event, catalog);
    switch (decision) {
      case ActionUnavailable():
        // Nothing executable — any text the model also sent alongside it still gets spoken
        // once onDone fires, same as if this event had never arrived.
        break;
      case ActionRunNow(:final action):
        _answerSubscription?.cancel();
        _answerSubscription = null;
        unawaited(_runAndDeliver(question, action, lang));
      case ActionNeedsConfirmation():
        // NO HANDS-FREE CONFIRMATION SURFACE EXISTS on this button — a sensitive action falls
        // back to the chat sheet, where a real tap can confirm it (AssistantChatSheet's own
        // inline confirm/cancel row), rather than ever running without one.
        _answerSubscription?.cancel();
        _answerSubscription = null;
        _goIdle();
        AssistantChatSheet.show(context);
    }
  }

  /// Carries out a run-now action, then DELIVERS whatever real answer it produced (a READ
  /// action) before returning to idle — never a silent `_goIdle()` for those, which would make
  /// the operator wait for a reply that simply never comes. `null` (navigation; nothing to say)
  /// goes idle immediately, same as before this existed.
  Future<void> _runAndDeliver(String question, AppAction action, String lang) async {
    final result = await _executor.execute(context, action);
    if (!mounted) return;
    if (result != null) {
      await _deliverAnswer(question, result, lang);
      return;
    }
    _goIdle();
  }

  /// Speaks [answer] aloud, or — when the operator's own reply-mode setting asks for text
  /// instead (see [LocalStorage.assistantReplyIsVoice]) — opens the chat sheet with [question]
  /// and [answer] already filled in, exactly as if he had typed the question there himself.
  /// This is the one place a voice QUESTION can still end in a WRITTEN answer.
  Future<void> _deliverAnswer(String question, String answer, String lang) async {
    if (!mounted || _state != _VoiceState.thinking) return; // cancelled meanwhile
    if (!widget.localStorage.assistantReplyIsVoice) {
      _goIdle();
      AssistantChatSheet.show(context, seed: AssistantTurn(question: question, answer: answer));
      return;
    }
    setState(() => _state = _VoiceState.speaking);
    await _tts.speak(answer, languageCode: lang);
    if (mounted && _state == _VoiceState.speaking) _goIdle();
  }

  IconData _mainIcon() {
    if (_state != _VoiceState.idle) return Icons.stop_rounded;
    return Icons.mic_rounded;
  }

  @override
  Widget build(BuildContext context) {
    // MediaQuery.sizeOf, NEVER a LayoutBuilder HERE. A LayoutBuilder is itself a
    // RenderObjectWidget — wrapping the Positioned this build() returns in one (as an earlier
    // version of this file did) inserts LayoutBuilder's own render object as the actual child
    // Stack sees, so Positioned's left/top attach one level too deep and are silently ignored:
    // the button always renders at Stack's default alignment, never where a drag left it. This
    // widget's build() must return Positioned directly — no RenderObjectWidget between it and
    // whatever Stack this sits in.
    final size = MediaQuery.sizeOf(context);
    final width = size.width;
    final height = size.height;
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
          if (_fraction != null) widget.localStorage.setMicButtonPosition(_fraction!);
        },
        onTap: _onTap,
        // LONG-PRESS SHOWS THE REAL EXCEPTION, NOT JUST "IT FAILED" — ensureReady() never
        // rethrows (by design, see AiModel.ensureReady's own doc comment), so before
        // AiModel.lastError existed a support report only ever carried "the red circle stayed
        // red", never the actual reason. A tap keeps retrying (the fix above); a long-press
        // is a diagnostic escape hatch that does not interrupt that flow.
        onLongPress: _modelStatus == AiModelStatus.error ? _showLastError : null,
        child: AnimatedBuilder(
          animation: _pulseController,
          builder: (context, child) {
            final pulse = _state == _VoiceState.idle ? 0.0 : _pulseController.value;
            return Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                if (pulse > 0)
                  Container(
                    width: _size + 20 * pulse,
                    height: _size + 20 * pulse,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.accent.withValues(alpha: 0.25 * (1 - pulse)),
                    ),
                  ),
                child!,
              ],
            );
          },
          child: Stack(
            alignment: Alignment.center,
            clipBehavior: Clip.none,
            children: [
              Container(
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
                child: Icon(
                  _mainIcon(),
                  color: AppColors.accentContrast,
                  size: 26,
                ),
              ),
              // THE ONLY VISIBLE TRACE OF THE BACKGROUND MODEL DOWNLOAD — a thin ring, never a
              // blocking dialog: the button (and every screen under it) stays fully usable while
              // this shows. Hidden entirely once ready/idle-with-no-model-story, so a device that
              // never runs the assistant (AiModelStatus.unavailable) sees no ring, ever.
              if (_state == _VoiceState.idle && _modelStatus == AiModelStatus.downloading)
                SizedBox(
                  width: _size + 6,
                  height: _size + 6,
                  child: CircularProgressIndicator(
                    value: _downloadPercent > 0 ? _downloadPercent / 100 : null,
                    strokeWidth: 2.5,
                    color: AppColors.accentContrast,
                    backgroundColor: AppColors.accentContrast.withValues(alpha: 0.25),
                  ),
                ),
              if (_state == _VoiceState.idle && _modelStatus == AiModelStatus.error)
                Positioned(
                  bottom: -2,
                  right: -2,
                  child: Container(
                    width: 16,
                    height: 16,
                    decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.redAccent),
                    child: const Icon(Icons.refresh_rounded, size: 11, color: Colors.white),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
