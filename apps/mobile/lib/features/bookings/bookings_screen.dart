import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show BranchTeamMember;
import 'package:raje3_mobile/core/services/bookings_service.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/models/booking_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

import 'booking_details_sheet.dart';
import 'booking_month_sheet.dart';
import 'booking_settings_sheet.dart';
import 'booking_status.dart';
import 'new_booking_sheet.dart';

/// «الحجوزات» — mobile-native mirror of apps/console/src/screens/Bookings.tsx's own DATA
/// (same routes, same one-operator-per-basket rule, same statuses), built with a completely
/// different SHAPE: an agenda (chronological list), never the console's staff-column grid —
/// a grid of narrow columns does not survive phone width (research behind this pass: mobile
/// scheduling apps — Fresha, Vagaro, Square Appointments — all converge on agenda-first).
///
/// NO CUSTOMER NAME ON A CARD YET — same real, pre-existing limitation the console's own
/// `BookingsList` carries (its own comment: "Booking carries only customer_id, and there is no
/// batch lookup yet"). Not fixed here — a backend change, out of scope for this screen.
class BookingsScreen extends StatefulWidget {
  const BookingsScreen({super.key});

  @override
  State<BookingsScreen> createState() => _BookingsScreenState();
}

class _BookingsScreenState extends State<BookingsScreen> {
  late final BookingsService _bookingsService;
  late final ServicesCatalogueService _servicesService;

  DateTime _selectedDate = DateTime.now();
  String? _staffFilter; // null = everyone

  List<Booking>? _bookings;
  List<ServiceItem>? _services;
  List<BranchTeamMember>? _staff;
  bool _loading = true;
  bool _failed = false;

  String get _branchId => context.read<BranchProvider>().selectedId ?? '';

  @override
  void initState() {
    super.initState();
    final apiClient = context.read<AuthProvider>().apiClient;
    _bookingsService = BookingsService(apiClient: apiClient);
    _servicesService = ServicesCatalogueService(apiClient: apiClient);
    _loadStatic();
    _loadDay();
  }

  Future<void> _loadStatic() async {
    final authProvider = context.read<AuthProvider>();
    final services = await _servicesService.list(includeRetired: false);
    final operators = await authProvider.fetchOperators();
    if (!mounted) return;
    setState(() {
      _services = services;
      _staff = operators?.where((o) => o.active && o.branchId == _branchId).toList(growable: false);
    });
  }

  Future<void> _loadDay() async {
    setState(() {
      _loading = true;
      _failed = false;
    });
    final rows = await _bookingsService.list(branchId: _branchId, date: dateKey(_selectedDate));
    if (!mounted) return;
    setState(() {
      _loading = false;
      _failed = rows == null;
      _bookings = rows;
    });
  }

  void _changeDate(DateTime d) {
    setState(() => _selectedDate = d);
    _loadDay();
  }

  String _serviceName(String id) =>
      _services?.firstWhere((s) => s.id == id, orElse: () => ServiceItem(
            id: id, name: '—', cycleDays: 0, priceMinor: 0, durationMinutes: 0, active: true,
            description: '', hasImage: false, eligibleStaffIds: const [], assignmentMode: 'auto',
            procedureStepIds: const [],
          )).name ??
      '—';

  String _staffName(String id) =>
      _staff?.firstWhere((s) => s.id == id, orElse: () => const BranchTeamMember(
            id: '', name: '—', role: 'operator', branchId: '', active: true,
          )).name ??
      '—';

  List<Booking> get _visible {
    final rows = (_bookings ?? const <Booking>[]).where((b) {
      if (_staffFilter != null && b.operatorId != _staffFilter) return false;
      return true;
    }).toList()
      ..sort((a, b) => a.startsAt.compareTo(b.startsAt));
    return rows;
  }

  Future<void> _openDetails(Booking b) async {
    final updated = await showModalBottomSheet<Booking>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => BookingDetailsSheet(
        booking: b,
        serviceName: _serviceName,
        staffName: _staffName,
        bookingsService: _bookingsService,
        services: _services ?? const [],
        staff: _staff ?? const [],
      ),
    );
    if (updated != null && mounted) {
      setState(() {
        _bookings = [
          for (final row in _bookings ?? const <Booking>[])
            if (row.id == updated.id) updated else row,
        ];
      });
    }
  }

  Future<void> _openMonth() async {
    final picked = await showModalBottomSheet<DateTime>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => BookingMonthSheet(
        branchId: _branchId,
        initialMonth: _selectedDate,
        bookingsService: _bookingsService,
      ),
    );
    if (picked != null) {
      setState(() => _selectedDate = picked);
      _loadDay();
    }
  }

  Future<void> _openSettings() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => BookingSettingsSheet(
        bookingsService: _bookingsService,
        staff: _staff ?? const [],
      ),
    );
  }

  Future<void> _openNewBooking() async {
    final created = await showModalBottomSheet<Booking>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => NewBookingSheet(
        branchId: _branchId,
        date: _selectedDate,
        services: _services ?? const [],
        staff: _staff ?? const [],
        bookingsService: _bookingsService,
      ),
    );
    if (created != null && mounted) {
      final createdDay = DateTime.fromMillisecondsSinceEpoch(created.startsAt * 1000);
      if (dateKey(createdDay) == dateKey(_selectedDate)) {
        setState(() => _bookings = [...?_bookings, created]);
      } else {
        setState(() => _selectedDate = createdDay);
        _loadDay();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return KbAnchor(
      id: 'bookings',
      child: Scaffold(
      backgroundColor: context.isDark ? AppDarkColors.surface0 : AppColors.surface0,
      body: SafeArea(
        child: Column(
          children: [
            _Header(count: _visible.length, onSettings: _openSettings, onOpenMonth: _openMonth),
            _DateStrip(selected: _selectedDate, onChanged: _changeDate),
            if ((_staff ?? const []).isNotEmpty)
              KbAnchor(
                id: 'bookings.staff_filter',
                child: _StaffFilterRow(
                  staff: _staff!,
                  selected: _staffFilter,
                  onChanged: (id) => setState(() => _staffFilter = id),
                ),
              ),
            const SizedBox(height: AppSpacing.sm),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadDay,
                child: _loading
                    ? const AppLoadingIndicator()
                    : _failed
                        ? EmptyState(
                            icon: Icons.cloud_off_rounded,
                            title: 'تعذّر تحميل حجوزات اليوم',
                            message: 'اسحب للأسفل لإعادة المحاولة',
                            actionText: 'إعادة المحاولة',
                            onAction: _loadDay,
                          )
                        : _visible.isEmpty
                            ? ListView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                children: const [
                                  SizedBox(height: 80),
                                  EmptyState(
                                    icon: Icons.event_available_rounded,
                                    title: 'لا حجوزات بهذا اليوم',
                                    message: 'اضغط + لإضافة حجز جديد',
                                  ),
                                ],
                              )
                            : ListView.separated(
                                physics: const AlwaysScrollableScrollPhysics(),
                                padding: const EdgeInsets.fromLTRB(
                                    AppSpacing.md, 0, AppSpacing.md, 100),
                                itemCount: _visible.length,
                                separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                                itemBuilder: (context, i) {
                                  final b = _visible[i];
                                  return KbAnchor(
                                    id: 'bookings.booking_card',
                                    child: _BookingCard(
                                      booking: b,
                                      services: b.serviceIds.map(_serviceName).toList(),
                                      staffName: _staffName(b.operatorId),
                                      onTap: () => _openDetails(b),
                                    ),
                                  );
                                },
                              ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: CapabilityGate(
        requires: const ['bookings.create'],
        child: KbAnchor(
          id: 'bookings.new_button',
          child: RjSheen(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: FloatingActionButton(
              onPressed: _openNewBooking,
              backgroundColor: context.isDark ? AppDarkColors.accent : AppColors.accent,
              child: const Icon(Icons.add_rounded, color: Colors.white),
            ),
          ),
        ),
      ),
      ),
    );
  }
}

/// The date-key format every booking route on the wire uses — `YYYY-MM-DD`, the shop's own
/// business day.
String dateKey(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class _Header extends StatelessWidget {
  final int count;
  final VoidCallback onSettings;
  final VoidCallback onOpenMonth;
  const _Header({required this.count, required this.onSettings, required this.onOpenMonth});

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    return RjSheen(
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, AppSpacing.lg),
        decoration: BoxDecoration(gradient: primaryGradient(dark: dark)),
        child: Row(
          children: [
            KbAnchor(
              id: 'bookings.month_button',
              child: IconButton(
                icon: const Icon(Icons.calendar_month_rounded, color: Colors.white, size: 26),
                tooltip: 'عرض الشهر',
                onPressed: onOpenMonth,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('الحجوزات',
                      style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
                  Text('$count حجز اليوم', style: const TextStyle(color: Colors.white70, fontSize: 13)),
                ],
              ),
            ),
            KbAnchor(
              id: 'bookings.settings_button',
              child: IconButton(
                icon: const Icon(Icons.tune_rounded, color: Colors.white),
                tooltip: 'إعدادات الحجوزات',
                onPressed: onSettings,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DateStrip extends StatefulWidget {
  final DateTime selected;
  final ValueChanged<DateTime> onChanged;
  const _DateStrip({required this.selected, required this.onChanged});

  @override
  State<_DateStrip> createState() => _DateStripState();
}

class _DateStripState extends State<_DateStrip> {
  static const _weekdays = ['اثنين', 'ثلاثاء', 'أربعاء', 'خميس', 'جمعة', 'سبت', 'أحد'];
  static const _itemExtent = 60.0; // 52 width + 4*2 margin

  late final DateTime _start;
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    final today = DateTime.now();
    _start = DateTime(today.year, today.month, today.day).subtract(const Duration(days: 7));
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToSelected());
  }

  @override
  void didUpdateWidget(_DateStrip oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (dateKey(oldWidget.selected) != dateKey(widget.selected)) _scrollToSelected();
  }

  void _scrollToSelected() {
    if (!_scrollController.hasClients) return;
    final index = widget.selected.difference(_start).inDays;
    final viewport = _scrollController.position.viewportDimension;
    final target = (index * _itemExtent - viewport / 2 + _itemExtent / 2)
        .clamp(0.0, _scrollController.position.maxScrollExtent);
    _scrollController.animateTo(target, duration: AppMotion.base, curve: Curves.easeOut);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final today = DateTime.now();
    final start = _start;
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final selected = widget.selected;
    final onChanged = widget.onChanged;

    return SizedBox(
      height: 76,
      child: Row(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              itemCount: 30,
              itemBuilder: (context, i) {
                final d = start.add(Duration(days: i));
                final isSelected = dateKey(d) == dateKey(selected);
                final isToday = dateKey(d) == dateKey(today);
                return GestureDetector(
                  onTap: () => onChanged(d),
                  child: AnimatedContainer(
                    duration: AppMotion.fast,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: 52,
                    decoration: BoxDecoration(
                      gradient: isSelected ? primaryGradient(dark: context.isDark) : null,
                      color: isSelected ? null : colors.surface,
                      borderRadius: AppRadius.cardRadius,
                      border: Border.all(
                          color: isSelected ? Colors.transparent : (isToday ? accent : colors.borderSubtle),
                          width: isToday && !isSelected ? 1.5 : 1),
                      boxShadow: isSelected ? AppShadows.button : null,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(_weekdays[d.weekday - 1],
                            style: AppTextStyles.caption.copyWith(
                                color: isSelected ? Colors.white70 : colors.textSecondary)),
                        const SizedBox(height: 2),
                        Text('${d.day}',
                            style: AppTextStyles.headlineSmall.copyWith(
                                color: isSelected ? Colors.white : colors.textPrimary)),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(left: AppSpacing.sm),
            child: KbAnchor(
              id: 'bookings.today_button',
              child: IconButton(
                icon: Icon(Icons.today_rounded, color: accent),
                tooltip: 'اذهب لليوم',
                onPressed: () => onChanged(DateTime.now()),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StaffFilterRow extends StatelessWidget {
  final List<BranchTeamMember> staff;
  final String? selected;
  final ValueChanged<String?> onChanged;
  const _StaffFilterRow({required this.staff, required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: SegmentedFilter<String?>(
        value: selected,
        onChanged: onChanged,
        options: [
          const SegmentedFilterOption(value: null, label: 'الكل'),
          for (final s in staff) SegmentedFilterOption(value: s.id, label: s.name),
        ],
      ),
    );
  }
}

class _BookingCard extends StatelessWidget {
  final Booking booking;
  final List<String> services;
  final String staffName;
  final VoidCallback onTap;
  const _BookingCard({
    required this.booking,
    required this.services,
    required this.staffName,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final tone = bookingStatusTone(booking.status, context.isDark);
    final time = TimeOfDay.fromDateTime(
        DateTime.fromMillisecondsSinceEpoch(booking.startsAt * 1000));
    final timeText = time.format(context);

    return Container(
      decoration: BoxDecoration(
        borderRadius: AppRadius.cardRadius,
        boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Material(
        color: context.appColors.surface,
        borderRadius: AppRadius.cardRadius,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.cardRadius,
          child: IntrinsicHeight(
            child: Row(
              children: [
                Container(
                  width: 6,
                  decoration: BoxDecoration(
                    color: tone.color,
                    borderRadius: const BorderRadius.horizontal(left: Radius.circular(AppRadius.card)),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(timeText,
                                style: AppTextStyles.labelMedium.copyWith(
                                    color: context.appColors.textPrimary,
                                    fontFeatures: const [FontFeature.tabularFigures()])),
                            const SizedBox(width: AppSpacing.sm),
                            AppBadge(text: tone.label, backgroundColor: tone.soft, textColor: tone.color),
                            const Spacer(),
                            if (booking.paymentStatus != 'none')
                              Icon(Icons.payments_rounded, size: 16, color: context.appColors.textMuted),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(services.join(' + '),
                            style: AppTextStyles.bodyMedium.copyWith(color: context.appColors.textPrimary),
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(Icons.person_outline, size: 14, color: context.appColors.textMuted),
                            const SizedBox(width: 4),
                            Text(staffName,
                                style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary)),
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
      ),
    );
  }
}
