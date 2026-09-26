import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/bookings_service.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

import 'bookings_screen.dart' show dateKey;

/// One month, jump-to-any-day — merges the two directions the owner asked for after comparing
/// them: a plain dot only says "something happened," a bare colour heatmap needs a legend to
/// read; this cell carries BOTH the intensity tint (busiest days read at a glance, relative to
/// the busiest day THIS month) and the real count as a number (an actionable fact, never a
/// guess). Four bands off the SAME accent token already used everywhere else in this app — no
/// new colour invented for this one screen.
class BookingMonthSheet extends StatefulWidget {
  final String branchId;
  final DateTime initialMonth;
  final BookingsService bookingsService;

  const BookingMonthSheet({
    super.key,
    required this.branchId,
    required this.initialMonth,
    required this.bookingsService,
  });

  @override
  State<BookingMonthSheet> createState() => _BookingMonthSheetState();
}

class _BookingMonthSheetState extends State<BookingMonthSheet> {
  late DateTime _month; // first day of the shown month
  Map<String, int>? _counts;
  bool _failed = false;

  static const _weekdayHeaders = ['أحد', 'اثنين', 'ثلاثاء', 'أربعاء', 'خميس', 'جمعة', 'سبت'];
  static const _monthNames = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
  ];

  @override
  void initState() {
    super.initState();
    _month = DateTime(widget.initialMonth.year, widget.initialMonth.month, 1);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _counts = null;
      _failed = false;
    });
    final start = _month;
    final end = DateTime(_month.year, _month.month + 1, 0);
    final rows = await widget.bookingsService.counts(
      branchId: widget.branchId, start: dateKey(start), end: dateKey(end),
    );
    if (!mounted) return;
    setState(() {
      _counts = rows;
      _failed = rows == null;
    });
  }

  void _changeMonth(int delta) {
    setState(() => _month = DateTime(_month.year, _month.month + delta, 1));
    _load();
  }

  /// Sunday-first grid, matching booking_settings_sheet.dart's own weekday convention — the
  /// number of blank leading cells before day 1 lands on the right column.
  int get _leadingBlanks => (_month.weekday % 7);

  int get _daysInMonth => DateTime(_month.year, _month.month + 1, 0).day;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final today = DateTime.now();
    final maxCount = (_counts ?? const {}).values.isEmpty
        ? 0
        : (_counts ?? const {}).values.reduce((a, b) => a > b ? a : b);

    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              KbAnchor(
                id: 'bookings.month_sheet.month_nav',
                child: IconButton(
                  icon: const Icon(Icons.chevron_right_rounded),
                  onPressed: () => _changeMonth(-1),
                ),
              ),
              Text('${_monthNames[_month.month - 1]} ${_month.year}',
                  style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary)),
              KbAnchor(
                id: 'bookings.month_sheet.month_nav',
                child: IconButton(
                  icon: const Icon(Icons.chevron_left_rounded),
                  onPressed: () => _changeMonth(1),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              for (final h in _weekdayHeaders)
                Expanded(
                  child: Center(
                    child: Text(h, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (_failed)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
              child: EmptyState(
                icon: Icons.cloud_off_rounded,
                title: 'تعذّر تحميل عدد الحجوزات',
                actionText: 'إعادة المحاولة',
                onAction: _load,
              ),
            )
          else if (_counts == null)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
              child: AppLoadingIndicator(),
            )
          else
            KbAnchor(
              id: 'bookings.month_sheet.day_cell',
              child: GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 7,
                  mainAxisSpacing: 6,
                  crossAxisSpacing: 6,
                  childAspectRatio: 1,
                ),
                itemCount: _leadingBlanks + _daysInMonth,
                itemBuilder: (context, i) {
                  if (i < _leadingBlanks) return const SizedBox.shrink();
                  final day = i - _leadingBlanks + 1;
                  final date = DateTime(_month.year, _month.month, day);
                  final count = _counts![dateKey(date)] ?? 0;
                  final isToday = dateKey(date) == dateKey(today);
                  return _DayCell(
                    day: day,
                    count: count,
                    maxCount: maxCount,
                    isToday: isToday,
                    onTap: () => Navigator.of(context).pop(date),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}

class _DayCell extends StatelessWidget {
  final int day;
  final int count;
  final int maxCount;
  final bool isToday;
  final VoidCallback onTap;

  const _DayCell({
    required this.day,
    required this.count,
    required this.maxCount,
    required this.isToday,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final colors = context.appColors;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;
    final accentSoft = dark ? AppDarkColors.accentSoft : AppColors.accentSoft;
    final accentOnSoft = dark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft;

    // Four bands off the SAME accent token, relative to the busiest day this month —
    // never a fixed absolute threshold, so a quiet shop and a packed one both read correctly.
    final share = maxCount == 0 ? 0.0 : count / maxCount;
    final Color background;
    final Color foreground;
    if (count == 0) {
      background = Colors.transparent;
      foreground = colors.textMuted;
    } else if (share <= 0.33) {
      background = accentSoft;
      foreground = accentOnSoft;
    } else if (share <= 0.66) {
      background = accent.withValues(alpha: 0.55);
      foreground = Colors.white;
    } else {
      background = accent;
      foreground = Colors.white;
    }

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: isToday ? Border.all(color: accent, width: 1.5) : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('$day',
                style: AppTextStyles.bodySmall.copyWith(color: foreground, fontWeight: FontWeight.w600)),
            if (count > 0)
              Text('$count',
                  style: AppTextStyles.caption.copyWith(color: foreground, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}
