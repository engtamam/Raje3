import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/features/apps/payment_webview_screen.dart'
    show paymentReturnMarker;
import 'package:raje3_mobile/models/app_store_model.dart'
    show Owned, CartPreview;

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
enum BranchErrorCode {
  none,
  locationRequired,
  limitReached,
  mainBranch,
  busy,
  unknown
}

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
  final int created;
  // WHO ELSE HE MAY SEE, BEYOND HIS OWN STATION — `staff.py::branch_scope`'s own three answers:
  // [visibleAll] (everything), [visibleBranchIds] (a named set), or neither (just [branchId]).
  final bool visibleAll;
  final List<String> visibleBranchIds;
  final WorkingHours? workingHours;
  final bool hasLogin;
  final bool hasPin;

  const BranchTeamMember({
    required this.id,
    required this.name,
    required this.role,
    required this.branchId,
    required this.active,
    this.created = 0,
    this.visibleAll = false,
    this.visibleBranchIds = const [],
    this.workingHours,
    this.hasLogin = false,
    this.hasPin = false,
  });

  factory BranchTeamMember.fromJson(Map<String, dynamic> json) =>
      BranchTeamMember(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        role: json['role'] as String? ?? '',
        branchId: json['branch_id'] as String? ?? '',
        active: json['active'] as bool? ?? true,
        created: (json['created'] as num?)?.toInt() ?? 0,
        visibleAll: json['visible_all'] as bool? ?? false,
        visibleBranchIds: ((json['visible_branch_ids'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(),
        workingHours: json['working_hours'] is Map
            ? WorkingHours.fromJson(
                Map<String, dynamic>.from(json['working_hours'] as Map))
            : null,
        hasLogin: json['has_login'] as bool? ?? false,
        hasPin: json['has_pin'] as bool? ?? false,
      );
}

/// One weekday's own hours — `0` Monday .. `6` Sunday, minutes-of-day (0-1440), matching
/// `staff.py`'s own `PUT .../working-hours` body exactly (never merged: the whole week is sent
/// every time).
class DayHours {
  final bool closed;
  final int startMinute;
  final int endMinute;

  const DayHours(
      {required this.closed,
      required this.startMinute,
      required this.endMinute});

  factory DayHours.fromJson(Map<String, dynamic> json) => DayHours(
        closed: json['closed'] as bool? ?? false,
        startMinute: (json['start_minute'] as num?)?.toInt() ?? 0,
        endMinute: (json['end_minute'] as num?)?.toInt() ?? 0,
      );

  Map<String, dynamic> toJson() =>
      {'closed': closed, 'start_minute': startMinute, 'end_minute': endMinute};

  DayHours copyWith({bool? closed, int? startMinute, int? endMinute}) =>
      DayHours(
        closed: closed ?? this.closed,
        startMinute: startMinute ?? this.startMinute,
        endMinute: endMinute ?? this.endMinute,
      );
}

class WorkingHours {
  final Map<String, DayHours> weekly;
  const WorkingHours({required this.weekly});

  factory WorkingHours.fromJson(Map<String, dynamic> json) {
    final weekly = json['weekly'];
    return WorkingHours(
      weekly: {
        if (weekly is Map)
          for (final entry in weekly.entries)
            entry.key.toString(): DayHours.fromJson(
                Map<String, dynamic>.from(entry.value as Map)),
      },
    );
  }

  Map<String, dynamic> toJson() => {
        'weekly': {
          for (final entry in weekly.entries) entry.key: entry.value.toJson()
        }
      };
}

/// The real, fixed role set — `apps/console/src/screens/Team.tsx`'s own radio options, matched
/// exactly (the server's `MemberIn.role` is a free string with no enum, but these four are the
/// only ones the product actually offers anywhere). Never invented for this screen.
enum StaffRole { operator, supervisor, marketer, manager }

extension StaffRoleValue on StaffRole {
  String get value => switch (this) {
        StaffRole.operator => 'operator',
        StaffRole.supervisor => 'supervisor',
        StaffRole.marketer => 'marketer',
        StaffRole.manager => 'manager',
      };
}

StaffRole? staffRoleFromValue(String value) {
  for (final r in StaffRole.values) {
    if (r.value == value) return r;
  }
  return null;
}

/// The outcome of hiring a new team member — `POST /staff/members` (staff.py::hire_member).
/// `notHired`'s message is the SERVER's own real sentence (e.g. «هذا الرقم مسجّل في منشأة
/// أخرى»), never a generic one — the only error here worth showing verbatim rather than mapping
/// to a fixed local string.
enum HireErrorCode { none, branchRequired, seatLimit, busy, notHired, unknown }

class HireResult {
  final HireErrorCode error;
  final String message;
  const HireResult.ok()
      : error = HireErrorCode.none,
        message = '';
  const HireResult.failed(this.error, {this.message = ''});
}

class ChangePasswordResult {
  final bool ok;
  final String message;
  const ChangePasswordResult.ok()
      : ok = true,
        message = '';
  const ChangePasswordResult.failed(this.message) : ok = false;
}

/// «الفوترة» — billing-service's own real models (`platform/services/billing-service/app/core/
/// models.py`), the SAME shapes `apps/console/src/billingShared.tsx`/`BillingStatusPane.tsx`
/// already read — this screen re-derives nothing new, only presents it mobile-natively. Money is
/// integer minor units end-to-end, exactly like the server; [Formatters.formatCurrency] converts
/// at the very edge of the UI, never here.
/// THE ONE `Plan` MODEL EVERY BILLING SURFACE SHARES — «الفوترة» (already-subscribed) and
/// «متجر التطبيقات» (browsing to buy) both read this same class, so a plan's shape is never
/// defined twice (found live, 2026-09-23: the store screen had started growing its own second
/// copy). `limits`/`active`/`listed` exist for the STORE's own read (which plan grants which
/// `feature.*` key, and which plans are even sellable) — absent/default for the billing screen's
/// own narrower read, which never needed them.
class BillingPlan {
  final String id;
  final String name;
  final int monthlyAmountMinor;
  final String currency;
  final Map<String, dynamic> limits;
  final bool active;
  final bool listed;
  final int trialDays;

  /// billingShared's own `includedAiCreditOf` — the SAME price row's `included_credit_minor`,
  /// `null` for every plan without such an allowance (never a zero-guess: a plan that never
  /// opted into this reads as "carries no such allowance", not "carries zero of it").
  final int? includedCreditMinor;

  const BillingPlan({
    required this.id,
    required this.name,
    required this.monthlyAmountMinor,
    required this.currency,
    this.limits = const {},
    this.active = true,
    this.listed = true,
    this.trialDays = 0,
    this.includedCreditMinor,
  });

  /// Free forever, or a trial that owes nothing today — mirrors the console's own
  /// `subscribeFlow.ts::needsNoPayment` and `services/operations`'s own `may_subscribe` so this
  /// app, the console, and the server never disagree about which plans need a pay-link at all.
  bool get needsPayment => monthlyAmountMinor > 0 && trialDays <= 0;

  factory BillingPlan.fromJson(Map<String, dynamic> json) {
    final prices =
        (json['prices'] as List?)?.whereType<Map>().toList() ?? const [];
    final monthly = prices.firstWhere(
      (p) => p['interval'] == 'month',
      orElse: () => prices.isNotEmpty ? prices.first : const {},
    );
    return BillingPlan(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      monthlyAmountMinor: (monthly['amount_minor'] as num?)?.toInt() ?? 0,
      currency: monthly['currency'] as String? ?? 'SAR',
      limits: Map<String, dynamic>.from((json['limits'] as Map?) ?? const {}),
      active: json['active'] != false,
      listed: json['listed'] != false,
      trialDays: (json['trial_days'] as num?)?.toInt() ?? 0,
      includedCreditMinor: _positiveOrNull(monthly['included_credit_minor']),
    );
  }

  static int? _positiveOrNull(dynamic v) {
    final n = (v as num?)?.toInt();
    return (n != null && n > 0) ? n : null;
  }

  /// billingShared.tsx::appKey — the one `feature.*` key this plan turns on, or empty for a
  /// capacity-only row (seats/branches carry no `feature.*` limit at all).
  String get appKey {
    for (final k in limits.keys) {
      if (k.startsWith('feature.')) {
        final lim = limits[k];
        final raw = lim is Map ? lim['limit'] : null;
        final n = raw is num ? raw : (raw == 'unlimited' ? -1 : 0);
        if (n != 0) return k;
      }
    }
    return '';
  }

  bool get isCapacity => appKey.isEmpty;

  /// billingShared.tsx::requiresAny — the OTHER feature keys this plan's own row says at least
  /// one of must already be held, straight off `plan.limits['plan.requires_any'].list`. Empty
  /// when the plan declares no dependency at all.
  List<String> get requiresAny {
    final raw = limits['plan.requires_any'];
    final list = raw is Map ? raw['list'] : null;
    if (list is! List) return const [];
    return list
        .whereType<String>()
        .where((k) => k.isNotEmpty)
        .toList(growable: false);
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

  factory BillingSubscription.fromJson(Map<String, dynamic> json) =>
      BillingSubscription(
        id: json['id'] as String? ?? '',
        planId: json['plan_id'] as String? ?? '',
        status: json['status'] as String? ?? '',
        quantity: (json['quantity'] as num?)?.toInt() ?? 1,
        currentPeriodEnd: (json['current_period_end'] as num?)?.toDouble() ?? 0,
        cancelAtPeriodEnd: json['cancel_at_period_end'] as bool? ?? false,
      );
}

/// `GET /api/v1/billing/discount-preview` — one rule's percent + the OTHER app whose ownership
/// earns/would-earn it (`owning_key`), mirrors billingShared.tsx's own `{percent, owning_key}`.
class DiscountInfo {
  final int percent;
  final String owningKey;
  const DiscountInfo({required this.percent, required this.owningKey});

  factory DiscountInfo.fromJson(Map<String, dynamic> j) => DiscountInfo(
        percent: (j['percent'] as num?)?.toInt() ?? 0,
        owningKey: j['owning_key'] as String? ?? '',
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

  factory RenewalPreviewLine.fromJson(Map<String, dynamic> json) =>
      RenewalPreviewLine(
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

  factory RenewalPreviewGroup.fromJson(Map<String, dynamic> json) =>
      RenewalPreviewGroup(
        currency: json['currency'] as String? ?? 'SAR',
        nextChargeAt: (json['next_charge_at'] as num?)?.toDouble(),
        lines: ((json['lines'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) =>
                RenewalPreviewLine.fromJson(Map<String, dynamic>.from(m)))
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

  const BillingUsageGauge(
      {required this.key, required this.current, required this.limit});

  factory BillingUsageGauge.fromJson(String key, Map<String, dynamic> json) {
    final rawLimit = json['limit'];
    final unlimited = rawLimit == null ||
        rawLimit == 'unlimited' ||
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

  const BranchConnectStatus(
      {required this.state, required this.message, required this.canSend});

  /// Three real states only — never a fourth invented one. `notStarted` (empty `state`),
  /// `connected` (`canSend`), `connectedCannotSend` (a real, distinct state, not lumped with
  /// `connected` — connect.py's own PIN-step note is exactly why this stays a third value).
  bool get notStarted => state.isEmpty;

  factory BranchConnectStatus.fromJson(Map<String, dynamic> json) =>
      BranchConnectStatus(
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
  final int expiresIn;
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
    this.expiresIn = 0,
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
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/account/me/name');
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
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/staff/vehicles');
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
      final rawBranding = branding is Map
          ? Map<String, dynamic>.from(branding)
          : <String, dynamic>{};
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
      await apiClient.dio
          .put<dynamic>('/api/v1/staff/shop-name', data: {'name': name});
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
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/account/me/mobile-ai-assistant');
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
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/staff/branches');
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
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/staff/branches', data: {
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
        return BranchWriteResult.ok(
            Branch.fromJson(Map<String, dynamic>.from(data)));
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
      final response = await apiClient.dio
          .patch<dynamic>('/api/v1/staff/branches/$branchId', data: {
        if (name != null) 'name': name,
        if (active != null) 'active': active,
        if (city != null) 'city': city,
        if (lat != null) 'lat': lat,
        if (lng != null) 'lng': lng,
      });
      // Same non-throwing-4xx trap as addBranch's own note above.
      final data = response.data;
      if (response.statusCode == 200 && data is Map) {
        return BranchWriteResult.ok(
            Branch.fromJson(Map<String, dynamic>.from(data)));
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
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/staff/operators');
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
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/staff/members', data: {
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

  /// One route for rename/role-change/station-move/branch-visibility-grant/stop/reactivate —
  /// `PATCH /api/v1/staff/operators/{id}` (`OperatorPatch`, staff.py). Every param `null` (the
  /// default) means "leave it" server-side — never send a field the caller did not actually mean
  /// to change. Returns the server's own real refusal sentence (`BRANCH_REQUIRED`,
  /// `NOT_STOPPED`, `REHIRE_REQUIRED`) or `null` on success.
  Future<String?> editOperator(
    String operatorId, {
    String? name,
    StaffRole? role,
    String? branchId,
    List<String>? visibleBranchIds,
    bool? visibleAll,
    bool? active,
  }) async {
    try {
      final response = await apiClient.dio
          .patch<dynamic>('/api/v1/staff/operators/$operatorId', data: {
        if (name != null) 'name': name,
        if (role != null) 'role': role.value,
        if (branchId != null) 'branch_id': branchId,
        if (visibleBranchIds != null) 'visible_branch_ids': visibleBranchIds,
        if (visibleAll != null) 'visible_all': visibleAll,
        if (active != null) 'active': active,
      });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusalMessage(response.data);
    } on DioException catch (e) {
      return _refusalMessage(e.response?.data) ?? '';
    }
  }

  String? _refusalMessage(dynamic data) {
    if (data is! Map) return '';
    final code = data['error'] as String?;
    final message = data['message'] as String?;
    return message?.isNotEmpty == true ? message : (code ?? '');
  }

  /// `PUT /api/v1/staff/operators/{id}/working-hours` — the WHOLE week, every call (never
  /// merged); `staff.py`'s own refusal when a day exceeds the shop's own hours.
  Future<String?> setWorkingHours(String operatorId, WorkingHours hours) async {
    try {
      final response = await apiClient.dio.put<dynamic>(
          '/api/v1/staff/operators/$operatorId/working-hours',
          data: hours.toJson());
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusalMessage(response.data);
    } on DioException catch (e) {
      return _refusalMessage(e.response?.data) ?? '';
    }
  }

  /// `DELETE /api/v1/staff/operators/{id}/working-hours` — back to inheriting the shop's own
  /// hours. Idempotent.
  Future<bool> clearWorkingHours(String operatorId) async {
    try {
      final response = await apiClient.dio
          .delete<dynamic>('/api/v1/staff/operators/$operatorId/working-hours');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
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
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/auth/change-password', data: {
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
          usage.add(BillingUsageGauge.fromJson(
              entry.key as String, Map<String, dynamic>.from(v)));
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
      final response = await apiClient.dio.post<dynamic>(
          '/api/v1/billing/subscriptions/$subscriptionId/cancel');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
    }
  }

  /// «تراجع عن إيقاف التجديد» — `POST /api/v1/billing/subscriptions/{id}/undo-cancel`.
  Future<bool> undoCancelSubscription(String subscriptionId) async {
    try {
      final response = await apiClient.dio.post<dynamic>(
          '/api/v1/billing/subscriptions/$subscriptionId/undo-cancel');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
    }
  }

  /// «ادفع الآن» — a trackable hosted-checkout LINK for an existing unpayable invoice,
  /// `POST /api/v1/billing/invoices/{id}/pay-link`. Returns the URL to open in-app
  /// (`payment_webview_screen.dart::openPaymentInApp`), `null` on any failure (a 409
  /// INVOICE_NOT_PAYABLE included — the caller simply has nothing to open). `return_url` is the
  /// same marker that screen's own NavigationDelegate watches for to auto-close — console's own
  /// BillingStatusPane.tsx passes `window.location.href` for the identical reason.
  Future<String?> invoicePayLink(String invoiceId) async {
    try {
      final response = await apiClient.dio.post<dynamic>(
          '/api/v1/billing/invoices/$invoiceId/pay-link',
          data: {'return_url': paymentReturnMarker});
      final data = response.data;
      if (response.statusCode != 201 || data is! Map) return null;
      return (data['pay_url'] as String?) ?? (data['checkout_url'] as String?);
    } on DioException {
      return null;
    }
  }

  // ── متجر التطبيقات — purchasing what is not yet owned. NO payment_token anywhere here: the
  // real, decided gateway (TuwaiqPay, owner's decision 2026-09-23) has no card-on-file/
  // synchronous charge at all; renewal is manual, through `invoicePayLink` above once a real
  // invoice falls due. `subscribe`/`checkout` themselves never charge synchronously either way —
  // they only create the row (trial or immediate period, per the plan's own `trial_days`). ────

  /// `GET /api/v1/subscription/apps` — this shop's real entitlement read, the one source every
  /// lock/unlock badge on the store screen reads.
  Future<Owned?> fetchOwnership() async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/subscription/apps');
      if ((response.statusCode ?? 0) >= 400) return null;
      final body = response.data;
      if (body is! Map) return null;
      return Owned.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/billing/plans` — every plan a shop MAY buy, not only what it already holds
  /// (`fetchBillingOverview`'s own narrower read). Same filter useAppBilling.ts::load applies.
  ///
  /// `visibleOverrideKeys` — feature keys ONE platform operator made visible for THIS shop
  /// specifically, on top of whatever is globally `listed` (`fetchAppVisibilityOverrides` below,
  /// `services/operations/app/core/app_visibility.py`'s own module docstring for the full design;
  /// same param `useAppBilling.ts` carries on the console side). A plan whose OWN feature key
  /// (its own `limits` map's non-`plan.*` entry) is in this list is kept even when `listed` is
  /// false — still excluded when `active` is false regardless, exactly like the console.
  Future<List<BillingPlan>?> fetchPurchasablePlans(
      {List<String> visibleOverrideKeys = const []}) async {
    try {
      // HIDDEN PLANS ONLY ARRIVE WHEN ASKED FOR — billing omits every `listed: false` plan unless
      // the call says `include_hidden=true` (honoured for `billing.manage`, which the owner holds),
      // so an override key could never match anything on the plain list. Asked only when an
      // override exists; a non-owner's refused ask falls back to the plain list. Same fix as
      // useAppBilling.ts on the console side.
      Response<dynamic>? response;
      if (visibleOverrideKeys.isNotEmpty) {
        try {
          response = await apiClient.dio.get<dynamic>('/api/v1/billing/plans',
              queryParameters: {'include_hidden': true});
          if ((response.statusCode ?? 0) >= 400) response = null;
        } on DioException {
          response = null;
        }
      }
      response ??= await apiClient.dio.get<dynamic>('/api/v1/billing/plans');
      if ((response.statusCode ?? 0) >= 400) return null;
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['plans'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => BillingPlan.fromJson(Map<String, dynamic>.from(m)))
          .where((p) =>
              p.active && (p.listed || visibleOverrideKeys.contains(p.appKey)))
          .toList();
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/subscription/apps/visibility-overrides` — which otherwise-hidden apps THIS shop
  /// specifically was shown. Tenant resolved server-side from this shop's own token; there is no
  /// tenant parameter on this route at all (the route's own docstring: what makes it IDOR-safe by
  /// construction). `[]` (never `null`) on any failure — a store screen must still render with
  /// nothing extra shown rather than break.
  Future<List<String>> fetchAppVisibilityOverrides() async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/subscription/apps/visibility-overrides');
      if ((response.statusCode ?? 0) >= 400) return const [];
      final body = response.data;
      if (body is! Map) return const [];
      final keys = (body['visible_keys'] as List?) ?? const [];
      return keys.whereType<String>().toList();
    } on DioException {
      return const [];
    }
  }

  /// `GET /api/v1/assistant/pricing/current` — `(unitsPerHalala, aiEnabled)`, the live
  /// halala→unit conversion rate `Wallet.tsx`'s own `unitsLabel` and the app-store's own
  /// `AiUnitsChip` both read. `null`/`true` (fail-open, same as useAppBilling.ts's own posture)
  /// when the action is absent or the read fails — the chip itself never renders without a real
  /// `includedCreditMinor` regardless, so a wrong `aiEnabled` guess here costs nothing.
  Future<(double?, bool)> fetchAiUnitsPerHalala() async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/assistant/pricing/current');
      final body = response.data;
      if (body is! Map) return (null, true);
      return (
        (body['ai_unit_units_per_halala'] as num?)?.toDouble(),
        body['ai_enabled'] != false,
      );
    } on DioException {
      return (null, true);
    }
  }

  /// `GET /api/v1/billing/discount-preview` — `(applied, potential)`, keyed by plan id. `applied`
  /// means the shop already qualifies (owns the `owning_key` app) and the discount is real today;
  /// `potential` is a marketing teaser for a plan not yet owned ("X% off if you also get Y").
  Future<(Map<String, DiscountInfo>, Map<String, DiscountInfo>)>
      fetchDiscountPreview() async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/billing/discount-preview');
      final body = response.data;
      if (body is! Map) {
        return (const <String, DiscountInfo>{}, const <String, DiscountInfo>{});
      }
      Map<String, DiscountInfo> parse(String key) {
        final m = body[key];
        if (m is! Map) return const {};
        return m.map((k, v) => MapEntry(k.toString(),
            DiscountInfo.fromJson(Map<String, dynamic>.from(v as Map))));
      }

      return (parse('applied'), parse('potential'));
    } on DioException {
      return (const <String, DiscountInfo>{}, const <String, DiscountInfo>{});
    }
  }

  /// `POST /api/v1/subscription/checkout/preview` — read-only, creates and charges nothing.
  Future<CartPreview?> checkoutPreview(List<String> planIds) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/subscription/checkout/preview', data: {
        'items':
            planIds.map((id) => {'plan_id': id, 'interval': 'month'}).toList(),
      });
      if ((response.statusCode ?? 0) >= 400) return null;
      final body = response.data;
      if (body is! Map) return null;
      return CartPreview.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/subscription` — one app, our own route (enforces WhatsApp-before-paid
  /// ordering). Returns `(ok, statusCode)` — the real HTTP status names the real refusal even
  /// though its text is stripped in transit (same posture `propose`/`subscribe` elsewhere take).
  Future<(bool, int?)> subscribeToApp(
      {required String planId, int quantity = 1}) async {
    try {
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/subscription', data: {
        'plan_id': planId,
        'quantity': quantity,
      });
      final status = response.statusCode ?? 0;
      return (status < 400, status >= 400 ? status : null);
    } on DioException catch (e) {
      return (false, e.response?.statusCode);
    }
  }

  /// `POST /api/v1/subscription/checkout-link` — a NEW paid subscription started with a real
  /// TuwaiqPay hosted link, never a card-form token this app has no way to mint (TuwaiqPay has no
  /// browser/app-side tokenisation at all). Mirrors the console's own `subscribeFlow.ts::
  /// startPaidCheckout` (2026-09-24): the subscription is created `incomplete` and activates only
  /// once the payment settles through billing's normal webhook/reconcile seam. Returns the real
  /// pay-link to open, or null on ANY refusal (`status` names the family — 409 WhatsApp-required,
  /// 503 gateway down, ...) — `null` with a status is a real refusal, `null` with none is a
  /// network failure, same distinction `subscribeToApp` already draws.
  Future<(String?, int?)> checkoutLink(
      {required String planId, int quantity = 1}) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/subscription/checkout-link', data: {
        'plan_id': planId,
        'quantity': quantity,
      });
      final data = response.data;
      final url = data is Map
          ? (data['checkout_url'] ?? data['pay_url']) as String?
          : null;
      return (url, null);
    } on DioException catch (e) {
      return (null, e.response?.statusCode);
    }
  }

  /// `POST /api/v1/subscription/checkout/link` — ONE real pay-link for the whole cart
  /// (base-services v0.25.31), replacing the old token-based `checkout` route this app never had
  /// a way to feed a real token to. An all-free/trial cart is already created (`checkout_required:
  /// false`, no link to open); the console's own `useAppBilling.ts::checkout` reads the exact
  /// same response shape.
  Future<(String?, bool, int?)> checkoutCart(List<String> planIds) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>('/api/v1/subscription/checkout/link', data: {
        'items':
            planIds.map((id) => {'plan_id': id, 'interval': 'month'}).toList(),
      });
      final data = response.data;
      if (data is! Map) return (null, true, null);
      final url = (data['checkout_url'] ?? data['pay_url']) as String?;
      final checkoutRequired = data['checkout_required'] != false;
      return (checkoutRequired ? url : null, true, null);
    } on DioException catch (e) {
      return (null, false, e.response?.statusCode);
    }
  }

  Future<bool> cancelCapacityUnit(String subscriptionId) =>
      cancelSubscription(subscriptionId);

  /// `POST /api/v1/billing/subscriptions/{id}/change` — the capacity stepper's +/-.
  Future<bool> changeCapacityQuantity(
      {required String subscriptionId,
      required String planId,
      required int quantity}) async {
    try {
      final response = await apiClient.dio.post<dynamic>(
          '/api/v1/billing/subscriptions/$subscriptionId/change',
          // `new_plan_id`, not `plan_id` — billing's ChangeIn field name; `plan_id` was refused
          // 422 on every press. Same fix as the console's useAppBilling.ts.
          data: {
            'new_plan_id': planId,
            'quantity': quantity,
          });
      return (response.statusCode ?? 0) < 400;
    } on DioException {
      return false;
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
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/subscription/renew-now');
      final data = response.data;
      if (response.statusCode != 200 && response.statusCode != 201) {
        return const [];
      }
      if (data is! Map) return const [];
      final urls = data['pay_urls'];
      if (urls is! List) return const [];
      return urls.whereType<String>().toList();
    } on DioException {
      return const [];
    }
  }

  Future<dynamic> _getList(String path, String key,
      {Map<String, dynamic>? query}) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>(path, queryParameters: query);
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
      final response = await apiClient.dio.get<dynamic>(
          '/api/v1/whatsapp/connect',
          queryParameters: {'branch_id': branchId});
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
            : (detail is List && detail.isNotEmpty
                ? detail.first.toString()
                : null);
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
        expiresIn: (map['expires_in'] as num?)?.toInt() ?? 0,
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
          return AuthResult.refused(said,
              reason: (map['reason'] as String?) ?? '');
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
