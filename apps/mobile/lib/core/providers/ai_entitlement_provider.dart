import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';

/// Whether THIS SHOP holds `feature.mobile_ai_assistant` — the one thing every AI surface in this
/// app (the floating mic, wake-word listening, any future assistant screen) must check before it
/// shows anything at all, on top of (never instead of) the compile-time driver switches in
/// ai_config.dart/tts_config.dart/speech_input_config.dart/wake_word_config.dart. Those decide
/// whether the CODE PATH exists in this build; this decides whether THIS SHOP has bought it — the
/// app is a real, listed, subscribe/cancel-able plan now (deploy/seed/plans.json,
/// core/apps.py, priced 0 today), never an auto-grant, so a shop that never subscribed — or
/// cancelled — must see nothing, regardless of how the build was compiled.
///
/// THREE STATES, NEVER TWO. [subscribed] is `null` until the first real answer lands — a build
/// that showed the mic for one frame before the first check resolved would flash the button on
/// and off, worse than a one-time delay. Once set, it stays at the LAST CONFIRMED answer (cached
/// via [LocalStorage]) across a failed re-check — a shop that paid must not lose the feature
/// because of one bad network moment; a shop this cached value came from was CONFIRMED
/// subscribed at some point, never guessed.
///
/// SETTINGS (on/off, voice-only, ...) ARE A SEPARATE, LATER PASS (owner's own explicit
/// deferral, 2026-09-21 — "شاشة الإعدادات مو الآن... ضمن حسابي") — this provider only answers
/// "may this shop see AI at all"; it holds no on/off preference of its own.
class AiEntitlementProvider extends ChangeNotifier {
  final AuthService authService;
  final LocalStorage localStorage;

  AiEntitlementProvider({required this.authService, required this.localStorage}) {
    _subscribed = localStorage.getMobileAiAssistantSubscribed();
  }

  bool? _subscribed;
  bool _refreshing = false;
  bool _everChecked = false;

  /// `null` = no confirmed answer yet (nothing shows). `true`/`false` = the last CONFIRMED
  /// answer, live or cached.
  bool? get subscribed => _subscribed;

  /// One real check per sign-in, mirroring [TenantProvider]'s own `updateAuth` — called from the
  /// SAME `ChangeNotifierProxyProvider<AuthProvider, AiEntitlementProvider>` wiring in main.dart.
  void updateAuth(AuthProvider auth) {
    if (auth.isAuthenticated && !_everChecked) {
      refresh();
    } else if (!auth.isAuthenticated) {
      _everChecked = false;
      _subscribed = null;
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      final answer = await authService.fetchMobileAiAssistantSubscribed();
      _everChecked = true;
      if (answer != null) {
        _subscribed = answer;
        await localStorage.setMobileAiAssistantSubscribed(answer);
      }
      // `answer == null` ("could not ask") deliberately leaves `_subscribed` at whatever the
      // constructor already loaded from cache — see this class's own doc comment.
      notifyListeners();
    } finally {
      _refreshing = false;
    }
  }
}
