import 'package:flutter/material.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:flutter_gemma_litertlm/flutter_gemma_litertlm.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_container.dart';
import 'package:raje3_mobile/core/ai/assistant_service.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/notification_service.dart';
import 'package:raje3_mobile/core/tts/tts_container.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';
import 'package:raje3_mobile/core/voice/speech_input_container.dart';
import 'package:raje3_mobile/core/voice/speech_input_model.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_container.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_model.dart';
import 'package:raje3_mobile/core/providers/ai_entitlement_provider.dart';
import 'package:raje3_mobile/core/providers/app_state_provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/locale_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/providers/tenant_provider.dart';
import 'package:raje3_mobile/core/providers/theme_provider.dart';
import 'package:raje3_mobile/core/router/app_router.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/storage/cache_manager.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // REQUIRED BY flutter_gemma ITSELF — found live (2026-09-28), a real crash on every device
  // ("Bad state: FlutterGemma not initialized!"): the plugin registers ZERO inference engines by
  // default (fully opt-in, per its own docs), so GemmaAiModel's `ModelFileType.litertlm` model
  // had no engine to load it with. LiteRtLmEngine (flutter_gemma_litertlm) is the one that reads
  // .litertlm files — the exact file type ai_config.dart/gemma_ai_model.dart already fetch.
  await FlutterGemma.initialize(inferenceEngines: const [LiteRtLmEngine()]);

  // Registers 'Cairo'/'Tajawal'/'Inter' as real, loaded font families — every
  // `TextStyle(fontFamily: AppTextStyles.arabicFont/englishFont)` in the app
  // (including the wordmark itself) resolves against these once loaded, so
  // this call is required even though nothing here reads its return value.
  GoogleFonts.cairo();
  GoogleFonts.tajawal();
  GoogleFonts.inter();

  final localStorage = LocalStorage();
  await localStorage.init();

  final secureStorage = SecureStorage();
  final apiClient = ApiClient(secureStorage: secureStorage);
  final cacheManager = CacheManager();

  final kbService = KbService();
  await kbService.init();

  final actionRegistry = ActionRegistry();
  await actionRegistry.init();

  final assistantService = AssistantService(
    aiModel: buildAiModel(),
    kbService: kbService,
    actionRegistry: actionRegistry,
  );
  final ttsModel = buildTtsModel();
  final speechInputModel = buildSpeechInputModel();
  final wakeWordModel = buildWakeWordModel();

  runApp(Raje3App(
    apiClient: apiClient,
    secureStorage: secureStorage,
    localStorage: localStorage,
    cacheManager: cacheManager,
    kbService: kbService,
    actionRegistry: actionRegistry,
    assistantService: assistantService,
    ttsModel: ttsModel,
    speechInputModel: speechInputModel,
    wakeWordModel: wakeWordModel,
  ));
}

class Raje3App extends StatelessWidget {
  final ApiClient apiClient;
  final SecureStorage secureStorage;
  final LocalStorage localStorage;
  final CacheManager cacheManager;
  final KbService kbService;
  final ActionRegistry actionRegistry;
  final AssistantService assistantService;
  final TtsModel ttsModel;
  final SpeechInputModel speechInputModel;
  final WakeWordModel wakeWordModel;

  const Raje3App({
    super.key,
    required this.apiClient,
    required this.secureStorage,
    required this.localStorage,
    required this.cacheManager,
    required this.kbService,
    required this.actionRegistry,
    required this.assistantService,
    required this.ttsModel,
    required this.speechInputModel,
    required this.wakeWordModel,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<LocalStorage>.value(value: localStorage),
        Provider<KbService>.value(value: kbService),
        Provider<ActionRegistry>.value(value: actionRegistry),
        Provider<AssistantService>.value(value: assistantService),
        Provider<TtsModel>.value(value: ttsModel),
        Provider<SpeechInputModel>.value(value: speechInputModel),
        Provider<WakeWordModel>.value(value: wakeWordModel),
        Provider<NotificationService>(
          create: (_) => NotificationService(apiClient: apiClient),
        ),
        ChangeNotifierProvider(
          create: (_) {
            final authProvider = AuthProvider(
              apiClient: apiClient,
              secureStorage: secureStorage,
              localStorage: localStorage,
            );
            // WITHOUT THIS, a genuinely expired session (AuthInterceptor's
            // own 401 handler clears the stored token and wants to force a
            // logout) never actually reaches AuthProvider — every screen
            // instead shows a generic "save failed" / "load failed" error
            // and the user stays stuck on a dead session. Found live: a
            // token that expired mid-session (15-minute TTL, no refresh
            // token — see api_interceptors.dart's own AuthInterceptor doc
            // comment) surfaced only as شاشة منشأتي's "تعذّر الحفظ" message.
            apiClient.onForceLogout = authProvider.forceLogout;
            return authProvider..tryAutoLogin();
          },
        ),
        ChangeNotifierProxyProvider<AuthProvider, TenantProvider>(
          create: (_) => TenantProvider(
            apiClient: apiClient,
            localStorage: localStorage,
            cacheManager: cacheManager,
          ),
          update: (context, auth, previous) => previous!..updateAuth(auth),
        ),
        ChangeNotifierProxyProvider<AuthProvider, AiEntitlementProvider>(
          create: (_) => AiEntitlementProvider(
            authService: AuthService(apiClient: apiClient, secureStorage: secureStorage),
            localStorage: localStorage,
          ),
          update: (context, auth, previous) => previous!..updateAuth(auth),
        ),
        ChangeNotifierProvider(create: (_) => ThemeProvider(localStorage: localStorage)),
        ChangeNotifierProvider(create: (_) => LocaleProvider(localStorage: localStorage)),
        ChangeNotifierProvider(create: (_) => AppStateProvider()),
        ChangeNotifierProvider(
          create: (_) => NavProvider(apiClient: apiClient, localStorage: localStorage),
        ),
        ChangeNotifierProxyProvider<AuthProvider, BranchProvider>(
          create: (_) => BranchProvider(localStorage: localStorage),
          update: (context, auth, previous) => previous!..updateAuth(auth),
        ),
      ],
      child: const _AppShell(),
    );
  }
}

/// Builds [AppRouter.router] EXACTLY ONCE, not on every rebuild — GoRouter already reacts to
/// auth/catalogue changes on its own via the `refreshListenable: Listenable.merge([auth, nav])`
/// AppRouter.router wires internally, so rebuilding a brand-new GoRouter (as the previous
/// Consumer4-wrapped version here did, on every AuthProvider/NavProvider/ThemeProvider/
/// LocaleProvider notification) was always redundant. It was also actively broken: AppRouter's
/// navigator keys (`_rootNavigatorKey`/`_shellNavKey`) are `static final`, so a second GoRouter
/// instance shares the SAME GlobalKeys as the first — and for one frame during MaterialApp's own
/// routerConfig swap, both Navigators exist at once, which Flutter refuses ("Multiple widgets
/// used the same GlobalKey"). FOUND LIVE, not theoretical: a real login followed by the
/// catalogue's own load() (exactly the auth-then-nav notification pair this rebuilt on) crashed
/// the entire shell blank on the very first end-to-end test against a real server.
class _AppShell extends StatefulWidget {
  const _AppShell();

  @override
  State<_AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<_AppShell> {
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    // context.read, not watch — this widget's own build() never needs to run again for an
    // auth/catalogue change; the router built here already listens for those itself.
    _router = AppRouter.router(context.read<AuthProvider>(), context.read<NavProvider>());
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<ThemeProvider, LocaleProvider>(
      builder: (context, themeProvider, localeProvider, _) {
        return MaterialApp.router(
          onGenerateTitle: (context) => S.of(context)?.appName ?? 'راجِع',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: themeProvider.mode,
          locale: localeProvider.locale,
          localizationsDelegates: S.localizationsDelegates,
          supportedLocales: S.supportedLocales,
          routerConfig: _router,
        );
      },
    );
  }
}

