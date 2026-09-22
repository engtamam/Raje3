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
/// «منشأتي» — the tenant's own name/logo/accent, and the raw `branding` map exactly as the
/// server sent it ([rawBranding], never trimmed to just the two known fields) so a later
/// [AuthService.setBranding] can merge without dropping a field this app does not know about yet
/// — the same discipline apps/console/src/screens/AccountPanes.tsx's own `saveBranding` follows.
class TenantIdentity {
  final String name;
  final String logoUrl;
  final String accent;
  final Map<String, dynamic> rawBranding;

  const TenantIdentity({
    required this.name,
    required this.logoUrl,
    required this.accent,
    required this.rawBranding,
  });
}

/// A branch — `Branch.public()`, services/operations/app/core/models.py. Every shop has a real
/// main branch (`core/branches.py::MAIN`) from signup, even a single-location shop: there is no
/// "no branches yet" state on this product, so [BranchesScreen] never designs for one.
class Branch {
  final String id;
  final String name;
  final bool active;
  final double lat;
  final double lng;
  final String city;

  const Branch({
    required this.id,
    required this.name,
    required this.active,
    required this.lat,
    required this.lng,
    required this.city,
  });

  /// `core/branches.py::MAIN` — the fixed id, not a name guess. The main branch can never be
  /// closed (`update_branch`'s own 409 `MAIN_BRANCH`) and its own toggle stays disabled for
  /// exactly that reason rather than failing the tap.
  bool get isMain => id == 'brn-main';

  factory Branch.fromJson(Map<String, dynamic> json) => Branch(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        active: json['active'] as bool? ?? true,
        lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
        lng: (json['lng'] as num?)?.toDouble() ?? 0.0,
        city: json['city'] as String? ?? '',
      );
}

/// The full `GET /staff/branches` read — the branch list ALONE cannot answer "can he add
/// another", that is a plan fact computed server-side alongside it (staff.py's own note on why
/// the entitlement travels with the read rather than being asked separately).
class BranchesResult {
  final List<Branch> branches;
  final bool mayAddBranch;

  const BranchesResult({required this.branches, required this.mayAddBranch});
}

/// The outcome of a branch create/update call — `BranchErrorCode.none` on success, otherwise the
/// exact real refusal (`LOCATION_REQUIRED`/`BRANCH_LIMIT`/`MAIN_BRANCH`/`BRANCH_BUSY`) so the
/// screen can show the real sentence the server already wrote rather than a generic failure.
enum BranchErrorCode { none, locationRequired, limitReached, mainBranch, busy, unknown }

class BranchWriteResult {
  final Branch? branch;
  final BranchErrorCode error;
  const BranchWriteResult.ok(this.branch) : error = BranchErrorCode.none;
  const BranchWriteResult.failed(this.error) : branch = null;
}

/// A team member row — `Operator.public()`. `GET /staff/operators` returns everyone the caller
/// may see already narrowed server-side (branch_scope) — never filtered by a `branch_id` param,
/// there isn't one — so [AuthService.fetchOperators] returns the whole visible roster and a
/// branch screen keeps only the rows whose `branchId` matches its own.
class BranchTeamMember {
  final String id;
  final String name;
  final String role;
  final String branchId;
  final bool active;

  const BranchTeamMember({
    required this.id,
    required this.name,
    required this.role,
    required this.branchId,
    required this.active,
  });

  factory BranchTeamMember.fromJson(Map<String, dynamic> json) => BranchTeamMember(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        role: json['role'] as String? ?? '',
        branchId: json['branch_id'] as String? ?? '',
        active: json['active'] as bool? ?? true,
      );
}

/// The real, fixed role set — `apps/console/src/screens/Team.tsx`'s own radio options, matched
/// exactly (the server's `MemberIn.role` is a free string with no enum, but these three are the
/// only ones the product actually offers anywhere). Never invented for this screen.
enum StaffRole { operator, supervisor, manager }

extension StaffRoleValue on StaffRole {
  String get value => switch (this) {
        StaffRole.operator => 'operator',
        StaffRole.supervisor => 'supervisor',
        StaffRole.manager => 'manager',
      };
}

/// The outcome of hiring a new team member — `POST /staff/members` (staff.py::hire_member).
/// `notHired`'s message is the SERVER's own real sentence (e.g. «هذا الرقم مسجّل في منشأة
/// أخرى»), never a generic one — the only error here worth showing verbatim rather than mapping
/// to a fixed local string.
enum HireErrorCode { none, branchRequired, seatLimit, busy, notHired, unknown }

class HireResult {
  final HireErrorCode error;
  final String message;
  const HireResult.ok() : error = HireErrorCode.none, message = '';
  const HireResult.failed(this.error, {this.message = ''});
}

class ChangePasswordResult {
  final bool ok;
  final String message;
  const ChangePasswordResult.ok() : ok = true, message = '';
  const ChangePasswordResult.failed(this.message) : ok = false;
}

/// «الفوترة» — billing-service's own real models (`platform/services/billing-service/app/core/
/// models.py`), the SAME shapes `apps/console/src/billingShared.tsx`/`BillingStatusPane.tsx`
/// already read — this screen re-derives nothing new, only presents it mobile-natively. Money is
/// integer minor units end-to-end, exactly like the server; [Formatters.formatCurrency] converts
/// at the very edge of the UI, never here.
class BillingPlan {
  final String id;
  final String name;
  final int monthlyAmountMinor;
  final String currency;

  const BillingPlan({
    required this.id,
    required this.name,
    required this.monthlyAmountMinor,
    required this.currency,
  });

  factory BillingPlan.fromJson(Map<String, dynamic> json) {
    final prices = (json['prices'] as List?)?.whereType<Map>().toList() ?? const [];
    final monthly = prices.firstWhere(
      (p) => p['interval'] == 'month',
      orElse: () => prices.isNotEmpty ? prices.first : const {},
    );
    return BillingPlan(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      monthlyAmountMinor: (monthly['amount_minor'] as num?)?.toInt() ?? 0,
      currency: monthly['currency'] as String? ?? 'SAR',
    );
  }
}

/// One subscribed app/capacity — `Subscription.to_dict()`. `planId` is the only link back to a
/// [BillingPlan]'s real display name; the model never invents one.
class BillingSubscription {
  final String id;
  final String planId;
  final String status;
  final int quantity;
  final double currentPeriodEnd;
  final bool cancelAtPeriodEnd;

  const BillingSubscription({
    required this.id,
    required this.planId,
    required this.status,
    required this.quantity,
    required this.currentPeriodEnd,
    required this.cancelAtPeriodEnd,
  });

  factory BillingSubscription.fromJson(Map<String, dynamic> json) => BillingSubscription(
        id: json['id'] as String? ?? '',
        planId: json['plan_id'] as String? ?? '',
        status: json['status'] as String? ?? '',
        quantity: (json['quantity'] as num?)?.toInt() ?? 1,
        currentPeriodEnd: (json['current_period_end'] as num?)?.toDouble() ?? 0,
        cancelAtPeriodEnd: json['cancel_at_period_end'] as bool? ?? false,
      );
}

/// One line inside a [RenewalPreviewGroup] — `billing.renewal_preview`'s own real breakdown, the
/// exact number the next invoice will cut (never a list-price guess).
class RenewalPreviewLine {
  final String subscriptionId;
  final String planName;
  final int totalMinor;

  const RenewalPreviewLine({
    required this.subscriptionId,
    required this.planName,
    required this.totalMinor,
  });

  factory RenewalPreviewLine.fromJson(Map<String, dynamic> json) => RenewalPreviewLine(
        subscriptionId: json['subscription_id'] as String? ?? '',
        planName: json['plan_name'] as String? ?? '',
        totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
      );
}

/// One (gateway, currency) group of the next renewal — never summed across currencies, same
/// posture the server's own consolidated-invoice cut takes.
class RenewalPreviewGroup {
  final String currency;
  final double? nextChargeAt;
  final List<RenewalPreviewLine> lines;
  final int subtotalMinor;
  final int discountMinor;
  final int taxMinor;
  final int totalMinor;

  const RenewalPreviewGroup({
    required this.currency,
    required this.nextChargeAt,
    required this.lines,
    required this.subtotalMinor,
    required this.discountMinor,
    required this.taxMinor,
    required this.totalMinor,
  });

  factory RenewalPreviewGroup.fromJson(Map<String, dynamic> json) => RenewalPreviewGroup(
        currency: json['currency'] as String? ?? 'SAR',
        nextChargeAt: (json['next_charge_at'] as num?)?.toDouble(),
        lines: ((json['lines'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) => RenewalPreviewLine.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
        subtotalMinor: (json['subtotal_minor'] as num?)?.toInt() ?? 0,
        discountMinor: (json['discount_minor'] as num?)?.toInt() ?? 0,
        taxMinor: (json['tax_minor'] as num?)?.toInt() ?? 0,
        totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
      );
}

/// One billed document — `Invoice.to_dict()`. `status` is one of draft|open|partially_paid|paid|
/// uncollectible|void, read verbatim, never re-derived.
class BillingInvoice {
  final String id;
  final String number;
  final String status;
  final int totalMinor;
  final String currency;
  final String created;

  const BillingInvoice({
    required this.id,
    required this.number,
    required this.status,
    required this.totalMinor,
    required this.currency,
    required this.created,
  });

  bool get isPayable => status == 'open' || status == 'partially_paid';

  factory BillingInvoice.fromJson(Map<String, dynamic> json) => BillingInvoice(
        id: json['id'] as String? ?? '',
        number: json['number'] as String? ?? '',
        status: json['status'] as String? ?? '',
        totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
        currency: json['currency'] as String? ?? 'SAR',
        created: json['created'] as String? ?? '',
      );
}

/// One entitlement gauge from `billing.my_usage` (`UsageService.summary`) — e.g. `staff.seats`,
/// `branches`. `limit == null` means unlimited (the server's own sentinel), never a huge number.
class BillingUsageGauge {
  final String key;
  final int current;
  final int? limit;

  const BillingUsageGauge({required this.key, required this.current, required this.limit});

  factory BillingUsageGauge.fromJson(String key, Map<String, dynamic> json) {
    final rawLimit = json['limit'];
    final unlimited = rawLimit == null || rawLimit == 'unlimited' ||
        (rawLimit is num && rawLimit < 0);
    return BillingUsageGauge(
      key: key,
      current: (json['current'] as num?)?.toInt() ?? 0,
      limit: unlimited ? null : (rawLimit as num?)?.toInt(),
    );
  }
}

/// The whole «الفوترة» screen's read, fetched in parallel — each piece degrades to empty on its
/// own failure rather than failing the whole screen (same posture `BillingStatusPane.tsx` takes:
/// a renewal-preview outage never hides the subscriptions list).
class BillingOverview {
  final List<BillingSubscription> subscriptions;
  final Map<String, BillingPlan> plansById;
  final List<RenewalPreviewGroup> renewalGroups;
  final List<BillingInvoice> invoices;
  final List<BillingUsageGauge> usage;

  const BillingOverview({
    required this.subscriptions,
    required this.plansById,
    required this.renewalGroups,
    required this.invoices,
    required this.usage,
  });
}

/// A branch's own WhatsApp connection state — `GET /whatsapp/connect?branch_id=`. `canSend` is
/// the real "is it actually usable" signal, separate from "the handshake succeeded" — a branch
/// can be `state` non-empty and still `canSend: false` (connect.py's own note on the PIN step).
class BranchConnectStatus {
  final String state;
  final String message;
  final bool canSend;

  const BranchConnectStatus({required this.state, required this.message, required this.canSend});

  /// Three real states only — never a fourth invented one. `notStarted` (empty `state`),
  /// `connected` (`canSend`), `connectedCannotSend` (a real, distinct state, not lumped with
  /// `connected` — connect.py's own PIN-step note is exactly why this stays a third value).
  bool get notStarted => state.isEmpty;

  factory BranchConnectStatus.fromJson(Map<String, dynamic> json) => BranchConnectStatus(
        state: json['state'] as String? ?? '',
        message: json['message'] as String? ?? '',
        canSend: json['can_send'] as bool? ?? false,
      );
}

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
    // OPTIONAL — see services/operations/app/core/signup.py's own NewShop.owner_name note for
    // why this never becomes a required field. Empty means the greeting still reads his phone
    // number, exactly like today.
    String ownerName = '',
    String affiliateRef = '',
    String code = '',
  }) {
    return _call(_signupBase, {
      'phone': phone,
      'password': password,
      'shop_name': shopName,
      'owner_name': ownerName,
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

  /// The account holder's own display name, or '' if none is set — a platform-wide,
  /// capability-free door (`GET /api/v1/account/me/name`, services/operations
  /// `app/api/v1/__init__.py`) exactly like apps/console/src/api.ts's own `getMyName`. Answers
  /// the plain `{"name": "..."}` shape directly, no `{success, data}` envelope — same reasoning
  /// as every other call in this file. Never throws: a failed read (offline, a transient 500)
  /// resolves to null so a caller degrades to the phone-number fallback rather than crashing.
  Future<String?> fetchOwnerName() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/account/me/name');
      final data = response.data;
      if (data is Map) return (data['name'] as String?) ?? '';
      return null;
    } on DioException {
      return null;
    }
  }

  /// Writes the account holder's own display name — `PATCH /api/v1/account/me/name`, the setter
  /// half of [fetchOwnerName] (same platform-wide, capability-free door). Returns the name the
  /// server actually stored (trimmed server-side) on success, `null` on any failure — the caller
  /// degrades by simply not updating local state, never by guessing what was saved.
  Future<String?> setOwnerName(String name) async {
    try {
      final response = await apiClient.dio.patch<dynamic>(
        '/api/v1/account/me/name',
        data: {'name': name},
      );
      final data = response.data;
      if (data is Map) return (data['name'] as String?) ?? '';
      return null;
    } on DioException {
      return null;
    }
  }

  /// Does this shop track vehicles at all — `GET /api/v1/staff/vehicles`
  /// (services/operations `app/api/v1/staff.py::read_vehicles`), the exact same read
  /// `visit_screen.dart`'s own plate field already assumed was somewhere. `operations.read`
  /// gated: a role that cannot see it gets a clean 403, resolved to `null` here exactly like an
  /// offline read — the caller degrades by hiding the control, never by guessing an answer.
  Future<bool?> fetchTracksVehicle() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/vehicles');
      final data = response.data;
      if (data is Map) return data['tracks_vehicle'] as bool? ?? false;
      return null;
    } on DioException {
      return null;
    }
  }

  /// Flips whether this shop tracks vehicles — `PUT /api/v1/staff/vehicles`
  /// (`operations.manage`, stricter than the read above — the owner's own call, same posture the
  /// route's own docstring states). Returns the value the server actually applied, `null` on any
  /// failure (never assumed to have taken effect).
  Future<bool?> setTracksVehicle(bool tracksVehicle) async {
    try {
      final response = await apiClient.dio.put<dynamic>(
        '/api/v1/staff/vehicles',
        data: {'tracks_vehicle': tracksVehicle},
      );
      final data = response.data;
      if (data is Map) return data['tracks_vehicle'] as bool? ?? tracksVehicle;
      return null;
    } on DioException {
      return null;
    }
  }

  /// The tenant's own real name/logo/accent — `GET /api/v1/tenant` (`tenant-service`, a platform
  /// microservice with no source in this repo). Read LIVE from the authenticated console session
  /// itself rather than guessed (`ToolSearch`/network-inspection pass, 2026-09-22) — the exact
  /// shape confirmed: `{name, branding: {logo_url, accent}, ...}`. `null` on any failure, same
  /// three-way honesty as every other read in this file.
  Future<TenantIdentity?> fetchTenant() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/tenant');
      final data = response.data;
      if (data is! Map) return null;
      final branding = data['branding'];
      final rawBranding = branding is Map ? Map<String, dynamic>.from(branding) : <String, dynamic>{};
      return TenantIdentity(
        name: data['name'] as String? ?? '',
        logoUrl: rawBranding['logo_url'] as String? ?? '',
        accent: rawBranding['accent'] as String? ?? '',
        rawBranding: rawBranding,
      );
    } on DioException {
      return null;
    }
  }

  /// The shop's own name — `PUT /api/v1/staff/shop-name` (services/operations, proxied to
  /// `tenant-service`'s internal rename route — see that route's own docstring for why a direct
  /// tenant-service call is not offered for the name specifically). Returns whether it saved.
  Future<bool> setShopName(String name) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/staff/shop-name', data: {'name': name});
      return true;
    } on DioException {
      return false;
    }
  }

  /// Logo + accent colour — `PUT /api/v1/tenant/branding`, body `{"branding": {...}}`. MERGED,
  /// never replaced — apps/console/src/screens/AccountPanes.tsx's own `saveBranding` comment
  /// documents the exact bug this guards against: sending the two fields at the TOP level (no
  /// `branding` envelope) 422s every time, silently, because `tenant-service`'s body model is
  /// `BrandingIn { branding: dict }`. `current` is the tenant's own branding map exactly as
  /// [fetchTenant] read it, spread first so a caller who only changed the colour never drops an
  /// existing logo, or the reverse. Returns whether it saved.
  Future<bool> setBranding({
    required Map<String, dynamic> current,
    String? logoUrl,
    String? accent,
  }) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/tenant/branding', data: {
        'branding': {
          ...current,
          if (logoUrl != null) 'logo_url': logoUrl,
          if (accent != null) 'accent': accent,
        },
      });
      return true;
    } on DioException {
      return false;
    }
  }

  /// Whether this shop holds `feature.mobile_ai_assistant` — GET /api/v1/account/me/mobile-ai-
  /// assistant (services/operations `app/api/v1/__init__.py`). `null` means "could not ask" (the
  /// request failed, OR the server itself answered `checked: false` — a billing-peer outage is
  /// the SAME uncertainty as a network failure from this caller's own point of view): never
  /// confused with a real, confirmed `false`. [AiEntitlementProvider] is the one place this
  /// distinction is actually used — a caller here just gets the honest three-way answer.
  Future<bool?> fetchMobileAiAssistantSubscribed() async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/account/me/mobile-ai-assistant');
      final data = response.data;
      if (data is! Map) return null;
      final checked = data['checked'] as bool? ?? false;
      if (!checked) return null;
      return data['subscribed'] as bool? ?? false;
    } on DioException {
      return null;
    }
  }

  /// «الفروع» — `GET /api/v1/staff/branches` (services/operations `staff.py::list_branches`).
  /// `null` on any failure, same three-way honesty as every other read in this file.
  Future<BranchesResult?> fetchBranches() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/branches');
      final data = response.data;
      if (data is! Map) return null;
      final rows = (data['branches'] as List?) ?? const [];
      return BranchesResult(
        branches: rows
            .whereType<Map>()
            .map((m) => Branch.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
        mayAddBranch: data['may_add_branch'] as bool? ?? false,
      );
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/branches` — location is optional on the shop's first branch, required
  /// from the second one on (`staff.py::create_branch`'s own `LOCATION_REQUIRED` refusal).
  Future<BranchWriteResult> addBranch({
    required String name,
    String city = '',
    double? lat,
    double? lng,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/branches', data: {
        'name': name,
        'city': city,
        if (lat != null) 'lat': lat,
        if (lng != null) 'lng': lng,
      });
      // apiClient's own Dio instance is configured to NOT throw on 4xx (except 401) — see
      // ApiClient's own `validateStatus` doc comment — so a real refusal (402 BRANCH_LIMIT, 400
      // LOCATION_REQUIRED) resolves here rather than throwing. The status code, never "did this
      // not throw", is what actually says whether it saved (found live: a 402's own error body is
      // still a Map, so the old `if (data is Map)` check here read a refusal as success).
      final data = response.data;
      if (response.statusCode == 201 && data is Map) {
        return BranchWriteResult.ok(Branch.fromJson(Map<String, dynamic>.from(data)));
      }
      return BranchWriteResult.failed(_branchErrorFromData(data));
    } on DioException catch (e) {
      return BranchWriteResult.failed(_branchErrorFromData(e.response?.data));
    }
  }

  /// `PATCH /api/v1/staff/branches/{id}` — rename, close/reopen, or fix location. NEVER a
  /// delete: `staff.py::update_branch`'s own docstring is explicit that one does not exist.
  Future<BranchWriteResult> patchBranch(
    String branchId, {
    String? name,
    bool? active,
    String? city,
    double? lat,
    double? lng,
  }) async {
    try {
      final response = await apiClient.dio.patch<dynamic>('/api/v1/staff/branches/$branchId', data: {
        if (name != null) 'name': name,
        if (active != null) 'active': active,
        if (city != null) 'city': city,
        if (lat != null) 'lat': lat,
        if (lng != null) 'lng': lng,
      });
      // Same non-throwing-4xx trap as addBranch's own note above.
      final data = response.data;
      if (response.statusCode == 200 && data is Map) {
        return BranchWriteResult.ok(Branch.fromJson(Map<String, dynamic>.from(data)));
      }
      return BranchWriteResult.failed(_branchErrorFromData(data));
    } on DioException catch (e) {
      return BranchWriteResult.failed(_branchErrorFromData(e.response?.data));
    }
  }

  BranchErrorCode _branchErrorFromData(dynamic data) {
    final code = data is Map ? data['error'] as String? : null;
    switch (code) {
      case 'LOCATION_REQUIRED':
        return BranchErrorCode.locationRequired;
      case 'BRANCH_LIMIT':
        return BranchErrorCode.limitReached;
      case 'MAIN_BRANCH':
        return BranchErrorCode.mainBranch;
      case 'BRANCH_BUSY':
        return BranchErrorCode.busy;
      default:
        return BranchErrorCode.unknown;
    }
  }

  /// «الفريق» scoped to one branch — `GET /api/v1/staff/operators` (no `branch_id` param exists
  /// server-side; the caller's own visibility already narrows the rows — see
  /// staff.py::list_operators's own docstring). Returns the FULL visible roster; a caller filters
  /// by `branchId` client-side. `null` on failure.
  Future<List<BranchTeamMember>?> fetchOperators() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/operators');
      final data = response.data;
      if (data is! Map) return null;
      final rows = (data['operators'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => BranchTeamMember.fromJson(Map<String, dynamic>.from(m)))
          .toList();
    } on DioException {
      return null;
    }
  }

  /// Hires a real team member (his own login, never a shared-tablet PIN) into one branch —
  /// `POST /api/v1/staff/members` (staff.py::hire_member). `branchId` is REQUIRED server-side,
  /// same as [MemberIn.branch_id]'s own note — this screen only ever calls it from inside a
  /// specific branch's own detail page, so there is always a real one to pass.
  Future<HireResult> hireMember({
    required String name,
    required String phone,
    required String password,
    required StaffRole role,
    required String branchId,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/members', data: {
        'name': name,
        'phone': phone,
        'password': password,
        'role': role.value,
        'branch_id': branchId,
      });
      // Same non-throwing-4xx trap staff.py's own branch routes have — apiClient's Dio does not
      // throw on 402/400/409, so success is the STATUS CODE (201), never "the call did not
      // throw" (found live: a 402 SEAT_LIMIT body is a Map too, and reading `is Map` alone as
      // success reported a refused hire as done).
      if (response.statusCode == 201) return const HireResult.ok();
      return _hireResultFromData(response.data);
    } on DioException catch (e) {
      return _hireResultFromData(e.response?.data);
    }
  }

  HireResult _hireResultFromData(dynamic data) {
    final code = data is Map ? data['error'] as String? : null;
    final message = data is Map ? data['message'] as String? ?? '' : '';
    switch (code) {
      case 'BRANCH_REQUIRED':
        return const HireResult.failed(HireErrorCode.branchRequired);
      case 'SEAT_LIMIT':
        return const HireResult.failed(HireErrorCode.seatLimit);
      case 'SEAT_BUSY':
        return const HireResult.failed(HireErrorCode.busy);
      case 'NOT_HIRED':
        return HireResult.failed(HireErrorCode.notHired, message: message);
      default:
        return const HireResult.failed(HireErrorCode.unknown);
    }
  }

  /// Change the signed-in owner/operator's own password — `POST /api/v1/auth/change-password`
  /// (identity-service, a platform microservice with no source in this repo; the exact contract
  /// — path, method, and the `old_password`/`new_password` body shape — was read LIVE from the
  /// authenticated console session's own real catalog, `identity.change_password`, never
  /// guessed). Returns the server's own real message on failure (a wrong current password reads
  /// as a specific sentence, not a generic one) — `true` on success.
  Future<ChangePasswordResult> changePassword(
      {required String oldPassword, required String newPassword}) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/auth/change-password', data: {
        'old_password': oldPassword,
        'new_password': newPassword,
      });
      // Same non-throwing-4xx trap every other write in this file now guards against — success
      // is a 2xx status code, never merely "the call did not throw".
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return const ChangePasswordResult.ok();
      final data = response.data;
      final message = data is Map ? data['message'] as String? ?? '' : '';
      return ChangePasswordResult.failed(message);
    } on DioException catch (e) {
      final data = e.response?.data;
      final message = data is Map ? data['message'] as String? ?? '' : '';
      return ChangePasswordResult.failed(message);
    }
  }

  /// «الفوترة» — every real read the screen needs, fetched in parallel. `billing-service` is a
  /// platform microservice with no source in this repo; every path below was read LIVE off the
  /// vendored `platform/services/billing-service/app/user_actions.py` submodule (same discipline
  /// as [changePassword]'s own note — never guessed, this time from local, readable source rather
  /// than a live catalog fetch). Subscriptions is the one piece that decides whether the screen
  /// has anything to show at all; every other list degrades to empty on its own failure.
  Future<BillingOverview> fetchBillingOverview() async {
    final results = await Future.wait([
      _getList('/api/v1/billing/subscriptions', 'subscriptions'),
      _getList('/api/v1/billing/plans', 'plans'),
      _getMap('/api/v1/billing/subscriptions/renewal-preview'),
      _getList('/api/v1/billing/invoices', 'invoices', query: {'limit': 20}),
      _getMap('/api/v1/billing/usage'),
    ]);

    final subs = (results[0] as List)
        .whereType<Map>()
        .map((m) => BillingSubscription.fromJson(Map<String, dynamic>.from(m)))
        .where((s) => s.status != 'canceled')
        .toList();

    final plansById = <String, BillingPlan>{};
    for (final m in (results[1] as List).whereType<Map>()) {
      final plan = BillingPlan.fromJson(Map<String, dynamic>.from(m));
      if (plan.id.isNotEmpty) plansById[plan.id] = plan;
    }

    final renewalRaw = results[2] as Map?;
    final renewalGroups = ((renewalRaw?['groups'] as List?) ?? const [])
        .whereType<Map>()
        .map((m) => RenewalPreviewGroup.fromJson(Map<String, dynamic>.from(m)))
        .toList();

    final invoices = (results[3] as List)
        .whereType<Map>()
        .map((m) => BillingInvoice.fromJson(Map<String, dynamic>.from(m)))
        .toList();

    final usageRaw = results[4] as Map?;
    final entitlements = usageRaw?['entitlements'];
    final usage = <BillingUsageGauge>[];
    if (entitlements is Map) {
      for (final entry in entitlements.entries) {
        final v = entry.value;
        // Only real GAUGES — `entitlements.evaluate()`'s own `kind` field (billing-service
        // `core/entitlements.py`) is "gauge" | "counter" | "boolean"; a boolean feature flag
        // (`feature.whatsapp`, `plan.standalone`, …) or a key the resolver could not answer
        // (`error`, no `kind`) has nothing to draw a progress bar from — found live: without
        // this check every `feature.*`/`plan.*` flag rendered as a bogus "1 / 0" bar.
        if (v is Map && v['kind'] == 'gauge') {
          usage.add(BillingUsageGauge.fromJson(entry.key as String, Map<String, dynamic>.from(v)));
        }
      }
    }

    return BillingOverview(
      subscriptions: subs,
      plansById: plansById,
      renewalGroups: renewalGroups,
      invoices: invoices,
      usage: usage,
    );
  }

  /// «إيقاف التجديد» — `POST /api/v1/billing/subscriptions/{id}/cancel`. `at_period_end` always
  /// true from this screen: the shop keeps what it already paid for until the period ends, never
  /// an immediate cutoff.
  Future<bool> cancelSubscription(String subscriptionId) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/billing/subscriptions/$subscriptionId/cancel');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
    }
  }

  /// «تراجع عن إيقاف التجديد» — `POST /api/v1/billing/subscriptions/{id}/undo-cancel`.
  Future<bool> undoCancelSubscription(String subscriptionId) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/billing/subscriptions/$subscriptionId/undo-cancel');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
    }
  }

  /// «ادفع الآن» — a trackable hosted-checkout LINK for an existing unpayable invoice,
  /// `POST /api/v1/billing/invoices/{id}/pay-link`. Returns the URL to open externally, `null` on
  /// any failure (a 409 INVOICE_NOT_PAYABLE included — the caller simply has nothing to open).
  Future<String?> invoicePayLink(String invoiceId) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/billing/invoices/$invoiceId/pay-link');
      final data = response.data;
      if (response.statusCode != 201 || data is! Map) return null;
      return (data['pay_url'] as String?) ?? (data['checkout_url'] as String?);
    } on DioException {
      return null;
    }
  }

  /// «جدّد الآن» — the same real early-renewal door the WhatsApp Flow's own button already calls,
  /// exposed here through operations' own proxy (`POST /api/v1/subscription/renew-now`, services/
  /// operations `app/user_actions.py::subscription.renew_now` — a real, local-source route, unlike
  /// the billing-service ones above). TENANT-WIDE, deliberately — the owner's own call,
  /// 2026-09-22: as long as an app is not cancelled it stays in the shop's one shared monthly
  /// cycle, so there is no per-app early renewal any more, only the whole due-together group at
  /// once (see `renewal_provider.py::RenewalProvider.renew_now`'s own docstring for the
  /// group-selection rule). Returns every real pay URL the group produced, to open one after
  /// another — empty on any failure, never guessed.
  Future<List<String>> renewSubscriptionsNow() async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/subscription/renew-now');
      final data = response.data;
      if (response.statusCode != 200 && response.statusCode != 201) return const [];
      if (data is! Map) return const [];
      final urls = data['pay_urls'];
      if (urls is! List) return const [];
      return urls.whereType<String>().toList();
    } on DioException {
      return const [];
    }
  }

  Future<dynamic> _getList(String path, String key, {Map<String, dynamic>? query}) async {
    try {
      final response = await apiClient.dio.get<dynamic>(path, queryParameters: query);
      final data = response.data;
      if (data is Map) return (data[key] as List?) ?? const [];
      return const [];
    } on DioException {
      return const [];
    }
  }

  Future<Map?> _getMap(String path) async {
    try {
      final response = await apiClient.dio.get<dynamic>(path);
      final data = response.data;
      return data is Map ? data : null;
    } on DioException {
      return null;
    }
  }

  /// A branch's own WhatsApp connection — `GET /api/v1/whatsapp/connect?branch_id=`
  /// (connect.py::whatsapp_connect_status). `null` on failure, never confused with the real,
  /// honest "لم تبدأ الربط بعد" (empty `state`) the server itself returns.
  Future<BranchConnectStatus?> fetchBranchConnectStatus(String branchId) async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/whatsapp/connect', queryParameters: {'branch_id': branchId});
      final data = response.data;
      if (data is! Map) return null;
      return BranchConnectStatus.fromJson(Map<String, dynamic>.from(data));
    } on DioException {
      return null;
    }
  }

  /// Whether this shop manages branches centrally or per-branch — `GET /api/v1/staff/mode`
  /// (staff.py::read_mode). Governs whether WhatsApp connects once for the whole shop or once
  /// per branch — see apps/console/src/screens/Connect.tsx's own `ConnectByBranch` for the same
  /// real conditional this mobile screen mirrors.
  Future<bool> fetchIsPerBranchMode() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/mode');
      final data = response.data;
      if (data is! Map) return false;
      return (data['mode'] as String?) == 'per_branch';
    } on DioException {
      return false;
    }
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
