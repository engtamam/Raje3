// Deep, state-machine-level tests for FloatingMicButton — the single button that drives
// idle → listening → thinking → speaking, and must cancel cleanly from ANY of those states
// (the owner's own explicit rule: cancelling always fully stops, never just mutes).
//
// SECURITY/CORRECTNESS EDGE CASES THIS FILE EXISTS FOR:
//   - a cancel issued mid-"thinking" must NEVER let a late-arriving answer start speaking
//     (the exact race AssistantChatSheet.dispose()/FloatingMicButton._onTap's own comment
//     calls out) — reproduced here with a fake AI model whose stream is closed manually.
//   - an empty recognized transcript must never reach the assistant at all.
//   - a slow isAvailable() must not let a double-tap start listening twice.
//   - the button must actually render at its dragged position (see floating_mic_button.dart's
//     own comment on the LayoutBuilder-wrapping-Positioned bug this test would have caught).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/ai/assistant_service.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';
import 'package:raje3_mobile/core/voice/speech_input_model.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/widgets/floating_mic_button.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeAiModel implements AiModel {
  StreamController<AiEvent>? controller;
  int askCount = 0;

  @override
  String get driver => 'fake';
  @override
  AiModelStatus get status => AiModelStatus.ready;
  @override
  Stream<AiModelStatus> get statusStream => Stream.value(AiModelStatus.ready);
  @override
  Stream<int> get downloadProgress => const Stream.empty();
  @override
  Future<void> ensureReady({List<AiTool> tools = const []}) async {}
  @override
  Stream<AiEvent> generate(String prompt, {String systemInstruction = ''}) {
    askCount++;
    // BROADCAST, DELIBERATELY — a single-subscription StreamController's cancel() resolves via
    // a real Timer internally, which tester.pump()/pump(duration) never drives (only
    // tester.runAsync() does, and that hangs here once a repeating Ticker is active — see
    // drainAsync's own comment). A broadcast controller's cancel() is synchronous instead,
    // which is what every test in this file that cancels mid-stream actually needs.
    final c = StreamController<AiEvent>.broadcast();
    controller = c;
    return c.stream;
  }

  @override
  Future<void> dispose() async {}
}

class _FakeTtsModel implements TtsModel {
  final List<String> spoken = [];
  int stopCalls = 0;
  Completer<void>? _pending;

  @override
  String get driver => 'fake';
  @override
  Future<bool> isLanguageAvailable(String languageCode) async => true;
  @override
  Future<void> speak(String text, {required String languageCode}) async {
    spoken.add(text);
    _pending = Completer<void>();
    await _pending!.future;
  }

  @override
  Future<void> stop() async {
    stopCalls++;
    if (_pending != null && !_pending!.isCompleted) _pending!.complete();
  }

  @override
  Future<void> dispose() async {}
}

class _FakeSpeechInputModel implements SpeechInputModel {
  bool available = true;
  Duration availabilityDelay = Duration.zero;
  int cancelCalls = 0;
  int startListeningCalls = 0;
  void Function(String text, {required bool isFinal})? _onResult;

  @override
  String get driver => 'fake';
  @override
  Future<bool> isAvailable() async {
    if (availabilityDelay > Duration.zero) await Future.delayed(availabilityDelay);
    return available;
  }

  @override
  Future<void> startListening({
    required String languageCode,
    required void Function(String text, {required bool isFinal}) onResult,
  }) async {
    startListeningCalls++;
    _onResult = onResult;
  }

  @override
  Future<void> cancel() async {
    cancelCalls++;
  }

  @override
  Future<void> dispose() async {}

  void emit(String text, {required bool isFinal}) => _onResult?.call(text, isFinal: isFinal);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _FakeAiModel ai;
  late _FakeTtsModel tts;
  late _FakeSpeechInputModel speech;
  late LocalStorage localStorage;
  late NavProvider nav;
  late ActionRegistry actionRegistry;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    ai = _FakeAiModel();
    tts = _FakeTtsModel();
    speech = _FakeSpeechInputModel();
    localStorage = LocalStorage();
    await localStorage.init();
    nav = NavProvider(apiClient: ApiClient(secureStorage: SecureStorage()), localStorage: localStorage);
    actionRegistry = ActionRegistry();
    await actionRegistry.init();
  });

  // A REAL GoRouter, not a bare MaterialApp — ActionExecutor.execute() calls context.goNamed(),
  // which throws with no GoRouter ancestor. The 'visit' route matches mobile_actions.json's own
  // real open_visit_app entry, so a test proposing that action exercises actual navigation, not
  // a mocked stand-in.
  Future<void> pumpButton(WidgetTester tester) async {
    final assistant = AssistantService(aiModel: ai, kbService: KbService(), actionRegistry: actionRegistry);
    final router = GoRouter(
      initialLocation: '/home',
      routes: [
        GoRoute(
          path: '/home',
          name: 'home',
          builder: (context, state) => Scaffold(
            body: Stack(children: [FloatingMicButton(localStorage: localStorage)]),
          ),
        ),
        GoRoute(path: '/visit', name: 'visit', builder: (context, state) => const Scaffold(body: Text('visit screen'))),
      ],
    );
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<NavProvider>.value(value: nav),
          Provider<AssistantService>.value(value: assistant),
          Provider<ActionRegistry>.value(value: actionRegistry),
          Provider<TtsModel>.value(value: tts),
          Provider<SpeechInputModel>.value(value: speech),
        ],
        child: MaterialApp.router(
          localizationsDelegates: S.localizationsDelegates,
          supportedLocales: S.supportedLocales,
          locale: const Locale('en'),
          routerConfig: router,
        ),
      ),
    );
    await tester.pump();
  }

  Icon micIcon(WidgetTester tester) => tester.widget<Icon>(find.byType(Icon));

  // _onTap is fired-and-forgotten by GestureDetector (onTap is a plain VoidCallback, so the
  // framework never awaits its Future) — each chained `await` inside it only advances one
  // microtask turn per pump(). A cancel path with two sequential awaits needs more than one
  // pump() to fully settle; pumpAndSettle() itself can't be used since the pulse animation
  // repeats forever and would never "settle".
  Future<void> drainAsync(WidgetTester tester) async {
    for (var i = 0; i < 3; i++) {
      await tester.pump();
    }
  }

  testWidgets('renders the mic icon at rest, idle', (tester) async {
    await pumpButton(tester);
    expect(micIcon(tester).icon, Icons.mic_rounded);
  });

  testWidgets('falls back to the text chat sheet when speech is unavailable', (tester) async {
    speech.available = false;
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump(); // isAvailable() resolves
    await tester.pump(); // bottom sheet animates in
    expect(find.byType(TextField), findsOneWidget);
    expect(speech.startListeningCalls, 0);
  });

  testWidgets('tap starts listening and shows the stop icon', (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    expect(speech.startListeningCalls, 1);
    expect(micIcon(tester).icon, Icons.stop_rounded);
  });

  testWidgets('tap again while listening cancels outright, back to idle — never a mute',
      (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    expect(speech.cancelCalls, 1);
    expect(micIcon(tester).icon, Icons.mic_rounded);
  });

  testWidgets('an empty recognized transcript returns to idle without asking the assistant',
      (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    speech.emit('   ', isFinal: true);
    await tester.pump();
    expect(ai.askCount, 0);
    expect(micIcon(tester).icon, Icons.mic_rounded);
  });

  testWidgets('a non-final partial result never triggers the assistant', (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    speech.emit('راجع', isFinal: false);
    await tester.pump();
    expect(ai.askCount, 0);
    expect(micIcon(tester).icon, Icons.stop_rounded); // still listening
  });

  testWidgets('full flow: listen → recognize → answer → speak → idle', (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first); // start listening
    await tester.pump();

    speech.emit('كم سعر الخدمة', isFinal: true); // recognized
    await tester.pump();
    expect(ai.askCount, 1); // now "thinking"

    ai.controller!
      ..add(AiTextToken('لا '))
      ..add(AiTextToken('أعرف'));
    await ai.controller!.close();
    await tester.pump(); // onDone fires → "speaking" starts

    expect(tts.spoken, ['لا أعرف']);
    expect(micIcon(tester).icon, Icons.stop_rounded); // speaking

    await tts.stop(); // simulate the platform engine finishing speech
    await tester.pump();
    expect(micIcon(tester).icon, Icons.mic_rounded); // back to idle
  });

  testWidgets(
      'a proposed action the session has no capability for never navigates and never crashes '
      '— the button still finishes the turn normally', (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    speech.emit('وديني لتسجيل زيارة', isFinal: true);
    await tester.pump();

    // nav's own catalog is empty in this harness — open_visit_app requires
    // operations.record_visit, so this MUST resolve as unavailable, not run.
    ai.controller!.add(AiActionProposed('open_visit_app', const {}));
    await ai.controller!.close();
    await tester.pump();

    expect(find.text('visit screen'), findsNothing); // never navigated
    await tts.stop();
    await tester.pump();
    expect(micIcon(tester).icon, Icons.mic_rounded); // still finished the turn cleanly
  });

  testWidgets(
      'cancelling mid-"thinking" must NEVER let a late-arriving answer start speaking '
      '(the race this file exists to catch)', (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();

    speech.emit('سؤال', isFinal: true);
    await tester.pump(); // "thinking" — ai.controller is now live

    await tester.tap(find.byType(GestureDetector).first); // cancel WHILE thinking
    await drainAsync(tester); // let the cancel()/stop() await chain finish before asserting
    expect(micIcon(tester).icon, Icons.mic_rounded); // back to idle immediately

    // The model answers anyway, arriving AFTER the cancel — must be discarded, not spoken. The
    // subscription is already cancelled by now, so this add()/close() reaches no listener —
    // no further real-timer wait is needed, a plain pump() is enough to let the widget settle.
    ai.controller!.add(AiTextToken('جواب متأخر'));
    await ai.controller!.close();
    await tester.pump();

    expect(tts.spoken, isEmpty);
    expect(micIcon(tester).icon, Icons.mic_rounded);
  });

  testWidgets('tap while speaking stops the voice immediately and returns to idle',
      (tester) async {
    await pumpButton(tester);
    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump();
    speech.emit('سؤال', isFinal: true);
    await tester.pump();
    ai.controller!.add(AiTextToken('رد'));
    await ai.controller!.close();
    await tester.pump(); // now speaking

    await tester.tap(find.byType(GestureDetector).first); // cancel while speaking
    await drainAsync(tester);

    expect(tts.stopCalls, greaterThanOrEqualTo(1));
    expect(micIcon(tester).icon, Icons.mic_rounded);
  });

  testWidgets('a slow isAvailable() cannot be double-tapped into listening twice', (tester) async {
    speech.availabilityDelay = const Duration(milliseconds: 200);
    await pumpButton(tester);

    await tester.tap(find.byType(GestureDetector).first);
    await tester.pump(const Duration(milliseconds: 50));
    await tester.tap(find.byType(GestureDetector).first); // lands inside the await window
    await tester.pump(const Duration(milliseconds: 200));

    expect(speech.startListeningCalls, 1);
  });

  testWidgets('renders at its dragged fraction, not at the Stack default alignment',
      (tester) async {
    await localStorage.setMicButtonPosition(const Offset(0.5, 0.5));
    await pumpButton(tester);

    final screenSize = tester.view.physicalSize / tester.view.devicePixelRatio;
    final topLeft = tester.getTopLeft(find.byType(GestureDetector).first);

    expect(topLeft.dx, closeTo(0.5 * screenSize.width, 1.0));
    expect(topLeft.dy, closeTo(0.5 * screenSize.height, 1.0));
  });
}
