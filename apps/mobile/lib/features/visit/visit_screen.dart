import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/effects/game_effects.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/premium/active_offer_banner.dart';
import 'package:raje3_mobile/widgets/premium/loyalty_balance_card.dart';

/// «تسجيل زيارة» — this is the screen an operator opens dozens of times a
/// day, every time a customer leaves the counter, so its whole design is one
/// argument: get him back to a blank, ready screen in five seconds.
///
/// Rebuilt from the previous pass (manual phone-search button, a checkbox
/// list of services, an always-open note field) around three changes that
/// each remove a tap or a wait, mirroring apps/console/src/screens/Visit.tsx's
/// own «budget is five seconds» screen:
///   - the phone field searches AS HE TYPES (search-service's own prefix
///     suggestions, `/customers/suggest`) and resolves itself once the number
///     is complete (`/customers/by-phone`) — no search button anywhere
///   - services are one-tap selection chips, not a scrollable checklist
///   - the note field is collapsed until asked for
/// and a save that confirms with a haptic + a checkmark, then clears itself
/// and refocuses the phone field — ready for the NEXT customer, not back to
/// menu.
///
/// Real endpoints (services/operations/app/api/v1/field.py):
///   - GET  /api/v1/field/customers/suggest?prefix=...     as-you-type matches
///   - GET  /api/v1/field/customers/by-phone?phone=...     exact lookup
///   - GET  /api/v1/field/catalogue                        services + packages
///   - POST /api/v1/field/visits                           VisitIn — records the visit
/// All four are shared, cross-client-type routes, so calls go through
/// [ApiClient.dio] directly rather than the `{success, data}` envelope
/// (see catalog_service.dart's own note).
class VisitScreen extends StatefulWidget {
  const VisitScreen({super.key});

  @override
  State<VisitScreen> createState() => _VisitScreenState();
}

class _VisitScreenState extends State<VisitScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entryController;
  final _phoneController = TextEditingController();
  final _noteController = TextEditingController();
  final _plateController = TextEditingController();
  final _nameController = TextEditingController();
  final _meterController = TextEditingController();
  final _phoneFocus = FocusNode();
  final _plateFocus = FocusNode();

  bool _loadingCatalogue = true;
  String? _catalogueError;
  List<Map<String, dynamic>> _services = [];
  List<Map<String, dynamic>> _packages = [];

  // ── Today's known appointments — `GET /api/v1/bookings`, resolved to today's business day and
  // this shop's own single branch (multi-branch: skipped entirely, same "not yet narrowed" rule
  // the rest of this app already holds to — see `_loadTodayBookings`'s own note). `null` = not
  // loaded / not applicable; an empty list is a real, silent "nobody today".
  List<Map<String, dynamic>>? _todayBookings;
  Map<String, String> _operatorNames = {};
  String _busyBookingId = '';

  /// service_id -> its own resolved loyalty points (`GET /api/v1/loyalty/settings`, the same
  /// tree `services_catalogue_service.dart`'s own `EarnSettingsTree` already models for
  /// «خدماتي ومنتجاتي») — fetched once alongside the catalogue purely for display on each tile;
  /// never sent back, never a source of truth for what the visit actually earns.
  final Map<String, int> _servicePoints = {};

  /// The package tapped to select its member services in one motion — highlighted itself, and its
  /// own tint carries onto every service tile it added, so the operator sees at a glance which
  /// selections came from one tap rather than several.
  String? _selectedPackageId;

  // ── Shop-to-shop coupon grant, riding on this same visit — `Visit.tsx`'s own "checkbox during
  // visit recording" surface. `null` = still unknown (or the tenant/role does not have this at
  // all — `operations.grant_coupon` absent from the catalogue means this section is never shown,
  // never a control that refuses). Scope note: this mobile pass supports the GENERAL grant only
  // (every app the beneficiary holds) — the console's own per-app scope picker reads from its
  // local app registry (`APP_ROWS`), which has no mobile equivalent yet; not stubbed, simply the
  // one real, always-available choice, "العام", built first.
  bool? _couponScreenEnabled;
  bool _couponOn = false;
  final _couponPhoneController = TextEditingController();
  final _couponPercentController = TextEditingController(text: '10');
  int _couponPercent = 10;

  // ── vehicle/plate — GET /api/v1/field/catalogue's own `tracks_vehicle`, the SAME server fact
  // apps/console/src/screens/Visit.tsx's own `showPlate` reads. A shop this is true for REFUSES
  // (`recorded: false`) any visit with no plausible plate — `core/plate.py::is_plausible` server-
  // side — so this field is never cosmetic once shown.
  bool _tracksVehicle = false;
  Timer? _plateLookupDebounce;
  bool _lookingUpPlate = false;
  String? _vehicleCustomerName;
  bool _plateLookedUp = false;
  Timer? _plateSuggestDebounce;
  List<Map<String, dynamic>> _plateSuggestions = [];

  Timer? _suggestDebounce;
  Timer? _exactDebounce;
  bool _lookingUp = false;
  String? _customerName;
  bool _lookedUp = false;
  List<Map<String, dynamic>> _suggestions = [];

  // ── the customer's own points/offer — a real preview, never a spend (§5.6.2's own "a tap,
  // never an inference"). Fetched once a customer is IDENTIFIED (by phone or by plate) and a real
  // `subject_ref` is known — GET /api/v1/loyalty/balance/{ref} and GET /api/v1/reminders/offer,
  // the exact shared, cross-client-type routes apps/console/src/screens/Visit.tsx's own
  // `balanceFor`/`offerFor` already call. Cleared the moment the identity changes, same rule
  // `_customerName`/`_vehicleCustomerName` above already follow.
  String? _subjectRef;
  int? _loyaltyPoints;
  int _loyaltyToNextReward = 0;
  List<Map<String, dynamic>> _loyaltyRewards = [];
  String? _offerText;
  String? _offerValue;

  bool _noteOpen = false;

  // ── Points redemption + offer application — real spends, never automatic. Mirrors
  // apps/console/src/screens/Visit.tsx's own `spend`/`applying` exactly (same two real doors:
  // `POST /api/v1/loyalty/redeem`, `POST /api/v1/field/visits/{id}/offer`), never invented.
  String _redeemingRewardId = '';
  String? _redeemedRewardName;
  bool _applyingOffer = false;

  /// service_id -> quantity. Only ids present here are sent.
  final Map<String, int> _selected = {};

  bool _saving = false;
  String? _saveError;
  bool _justSaved = false;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      vsync: this,
      duration: AppMotion.slow,
    );
    _entryController.forward();
    _loadCatalogue();
    // THE KEYBOARD IS ALREADY UP THE MOMENT HE LANDS HERE — the first thing this
    // screen asks for is the one thing he always has in hand at the counter.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _phoneFocus.requestFocus();
    });
    // A BRANCH SWITCH ELSEWHERE (the home hero's own chip) MUST REACH TODAY'S APPOINTMENTS HERE
    // TOO — this screen is reachable without ever leaving it, so a stale diary from the branch he
    // just left would show the wrong shop's own customers.
    context.read<BranchProvider>().addListener(_onBranchChanged);
  }

  void _onBranchChanged() {
    if (mounted) _loadTodayBookings();
  }

  @override
  void dispose() {
    context.read<BranchProvider>().removeListener(_onBranchChanged);
    _entryController.dispose();
    _phoneController.dispose();
    _noteController.dispose();
    _plateController.dispose();
    _nameController.dispose();
    _meterController.dispose();
    _couponPhoneController.dispose();
    _couponPercentController.dispose();
    _phoneFocus.dispose();
    _plateFocus.dispose();
    _suggestDebounce?.cancel();
    _exactDebounce?.cancel();
    _plateLookupDebounce?.cancel();
    _plateSuggestDebounce?.cancel();
    super.dispose();
  }

  AuthProvider get _api => context.read<AuthProvider>();

  Future<void> _loadCatalogue() async {
    setState(() {
      _loadingCatalogue = true;
      _catalogueError = null;
    });
    try {
      final response = await _api.apiClient.dio.get<dynamic>('/api/v1/field/catalogue');
      final body = response.data;
      final services = body is Map<String, dynamic>
          ? (body['services'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .toList()
          : <Map<String, dynamic>>[];
      final packages = body is Map<String, dynamic>
          ? (body['packages'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .toList()
          : <Map<String, dynamic>>[];
      final tracksVehicle = body is Map<String, dynamic> && body['tracks_vehicle'] == true;
      if (!mounted) return;
      setState(() {
        _services = services;
        _packages = packages;
        _tracksVehicle = tracksVehicle;
        _loadingCatalogue = false;
      });
      unawaited(_loadServicePoints());
      unawaited(_loadCouponPreference());
      unawaited(_loadTodayBookings());
    } on DioException {
      if (!mounted) return;
      setState(() {
        _catalogueError = S.of(context)!.visitCatalogueLoadErrorFallback;
        _loadingCatalogue = false;
      });
    }
  }

  /// «كم نقطة يكسبها العميل من كل خدمة» — a real, resolved number per tile (service's own
  /// override → its group → tenant general → platform floor), read once from the same tree
  /// `services_catalogue_service.dart`'s own `EarnSettingsTree` models. Silent on failure: a shop
  /// with no loyalty programme, or a role without `loyalty.read`, simply shows no points badge —
  /// never a blocked grid over a purely decorative number.
  Future<void> _loadServicePoints() async {
    try {
      final response = await _api.apiClient.dio.get<dynamic>('/api/v1/loyalty/settings');
      final body = response.data;
      if (body is! Map) return;
      final generalPoints = (body['general'] is Map ? (body['general']['points'] as num?) : null)?.toInt();
      final defaultPoints = (body['defaults'] is Map ? (body['defaults']['points'] as num?) : null)?.toInt();
      final serviceGroup = <String, String>{
        for (final e in ((body['service_group'] as Map?) ?? const {}).entries)
          e.key.toString(): e.value.toString(),
      };
      final groupPoints = <String, int>{
        for (final e in ((body['groups'] as Map?) ?? const {}).entries)
          e.key.toString(): (e.value is Map ? (e.value['points'] as num?)?.toInt() : null) ?? 0,
      };
      final servicePoints = <String, int>{
        for (final e in ((body['services'] as Map?) ?? const {}).entries)
          e.key.toString(): (e.value is Map ? (e.value['points'] as num?)?.toInt() : null) ?? 0,
      };
      if (!mounted) return;
      setState(() {
        for (final service in _services) {
          final id = service['id'] as String? ?? '';
          if (id.isEmpty) continue;
          final own = servicePoints[id];
          final group = serviceGroup[id];
          final resolved = own ?? (group != null ? groupPoints[group] : null) ?? generalPoints ?? defaultPoints ?? 0;
          if (resolved > 0) _servicePoints[id] = resolved;
        }
      });
    } on DioException {
      // Decorative only — never blocks or errors the screen.
    }
  }

  /// `GET /api/v1/staff/coupons/preferences` — whether the owner turned the visit-screen coupon
  /// checkbox ON at all («تحالف استراتيجي»'s own switch). Never fetched unless the role already
  /// carries `operations.grant_coupon` — the same capability the server itself checks before
  /// attempting any grant, so a role/tenant without it never even asks.
  Future<void> _loadCouponPreference() async {
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['operations.grant_coupon'])) return;
    try {
      final response = await _api.apiClient.dio.get<dynamic>('/api/v1/staff/coupons/preferences');
      final body = response.data;
      final enabled = body is Map && body['visit_grant_enabled'] == true;
      if (!mounted) return;
      setState(() => _couponScreenEnabled = enabled);
    } on DioException {
      if (mounted) setState(() => _couponScreenEnabled = false);
    }
  }

  /// Every open booking for TODAY, this shop's own business day — an operator recognises a walk-
  /// in he already knows is coming and confirms it in one tap, never a lookup. Reads the real
  /// branch scope from [BranchProvider] — the home hero's own switcher — rather than re-guessing
  /// it here; a single-branch shop resolves silently (BranchProvider auto-selects its only
  /// branch), a multi-branch shop that has not opened the switcher yet still gets its default
  /// (BranchProvider.load's own "first branch" fallback), and the chip is always there to correct
  /// it explicitly.
  Future<void> _loadTodayBookings() async {
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['bookings.read'])) return;
    final branchProvider = context.read<BranchProvider>();
    if (!branchProvider.loaded) await branchProvider.load();
    final branchId = branchProvider.selectedId;
    if (branchId == null) return;
    final now = DateTime.now();
    final dateStr =
        '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    try {
      final response = await _api.apiClient.dio
          .get<dynamic>('/api/v1/bookings', queryParameters: {'branch_id': branchId, 'date': dateStr});
      final body = response.data;
      final rows = body is Map<String, dynamic>
          ? (body['bookings'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .where((b) => b['status'] == 'booked')
              .toList()
          : <Map<String, dynamic>>[];
      rows.sort((a, b) =>
          ((a['starts_at'] as num?) ?? 0).compareTo((b['starts_at'] as num?) ?? 0));
      if (!mounted) return;
      setState(() => _todayBookings = rows);
      final operators = await _api.fetchOperators();
      if (operators != null && mounted) {
        setState(() => _operatorNames = {for (final o in operators) o.id: o.name});
      }
    } on DioException {
      if (mounted) setState(() => _todayBookings = const []);
    }
  }

  /// One tap: `PATCH /api/v1/bookings/{id}/attend` creates the real visit server-side directly
  /// from what the booking already decided (customer, services, operator) — genuinely faster than
  /// opening the visit form, not merely a shortcut to it.
  Future<void> _attendBooking(Map<String, dynamic> booking) async {
    final id = booking['id'] as String? ?? '';
    if (id.isEmpty || _busyBookingId.isNotEmpty) return;
    HapticFeedback.selectionClick();
    setState(() => _busyBookingId = id);
    try {
      final response = await _api.apiClient.dio.patch<dynamic>(
        '/api/v1/bookings/${Uri.encodeComponent(id)}/attend',
        data: {'occurred_at': DateTime.now().millisecondsSinceEpoch ~/ 1000},
      );
      if (!mounted) return;
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) {
        HapticFeedback.mediumImpact();
        setState(() {
          _todayBookings = _todayBookings!.where((b) => b['id'] != id).toList();
          _busyBookingId = '';
        });
      } else {
        setState(() {
          _busyBookingId = '';
          _saveError = S.of(context)!.visitBookingAttendFailed;
        });
      }
    } on DioException {
      if (!mounted) return;
      setState(() {
        _busyBookingId = '';
        _saveError = S.of(context)!.visitBookingAttendFailed;
      });
    }
  }

  // ── Phone: as-you-type suggestions, then a self-resolving exact lookup ────

  void _onPhoneChanged(String raw) {
    final phone = raw.trim();
    // The number changed — whatever we knew about the last one no longer applies.
    if (_lookedUp || _customerName != null) {
      setState(() {
        _lookedUp = false;
        _customerName = null;
      });
    }
    _clearLoyaltyAndOffer();
    _suggestDebounce?.cancel();
    _exactDebounce?.cancel();

    if (phone.length < 3) {
      setState(() => _suggestions = []);
      return;
    }
    // SUGGESTIONS, while he is still typing — search-service's own prefix match.
    _suggestDebounce = Timer(const Duration(milliseconds: 180), () => _fetchSuggestions(phone));

    // THE NUMBER RESOLVED ITSELF the moment it became a real one — no button to press.
    if (Validators.validatePhone(phone) == null) {
      _exactDebounce = Timer(const Duration(milliseconds: 180), () => _lookupExact(phone));
    }
  }

  Future<void> _fetchSuggestions(String prefix) async {
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/suggest',
        queryParameters: {'prefix': prefix},
      );
      if (!mounted || _phoneController.text.trim() != prefix) return;
      final body = response.data;
      final rows = body is Map<String, dynamic>
          ? (body['customers'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .toList()
          : <Map<String, dynamic>>[];
      setState(() => _suggestions = rows);
    } on DioException {
      // A FAILED SUGGESTION MUST NEVER BLOCK ENTRY — he can still type the whole number and
      // save; a missing suggestion costs a second, a blocked screen costs the visit.
      if (mounted) setState(() => _suggestions = []);
    }
  }

  /// Pick a suggested customer directly — the suggestion already carries the name, so this
  /// skips a second round trip that `_lookupExact` would otherwise make for the same number.
  void _pickSuggestion(Map<String, dynamic> customer) {
    final phone = customer['phone'] as String? ?? '';
    if (phone.isEmpty) return;
    HapticFeedback.selectionClick();
    _suggestDebounce?.cancel();
    _exactDebounce?.cancel();
    _phoneController.value = TextEditingValue(
      text: phone,
      selection: TextSelection.collapsed(offset: phone.length),
    );
    final foundName = customer['name'] as String?;
    setState(() {
      _suggestions = [];
      _customerName = foundName;
      _lookedUp = true;
      _lookingUp = false;
      if (foundName != null && foundName.isNotEmpty) _nameController.text = foundName;
    });
    // THE SUGGESTION ROW HAS NO `subject_ref` (search-service's own `suggest`/`search` answer
    // names/phones only) — a quiet, un-flagged re-lookup fetches it purely for the loyalty/offer
    // preview below; `_lookedUp`/`_customerName` are already correct from the row above, so this
    // never re-flickers the "known customer" badge the way surfacing `_lookingUp` here would.
    unawaited(_lookupExact(phone, silent: true));
  }

  Future<void> _lookupExact(String phone, {bool silent = false}) async {
    if (!silent) {
      setState(() {
        _lookingUp = true;
        _lookedUp = false;
        _customerName = null;
        _suggestions = [];
      });
    }
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/by-phone',
        queryParameters: {'phone': phone},
      );
      if (!mounted || _phoneController.text.trim() != phone) return;
      final body = response.data;
      final customer = body is Map<String, dynamic> ? body['customer'] : null;
      final subjectRef = customer is Map<String, dynamic> ? customer['subject_ref'] as String? : null;
      if (!silent) {
        final foundName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
        setState(() {
          _customerName = foundName;
          _lookedUp = true;
          _lookingUp = false;
          if (foundName != null && foundName.isNotEmpty) _nameController.text = foundName;
        });
      }
      if (subjectRef != null && subjectRef.isNotEmpty) {
        unawaited(_loadLoyaltyAndOffer(subjectRef));
      }
    } on DioException {
      if (!mounted || silent) return;
      setState(() {
        _lookingUp = false;
        _lookedUp = false;
      });
    }
  }

  // ── Plate: format-as-you-type, then a self-resolving lookup — same shape as the phone field
  // above, GET /api/v1/field/customers/by-plate (the exact route apps/console/src/api.ts's own
  // `customerByPlate` calls) so a returning car is recognised the same way a returning number
  // already is. NEVER the reverse of the phone flow's UX depth just because this field is newer.

  void _onPlateChanged(String raw) {
    final formatted = Formatters.formatPlate(raw);
    if (formatted != raw) {
      _plateController.value = TextEditingValue(
        text: formatted,
        selection: TextSelection.collapsed(offset: formatted.length),
      );
    }
    if (_plateLookedUp || _vehicleCustomerName != null) {
      setState(() {
        _plateLookedUp = false;
        _vehicleCustomerName = null;
      });
    }
    _clearLoyaltyAndOffer();
    _plateSuggestDebounce?.cancel();
    _plateLookupDebounce?.cancel();
    final plate = formatted.trim();
    // TWO CHARACTERS ARE ENOUGH TO NARROW A YARD — same threshold `Visit.tsx`'s own plate
    // suggestions use; an operator reading four characters off a bumper should not have to type
    // the whole plate before a car we already know starts showing up.
    if (plate.length < 2) {
      setState(() => _plateSuggestions = []);
    } else {
      _plateSuggestDebounce =
          Timer(const Duration(milliseconds: 250), () => _fetchPlateSuggestions(plate));
    }
    if (plate.length < 3) return;
    _plateLookupDebounce = Timer(const Duration(milliseconds: 220), () => _lookupPlate(plate));
  }

  /// Same `/customers/suggest` route the phone field already calls — it indexes plates too (see
  /// `field.py::suggest_customers`'s own row shape) — filtered here to rows that actually carry
  /// one, since the same prefix can just as plausibly match somebody's phone number.
  Future<void> _fetchPlateSuggestions(String prefix) async {
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/suggest',
        queryParameters: {'prefix': prefix},
      );
      if (!mounted || _plateController.text.trim() != prefix) return;
      final body = response.data;
      final rows = body is Map<String, dynamic>
          ? (body['customers'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .where((c) => (c['plate'] as String?)?.isNotEmpty == true)
              .take(4)
              .toList()
          : <Map<String, dynamic>>[];
      setState(() => _plateSuggestions = rows);
    } on DioException {
      if (mounted) setState(() => _plateSuggestions = []);
    }
  }

  /// Pick a plate suggestion directly — fills both the plate and, when the row carries one, the
  /// phone/name too, same one-tap shortcut the phone field's own suggestions already give.
  void _pickPlateSuggestion(Map<String, dynamic> hit) {
    final plate = hit['plate'] as String? ?? '';
    if (plate.isEmpty) return;
    HapticFeedback.selectionClick();
    _plateSuggestDebounce?.cancel();
    _plateLookupDebounce?.cancel();
    final formatted = Formatters.formatPlate(plate);
    _plateController.value =
        TextEditingValue(text: formatted, selection: TextSelection.collapsed(offset: formatted.length));
    final phone = hit['phone'] as String? ?? '';
    final foundName = hit['name'] as String?;
    setState(() {
      _plateSuggestions = [];
      _vehicleCustomerName = foundName;
      _plateLookedUp = true;
      _lookingUpPlate = false;
      if (phone.isNotEmpty) _phoneController.text = phone;
      if (foundName != null && foundName.isNotEmpty) _nameController.text = foundName;
    });
    if (phone.isNotEmpty) unawaited(_lookupExact(phone, silent: true));
  }

  Future<void> _lookupPlate(String plate) async {
    setState(() => _lookingUpPlate = true);
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/by-plate',
        queryParameters: {'plate': plate},
      );
      if (!mounted || _plateController.text.trim() != plate) return;
      final body = response.data;
      final customer = body is Map<String, dynamic> ? body['customer'] : null;
      final subjectRef = customer is Map<String, dynamic> ? customer['subject_ref'] as String? : null;
      final foundName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
      setState(() {
        _vehicleCustomerName = foundName;
        _plateLookedUp = true;
        _lookingUpPlate = false;
        if (foundName != null && foundName.isNotEmpty) _nameController.text = foundName;
      });
      if (subjectRef != null && subjectRef.isNotEmpty) {
        unawaited(_loadLoyaltyAndOffer(subjectRef));
      }
    } on DioException {
      // SAME RULE AS THE PHONE LOOKUP ABOVE — a failed lookup never blocks entry.
      if (!mounted) return;
      setState(() {
        _lookingUpPlate = false;
        _plateLookedUp = false;
      });
    }
  }

  // ── Loyalty balance + offer preview — fired once a real `subject_ref` is known, from EITHER
  // identification path (phone or plate). Never blocks entry, same "advisory, not a spend"
  // posture the by-phone route's own `points_balance` field already takes server-side.

  void _clearLoyaltyAndOffer() {
    if (_subjectRef == null && _loyaltyPoints == null && _offerText == null) return;
    setState(() {
      _subjectRef = null;
      _loyaltyPoints = null;
      _loyaltyToNextReward = 0;
      _loyaltyRewards = [];
      _offerText = null;
      _offerValue = null;
    });
  }

  Future<void> _loadLoyaltyAndOffer(String subjectRef) async {
    setState(() => _subjectRef = subjectRef);
    final results = await Future.wait([
      _api.apiClient.dio
          .get<dynamic>('/api/v1/loyalty/balance/${Uri.encodeComponent(subjectRef)}')
          .then<dynamic>((r) => r.data)
          .catchError((_) => null),
      _api.apiClient.dio
          .get<dynamic>('/api/v1/reminders/offer', queryParameters: {'subject_ref': subjectRef})
          .then<dynamic>((r) => r.data)
          .catchError((_) => null),
    ]);
    // THE IDENTITY MAY HAVE MOVED ON WHILE THIS WAS IN FLIGHT — an operator who typed a second
    // number before the first customer's balance came back must never see it attached to the
    // wrong person.
    if (!mounted || _subjectRef != subjectRef) return;

    final balance = results[0];
    if (balance is Map<String, dynamic>) {
      final rewards = (balance['rewards'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .toList();
      setState(() {
        _loyaltyPoints = (balance['points'] as num?)?.toInt();
        _loyaltyToNextReward = (balance['to_next_reward'] as num?)?.toInt() ?? 0;
        _loyaltyRewards = rewards;
      });
    }

    final offerBody = results[1];
    final offer = offerBody is Map<String, dynamic> ? offerBody['offer'] : null;
    if (offer is Map<String, dynamic>) {
      setState(() {
        _offerText = offer['text'] as String?;
        _offerValue = offer['value'] as String?;
      });
    }
  }

  /// «استبدال النقاط» — the ONE tap that actually spends a reward, `POST /api/v1/loyalty/redeem`
  /// (`apps/console/src/api.ts`'s own `redeem`, same body shape: subject_ref/reward_id/
  /// idempotency_key). A fresh idempotency key is minted AT THE PRESS, never inside the request —
  /// same discipline `api.ts`'s own doc comment on that function states, so a retry of the same
  /// press never spends twice. Never blocks entry or the visit save — a failed redeem just shows
  /// the server's own real reason inline.
  Future<void> _redeemReward(Map<String, dynamic> reward) async {
    final subjectRef = _subjectRef;
    if (subjectRef == null || _redeemingRewardId.isNotEmpty) return;
    final rewardId = reward['id'] as String? ?? '';
    final rewardName = reward['name'] as String? ?? '';
    if (rewardId.isEmpty) return;
    setState(() {
      _redeemingRewardId = rewardId;
      _redeemedRewardName = null;
    });
    try {
      final response = await _api.apiClient.dio.post<dynamic>(
        '/api/v1/loyalty/redeem',
        data: {
          'subject_ref': subjectRef,
          'reward_id': rewardId,
          'idempotency_key': DateTime.now().microsecondsSinceEpoch.toString(),
        },
      );
      if (!mounted) return;
      // Same non-throwing-4xx trap every write in this app now guards against — success is a
      // real 2xx status, never merely "the call did not throw".
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) {
        HapticFeedback.mediumImpact();
        // THE COUNTER'S OWN CELEBRATION MOMENT — `celebrate`, never `pointsEarned`: this is a
        // SPEND (points went down), so a rising "+N" here would read backwards to whoever is
        // watching over the operator's shoulder. Fired on THIS context, before the reward row
        // itself rebuilds under the coming setState, so the burst centres on the screen the
        // operator is actually looking at right now.
        if (mounted) GameEffects.celebrate(context);
        setState(() {
          _redeemedRewardName = rewardName;
          _redeemingRewardId = '';
        });
        // THE BALANCE JUST CHANGED — re-read it for real rather than guess the new number
        // client-side; also refreshes which rewards are still affordable.
        unawaited(_loadLoyaltyAndOffer(subjectRef));
      } else {
        final body = response.data;
        final message = body is Map ? body['message'] as String? : null;
        setState(() {
          _redeemingRewardId = '';
          _saveError = message ?? S.of(context)!.visitPointsRedeemFailed;
        });
      }
    } on DioException {
      if (!mounted) return;
      setState(() {
        _redeemingRewardId = '';
        _saveError = S.of(context)!.visitPointsRedeemFailed;
      });
    }
  }

  /// «تطبيق العرض» — fired only AFTER the visit itself is safely recorded (the real visit id
  /// `_save`'s own success response carries), never alongside it — the same race `Visit.tsx`'s own
  /// `commit` comment documents avoiding. Fire-and-forget, same posture console's queue-deferred
  /// apply takes: the visit already saved successfully regardless of whether this follow-up call
  /// succeeds, so nothing here can undo or block that.
  Future<void> _applyOffer(String visitId, String subjectRef) async {
    try {
      await _api.apiClient.dio.post<dynamic>(
        '/api/v1/field/visits/${Uri.encodeComponent(visitId)}/offer',
        data: {'subject_ref': subjectRef},
      );
    } on DioException {
      // Never surfaced — the visit is already saved; a failed offer-apply is not a failed visit.
    }
  }

  // ── Services ──────────────────────────────────────────────────────────────

  void _toggleService(String serviceId) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_selected.containsKey(serviceId)) {
        _selected.remove(serviceId);
      } else {
        _selected[serviceId] = 1;
      }
      _clearPackageIfIncomplete();
    });
  }

  /// A package attribution must never travel with an INCOMPLETE set of its own member services —
  /// `package_id` tells the server "price this visit as the package", so a package badge left on
  /// after the operator manually dropped one of its two services would misprice the visit at the
  /// bundle's price for work that was not actually the bundle. Deselecting the package tag itself
  /// never touches which services stay chosen — only ever the reverse.
  void _clearPackageIfIncomplete() {
    final id = _selectedPackageId;
    if (id == null) return;
    final pkg = _packages.cast<Map<String, dynamic>?>().firstWhere((p) => p?['id'] == id, orElse: () => null);
    final memberIds = ((pkg?['service_ids'] as List?) ?? const []).map((e) => e.toString());
    if (!memberIds.every(_selected.containsKey)) {
      _selectedPackageId = null;
    }
  }

  void _changeQuantity(String serviceId, int delta) {
    HapticFeedback.selectionClick();
    setState(() {
      final current = _selected[serviceId] ?? 1;
      final next = (current + delta).clamp(1, 20);
      _selected[serviceId] = next;
    });
  }

  /// A typed quantity, not just +/- taps — an operator selling "12× غسيل" types the number once
  /// instead of tapping the stepper eleven times. Same 1–20 ceiling `_changeQuantity` already
  /// enforces server-side (`check_quantities`'s own per-line cap).
  void _setQuantity(String serviceId, int value) {
    HapticFeedback.selectionClick();
    setState(() => _selected[serviceId] = value.clamp(1, 20));
  }

  Future<void> _promptQuantity(BuildContext context, String serviceId, int current) async {
    final s = S.of(context)!;
    final controller = TextEditingController(text: '$current');
    final value = await showDialog<int>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.visitQuantityDialogTitle),
        content: KbAnchor(
          id: 'visit.quantity_dialog_field',
          child: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: TextInputType.number,
          textAlign: TextAlign.center,
          textDirection: TextDirection.ltr,
          style: AppTextStyles.displaySmall,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
          TextButton(
            onPressed: () =>
                Navigator.of(dialogContext).pop(int.tryParse(controller.text.trim())),
            child: Text(s.servicesSave),
          ),
        ],
      ),
    );
    if (value != null && value > 0) _setQuantity(serviceId, value);
  }

  /// One tap adds every member service of the package at quantity 1; tapping the SAME package
  /// again undoes exactly what it added — never anything the operator separately chose by hand.
  /// Mirrors `Visit.tsx`'s own `selectPackage` exactly: a visit sells one package at a time, so
  /// picking a second one first steps the previous one aside.
  void _selectPackage(Map<String, dynamic> pkg) {
    HapticFeedback.selectionClick();
    final id = pkg['id'] as String? ?? '';
    if (id.isEmpty) return;
    final memberIds = ((pkg['service_ids'] as List?) ?? const [])
        .map((e) => e.toString())
        .toList(growable: false);
    setState(() {
      if (_selectedPackageId == id) {
        for (final sid in memberIds) {
          _selected.remove(sid);
        }
        _selectedPackageId = null;
        return;
      }
      if (_selectedPackageId != null) {
        final previous = _packages.cast<Map<String, dynamic>?>().firstWhere(
            (p) => p?['id'] == _selectedPackageId,
            orElse: () => null);
        final previousIds = ((previous?['service_ids'] as List?) ?? const [])
            .map((e) => e.toString());
        for (final sid in previousIds) {
          _selected.remove(sid);
        }
      }
      for (final sid in memberIds) {
        _selected[sid] = 1;
      }
      _selectedPackageId = id;
    });
  }

  // ── Save ──────────────────────────────────────────────────────────────────

  /// PLAUSIBLE, NOT THE SAUDI FORMAT — matches `_canSave`/`_save`'s own client-side mirror of
  /// `core/plate.py::is_plausible` exactly: one letter and one digit, in any script.
  bool get _plateOk => !_tracksVehicle || Formatters.isPlatePlausible(_plateController.text);

  bool get _canSave =>
      _phoneController.text.trim().length >= 3 && _selected.isNotEmpty && _plateOk && !_saving;

  Future<void> _save() async {
    final phone = _phoneController.text.trim();
    final plate = _plateController.text.trim();
    if (phone.length < 3 || _selected.isEmpty || !_plateOk) {
      HapticFeedback.heavyImpact();
      setState(() {
        _saveError = phone.length < 3
            ? S.of(context)!.visitEnterCustomerPhone
            : (!_plateOk
                ? S.of(context)!.visitPlateRequired
                : S.of(context)!.visitSelectAtLeastOneService);
      });
      return;
    }
    setState(() {
      _saving = true;
      _saveError = null;
    });
    try {
      final name = _nameController.text.trim();
      final meter = _meterController.text.trim();
      final response = await _api.apiClient.dio.post<dynamic>(
        '/api/v1/field/visits',
        data: {
          'phone': phone,
          if (_tracksVehicle) 'plate': plate,
          if (name.isNotEmpty) 'name': name,
          if (_tracksVehicle && meter.isNotEmpty) 'meter': int.tryParse(meter),
          'service_ids': _selected.keys.toList(),
          'quantities': _selected,
          if (_selectedPackageId != null) 'package_id': _selectedPackageId,
          'note': _noteController.text.trim(),
          if (_couponOn && _couponPhoneController.text.trim().isNotEmpty) ...{
            'coupon_phone': _couponPhoneController.text.trim(),
            'coupon_percent': _couponPercent,
            // GENERAL ONLY — this pass's own scope decision, see this file's own header comment
            // on `_couponScreenEnabled` for why there is no per-app picker yet.
            'coupon_general': true,
          },
          'idempotency_key': DateTime.now().microsecondsSinceEpoch.toString(),
          'occurred_at': DateTime.now().millisecondsSinceEpoch ~/ 1000,
        },
      );
      final body = response.data;
      final bodyMap = body is Map<String, dynamic> ? body : null;
      final recorded = bodyMap == null ? true : bodyMap['recorded'] != false;
      if (!mounted) return;
      if (recorded) {
        HapticFeedback.mediumImpact();
        // CAPTURED BEFORE THE CLEAR BELOW WIPES THEM — the offer applies to THIS visit, using the
        // subject/visit id this exact save just produced, never whatever the screen holds after.
        final visitIdForOffer = _applyingOffer && _subjectRef != null
            ? (bodyMap?['visit'] is Map ? (bodyMap!['visit']['id'] as String?) : null)
            : null;
        final subjectRefForOffer = _subjectRef;
        setState(() {
          _saving = false;
          _justSaved = true;
          _selected.clear();
          _selectedPackageId = null;
          _phoneController.clear();
          _noteController.clear();
          _plateController.clear();
          _nameController.clear();
          _meterController.clear();
          _couponOn = false;
          _couponPhoneController.clear();
          _couponPercent = 10;
          _couponPercentController.text = '10';
          _noteOpen = false;
          _lookedUp = false;
          _customerName = null;
          _suggestions = [];
          _plateLookedUp = false;
          _vehicleCustomerName = null;
          _plateSuggestions = [];
          _subjectRef = null;
          _loyaltyPoints = null;
          _loyaltyToNextReward = 0;
          _loyaltyRewards = [];
          _offerText = null;
          _offerValue = null;
          _applyingOffer = false;
          _redeemedRewardName = null;
        });
        if (visitIdForOffer != null && visitIdForOffer.isNotEmpty && subjectRefForOffer != null) {
          unawaited(_applyOffer(visitIdForOffer, subjectRefForOffer));
        }
        // READY FOR THE NEXT CUSTOMER — the whole point of the redesign. The keyboard comes
        // straight back up on the now-empty phone field, exactly as it was when he first landed.
        _phoneFocus.requestFocus();
        Timer(const Duration(milliseconds: 1400), () {
          if (mounted) setState(() => _justSaved = false);
        });
      } else {
        final reason = bodyMap['reason'] as String?;
        HapticFeedback.heavyImpact();
        setState(() {
          _saving = false;
          _saveError = reason ?? S.of(context)!.visitSaveErrorFallback;
        });
      }
    } on DioException {
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      setState(() {
        _saving = false;
        _saveError = S.of(context)!.visitSaveErrorNetworkFallback;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return KbAnchor(
      id: 'visit.register',
      child: Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(
        title: Text(S.of(context)!.visitTitle),
      ),
      body: Stack(
        children: [
          _loadingCatalogue
              ? const Center(child: CircularProgressIndicator())
              : _catalogueError != null
                  ? _RetryBody(message: _catalogueError!, onRetry: _loadCatalogue)
                  : AnimatedBuilder(
                      animation: _entryController,
                      builder: (context, _) {
                        final anim = CurvedAnimation(
                          parent: _entryController,
                          curve: Curves.easeOut,
                        ).value;
                        return Opacity(
                          opacity: anim,
                          child: Transform.translate(
                            offset: Offset(0, 16 * (1 - anim)),
                            child: _buildForm(),
                          ),
                        );
                      },
                    ),
          _buildSavedBanner(),
        ],
      ),
      ),
    );
  }

  Widget _buildForm() {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.md),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_todayBookings != null && _todayBookings!.isNotEmpty) ...[
                  _buildTodayBookings(),
                  const SizedBox(height: AppSpacing.lg),
                ],
                if (_tracksVehicle) ...[
                  _buildPlateCard(),
                  const SizedBox(height: AppSpacing.lg),
                ],
                _buildPhoneCard(),
                _buildLoyaltyAndOfferSection(),
                const SizedBox(height: AppSpacing.lg),
                if (_packages.isNotEmpty) ...[
                  _buildPackagesRail(),
                  const SizedBox(height: AppSpacing.lg),
                ],
                _buildServicesGrid(),
                const SizedBox(height: AppSpacing.md),
                _buildNameAndMeterFields(),
                if (_couponScreenEnabled == true) ...[
                  const SizedBox(height: AppSpacing.md),
                  _buildCouponSection(),
                ],
                const SizedBox(height: AppSpacing.md),
                _buildNoteToggle(),
                if (_saveError != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: [
                      const Icon(Icons.error_outline_rounded, size: 16, color: AppColors.danger),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(
                        child: Text(
                          _saveError!,
                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger),
                        ),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: AppSpacing.xxl),
              ],
            ),
          ),
        ),
        _buildBottomBar(),
      ],
    );
  }

  // ── Today's known appointments — a real fact this operator can act on before the customer
  // even opens his mouth: he already knows who is coming and when. First on screen, ahead of
  // everything else, because recognising a face at the door beats typing a number every time.

  Widget _buildTodayBookings() {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final rows = _todayBookings!.take(6).toList();
    return KbAnchor(
      id: 'visit.register.today_bookings',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: context.isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(
              color: (context.isDark ? AppDarkColors.info : AppColors.info).withValues(alpha: 0.25)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.event_available_rounded,
                    size: 16, color: context.isDark ? AppDarkColors.info : AppColors.info),
                const SizedBox(width: AppSpacing.xs),
                Text(s.visitTodayBookingsTitle,
                    style: AppTextStyles.labelMedium.copyWith(
                        color: context.isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft,
                        fontWeight: FontWeight.w800)),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final b in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: _TodayBookingRow(
                  timeLabel: Formatters.formatTime(
                      DateTime.fromMillisecondsSinceEpoch(((b['starts_at'] as num?) ?? 0).toInt() * 1000),
                      locale: locale),
                  operatorName: _operatorNames[b['operator_id'] as String? ?? ''] ?? '',
                  serviceNames: ((b['service_ids'] as List?) ?? const [])
                      .map((id) => _services
                          .cast<Map<String, dynamic>?>()
                          .firstWhere((svc) => svc?['id'] == id, orElse: () => null)?['name'] as String?)
                      .whereType<String>()
                      .join(' + '),
                  busy: _busyBookingId == b['id'],
                  onAttend: () => _attendBooking(b),
                ),
              ),
          ],
        ),
      ),
    );
  }

  // ── Plate — shown ONLY when `_tracksVehicle` (this shop's own «حسابي» setting), and FIRST,
  // above the phone — «بنشر، مغسلة وتنجيد: العميل هو السيارة» (spec 4.3, the same ordering
  // console's own Visit.tsx already commits to: "THE ORDER IS THE CUSTOMER FIRST: plate → who").
  // A real plate chip (the formatted text in a bordered, letter-spaced strip that reads like an
  // actual plate) rather than a plain text field — the "فخم" the owner asked for is exactly this:
  // the field looks like the object it represents, not a generic input box with a label on top.

  Widget _buildPlateCard() {
    final formatted = Formatters.formatPlate(_plateController.text);
    final showError = !_plateOk && formatted.isNotEmpty;
    return KbAnchor(
      id: 'visit.register.plate_field',
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: AppCardDecorations.elevated,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.directions_car_filled_rounded, size: 16, color: AppColors.textSecondary),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  S.of(context)!.visitPlateFieldLabel,
                  style: AppTextStyles.labelMedium.copyWith(
                    color: AppColors.textSecondary,
                    letterSpacing: 0.2,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            // THE PLATE CHIP — a real number-plate silhouette: a bordered, near-white strip with
            // wide-tracked bold text, so a glance recognises "this is the plate field" before he
            // even reads the label, exactly like the physical object clipped to the car outside.
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.surface0,
                borderRadius: AppRadius.standardRadius,
                border: Border.all(
                  color: showError ? AppColors.danger : AppColors.borderStrong,
                  width: showError ? 1.5 : 1.5,
                ),
              ),
              child: TextField(
                controller: _plateController,
                focusNode: _plateFocus,
                textAlign: TextAlign.center,
                textDirection: TextDirection.ltr,
                textCapitalization: TextCapitalization.characters,
                style: AppTextStyles.displaySmall.copyWith(
                  fontSize: 26,
                  letterSpacing: 4,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
                onChanged: _onPlateChanged,
                decoration: InputDecoration(
                  hintText: '1234 ABC',
                  hintStyle: AppTextStyles.displaySmall.copyWith(
                    fontSize: 26,
                    letterSpacing: 4,
                    color: AppColors.textMuted,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                  suffixIcon: _lookingUpPlate
                      ? const Padding(
                          padding: EdgeInsets.all(8),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accent),
                          ),
                        )
                      : null,
                ),
              ),
            ),
            AnimatedSize(
              duration: AppMotion.base,
              curve: Curves.easeOut,
              alignment: Alignment.topCenter,
              child: showError
                  ? Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.sm),
                      child: Text(
                        S.of(context)!.visitPlateRequired,
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger),
                      ),
                    )
                  : (_plateSuggestions.isNotEmpty
                      ? _buildPlateSuggestions()
                      : (_plateLookedUp ? _buildVehicleBadge() : const SizedBox(width: double.infinity))),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVehicleBadge() {
    final known = _vehicleCustomerName != null && _vehicleCustomerName!.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: AppSpacing.xs),
        decoration: BoxDecoration(
          color: known ? AppColors.successSoft : AppColors.infoSoft,
          borderRadius: BorderRadius.circular(AppRadius.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              known ? Icons.badge_rounded : Icons.directions_car_outlined,
              size: 16,
              color: known ? AppColors.success : AppColors.info,
            ),
            const SizedBox(width: AppSpacing.xs),
            Text(
              known ? S.of(context)!.visitKnownVehicle(_vehicleCustomerName!) : S.of(context)!.visitNewVehicle,
              style: AppTextStyles.bodySmall.copyWith(
                color: known ? AppColors.successOnSoft : AppColors.infoOnSoft,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// A car he read four characters off a bumper — finishing the plate by hand when we already
  /// hold it is work we can do for him, and one tap fills the owner too. Mirrors the phone
  /// field's own suggestion list, car-toned instead of person-toned.
  Widget _buildPlateSuggestions() {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: Column(
        children: [
          for (final hit in _plateSuggestions)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Material(
                color: AppColors.surface2,
                borderRadius: AppRadius.standardRadius,
                child: InkWell(
                  borderRadius: AppRadius.standardRadius,
                  onTap: () => _pickPlateSuggestion(hit),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                    child: Row(
                      children: [
                        Container(
                          width: 30,
                          height: 30,
                          alignment: Alignment.center,
                          decoration: const BoxDecoration(
                            color: AppColors.infoSoft,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.directions_car_rounded, size: 16, color: AppColors.info),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Text(
                          Formatters.formatPlate(hit['plate'] as String? ?? ''),
                          textDirection: TextDirection.ltr,
                          style: AppTextStyles.bodyMedium.copyWith(
                              fontWeight: FontWeight.w700, fontFeatures: const [FontFeature.tabularFigures()]),
                        ),
                        const Spacer(),
                        Text(
                          (hit['name'] as String?)?.isNotEmpty == true ? hit['name'] as String : '—',
                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // ── Loyalty + offer — the "فخم" surface the owner asked for by name: the moment a real
  // customer is identified, his own points and any live offer appear as premium, animated cards,
  // never a plain row of numbers. `AnimatedSize` so the layout never jumps when either arrives
  // (balance and offer resolve independently, at different speeds).

  Widget _buildLoyaltyAndOfferSection() {
    final hasOffer = _offerText != null && _offerText!.isNotEmpty;
    final hasBalance = _loyaltyPoints != null;
    if (!hasOffer && !hasBalance) return const SizedBox.shrink();
    return AnimatedSize(
      duration: AppMotion.slow,
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: const EdgeInsets.only(top: AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (hasOffer) ...[
              KbAnchor(
                id: 'visit.register.offer_apply_toggle',
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.xs),
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color(0xFF9C6B0F), Color(0xFFD4AF37), Color(0xFFF0D98C)],
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                    ),
                    borderRadius: BorderRadius.only(
                      bottomLeft: Radius.circular(AppRadius.card),
                      bottomRight: Radius.circular(AppRadius.card),
                    ),
                  ),
                  margin: const EdgeInsets.only(top: -1),
                  child: Column(
                    children: [
                      ActiveOfferApplyToggle(
                        applying: _applyingOffer,
                        onChanged: (v) => setState(() => _applyingOffer = v),
                        label: S.of(context)!.visitOfferApplyLabel,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              ActiveOfferBanner(text: _offerText!, value: _offerValue),
              if (hasBalance) const SizedBox(height: AppSpacing.md),
            ],
            if (hasBalance) ...[
              LoyaltyBalanceCard(
                points: _loyaltyPoints!,
                toNextReward: _loyaltyToNextReward,
                rewards: _loyaltyRewards,
              ),
              _buildRedeemableRewards(),
            ],
          ],
        ),
      ),
    );
  }

  /// The REAL, tappable rewards list — `LoyaltyBalanceCard` above only shows up to two as a
  /// decorative preview; this is the full, actionable list, one tap per reward spends it
  /// immediately (`_redeemReward`). Mirrors `Visit.tsx`'s own `<ul>` under the points panel.
  Widget _buildRedeemableRewards() {
    if (_loyaltyRewards.isEmpty) return const SizedBox.shrink();
    final s = S.of(context)!;
    return KbAnchor(
      id: 'visit.register.redeem_rewards',
      child: Padding(
        padding: const EdgeInsets.only(top: AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_redeemedRewardName != null)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle_rounded, size: 16, color: AppColors.success),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        s.visitPointsRedeemedMessage(_redeemedRewardName!),
                        style: AppTextStyles.bodySmall
                            .copyWith(color: AppColors.success, fontWeight: FontWeight.w700),
                      ),
                    ),
                  ],
                ),
              ),
            for (final r in _loyaltyRewards)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Material(
                  color: AppColors.surface2,
                  borderRadius: AppRadius.standardRadius,
                  child: InkWell(
                    borderRadius: AppRadius.standardRadius,
                    onTap: _redeemingRewardId.isEmpty ? () => _redeemReward(r) : null,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                      child: Row(
                        children: [
                          const Icon(Icons.redeem_rounded, size: 16, color: AppColors.accent),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Text('${r['name'] ?? ''}',
                                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600)),
                          ),
                          if (_redeemingRewardId == (r['id'] as String? ?? ''))
                            const SizedBox(
                                width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                          else
                            Text(s.visitPointsRedeemCost((r['cost'] as num?)?.toInt() ?? 0),
                                style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  // ── Phone — one floating, elevated module: field, suggestions, and the
  //    resolved-customer state all live inside it, so the eye never has to
  //    jump between separate boxes while he is mid-lookup. ────────────────

  Widget _buildPhoneCard() {
    return KbAnchor(
      id: 'visit.register.phone_field',
      child: Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: AppCardDecorations.elevated,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            S.of(context)!.visitCustomerPhoneFieldLabel,
            style: AppTextStyles.labelMedium.copyWith(
              color: AppColors.textSecondary,
              letterSpacing: 0.2,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          TextField(
            controller: _phoneController,
            focusNode: _phoneFocus,
            keyboardType: TextInputType.phone,
            textDirection: TextDirection.ltr,
            style: AppTextStyles.displaySmall.copyWith(fontSize: 28, letterSpacing: 0.5),
            onChanged: _onPhoneChanged,
            decoration: InputDecoration(
              hintText: '05xxxxxxxx',
              hintStyle: AppTextStyles.displaySmall.copyWith(fontSize: 28, color: AppColors.textMuted),
              border: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.zero,
              suffixIcon: _lookingUp
                  ? const Padding(
                      padding: EdgeInsets.all(8),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accent),
                      ),
                    )
                  : null,
            ),
          ),
          AnimatedSize(
            duration: AppMotion.base,
            curve: Curves.easeOut,
            alignment: Alignment.topCenter,
            child: _suggestions.isNotEmpty
                ? _buildSuggestions()
                : (_lookedUp ? _buildCustomerBadge() : const SizedBox(width: double.infinity)),
          ),
        ],
      ),
      ),
    );
  }

  /// UP TO FOUR, WHILE HE IS STILL TYPING — spec 4.3's own rule (apps/console/src/screens/Visit.tsx):
  /// whoever types five correct digits and sees nothing concludes the customer is new, and
  /// registers him a second time. Takes no height at all once he picks one or finishes the number.
  Widget _buildSuggestions() {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: Column(
        children: [
          for (final c in _suggestions.take(4))
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Material(
                color: AppColors.surface2,
                borderRadius: AppRadius.standardRadius,
                child: InkWell(
                  borderRadius: AppRadius.standardRadius,
                  onTap: () => _pickSuggestion(c),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.md,
                      vertical: AppSpacing.sm,
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 30,
                          height: 30,
                          alignment: Alignment.center,
                          decoration: const BoxDecoration(
                            color: AppColors.accentSoft,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.person_rounded, size: 16, color: AppColors.accent),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Text(
                          (c['name'] as String?)?.isNotEmpty == true ? c['name'] as String : '—',
                          style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600),
                        ),
                        const Spacer(),
                        Text(
                          c['phone'] as String? ?? '',
                          textDirection: TextDirection.ltr,
                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildCustomerBadge() {
    final known = _customerName != null && _customerName!.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: AppSpacing.xs),
        decoration: BoxDecoration(
          color: known ? AppColors.successSoft : AppColors.infoSoft,
          borderRadius: BorderRadius.circular(AppRadius.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              known ? Icons.badge_rounded : Icons.person_add_alt_1_rounded,
              size: 16,
              color: known ? AppColors.success : AppColors.info,
            ),
            const SizedBox(width: AppSpacing.xs),
            Text(
              known ? S.of(context)!.visitKnownCustomer(_customerName!) : S.of(context)!.visitNewCustomer,
              style: AppTextStyles.bodySmall.copyWith(
                color: known ? AppColors.successOnSoft : AppColors.infoOnSoft,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Packages — one tap sells the whole bundle, the same "متجر متعدد الخدمات"
  //    professional shop-catalogue feel the owner asked for: a horizontal rail
  //    of real product cards, never a plain filter chip. ─────────────────────

  Widget _buildPackagesRail() {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'visit.register.packages_rail',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFFBF1DD), Color(0xFFF3E1B8)],
          ),
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: const Color(0xFFE0AA4D).withValues(alpha: 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 24,
                  height: 24,
                  decoration: const BoxDecoration(
                    color: Color(0xFFB7862B),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.workspace_premium_rounded, size: 14, color: Colors.white),
                ),
                const SizedBox(width: AppSpacing.xs),
                Text(s.visitPackagesSectionTitle,
                    style: AppTextStyles.labelMedium
                        .copyWith(color: const Color(0xFF7A5A17), fontWeight: FontWeight.w800)),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            SizedBox(
              height: 132,
              child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _packages.length,
              separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.sm),
              itemBuilder: (context, i) {
                final pkg = _packages[i];
                final id = pkg['id'] as String? ?? '';
                final memberNames = ((pkg['service_ids'] as List?) ?? const [])
                    .map((sid) => _services.cast<Map<String, dynamic>?>().firstWhere(
                        (svc) => svc?['id'] == sid,
                        orElse: () => null)?['name'] as String?)
                    .whereType<String>()
                    .join(' + ');
                return _PackageCard(
                  name: pkg['name'] as String? ?? '',
                  memberNames: memberNames,
                  priceMinor: (pkg['price_minor'] as num?)?.toInt() ?? 0,
                  hasImage: pkg['has_image'] == true,
                  imageUrl: '/api/v1/field/catalogue/packages/$id/image',
                  selected: _selectedPackageId == id,
                  onTap: () => _selectPackage(pkg),
                );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Services — a real product grid: photo, name, price, points, and a
  //    quantity stepper once selected — never a flat grey chip wall. ───────

  static const List<List<Color>> _serviceTonePalette = [
    [Color(0xFF6D5FE8), Color(0xFF8B7CF6)], // violet
    [Color(0xFF0E8A64), Color(0xFF17B37F)], // emerald
    [Color(0xFFC2622B), Color(0xFFE0823F)], // amber-orange
    [Color(0xFF2F5F8F), Color(0xFF4B84BD)], // ocean blue
    [Color(0xFFB7412F), Color(0xFFDD5C45)], // clay red
    [Color(0xFFA0680A), Color(0xFFC98A1F)], // gold
  ];

  Widget _buildServicesGrid() {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'visit.register.services_grid',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  _selected.isEmpty
                      ? s.visitServicesSectionTitle
                      : s.visitServicesSelectedCount(_selected.length),
                  style: AppTextStyles.labelMedium.copyWith(color: AppColors.textSecondary),
                ),
              ),
              if (_selected.isNotEmpty)
                KbAnchor(
                  id: 'visit.register.clear_all_button',
                  child: TextButton(
                    onPressed: () => setState(() {
                      _selected.clear();
                      _selectedPackageId = null;
                    }),
                    style: TextButton.styleFrom(
                      foregroundColor: AppColors.danger,
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: Text(s.visitClearAllButton, style: AppTextStyles.caption),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (_services.isEmpty)
            Text(s.visitNoServicesYet, style: AppTextStyles.bodySmall)
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: AppSpacing.sm,
                crossAxisSpacing: AppSpacing.sm,
                childAspectRatio: 0.86,
              ),
              itemCount: _services.length,
              itemBuilder: (context, i) {
                final service = _services[i];
                final id = service['id'] as String? ?? '';
                final tone = _serviceTonePalette[i % _serviceTonePalette.length];
                return _ServiceTile(
                  name: service['name'] as String? ?? '',
                  priceMinor: (service['price_minor'] as num?)?.toInt() ?? 0,
                  points: _servicePoints[id],
                  hasImage: service['has_image'] == true,
                  imageUrl: '/api/v1/field/catalogue/services/$id/image',
                  toneGradient: tone,
                  quantity: _selected[id],
                  onTap: () => _toggleService(id),
                  onQuantityChange: (delta) => _changeQuantity(id, delta),
                  onQuantityTap: () => _promptQuantity(context, id, _selected[id] ?? 1),
                );
              },
            ),
        ],
      ),
    );
  }

  // ── Name + meter — always on screen, never behind a second tap; the meter
  //    is asked only where the shop's own «حسابي» setting tracks vehicles. ──

  Widget _buildNameAndMeterFields() {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'visit.register.name_meter_fields',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: _tracksVehicle ? 3 : 1,
            child: TextField(
              controller: _nameController,
              style: AppTextStyles.bodyMedium,
              decoration: InputDecoration(
                filled: true,
                fillColor: AppColors.surface2,
                hintText: s.visitNameFieldHint,
                prefixIcon: const Icon(Icons.badge_outlined, size: 18, color: AppColors.textMuted),
                border: OutlineInputBorder(
                    borderRadius: AppRadius.standardRadius, borderSide: BorderSide.none),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              ),
            ),
          ),
          if (_tracksVehicle) ...[
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              flex: 2,
              child: TextField(
                controller: _meterController,
                keyboardType: TextInputType.number,
                textDirection: TextDirection.ltr,
                style: AppTextStyles.bodyMedium.copyWith(fontFeatures: const [FontFeature.tabularFigures()]),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: AppColors.surface2,
                  hintText: s.visitMeterFieldHint,
                  prefixIcon:
                      const Icon(Icons.speed_rounded, size: 18, color: AppColors.textMuted),
                  border: OutlineInputBorder(
                      borderRadius: AppRadius.standardRadius, borderSide: BorderSide.none),
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ── Coupon — «تحالف استراتيجي»'s own visit-screen shortcut: a discount on another shop's own
  // subscription, riding on this same visit's own save. Collapsed to one checkbox until asked
  // for, same posture the note field already takes — this is a rare act on the busiest screen in
  // the product, never a permanent block of fields in the way of the ordinary five-second visit.

  Widget _buildCouponSection() {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'visit.register.coupon_section',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: (context.isDark ? AppDarkColors.accentSoft : AppColors.accentSoft),
          borderRadius: AppRadius.standardRadius,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => setState(() => _couponOn = !_couponOn),
              borderRadius: AppRadius.standardRadius,
              child: Row(
                children: [
                  Icon(Icons.card_giftcard_rounded,
                      size: 18, color: context.isDark ? AppDarkColors.accent : AppColors.accent),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(s.visitCouponCheckboxLabel,
                        style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
                  ),
                  Switch(
                    value: _couponOn,
                    onChanged: (v) => setState(() => _couponOn = v),
                    activeThumbColor: context.isDark ? AppDarkColors.accent : AppColors.accent,
                  ),
                ],
              ),
            ),
            AnimatedSize(
              duration: AppMotion.base,
              curve: Curves.easeOut,
              alignment: Alignment.topCenter,
              child: !_couponOn
                  ? const SizedBox(width: double.infinity)
                  : Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.sm),
                      child: Row(
                        children: [
                          Expanded(
                            flex: 3,
                            child: TextField(
                              controller: _couponPhoneController,
                              keyboardType: TextInputType.phone,
                              textDirection: TextDirection.ltr,
                              style: AppTextStyles.bodySmall,
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.surface1,
                                hintText: s.visitCouponPhoneHint,
                                isDense: true,
                                border: OutlineInputBorder(
                                    borderRadius: AppRadius.standardRadius, borderSide: BorderSide.none),
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: AppSpacing.sm, vertical: AppSpacing.sm),
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: TextField(
                              controller: _couponPercentController,
                              keyboardType: TextInputType.number,
                              textDirection: TextDirection.ltr,
                              textAlign: TextAlign.center,
                              style: AppTextStyles.bodySmall,
                              onChanged: (v) {
                                final n = int.tryParse(v);
                                if (n != null) _couponPercent = n.clamp(1, 100);
                              },
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.surface1,
                                suffixText: '%',
                                isDense: true,
                                border: OutlineInputBorder(
                                    borderRadius: AppRadius.standardRadius, borderSide: BorderSide.none),
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: AppSpacing.sm, vertical: AppSpacing.sm),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Note — collapsed until asked for ─────────────────────────────────────

  Widget _buildNoteToggle() {
    return KbAnchor(
      id: 'visit.register.note_field',
      child: AnimatedSize(
      duration: AppMotion.base,
      curve: Curves.easeOut,
      alignment: Alignment.topCenter,
      child: _noteOpen
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      S.of(context)!.visitNoteSectionTitle,
                      style: AppTextStyles.labelMedium.copyWith(color: AppColors.textSecondary),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close_rounded, size: 18, color: AppColors.textMuted),
                      onPressed: () => setState(() {
                        _noteOpen = false;
                        _noteController.clear();
                      }),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ),
                TextField(
                  controller: _noteController,
                  maxLines: 2,
                  autofocus: true,
                  style: AppTextStyles.bodyMedium,
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: AppColors.surface2,
                    border: OutlineInputBorder(
                      borderRadius: AppRadius.standardRadius,
                      borderSide: BorderSide.none,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: AppRadius.standardRadius,
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: AppRadius.standardRadius,
                      borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
                    ),
                    contentPadding: const EdgeInsets.all(AppSpacing.md),
                  ),
                ),
              ],
            )
          : Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () => setState(() => _noteOpen = true),
                icon: const Icon(Icons.add_rounded, size: 16),
                label: Text(S.of(context)!.visitNoteSectionTitle),
                style: TextButton.styleFrom(foregroundColor: AppColors.textSecondary),
              ),
            ),
      ),
    );
  }

  // ── Bottom bar ────────────────────────────────────────────────────────────

  Widget _buildBottomBar() {
    return KbAnchor(
      id: 'visit.register.save_button',
      child: Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.md,
        MediaQuery.of(context).padding.bottom + AppSpacing.sm,
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface1,
        border: Border(top: BorderSide(color: AppColors.borderSubtle)),
      ),
      child: SizedBox(
        width: double.infinity,
        height: 56,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: _canSave ? appPrimaryGradient : null,
            color: _canSave ? null : AppColors.surface3,
            borderRadius: AppRadius.cardRadius,
            boxShadow: _canSave
                ? [
                    BoxShadow(
                      color: AppColors.accent.withValues(alpha: 0.30),
                      blurRadius: 20,
                      offset: const Offset(0, 8),
                    ),
                  ]
                : null,
          ),
          child: Material(
            color: Colors.transparent,
            borderRadius: AppRadius.cardRadius,
            child: InkWell(
              borderRadius: AppRadius.cardRadius,
              onTap: _canSave ? _save : null,
              child: Center(
                child: _saving
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accentContrast),
                      )
                    : Text(
                        S.of(context)!.visitSaveButtonLabel,
                        style: AppTextStyles.button.copyWith(
                          fontSize: 16,
                          color: _canSave ? AppColors.accentContrast : AppColors.textMuted,
                        ),
                      ),
              ),
            ),
          ),
        ),
      ),
      ),
    );
  }

  // ── Success confirmation — brief, then gone; never blocks the next entry ──

  Widget _buildSavedBanner() {
    return Positioned(
      top: AppSpacing.md,
      left: AppSpacing.md,
      right: AppSpacing.md,
      child: IgnorePointer(
        child: AnimatedSlide(
          duration: AppMotion.base,
          curve: Curves.easeOut,
          offset: _justSaved ? Offset.zero : const Offset(0, -1.5),
          child: AnimatedOpacity(
            duration: AppMotion.base,
            opacity: _justSaved ? 1 : 0,
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              decoration: BoxDecoration(
                color: AppColors.successSoft,
                borderRadius: AppRadius.cardRadius,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.textPrimary.withValues(alpha: 0.10),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 20),
                  const SizedBox(width: AppSpacing.sm),
                  Text(
                    S.of(context)!.visitSavedMessage,
                    style: AppTextStyles.bodyMedium.copyWith(
                      color: AppColors.successOnSoft,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// One product tile — photo (or a tonal gradient monogram when the service has none), name,
/// price, a points badge when the catalogue earns any, and a quantity stepper that only takes
/// over the footer once selected. The "احترافية" the owner asked for by name: a real catalogue
/// card, never a grey pill with text on it.
class _ServiceTile extends StatelessWidget {
  final String name;
  final int priceMinor;
  final int? points;
  final bool hasImage;
  final String imageUrl;
  final List<Color> toneGradient;
  final int? quantity;
  final VoidCallback onTap;
  final ValueChanged<int> onQuantityChange;
  final VoidCallback onQuantityTap;

  const _ServiceTile({
    required this.name,
    required this.priceMinor,
    required this.points,
    required this.hasImage,
    required this.imageUrl,
    required this.toneGradient,
    required this.quantity,
    required this.onTap,
    required this.onQuantityChange,
    required this.onQuantityTap,
  });

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final selected = quantity != null;
    final tone = toneGradient[0];
    return AnimatedContainer(
      duration: AppMotion.fast,
      curve: Curves.easeOut,
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: selected ? tone : AppColors.borderSubtle, width: selected ? 2 : 1),
        boxShadow: selected
            ? [BoxShadow(color: tone.withValues(alpha: 0.30), blurRadius: 16, offset: const Offset(0, 6))]
            : AppShadows.card,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.cardRadius,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // THE PHOTO STRIP — a real image when the service has one, otherwise a tonal
              // gradient carrying the service's own initial like a real product placeholder,
              // never a bare grey box.
              AspectRatio(
                aspectRatio: 1.6,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (hasImage)
                      _CatalogueImage(path: imageUrl, toneGradient: toneGradient, initial: name)
                    else
                      _ToneMonogram(toneGradient: toneGradient, initial: name),
                    if (selected)
                      Positioned.directional(
                        textDirection: Directionality.of(context),
                        top: 6,
                        end: 6,
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
                          child: const Icon(Icons.check_rounded, size: 14, color: Colors.white),
                        ),
                      ),
                    if (points != null && points! > 0)
                      Positioned.directional(
                        textDirection: Directionality.of(context),
                        top: 6,
                        start: 6,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.45),
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.stars_rounded, size: 11, color: Color(0xFFF6B93B)),
                              const SizedBox(width: 2),
                              Text('$points',
                                  style: AppTextStyles.caption
                                      .copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.sm, 6, AppSpacing.sm, AppSpacing.sm),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              priceMinor > 0
                                  ? Formatters.formatCurrency(priceMinor / 100, locale: locale)
                                  : s.servicesNoPrice,
                              style: AppTextStyles.caption.copyWith(
                                  color: tone, fontWeight: FontWeight.w800),
                            ),
                          ),
                          if (selected)
                            _QuantityStepper(
                              quantity: quantity!,
                              tone: tone,
                              onChange: onQuantityChange,
                              onTapNumber: onQuantityTap,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One appointment, one tap. The check button IS the whole act — no visit form, no confirmation
/// screen; `_attendBooking` records the real visit the instant this is pressed.
class _TodayBookingRow extends StatelessWidget {
  const _TodayBookingRow({
    required this.timeLabel,
    required this.operatorName,
    required this.serviceNames,
    required this.busy,
    required this.onAttend,
  });
  final String timeLabel;
  final String operatorName;
  final String serviceNames;
  final bool busy;
  final VoidCallback onAttend;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final ink = dark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: (dark ? AppDarkColors.info : AppColors.info).withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
            child: Text(timeLabel,
                textDirection: TextDirection.ltr,
                style: AppTextStyles.caption.copyWith(color: ink, fontWeight: FontWeight.w800)),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              [operatorName, if (serviceNames.isNotEmpty) serviceNames]
                  .where((s) => s.isNotEmpty)
                  .join(' · '),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary),
            ),
          ),
          InkWell(
            onTap: busy ? null : onAttend,
            customBorder: const CircleBorder(),
            child: Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: (dark ? AppDarkColors.info : AppColors.info).withValues(alpha: 0.18),
                shape: BoxShape.circle,
              ),
              child: busy
                  ? SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: ink))
                  : Icon(Icons.check_rounded, size: 16, color: ink),
            ),
          ),
        ],
      ),
    );
  }
}

class _ToneMonogram extends StatelessWidget {
  const _ToneMonogram({required this.toneGradient, required this.initial});
  final List<Color> toneGradient;
  final String initial;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: toneGradient,
        ),
      ),
      alignment: Alignment.center,
      child: Text(
        initial.isNotEmpty ? initial.substring(0, 1).toUpperCase() : '?',
        style: AppTextStyles.headlineMedium.copyWith(color: Colors.white.withValues(alpha: 0.9)),
      ),
    );
  }
}

/// Lazy, cached-per-widget-instance fetch of one catalogue photo (service or package) — never
/// requested unless `hasImage` already said one exists, matching the route's own 404-when-absent
/// contract; a tonal monogram covers every frame before the bytes land and on any failure.
class _CatalogueImage extends StatefulWidget {
  const _CatalogueImage({required this.path, required this.toneGradient, required this.initial});
  final String path;
  final List<Color> toneGradient;
  final String initial;

  @override
  State<_CatalogueImage> createState() => _CatalogueImageState();
}

class _CatalogueImageState extends State<_CatalogueImage> {
  Uint8List? _bytes;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final response = await context.read<AuthProvider>().apiClient.dio.get<List<int>>(
            widget.path,
            options: Options(responseType: ResponseType.bytes),
          );
      final data = response.data;
      if (!mounted || data == null) return;
      setState(() => _bytes = Uint8List.fromList(data));
    } on DioException {
      if (mounted) setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_bytes != null) return Image.memory(_bytes!, fit: BoxFit.cover);
    if (_failed) return _ToneMonogram(toneGradient: widget.toneGradient, initial: widget.initial);
    return _ToneMonogram(toneGradient: widget.toneGradient, initial: widget.initial);
  }
}

/// A real product card for a package — matches `_ServiceTile`'s own visual language (photo strip
/// + name + price) so «الباقات» reads as the same professional catalogue, not a second, plainer
/// control bolted on beside it.
class _PackageCard extends StatelessWidget {
  const _PackageCard({
    required this.name,
    required this.memberNames,
    required this.priceMinor,
    required this.hasImage,
    required this.imageUrl,
    required this.selected,
    required this.onTap,
  });
  final String name;
  final String memberNames;
  final int priceMinor;
  final bool hasImage;
  final String imageUrl;
  final bool selected;
  final VoidCallback onTap;

  static const _tone = [Color(0xFFB7862B), Color(0xFFE0AA4D)];

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    return SizedBox(
      width: 160,
      child: AnimatedContainer(
        duration: AppMotion.fast,
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: selected ? _tone[0] : AppColors.borderSubtle, width: selected ? 2 : 1),
          boxShadow: selected
              ? [BoxShadow(color: _tone[0].withValues(alpha: 0.30), blurRadius: 16, offset: const Offset(0, 6))]
              : AppShadows.card,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: AppRadius.cardRadius,
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(
                  height: 60,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      if (hasImage)
                        _CatalogueImage(path: imageUrl, toneGradient: _tone, initial: name)
                      else
                        _ToneMonogram(toneGradient: _tone, initial: name),
                      Positioned.directional(
                        textDirection: Directionality.of(context),
                        top: 4,
                        start: 4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.4),
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.inventory_2_rounded, size: 10, color: Colors.white),
                              const SizedBox(width: 3),
                              Text(s.servicesPageTabPackages,
                                  style: AppTextStyles.caption
                                      .copyWith(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                      ),
                      if (selected)
                        Positioned.directional(
                          textDirection: Directionality.of(context),
                          top: 4,
                          end: 4,
                          child: Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(color: _tone[0], shape: BoxShape.circle),
                            child: const Icon(Icons.check_rounded, size: 12, color: Colors.white),
                          ),
                        ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.xs),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w800)),
                      Text(memberNames,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.caption.copyWith(color: AppColors.textMuted, fontSize: 10)),
                      const SizedBox(height: 2),
                      Text(Formatters.formatCurrency(priceMinor / 100, locale: locale),
                          style: AppTextStyles.caption
                              .copyWith(color: _tone[0], fontWeight: FontWeight.w800)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Bigger, thumb-friendly +/-, and the number itself is a real button — tapping it opens
/// [_VisitScreenState._promptQuantity] to type "12" once instead of tapping +11 times (the
/// owner's own ask, found live: the old 18px controls were "صغيرة" and typed-entry was missing
/// entirely).
class _QuantityStepper extends StatelessWidget {
  final int quantity;
  final Color tone;
  final ValueChanged<int> onChange;
  final VoidCallback onTapNumber;
  const _QuantityStepper({
    required this.quantity,
    required this.tone,
    required this.onChange,
    required this.onTapNumber,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _stepperButton(Icons.remove_rounded, () => onChange(-1)),
        InkWell(
          onTap: onTapNumber,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          child: Container(
            constraints: const BoxConstraints(minWidth: 26),
            padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 2),
            alignment: Alignment.center,
            child: Text(
              '$quantity',
              textAlign: TextAlign.center,
              style: AppTextStyles.bodySmall.copyWith(color: tone, fontWeight: FontWeight.w800),
            ),
          ),
        ),
        _stepperButton(Icons.add_rounded, () => onChange(1)),
      ],
    );
  }

  Widget _stepperButton(IconData icon, VoidCallback onTap) {
    return InkWell(
      customBorder: const CircleBorder(),
      onTap: onTap,
      child: Container(
        width: 28,
        height: 28,
        alignment: Alignment.center,
        decoration: BoxDecoration(color: tone.withValues(alpha: 0.16), shape: BoxShape.circle),
        child: Icon(icon, size: 16, color: tone),
      ),
    );
  }
}

class _RetryBody extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _RetryBody({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(onPressed: onRetry, child: Text(S.of(context)!.retry)),
          ],
        ),
      ),
    );
  }
}
