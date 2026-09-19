import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';

/// Service layer for authentication against Raje3's REAL identity door.
///
/// THIS IS NOT THE GENERIC REST ENVELOPE THE REST OF THE APP USES. Every
/// other backend route this app calls answers `{success, data, message_ar,
/// message_en, meta}` (see api_response.dart) — [ApiClient]'s `_parseResponse`
/// is built around that shape. `services/operations/app/api/v1/signup.py` is
/// the ONE real door that predates and does not follow it: it answers a flat
/// body on success (whatever identity minted, e.g. `access_token`,
/// `refresh_token`, `tenant`, spread straight through) and `{"ok": false,
/// "message": "...", "reason": "..."}` on refusal, returned with a plain 400
/// rather than raised — see signup.py's own `_refused()` docstring for why.
/// Reusing `ApiClient.post<T>` here would silently swallow every field
/// because `_parseResponse` only ever reads `json['data']`, which this door
/// never sends. So this service talks to it directly through `apiClient.dio`,
/// matching exactly what apps/console/src/auth.ts's own `post()` helper does
/// for the same two routes.
///
/// THE WHOLE FLOW IS PHONE-ONLY — NO EMAIL FIELD EXISTS ANYWHERE ON EITHER
/// DOOR. Opening a shop takes phone + password + shop name; signing back in
/// takes phone + password (+ an OTP code only when the deployment turns
/// `SIGNUP_REQUIRE_OTP` on — off today, see deploy/services/operations.values.yaml).
class AuthResult {
  final bool ok;
  final String message;
  final String reason;
  final String tenant;
  final String phone;
  final String accessToken;
  final String refreshToken;
  final bool trialStarted;
  final int trialEnd;

  const AuthResult({
    required this.ok,
    this.message = '',
    this.reason = '',
    this.tenant = '',
    this.phone = '',
    this.accessToken = '',
    this.refreshToken = '',
    this.trialStarted = false,
    this.trialEnd = 0,
  });

  factory AuthResult.refused(String message, {String reason = ''}) =>
      AuthResult(ok: false, message: message, reason: reason);
}

class AuthService {
  final ApiClient apiClient;
  final SecureStorage secureStorage;

  static const String _signupBase = '/api/v1/signup';

  AuthService({
    required this.apiClient,
    required this.secureStorage,
  });

  /// Sign in with phone + password (+ OTP code, only when the server asked
  /// for one on a previous attempt). Backs onto
  /// `POST /api/v1/signup/signin` -> `SignupService.sign_in`, which resolves
  /// the shop from the phone and forwards to identity's own membership mint.
  Future<AuthResult> signIn(String phone, String password, {String code = ''}) {
    return _call('$_signupBase/signin', {
      'phone': phone,
      'password': password,
      'code': code,
    });
  }

  /// Open a brand-new shop: phone + password + shop name is the whole form —
  /// see `services/operations/app/core/signup.py`'s own note on why there is
  /// a fourth field and not a fifth. `code` is only spent when the deployment
  /// has turned OTP-at-signup on (empty is always valid otherwise).
  ///
  /// NO TOKEN COMES BACK FROM THIS CALL, deliberately — the account exists
  /// and the ordinary sign-in door is one call away, so callers should
  /// immediately follow a success with [signIn] using the same phone/password
  /// (exactly what the console's own `openShop()` in apps/console/src/auth.ts
  /// does).
  Future<AuthResult> openShop({
    required String phone,
    required String password,
    required String shopName,
    String affiliateRef = '',
    String code = '',
  }) {
    return _call(_signupBase, {
      'phone': phone,
      'password': password,
      'shop_name': shopName,
      'affiliate_ref': affiliateRef,
      'code': code,
    });
  }

  /// Ask identity to send a verification code to this phone number.
  /// Only meaningful once `SIGNUP_OTP_DELIVERABLE` is on for the deployment —
  /// otherwise the server refuses with reason `undeliverable` rather than
  /// pretending to have sent something nobody will receive.
  Future<AuthResult> requestCode(String phone) {
    return _call('$_signupBase/code', {'phone': phone});
  }

  /// Spend a code sent by [requestCode] and record the verdict, so a later
  /// sign-in attempt on this number is no longer refused with `unverified`.
  Future<AuthResult> verifyCode(String phone, String code) {
    return _call('$_signupBase/verify', {'phone': phone, 'code': code});
  }

  /// Whether a token is currently stored and not past its recorded expiry.
  Future<bool> isLoggedIn() async {
    final hasToken = await secureStorage.hasAccessToken();
    if (!hasToken) return false;
    return !(await secureStorage.isTokenExpired());
  }

  Future<void> logout() async {
    await secureStorage.clearAll();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL — the one raw call every method above funnels through.
  // ─────────────────────────────────────────────────────────────────────────

  Future<AuthResult> _call(String path, Map<String, dynamic> body) async {
    try {
      final response = await apiClient.dio.post<dynamic>(path, data: body);
      final data = response.data;
      if (data is! Map) {
        return AuthResult.refused('استجابة غير صالحة من الخادم');
      }
      final map = Map<String, dynamic>.from(data);
      // ANY NON-2xx STATUS IS A REFUSAL, not just the `{"ok": false}` shape
      // `_refused()` in signup.py builds by hand. `apiClient`'s Dio instance
      // is configured with `validateStatus: status < 500 && status != 401`
      // (api_client.dart), so a 422 from FastAPI's own pydantic validation —
      // a phone/password shorter than the field's own min_length — resolves
      // here rather than throwing, and its body has no `ok` key at all
      // (FastAPI's default `{"detail": [...]}` shape). Checking only
      // `map['ok'] == false` would read that as success.
      final status = response.statusCode ?? 200;
      if (map['ok'] == false || status >= 300) {
        final detail = map['detail'];
        final detailText = detail is String
            ? detail
            : (detail is List && detail.isNotEmpty ? detail.first.toString() : null);
        return AuthResult.refused(
          (map['message'] as String?) ?? detailText ?? 'تعذّر إتمام العملية',
          reason: (map['reason'] as String?) ?? '',
        );
      }
      return AuthResult(
        ok: true,
        tenant: (map['tenant'] as String?) ?? '',
        phone: (map['phone'] as String?) ?? '',
        accessToken: (map['access_token'] as String?) ?? '',
        refreshToken: (map['refresh_token'] as String?) ?? '',
        trialStarted: map['trial_started'] == true,
        trialEnd: (map['trial_end'] as num?)?.toInt() ?? 0,
      );
    } on DioException catch (e) {
      // The server's own refusal body — signup.py returns 400, never raises,
      // but a malformed request (422 from pydantic) or a network failure
      // still surfaces as a DioException.
      final data = e.response?.data;
      if (data is Map) {
        final map = Map<String, dynamic>.from(data);
        final said = (map['message'] as String?) ?? (map['detail'] as String?);
        if (said != null) {
          return AuthResult.refused(said, reason: (map['reason'] as String?) ?? '');
        }
      }
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        return AuthResult.refused('تعذّر الاتصال بالخادم. تحقّق من الإنترنت.');
      }
      return AuthResult.refused('حدث خطأ غير متوقع. حاول مرة أخرى.');
    } catch (_) {
      return AuthResult.refused('حدث خطأ غير متوقع. حاول مرة أخرى.');
    }
  }
}
