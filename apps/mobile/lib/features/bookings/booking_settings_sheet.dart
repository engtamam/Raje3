import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/auth_service.dart' show BranchTeamMember, DayHours, WorkingHours;
import 'package:raje3_mobile/core/services/bookings_service.dart';
import 'package:raje3_mobile/models/booking_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/date_time_picker_sheet.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «إعدادات الحجوزات» — mobile mirror of apps/console/src/screens/BookingSettingsDialog.tsx:
/// ONE shop-wide weekly policy (never a single employee's own hours — that's a completely
/// different route, already built at account.shop.branches.detail.edit_member.working_hours),
/// and the "auto" tie-breaker among an "auto" service's several eligible operators.
///
/// OPENED FROM INSIDE THE BOOKINGS SCREEN ITSELF (a settings icon, same as the console's own
/// gear button beside its filter row) — NEVER from "منشأتي"/team settings. Confirmed against
/// Bookings.tsx before building this: the gear icon lives in that screen's own header.
///
/// NO CAPABILITY GATE ON EITHER SAVE BUTTON, ON PURPOSE — both PATCH routes enforce
/// `bookings.manage`, a capability the catalogue never declares an action id for (same
/// documented gap as BookingSettingsDialog.tsx's own two save buttons; see
/// ci/check_action_level_gating.py's EXEMPT entry for this file). The backend still refuses
/// safely either way.
class BookingSettingsSheet extends StatefulWidget {
  final BookingsService bookingsService;
  final List<BranchTeamMember> staff;

  const BookingSettingsSheet({super.key, required this.bookingsService, required this.staff});

  @override
  State<BookingSettingsSheet> createState() => _BookingSettingsSheetState();
}

// Sunday-first, same order the console's own DISPLAY_ORDER uses — the shop's own week starts
// Sunday, even though day 0 in the wire format is Monday (Python's `date.weekday()`).
const _kDisplayOrder = [6, 0, 1, 2, 3, 4, 5];
const _kDayLabels = ['اثنين', 'ثلاثاء', 'أربعاء', 'خميس', 'جمعة', 'سبت', 'أحد'];
const _kDefaultStart = 8 * 60;
const _kDefaultEnd = 22 * 60;

const _kAlgorithms = [
  (value: 'nearest', label: 'الأقرب', hint: 'يختار العامل الأقرب دوره لهذا الوقت.'),
  (value: 'least_loaded', label: 'الأقل حجوزات', hint: 'يختار العامل الأقل ازدحامًا هذا اليوم.'),
  (value: 'manual_order', label: 'ترتيب يدوي', hint: 'يختار حسب الترتيب اللي تحدّده أدناه.'),
];

class _BookingSettingsSheetState extends State<BookingSettingsSheet> {
  String _tab = 'hours';
  bool _loading = true;
  bool _failed = false;

  Map<int, DayHours> _days = {};
  bool _hoursSaving = false;
  String? _hoursError;

  String _algorithm = 'nearest';
  List<String> _manualOrder = [];
  bool _assignSaving = false;
  String? _assignError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final hours = await widget.bookingsService.workingHours();
    final assignment = await widget.bookingsService.assignmentSettings();
    if (!mounted) return;
    if (hours == null || assignment == null) {
      setState(() {
        _loading = false;
        _failed = true;
      });
      return;
    }
    setState(() {
      _loading = false;
      _days = {
        for (var i = 0; i < 7; i++)
          i: hours.weekly['$i'] ??
              const DayHours(closed: false, startMinute: _kDefaultStart, endMinute: _kDefaultEnd),
      };
      _algorithm = assignment.algorithm;
      _manualOrder = List.of(assignment.manualOrder);
    });
  }

  static String _label(int minutes) =>
      '${(minutes ~/ 60).toString().padLeft(2, '0')}:${(minutes % 60).toString().padLeft(2, '0')}';

  Future<void> _pickTime(int day, {required bool isStart}) async {
    final current = _days[day]!;
    final initial = TimeOfDay(
        hour: (isStart ? current.startMinute : current.endMinute) ~/ 60,
        minute: (isStart ? current.startMinute : current.endMinute) % 60);
    final picked = await pickTimeSheet(context, initial: initial);
    if (picked == null) return;
    final minutes = picked.hour * 60 + picked.minute;
    setState(() {
      _days[day] =
          isStart ? current.copyWith(startMinute: minutes) : current.copyWith(endMinute: minutes);
    });
  }

  Future<void> _saveHours() async {
    setState(() {
      _hoursSaving = true;
      _hoursError = null;
    });
    final saved = await widget.bookingsService
        .setWorkingHours(WorkingHours(weekly: {for (final e in _days.entries) '${e.key}': e.value}));
    if (!mounted) return;
    if (saved != null) {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _hoursSaving = false;
      _hoursError = 'تعذّر حفظ ساعات العمل';
    });
  }

  List<BranchTeamMember> get _ordered {
    final byId = {for (final s in widget.staff) s.id: s};
    final rows = [
      for (final id in _manualOrder)
        if (byId[id] != null) byId[id]!,
      for (final s in widget.staff)
        if (!_manualOrder.contains(s.id)) s,
    ];
    return rows;
  }

  void _move(String id, int dir) {
    final current = _ordered.map((s) => s.id).toList();
    final i = current.indexOf(id);
    final j = i + dir;
    if (i < 0 || j < 0 || j >= current.length) return;
    final tmp = current[i];
    current[i] = current[j];
    current[j] = tmp;
    setState(() => _manualOrder = current);
  }

  Future<void> _saveAssignment() async {
    setState(() {
      _assignSaving = true;
      _assignError = null;
    });
    final saved = await widget.bookingsService
        .setAssignmentSettings(AssignmentSettings(algorithm: _algorithm, manualOrder: _manualOrder));
    if (!mounted) return;
    if (saved != null) {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _assignSaving = false;
      _assignError = 'تعذّر حفظ طريقة التوزيع';
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: _loading
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.xxl), child: AppLoadingIndicator())
          : _failed
              ? Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
                  child: EmptyState(
                    icon: Icons.settings_outlined,
                    title: 'تعذّر تحميل إعدادات الحجوزات',
                    actionText: 'إعادة المحاولة',
                    onAction: () {
                      setState(() => _loading = true);
                      _load();
                    },
                  ),
                )
              : SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('إعدادات الحجوزات', style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary)),
                      const SizedBox(height: AppSpacing.md),
                      KbAnchor(
                        id: 'bookings.settings.tabs',
                        child: SegmentedFilter<String>(
                          value: _tab,
                          onChanged: (v) => setState(() => _tab = v),
                          options: const [
                            SegmentedFilterOption(value: 'hours', label: 'ساعات العمل'),
                            SegmentedFilterOption(value: 'assignment', label: 'طريقة التوزيع'),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      if (_tab == 'hours') ..._hoursTab() else ..._assignmentTab(),
                    ],
                  ),
                ),
    );
  }

  List<Widget> _hoursTab() {
    final colors = context.appColors;
    return [
      Text('ساعات فتح الحجوزات للمحل — تُطبَّق على كل الفروع.',
          style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted)),
      const SizedBox(height: AppSpacing.md),
      for (final day in _kDisplayOrder)
        KbAnchor(
          id: 'bookings.settings.hours.time_pickers',
          child: Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Row(
              children: [
                SizedBox(width: 56, child: Text(_kDayLabels[day], style: AppTextStyles.bodySmall)),
                Switch(
                  value: !_days[day]!.closed,
                  onChanged: (open) => setState(() => _days[day] = _days[day]!.copyWith(closed: !open)),
                ),
                if (!_days[day]!.closed) ...[
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _pickTime(day, isStart: true),
                      child: Text(_label(_days[day]!.startMinute)),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Text('—'),
                  const SizedBox(width: 6),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _pickTime(day, isStart: false),
                      child: Text(_label(_days[day]!.endMinute)),
                    ),
                  ),
                ] else
                  Expanded(
                    child: Text('مغلق', textAlign: TextAlign.center,
                        style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted)),
                  ),
              ],
            ),
          ),
        ),
      if (_hoursError != null) ...[
        const SizedBox(height: AppSpacing.sm),
        AppAlert(type: AlertType.error, message: _hoursError!),
      ],
      const SizedBox(height: AppSpacing.lg),
      KbAnchor(
        id: 'bookings.settings.hours.save',
        child: PrimaryButton(text: 'حفظ', isLoading: _hoursSaving, onPressed: _hoursSaving ? null : _saveHours),
      ),
    ];
  }

  List<Widget> _assignmentTab() {
    final colors = context.appColors;
    final hint = _kAlgorithms.firstWhere((a) => a.value == _algorithm).hint;
    return [
      Text('كيف يُختار العامل تلقائيًا لخدمة "توزيع تلقائي" بين أكثر من موظف مؤهل.',
          style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted)),
      const SizedBox(height: AppSpacing.md),
      KbAnchor(
        id: 'bookings.settings.assignment.algorithm',
        child: SegmentedFilter<String>(
          value: _algorithm,
          onChanged: (v) => setState(() => _algorithm = v),
          options: [for (final a in _kAlgorithms) SegmentedFilterOption(value: a.value, label: a.label)],
        ),
      ),
      const SizedBox(height: AppSpacing.sm),
      Text(hint, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
      if (_algorithm == 'manual_order') ...[
        const SizedBox(height: AppSpacing.md),
        if (widget.staff.isEmpty)
          Text('ما فيه موظفين ميدانيين بعد', style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted))
        else
          KbAnchor(
            id: 'bookings.settings.assignment.manual_order',
            child: Column(
              children: [
                for (var i = 0; i < _ordered.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        Icon(Icons.drag_indicator, size: 16, color: colors.textMuted),
                        const SizedBox(width: 6),
                        Expanded(child: Text(_ordered[i].name, style: AppTextStyles.bodySmall.copyWith(color: colors.textPrimary))),
                        IconButton(
                          icon: const Icon(Icons.arrow_upward_rounded, size: 18),
                          onPressed: i == 0 ? null : () => _move(_ordered[i].id, -1),
                        ),
                        IconButton(
                          icon: const Icon(Icons.arrow_downward_rounded, size: 18),
                          onPressed: i == _ordered.length - 1 ? null : () => _move(_ordered[i].id, 1),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
      ],
      if (_assignError != null) ...[
        const SizedBox(height: AppSpacing.sm),
        AppAlert(type: AlertType.error, message: _assignError!),
      ],
      const SizedBox(height: AppSpacing.lg),
      KbAnchor(
        id: 'bookings.settings.assignment.save',
        child: PrimaryButton(text: 'حفظ', isLoading: _assignSaving, onPressed: _assignSaving ? null : _saveAssignment),
      ),
    ];
  }
}
