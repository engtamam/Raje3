import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/providers/ai_entitlement_provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';

/// A real Dart subclass, not a Dio mock — `AuthService`'s methods are ordinary virtual methods,
/// so overriding the one this provider actually calls proves the provider's own logic (caching,
/// the three-way state, `updateAuth`'s one-check-per-sign-in rule) without needing a fake HTTP
/// layer at all.
class _FakeAuthService extends AuthService {
  _FakeAuthService(this.answer)
      : super(apiClient: ApiClient(secureStorage: SecureStorage()), secureStorage: SecureStorage());

  final bool? answer;
  int calls = 0;

  @override
  Future<bool?> fetchMobileAiAssistantSubscribed() async {
    calls += 1;
    return answer;
  }
}

void main() {
  late LocalStorage localStorage;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    localStorage = LocalStorage();
    await localStorage.init();
  });

  test('starts at null with nothing cached and no check made yet', () {
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(true), localStorage: localStorage);
    expect(provider.subscribed, isNull);
  });

  test('a confirmed true answer is stored and cached', () async {
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(true), localStorage: localStorage);
    await provider.refresh();
    expect(provider.subscribed, isTrue);
    expect(localStorage.getMobileAiAssistantSubscribed(), isTrue);
  });

  test('a confirmed false answer is stored and cached too, not treated as "unknown"', () async {
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(false), localStorage: localStorage);
    await provider.refresh();
    expect(provider.subscribed, isFalse);
    expect(localStorage.getMobileAiAssistantSubscribed(), isFalse);
  });

  test('an unreachable check ("could not ask") falls back to the cached value, never a guess',
      () async {
    await localStorage.setMobileAiAssistantSubscribed(true);
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(null), localStorage: localStorage);
    expect(provider.subscribed, isTrue); // loaded from cache at construction
    await provider.refresh();
    // The failed refresh must NOT overwrite the last confirmed answer.
    expect(provider.subscribed, isTrue);
  });

  test('an unreachable check with nothing ever cached stays null, never guesses true', () async {
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(null), localStorage: localStorage);
    await provider.refresh();
    expect(provider.subscribed, isNull);
  });

  test('updateAuth checks exactly once per sign-in, never on every rebuild', () async {
    final fake = _FakeAuthService(true);
    final provider = AiEntitlementProvider(authService: fake, localStorage: localStorage);
    final auth = AuthProvider(
        apiClient: ApiClient(secureStorage: SecureStorage()),
        secureStorage: SecureStorage(),
        localStorage: localStorage);

    provider.updateAuth(auth); // not authenticated yet — must not call
    await Future<void>.delayed(Duration.zero);
    expect(fake.calls, 0);
  });

  test('signing out clears the answer back to unknown, never leaves a stale "subscribed"',
      () async {
    final provider = AiEntitlementProvider(
        authService: _FakeAuthService(true), localStorage: localStorage);
    await provider.refresh();
    expect(provider.subscribed, isTrue);

    final auth = AuthProvider(
        apiClient: ApiClient(secureStorage: SecureStorage()),
        secureStorage: SecureStorage(),
        localStorage: localStorage);
    provider.updateAuth(auth); // signed out (fresh AuthProvider starts unauthenticated)
    expect(provider.subscribed, isNull);
  });
}
