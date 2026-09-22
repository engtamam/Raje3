import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
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
  final _phoneFocus = FocusNode();
  final _plateFocus = FocusNode();

  bool _loadingCatalogue = true;
  String? _catalogueError;
  List<Map<String, dynamic>> _services = [];

  // ── vehicle/plate — GET /api/v1/field/catalogue's own `tracks_vehicle`, the SAME server fact
  // apps/console/src/screens/Visit.tsx's own `showPlate` reads. A shop this is true for REFUSES
  // (`recorded: false`) any visit with no plausible plate — `core/plate.py::is_plausible` server-
  // side — so this field is never cosmetic once shown.
  bool _tracksVehicle = false;
  Timer? _plateLookupDebounce;
  bool _lookingUpPlate = false;
  String? _vehicleCustomerName;
  bool _plateLookedUp = false;

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
  }

  @override
  void dispose() {
    _entryController.dispose();
    _phoneController.dispose();
    _noteController.dispose();
    _plateController.dispose();
    _phoneFocus.dispose();
    _plateFocus.dispose();
    _suggestDebounce?.cancel();
    _exactDebounce?.cancel();
    _plateLookupDebounce?.cancel();
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
      final tracksVehicle = body is Map<String, dynamic> && body['tracks_vehicle'] == true;
      if (!mounted) return;
      setState(() {
        _services = services;
        _tracksVehicle = tracksVehicle;
        _loadingCatalogue = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _catalogueError = S.of(context)!.visitCatalogueLoadErrorFallback;
        _loadingCatalogue = false;
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
    setState(() {
      _suggestions = [];
      _customerName = customer['name'] as String?;
      _lookedUp = true;
      _lookingUp = false;
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
        setState(() {
          _customerName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
          _lookedUp = true;
          _lookingUp = false;
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
    _plateLookupDebounce?.cancel();
    final plate = formatted.trim();
    if (plate.length < 3) return;
    _plateLookupDebounce = Timer(const Duration(milliseconds: 220), () => _lookupPlate(plate));
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
      setState(() {
        _vehicleCustomerName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
        _plateLookedUp = true;
        _lookingUpPlate = false;
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
    });
  }

  void _changeQuantity(String serviceId, int delta) {
    HapticFeedback.selectionClick();
    setState(() {
      final current = _selected[serviceId] ?? 1;
      final next = (current + delta).clamp(1, 20);
      _selected[serviceId] = next;
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
      final response = await _api.apiClient.dio.post<dynamic>(
        '/api/v1/field/visits',
        data: {
          'phone': phone,
          if (_tracksVehicle) 'plate': plate,
          'service_ids': _selected.keys.toList(),
          'quantities': _selected,
          'note': _noteController.text.trim(),
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
          _phoneController.clear();
          _noteController.clear();
          _plateController.clear();
          _noteOpen = false;
          _lookedUp = false;
          _customerName = null;
          _suggestions = [];
          _plateLookedUp = false;
          _vehicleCustomerName = null;
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
                if (_tracksVehicle) ...[
                  _buildPlateCard(),
                  const SizedBox(height: AppSpacing.lg),
                ],
                _buildPhoneCard(),
                _buildLoyaltyAndOfferSection(),
                const SizedBox(height: AppSpacing.lg),
                _buildServicesGrid(),
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
                  : (_plateLookedUp ? _buildVehicleBadge() : const SizedBox(width: double.infinity)),
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

  // ── Services — one-tap chips, not a checklist ────────────────────────────

  Widget _buildServicesGrid() {
    return KbAnchor(
      id: 'visit.register.services_grid',
      child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          S.of(context)!.visitServicesSectionTitle,
          style: AppTextStyles.labelMedium.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.sm),
        if (_services.isEmpty)
          Text(S.of(context)!.visitNoServicesYet, style: AppTextStyles.bodySmall)
        else
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              for (final service in _services)
                _ServiceChip(
                  name: service['name'] as String? ?? '',
                  quantity: _selected[service['id'] as String? ?? ''],
                  onTap: () => _toggleService(service['id'] as String? ?? ''),
                  onQuantityChange: (delta) =>
                      _changeQuantity(service['id'] as String? ?? '', delta),
                ),
            ],
          ),
      ],
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

/// One tap to add at quantity 1; the stepper only appears once selected, so an unselected chip
/// never carries a control the customer's actual count has no use for yet.
class _ServiceChip extends StatelessWidget {
  final String name;
  final int? quantity;
  final VoidCallback onTap;
  final ValueChanged<int> onQuantityChange;

  const _ServiceChip({
    required this.name,
    required this.quantity,
    required this.onTap,
    required this.onQuantityChange,
  });

  @override
  Widget build(BuildContext context) {
    final selected = quantity != null;
    return AnimatedContainer(
      duration: AppMotion.fast,
      curve: Curves.easeOut,
      decoration: BoxDecoration(
        gradient: selected ? appPrimaryGradient : null,
        color: selected ? null : AppColors.surface2,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: selected ? null : Border.all(color: AppColors.borderSubtle),
        boxShadow: selected
            ? [
                BoxShadow(
                  color: AppColors.accent.withValues(alpha: 0.35),
                  blurRadius: 14,
                  offset: const Offset(0, 5),
                ),
              ]
            : null,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          onTap: onTap,
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: selected ? AppSpacing.xs : AppSpacing.sm,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  name,
                  style: AppTextStyles.bodyMedium.copyWith(
                    color: selected ? AppColors.accentContrast : AppColors.textPrimary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
                if (selected) ...[
                  const SizedBox(width: AppSpacing.xs),
                  _QuantityStepper(quantity: quantity!, onChange: onQuantityChange),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _QuantityStepper extends StatelessWidget {
  final int quantity;
  final ValueChanged<int> onChange;
  const _QuantityStepper({required this.quantity, required this.onChange});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _stepperButton(Icons.remove_rounded, () => onChange(-1)),
        SizedBox(
          width: 20,
          child: Text(
            '$quantity',
            textAlign: TextAlign.center,
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.accentContrast,
              fontWeight: FontWeight.w700,
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
        width: 22,
        height: 22,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.22),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 14, color: AppColors.accentContrast),
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
