import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/providers/app_state_provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/locale_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/providers/tenant_provider.dart';
import 'package:raje3_mobile/core/providers/theme_provider.dart';
import 'package:raje3_mobile/core/router/app_router.dart';
import 'package:raje3_mobile/core/storage/cache_manager.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final localStorage = LocalStorage();
  await localStorage.init();

  final secureStorage = SecureStorage();
  final apiClient = ApiClient(secureStorage: secureStorage);
  final cacheManager = CacheManager();

  runApp(Raje3App(
    apiClient: apiClient,
    secureStorage: secureStorage,
    localStorage: localStorage,
    cacheManager: cacheManager,
  ));
}

class Raje3App extends StatelessWidget {
  final ApiClient apiClient;
  final SecureStorage secureStorage;
  final LocalStorage localStorage;
  final CacheManager cacheManager;

  const Raje3App({
    super.key,
    required this.apiClient,
    required this.secureStorage,
    required this.localStorage,
    required this.cacheManager,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => AuthProvider(
            apiClient: apiClient,
            secureStorage: secureStorage,
            localStorage: localStorage,
          )..tryAutoLogin(),
        ),
        ChangeNotifierProxyProvider<AuthProvider, TenantProvider>(
          create: (_) => TenantProvider(
            apiClient: apiClient,
            localStorage: localStorage,
            cacheManager: cacheManager,
          ),
          update: (context, auth, previous) => previous!..updateAuth(auth),
        ),
        ChangeNotifierProvider(create: (_) => ThemeProvider(localStorage: localStorage)),
        ChangeNotifierProvider(create: (_) => LocaleProvider(localStorage: localStorage)),
        ChangeNotifierProvider(create: (_) => AppStateProvider()),
        ChangeNotifierProvider(
          create: (_) => NavProvider(apiClient: apiClient, localStorage: localStorage),
        ),
      ],
      child: Consumer4<AuthProvider, NavProvider, ThemeProvider, LocaleProvider>(
        builder: (context, authProvider, navProvider, themeProvider, localeProvider, _) {
          final router = AppRouter.router(authProvider, navProvider);
          return MaterialApp.router(
            onGenerateTitle: (context) => S.of(context)?.appName ?? 'راجِع',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.light,
            darkTheme: AppTheme.dark,
            themeMode: themeProvider.mode,
            locale: localeProvider.locale,
            localizationsDelegates: S.localizationsDelegates,
            supportedLocales: S.supportedLocales,
            routerConfig: router,
          );
        },
      ),
    );
  }
}
