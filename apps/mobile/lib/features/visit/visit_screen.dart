import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

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
  final _phoneFocus = FocusNode();

  bool _loadingCatalogue = true;
  String? _catalogueError;
  List<Map<String, dynamic>> _services = [];

  Timer? _suggestDebounce;
  Timer? _exactDebounce;
  bool _lookingUp = false;
  String? _customerName;
  bool _lookedUp = false;
  List<Map<String, dynamic>> _suggestions = [];

  bool _noteOpen = false;

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
    _phoneFocus.dispose();
    _suggestDebounce?.cancel();
    _exactDebounce?.cancel();
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
      if (!mounted) return;
      setState(() {
        _services = services;
        _loadingCatalogue = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _catalogueError = 'تعذّر تحميل الخدمات. اسحب للأسفل لإعادة المحاولة.';
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
  }

  Future<void> _lookupExact(String phone) async {
    setState(() {
      _lookingUp = true;
      _lookedUp = false;
      _customerName = null;
      _suggestions = [];
    });
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/by-phone',
        queryParameters: {'phone': phone},
      );
      if (!mounted || _phoneController.text.trim() != phone) return;
      final body = response.data;
      final customer = body is Map<String, dynamic> ? body['customer'] : null;
      setState(() {
        _customerName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
        _lookedUp = true;
        _lookingUp = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _lookingUp = false;
        _lookedUp = false;
      });
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

  bool get _canSave => _phoneController.text.trim().length >= 3 && _selected.isNotEmpty && !_saving;

  Future<void> _save() async {
    final phone = _phoneController.text.trim();
    if (phone.length < 3 || _selected.isEmpty) {
      HapticFeedback.heavyImpact();
      setState(() {
        _saveError = phone.length < 3 ? 'أدخل رقم جوال العميل' : 'اختر خدمة واحدة على الأقل';
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
        setState(() {
          _saving = false;
          _justSaved = true;
          _selected.clear();
          _phoneController.clear();
          _noteController.clear();
          _noteOpen = false;
          _lookedUp = false;
          _customerName = null;
          _suggestions = [];
        });
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
          _saveError = reason ?? 'تعذّر تسجيل الزيارة.';
        });
      }
    } on DioException {
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      setState(() {
        _saving = false;
        _saveError = 'تعذّر تسجيل الزيارة. تحقق من الاتصال وحاول مرة أخرى.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('تسجيل زيارة')),
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
                _buildPhoneCard(),
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

  // ── Phone — one floating, elevated module: field, suggestions, and the
  //    resolved-customer state all live inside it, so the eye never has to
  //    jump between separate boxes while he is mid-lookup. ────────────────

  Widget _buildPhoneCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: AppCardDecorations.elevated,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'رقم جوال العميل',
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
              known ? 'عميل معروف: $_customerName' : 'عميل جديد',
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'الخدمات',
          style: AppTextStyles.labelMedium.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.sm),
        if (_services.isEmpty)
          const Text('لا توجد خدمات بعد.', style: AppTextStyles.bodySmall)
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
    );
  }

  // ── Note — collapsed until asked for ─────────────────────────────────────

  Widget _buildNoteToggle() {
    return AnimatedSize(
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
                      'ملاحظة',
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
                label: const Text('ملاحظة'),
                style: TextButton.styleFrom(foregroundColor: AppColors.textSecondary),
              ),
            ),
    );
  }

  // ── Bottom bar ────────────────────────────────────────────────────────────

  Widget _buildBottomBar() {
    return Container(
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
                        'حفظ الزيارة',
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
                    'تم تسجيل الزيارة',
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
            OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
          ],
        ),
      ),
    );
  }
}
