import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show BranchTeamMember;
import 'package:raje3_mobile/core/services/bookings_service.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/models/booking_model.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/models/points_model.dart' show Reward;
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

import 'bookings_screen.dart' show dateKey;

/// A hijacked, real state: no single staff member covers every chosen service together — the
/// server's own `create()` books a whole basket under ONE operator id, so a split booking is not
/// something the backend can do (docs/خطة-تنفيذ-الحجوزات.md §6, same rule BookingDialog.tsx
/// documents). Told plainly, never hidden behind a spinner that just never finds a slot.
const _kSlotsPerScreen = 8;

/// New-booking AND edit-booking — same sheet, same "one operator per basket" conflict logic
/// apps/console/src/screens/BookingDialog.tsx already enforces, mirrored step for step: SEQUENTIAL
/// STEPS on mobile (services → staff → time → confirm; +customer first when creating), not the
/// console's single long form — the direction the owner asked for and confirmed.
class NewBookingSheet extends StatefulWidget {
  final String branchId;
  final DateTime date;
  final List<ServiceItem> services;
  final List<BranchTeamMember> staff;
  final BookingsService bookingsService;
  final Booking? editing;

  const NewBookingSheet({
    super.key,
    required this.branchId,
    required this.date,
    required this.services,
    required this.staff,
    required this.bookingsService,
    this.editing,
  });

  @override
  State<NewBookingSheet> createState() => _NewBookingSheetState();
}

class _NewBookingSheetState extends State<NewBookingSheet> {
  late final CustomersService _customersService;
  late final PageController _pageController;
  int _page = 0;

  // customer step
  final _phoneController = TextEditingController();
  final _nameController = TextEditingController();
  Customer? _selectedCustomer;
  List<CustomerHit> _suggestions = const [];
  Timer? _debounce;
  NoShowRisk? _risk;
  // «نية استرجاع مكافأة» (bookings.edit_reward) — chosen now, spent only on attend(), same
  // "intent recorded up front, redemption deferred" rule BookingDialog.tsx's own reward step
  // documents. `null` while still loading, empty list once resolved with nothing redeemable.
  List<Reward>? _redeemableRewards;
  String _intendedRewardId = '';

  // services step
  final Set<String> _chosen = {};
  final Map<String, int> _quantities = {};

  // staff step
  String? _operatorId; // null = "أي متاح"

  // time step
  late DateTime _day;
  List<BookingSlot>? _slots;
  int? _pickedStartsAt;
  String? _pickedOperatorId;
  bool _jumping = false;
  String? _slotsError;

  // confirm step
  final _noteController = TextEditingController();
  String _paymentStatus = 'none';
  final _depositController = TextEditingController();

  bool _saving = false;
  String? _error;

  bool get _isEditing => widget.editing != null;

  @override
  void initState() {
    super.initState();
    _customersService = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    _pageController = PageController();
    _day = DateTime(widget.date.year, widget.date.month, widget.date.day);
    final editing = widget.editing;
    if (editing != null) {
      _chosen.addAll(editing.serviceIds);
      _quantities.addAll(editing.quantities);
      _operatorId = editing.operatorId;
      _pickedStartsAt = editing.startsAt;
      _pickedOperatorId = editing.operatorId;
      _day = DateTime.fromMillisecondsSinceEpoch(editing.startsAt * 1000);
      _noteController.text = editing.note;
      _paymentStatus = editing.paymentStatus;
      if (editing.depositAmountMinor != null) {
        _depositController.text = (editing.depositAmountMinor! / 100).toStringAsFixed(0);
      }
      _intendedRewardId = editing.intendedRewardId ?? '';
      _loadRewardsForCustomerId(editing.customerId);
    }
    _page = _isEditing ? 0 : 0;
  }

  /// Resolves the subject_ref behind either an EXISTING booking's own customer id (edit mode)
  /// or a freshly-picked suggestion's phone (create mode), then reads what that customer may
  /// redeem. Silent on failure, same posture as every other secondary read in this sheet — a
  /// customer with a real reward whose read simply failed looks like one with none, never a
  /// crash.
  Future<void> _loadRewardsForCustomerId(String customerId) async {
    final record = await _customersService.record(customerId);
    if (record == null || !mounted) return;
    await _loadRewardsForSubjectRef(record.customer.subjectRef);
  }

  Future<void> _loadRewardsForPhone(String phone) async {
    final customer = await _customersService.byPhone(phone);
    if (customer == null || !mounted) return;
    await _loadRewardsForSubjectRef(customer.subjectRef);
  }

  Future<void> _loadRewardsForSubjectRef(String subjectRef) async {
    if (subjectRef.isEmpty) return;
    final balance = await _customersService.loyaltyBalance(subjectRef);
    if (!mounted) return;
    setState(() => _redeemableRewards = balance?.rewards ?? const []);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _pageController.dispose();
    _phoneController.dispose();
    _nameController.dispose();
    _noteController.dispose();
    _depositController.dispose();
    super.dispose();
  }

  // ── steps layout: [customer?] services staff time confirm ──────────────────────────────
  List<String> get _stepTitles => [
        if (!_isEditing) 'العميل',
        'الخدمات',
        'الموظف',
        'الوقت',
        'التأكيد',
      ];

  int get _serviceStepIndex => _isEditing ? 0 : 1;
  int get _staffStepIndex => _serviceStepIndex + 1;
  int get _timeStepIndex => _staffStepIndex + 1;
  int get _confirmStepIndex => _timeStepIndex + 1;

  // ── derived: staff eligible for every chosen service together ───────────────────────────
  Set<String> get _fieldStaffIds =>
      widget.staff.where((o) => o.role == 'operator').map((o) => o.id).toSet();

  List<BranchTeamMember> get _eligibleStaff {
    if (_chosen.isEmpty) return widget.staff;
    final perService = _chosen.map((id) {
      final svc = widget.services.firstWhere((s) => s.id == id,
          orElse: () => ServiceItem(
              id: id, name: '', cycleDays: 0, priceMinor: 0, durationMinutes: 0, active: true,
              description: '', hasImage: false, eligibleStaffIds: const [], assignmentMode: 'auto',
              procedureStepIds: const []));
      return svc.eligibleStaffIds.isNotEmpty ? svc.eligibleStaffIds.toSet() : _fieldStaffIds;
    }).toList();
    return widget.staff.where((o) => perService.every((set) => set.contains(o.id))).toList();
  }

  bool get _anyNamed => _chosen
      .any((id) => widget.services.firstWhere((s) => s.id == id,
          orElse: () => ServiceItem(id: id, name: '', cycleDays: 0, priceMinor: 0,
              durationMinutes: 0, active: true, description: '', hasImage: false,
              eligibleStaffIds: const [], assignmentMode: 'auto', procedureStepIds: const []))
          .assignmentMode == 'named');

  bool get _noCommonOperator => _chosen.length > 1 && _eligibleStaff.isEmpty;

  int get _durationTotal => _chosen.fold(0, (sum, id) {
        final svc = widget.services.firstWhere((s) => s.id == id,
            orElse: () => ServiceItem(id: id, name: '', cycleDays: 0, priceMinor: 0,
                durationMinutes: 0, active: true, description: '', hasImage: false,
                eligibleStaffIds: const [], assignmentMode: 'auto', procedureStepIds: const []));
        return sum + svc.durationMinutes * (_quantities[id] ?? 1);
      });

  bool get _depositMissing =>
      _paymentStatus == 'deposit' && (double.tryParse(_depositController.text.trim()) ?? 0) <= 0;

  // ── customer search ──────────────────────────────────────────────────────────────────────
  void _onPhoneChanged(String value) {
    setState(() => _selectedCustomer = null);
    _debounce?.cancel();
    if (value.trim().length < 3) {
      setState(() => _suggestions = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () async {
      final result = await _customersService.suggest(value.trim());
      if (mounted) setState(() => _suggestions = result.hits);
    });
  }

  Future<void> _pickCustomer(CustomerHit hit) async {
    setState(() {
      _selectedCustomer = Customer(
          id: hit.id, phone: hit.phone, name: hit.name, created: 0, lastVisit: 0, visitCount: 0,
          lastBranchId: '', source: '', subjectRef: '');
      _phoneController.text = hit.phone;
      _nameController.text = hit.name;
      _suggestions = const [];
    });
    final risk = await widget.bookingsService.risk(hit.id);
    if (mounted) setState(() => _risk = risk);
    await _loadRewardsForPhone(hit.phone);
  }

  // ── slots ────────────────────────────────────────────────────────────────────────────────
  Future<void> _searchSlots() async {
    if (_chosen.isEmpty || _noCommonOperator) {
      setState(() => _slots = const []);
      return;
    }
    setState(() {
      _slots = null;
      _slotsError = null;
    });
    final dayStart = DateTime(_day.year, _day.month, _day.day);
    final now = DateTime.now();
    final isToday = dateKey(_day) == dateKey(now);
    final after = (isToday ? now : dayStart).millisecondsSinceEpoch ~/ 1000;
    final windowEnd = dayStart.add(const Duration(days: 1)).millisecondsSinceEpoch ~/ 1000;
    final candidates = _operatorId != null ? [_operatorId!] : _eligibleStaff.map((o) => o.id).toList();
    if (candidates.isEmpty) {
      setState(() => _slots = const []);
      return;
    }
    final rows = await widget.bookingsService.nearestSlotsAny(
      branchId: widget.branchId,
      operatorIds: candidates,
      serviceIds: _chosen.toList(),
      after: after,
      windowEnd: windowEnd,
      maxSlots: _kSlotsPerScreen,
      excludeBookingId: widget.editing?.id,
      quantities: Map.of(_quantities),
    );
    if (!mounted) return;
    setState(() {
      _slots = rows ?? const [];
      if (rows == null) _slotsError = 'تعذّر البحث عن مواعيد فاضية';
    });
  }

  Future<void> _jumpToNearestDay() async {
    if (_chosen.isEmpty || _jumping) return;
    setState(() {
      _jumping = true;
      _slotsError = null;
    });
    final after = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final candidates = _operatorId != null ? [_operatorId!] : _eligibleStaff.map((o) => o.id).toList();
    int? best;
    String? bestOperator;
    for (final opId in candidates) {
      final startsAt = await widget.bookingsService.nearestSlot(
        branchId: widget.branchId, operatorId: opId, serviceIds: _chosen.toList(), after: after,
        excludeBookingId: widget.editing?.id, quantities: Map.of(_quantities),
      );
      if (startsAt != null && (best == null || startsAt < best)) {
        best = startsAt;
        bestOperator = opId;
      }
    }
    if (!mounted) return;
    if (best == null) {
      setState(() {
        _jumping = false;
        _slotsError = 'ما فيه موعد فاضٍ قريب لهذي التركيبة';
      });
      return;
    }
    final foundDay = DateTime.fromMillisecondsSinceEpoch(best * 1000);
    setState(() {
      _jumping = false;
      _day = DateTime(foundDay.year, foundDay.month, foundDay.day);
      _operatorId ??= bestOperator;
    });
    _searchSlots();
  }

  // ── validation / navigation ──────────────────────────────────────────────────────────────
  bool _canAdvance(int step) {
    if (step == 0 && !_isEditing) {
      return _selectedCustomer != null || _phoneController.text.trim().length >= 8;
    }
    if (step == _serviceStepIndex) return _chosen.isNotEmpty;
    if (step == _staffStepIndex) return !_noCommonOperator;
    if (step == _timeStepIndex) return _pickedStartsAt != null && _pickedOperatorId != null;
    return true;
  }

  void _next() {
    final step = _page;
    if (!_canAdvance(step)) return;
    if (step == _staffStepIndex) _searchSlots();
    setState(() => _page++);
    _pageController.animateToPage(_page, duration: AppMotion.base, curve: Curves.easeOut);
  }

  void _back() {
    setState(() => _page--);
    _pageController.animateToPage(_page, duration: AppMotion.base, curve: Curves.easeOut);
  }

  Future<void> _confirm() async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      if (_isEditing) {
        final editing = widget.editing!;
        Booking? booking = editing;
        final servicesChanged = !(_chosen.length == editing.serviceIds.length &&
            _chosen.every(editing.serviceIds.contains) &&
            const MapEquality().equals(_quantities, editing.quantities));
        if (servicesChanged) {
          booking = await widget.bookingsService
              .editServices(editing.id, _chosen.toList(), quantities: Map.of(_quantities));
        }
        if (_pickedStartsAt != editing.startsAt || _pickedOperatorId != editing.operatorId) {
          booking = await widget.bookingsService
              .reschedule(editing.id, _pickedStartsAt!, operatorId: _pickedOperatorId);
        }
        if (_noteController.text.trim() != editing.note) {
          booking = await widget.bookingsService.editNote(editing.id, _noteController.text.trim());
        }
        if (_paymentStatus != editing.paymentStatus ||
            (_paymentStatus == 'deposit' &&
                _depositMinor != editing.depositAmountMinor)) {
          booking = await widget.bookingsService.editPayment(editing.id, _paymentStatus,
              depositAmountMinor: _paymentStatus == 'deposit' ? _depositMinor : null);
        }
        if (_intendedRewardId != (editing.intendedRewardId ?? '')) {
          booking = await widget.bookingsService
              .editReward(editing.id, _intendedRewardId.isEmpty ? null : _intendedRewardId);
        }
        if (booking == null) {
          setState(() => _error = 'تعذّر حفظ التعديل');
          return;
        }
        if (mounted) Navigator.of(context).pop(booking);
        return;
      }

      var customer = _selectedCustomer;
      if (customer == null) {
        customer = await _customersService.ensure(
            phone: _phoneController.text.trim(), name: _nameController.text.trim());
        if (customer == null) {
          setState(() => _error = 'تعذّر تسجيل العميل — تحقق من الرقم');
          return;
        }
      }
      final created = await widget.bookingsService.create(
        branchId: widget.branchId,
        operatorId: _pickedOperatorId!,
        customerId: customer.id,
        serviceIds: _chosen.toList(),
        quantities: Map.of(_quantities),
        startsAt: _pickedStartsAt!,
        note: _noteController.text.trim(),
        paymentStatus: _paymentStatus,
        depositAmountMinor: _paymentStatus == 'deposit' ? _depositMinor : null,
        intendedRewardId: _intendedRewardId.isEmpty ? null : _intendedRewardId,
      );
      if (created == null) {
        setState(() => _error = 'تعذّر إتمام الحجز — حاول مرة أخرى');
        return;
      }
      if (mounted) Navigator.of(context).pop(created);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  int? get _depositMinor {
    final v = double.tryParse(_depositController.text.trim());
    if (v == null || v <= 0) return null;
    return (v * 100).round();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final titles = _stepTitles;
    return Container(
      height: appSheetMaxHeight(context) * 0.94,
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 10),
          Container(width: 40, height: 4,
              decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Text(_isEditing ? 'تعديل الحجز' : 'حجز جديد',
                    style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary)),
                const Spacer(),
                Text('${_page + 1}/${titles.length}',
                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
            ),
          ),
          _StepDots(count: titles.length, current: _page),
          const SizedBox(height: AppSpacing.sm),
          Expanded(
            child: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                if (!_isEditing) _customerStep(),
                _servicesStep(),
                _staffStep(),
                _timeStep(),
                _confirmStep(),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: Text(_error!,
                  style: AppTextStyles.bodySmall.copyWith(
                      color: context.isDark ? AppDarkColors.danger : AppColors.danger)),
            ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                if (_page > 0)
                  Expanded(child: SecondaryButton(text: 'رجوع', onPressed: _back)),
                if (_page > 0) const SizedBox(width: AppSpacing.sm),
                Expanded(
                  flex: 2,
                  child: _page == _confirmStepIndex
                      ? PrimaryButton(
                          text: _isEditing ? 'حفظ التعديل' : 'تأكيد الحجز',
                          isLoading: _saving,
                          onPressed: _depositMissing ? null : _confirm,
                        )
                      : PrimaryButton(
                          text: 'التالي',
                          onPressed: _canAdvance(_page) ? _next : null,
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── step 0: customer ─────────────────────────────────────────────────────────────────────
  Widget _customerStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          KbAnchor(
            id: 'bookings.new_sheet.phone_field',
            child: AppTextField(
              labelText: 'جوال العميل',
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              textDirection: TextDirection.ltr,
              prefixIcon: Icons.phone_iphone_rounded,
              onChanged: _onPhoneChanged,
            ),
          ),
          if (_suggestions.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Material(
              type: MaterialType.transparency,
              child: Column(
                children: _suggestions.take(5).map((hit) => ListTile(
                      onTap: () => _pickCustomer(hit),
                      leading: const Icon(Icons.person_outline),
                      title: Text(hit.name.isNotEmpty ? hit.name : hit.phone),
                      subtitle: hit.name.isNotEmpty ? Text(hit.phone, textDirection: TextDirection.ltr) : null,
                    )).toList(),
              ),
            ),
          ],
          if (_selectedCustomer == null && _phoneController.text.trim().length >= 3) ...[
            const SizedBox(height: AppSpacing.sm),
            KbAnchor(
              id: 'bookings.new_sheet.name_field',
              child: AppTextField(labelText: 'الاسم (اختياري لعميل جديد)', controller: _nameController),
            ),
          ],
          if (_selectedCustomer != null && _risk != null && _risk!.risky) ...[
            const SizedBox(height: AppSpacing.md),
            AppAlert(
              type: AlertType.warning,
              title: 'مؤشّر عدم حضور',
              message:
                  'لم يحضر ${_risk!.noShows} من أصل ${_risk!.considered} من آخر مواعيده — فوق حد ${_risk!.thresholdPercent}٪. فكّر تطلب عربون.',
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
        ],
      ),
    );
  }

  // ── step: services ───────────────────────────────────────────────────────────────────────
  Widget _servicesStep() {
    final colors = context.appColors;
    final active = widget.services.where((s) => s.active).toList();
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          KbAnchor(
            id: 'bookings.new_sheet.services_grid',
            child: Column(
              children: active.map((s) {
                final selected = _chosen.contains(s.id);
                final qty = _quantities[s.id] ?? 1;
                return Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: AppCard(
                    hasShadow: false,
                    onTap: () => setState(() {
                      if (selected) {
                        _chosen.remove(s.id);
                        _quantities.remove(s.id);
                      } else {
                        _chosen.add(s.id);
                      }
                    }),
                    child: Row(
                      children: [
                        Icon(selected ? Icons.check_circle_rounded : Icons.circle_outlined,
                            color: selected
                                ? (context.isDark ? AppDarkColors.accent : AppColors.accent)
                                : colors.textMuted),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(s.name, style: AppTextStyles.bodyMedium.copyWith(color: colors.textPrimary)),
                              Text('${s.durationMinutes} د',
                                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                            ],
                          ),
                        ),
                        if (selected)
                          _QuantityStepper(
                            quantity: qty,
                            onChanged: (n) => setState(() => _quantities[s.id] = n),
                          ),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          if (_chosen.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
              child: Text('إجمالي المدة: $_durationTotal دقيقة',
                  style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
            ),
          const SizedBox(height: AppSpacing.xl),
        ],
      ),
    );
  }

  // ── step: staff ───────────────────────────────────────────────────────────────────────────
  Widget _staffStep() {
    if (_noCommonOperator) {
      return const Padding(
        padding: EdgeInsets.all(AppSpacing.md),
        child: AppAlert(
          type: AlertType.error,
          title: 'ما فيه موظف يقدر يسوي كل الخدمات المختارة مع بعض',
          message: 'جرّب تحجز كل خدمة لحالها، أو ارجع وشيل واحدة من الخدمات المتعارضة.',
        ),
      );
    }
    if (!_anyNamed) {
      return const Padding(
        padding: EdgeInsets.all(AppSpacing.md),
        child: AppAlert(
          type: AlertType.info,
          message: 'كل الخدمات المختارة "توزيع تلقائي" — النظام يختار الموظف المناسب وقت الحجز.',
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: KbAnchor(
        id: 'bookings.new_sheet.staff_field',
        child: Column(
          children: [
            _staffTile(null, 'أي متاح'),
            ..._eligibleStaff.map((o) => _staffTile(o.id, o.name)),
          ],
        ),
      ),
    );
  }

  Widget _staffTile(String? id, String label) {
    final selected = _operatorId == id;
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: AppCard(
        hasShadow: false,
        onTap: () => setState(() => _operatorId = id),
        child: Row(
          children: [
            Icon(selected ? Icons.radio_button_checked : Icons.radio_button_off,
                color: selected ? (context.isDark ? AppDarkColors.accent : AppColors.accent) : colors.textMuted),
            const SizedBox(width: AppSpacing.sm),
            Text(label, style: AppTextStyles.bodyMedium.copyWith(color: colors.textPrimary)),
          ],
        ),
      ),
    );
  }

  // ── step: time ────────────────────────────────────────────────────────────────────────────
  Widget _timeStep() {
    final colors = context.appColors;
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          KbAnchor(
            id: 'bookings.new_sheet.day_nav',
            child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.chevron_right_rounded),
                onPressed: () {
                  setState(() => _day = _day.subtract(const Duration(days: 1)));
                  _searchSlots();
                },
              ),
              Expanded(
                child: Text(dateKey(_day), textAlign: TextAlign.center,
                    style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary)),
              ),
              IconButton(
                icon: const Icon(Icons.chevron_left_rounded),
                onPressed: () {
                  setState(() => _day = _day.add(const Duration(days: 1)));
                  _searchSlots();
                },
              ),
            ],
            ),
          ),
          KbAnchor(
            id: 'bookings.new_sheet.time_slots',
            child: _slots == null
                ? const Padding(
                    padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
                    child: AppLoadingIndicator())
                : _slots!.isEmpty
                    ? Column(
                        children: [
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                            child: Text('ما فيه مواعيد فاضية بهذا اليوم',
                                style: AppTextStyles.bodyMedium.copyWith(color: colors.textSecondary)),
                          ),
                          SecondaryButton(
                            text: _jumping ? 'جاري البحث...' : 'أقرب يوم فيه موعد',
                            onPressed: _jumping ? null : _jumpToNearestDay,
                          ),
                        ],
                      )
                    : Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.sm,
                        children: _slots!.map((slot) {
                          final picked = _pickedStartsAt == slot.startsAt && _pickedOperatorId == slot.operatorId;
                          final time = TimeOfDay.fromDateTime(
                              DateTime.fromMillisecondsSinceEpoch(slot.startsAt * 1000));
                          final opName = _operatorId == null
                              ? widget.staff.firstWhere((o) => o.id == slot.operatorId,
                                  orElse: () => const BranchTeamMember(
                                      id: '', name: '', role: '', branchId: '', active: true)).name
                              : '';
                          return ChoiceChip(
                            label: Text(opName.isNotEmpty ? '${time.format(context)} · $opName' : time.format(context)),
                            selected: picked,
                            onSelected: (_) => setState(() {
                              _pickedStartsAt = slot.startsAt;
                              _pickedOperatorId = slot.operatorId;
                            }),
                          );
                        }).toList(),
                      ),
          ),
          if (_slotsError != null)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.sm),
              child: Text(_slotsError!,
                  style: AppTextStyles.bodySmall.copyWith(
                      color: context.isDark ? AppDarkColors.danger : AppColors.danger)),
            ),
          const SizedBox(height: AppSpacing.xl),
        ],
      ),
    );
  }

  // ── step: confirm ─────────────────────────────────────────────────────────────────────────
  Widget _confirmStep() {
    final colors = context.appColors;
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          KbAnchor(
            id: 'bookings.new_sheet.note_field',
            child: AppTextField(labelText: 'ملاحظة (اختياري)', controller: _noteController, maxLines: 2),
          ),
          const SizedBox(height: AppSpacing.md),
          Text('حالة الدفع', style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary)),
          const SizedBox(height: AppSpacing.sm),
          KbAnchor(
            id: 'bookings.new_sheet.payment_field',
            child: SegmentedFilter<String>(
              value: _paymentStatus,
              onChanged: (v) => setState(() => _paymentStatus = v),
              options: const [
                SegmentedFilterOption(value: 'none', label: 'بدون'),
                SegmentedFilterOption(value: 'deposit', label: 'عربون'),
                SegmentedFilterOption(value: 'paid', label: 'مدفوع'),
              ],
            ),
          ),
          if (_paymentStatus == 'deposit') ...[
            const SizedBox(height: AppSpacing.md),
            KbAnchor(
              id: 'bookings.new_sheet.deposit_field',
              child: AppTextField(
                labelText: 'مبلغ العربون (ر.س)',
                controller: _depositController,
                keyboardType: TextInputType.number,
                textDirection: TextDirection.ltr,
              ),
            ),
          ],
          if ((_redeemableRewards ?? const []).isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Text('نية استرجاع مكافأة',
                style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary)),
            const SizedBox(height: 4),
            Text('يُختار الآن، يُصرف فعليًا فقط عند «حضر» — نقاطه ما تُخصم لزيارة لسه ما صارت.',
                style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted)),
            const SizedBox(height: AppSpacing.sm),
            KbAnchor(
              id: 'bookings.new_sheet.reward_field',
              child: Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  ChoiceChip(
                    label: const Text('بدون'),
                    selected: _intendedRewardId.isEmpty,
                    onSelected: (_) => setState(() => _intendedRewardId = ''),
                  ),
                  for (final reward in _redeemableRewards!)
                    ChoiceChip(
                      label: Text('${reward.name} — ${reward.cost} نقطة'),
                      selected: _intendedRewardId == reward.id,
                      onSelected: (_) => setState(() => _intendedRewardId = reward.id),
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
        ],
      ),
    );
  }
}

class _QuantityStepper extends StatelessWidget {
  final int quantity;
  final ValueChanged<int> onChanged;
  const _QuantityStepper({required this.quantity, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return KbAnchor(
      id: 'bookings.new_sheet.quantity_stepper',
      child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          icon: const Icon(Icons.remove_circle_outline, size: 20),
          onPressed: quantity > 1 ? () => onChanged(quantity - 1) : null,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
        ),
        SizedBox(
          width: 24,
          child: Text('$quantity', textAlign: TextAlign.center,
              style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary)),
        ),
        IconButton(
          icon: const Icon(Icons.add_circle_outline, size: 20),
          onPressed: () => onChanged(quantity + 1),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
        ),
      ],
      ),
    );
  }
}

class _StepDots extends StatelessWidget {
  final int count;
  final int current;
  const _StepDots({required this.count, required this.current});

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final colors = context.appColors;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (i) {
        final active = i <= current;
        return AnimatedContainer(
          duration: AppMotion.fast,
          margin: const EdgeInsets.symmetric(horizontal: 3),
          width: i == current ? 20 : 8,
          height: 8,
          decoration: BoxDecoration(
            color: active ? accent : colors.borderSubtle,
            borderRadius: BorderRadius.circular(4),
          ),
        );
      }),
    );
  }
}

/// Tiny local map-equality helper — avoids pulling `package:collection` in for one comparison.
class MapEquality {
  const MapEquality();
  bool equals(Map<String, int> a, Map<String, int> b) {
    if (a.length != b.length) return false;
    for (final entry in a.entries) {
      if (b[entry.key] != entry.value) return false;
    }
    return true;
  }
}
