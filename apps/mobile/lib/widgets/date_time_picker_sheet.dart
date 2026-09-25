import 'package:flutter/material.dart';
import 'package:intl/intl.dart' hide TextDirection;

import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

// arabic-indic-digits: intentional — names the exact glyphs the bug below produced.
/// A calendar + time picker built ENTIRELY from our own widgets — never Flutter's stock
/// `showDatePicker`/`showTimePicker`. Found live: Flutter's bundled `MaterialLocalizationAr`
/// hardcodes Eastern Arabic-Indic digits (the day grid showed "٢٢") regardless of this app's own
/// Formatters/intl choices, which both correctly give Western digits for 'ar' — the bug is
/// specific to Flutter's own generated Material picker widgets, not to intl. Plain Dart string
/// interpolation (`'$day'`) is never locale-converted, so a fully custom picker sidesteps the bug
/// by construction rather than working around it.
Future<DateTime?> pickDaySheet(
  BuildContext context, {
  DateTime? initial,
  required DateTime firstDate,
  required DateTime lastDate,
}) {
  return showModalBottomSheet<DateTime>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _DayPickerSheet(initial: initial, firstDate: firstDate, lastDate: lastDate),
  );
}

Future<TimeOfDay?> pickTimeSheet(BuildContext context, {TimeOfDay? initial}) {
  return showModalBottomSheet<TimeOfDay>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _TimePickerSheet(initial: initial),
  );
}

class _DayPickerSheet extends StatefulWidget {
  const _DayPickerSheet({this.initial, required this.firstDate, required this.lastDate});
  final DateTime? initial;
  final DateTime firstDate;
  final DateTime lastDate;

  @override
  State<_DayPickerSheet> createState() => _DayPickerSheetState();
}

class _DayPickerSheetState extends State<_DayPickerSheet> {
  late DateTime _month;
  DateTime? _selected;

  @override
  void initState() {
    super.initState();
    final base = widget.initial ?? widget.firstDate;
    _month = DateTime(base.year, base.month, 1);
    _selected = widget.initial;
  }

  bool get _canGoPrev => !DateTime(_month.year, _month.month, 0).isBefore(widget.firstDate);
  bool get _canGoNext => !DateTime(_month.year, _month.month + 1, 1).isAfter(widget.lastDate);

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.localeOf(context).languageCode;
    // NEVER DateFormat.yMMMM/.y — on Flutter web this can fall through to the browser's own
    // native Intl engine, which (unlike this package's bundled ICU data) renders 'ar' digits as
    // Eastern Arabic-Indic. Only the MONTH NAME comes from intl (pure text, no digit risk); the
    // year is plain Dart interpolation, always ASCII.
    final monthLabel = '${DateFormat.MMMM(locale).format(_month)} ${_month.year}';
    // 2024-01-07 is a known Sunday — a fixed anchor to read this locale's own weekday order from,
    // regardless of which day .weekday itself considers "first".
    final weekdayLabels =
        List.generate(7, (i) => DateFormat.E(locale).format(DateTime(2024, 1, 7 + i)));
    final firstWeekday = DateTime(_month.year, _month.month, 1).weekday % 7; // 0=Sun
    final daysInMonth = DateTime(_month.year, _month.month + 1, 0).day;

    return Container(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
      decoration: const BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              IconButton(
                onPressed: _canGoPrev
                    ? () => setState(() => _month = DateTime(_month.year, _month.month - 1, 1))
                    : null,
                // Same body-level chevron mapping AppBackButton itself verified live: RTL points
                // this "previous" control left, LTR right — never the opposite AppBar-leading
                // swap, which reads backwards in this build.
                icon: Icon(Directionality.of(context) == TextDirection.rtl
                    ? Icons.chevron_left_rounded
                    : Icons.chevron_right_rounded),
              ),
              Expanded(
                child: Text(monthLabel,
                    textAlign: TextAlign.center, style: AppTextStyles.labelMedium)),
              IconButton(
                onPressed: _canGoNext
                    ? () => setState(() => _month = DateTime(_month.year, _month.month + 1, 1))
                    : null,
                icon: Icon(Directionality.of(context) == TextDirection.rtl
                    ? Icons.chevron_right_rounded
                    : Icons.chevron_left_rounded),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: [
              for (final w in weekdayLabels)
                Expanded(
                  child: Center(
                    child: Text(w,
                        style: AppTextStyles.caption.copyWith(color: AppColors.textMuted)),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          GridView.count(
            crossAxisCount: 7,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              for (var i = 0; i < firstWeekday; i++) const SizedBox.shrink(),
              for (var day = 1; day <= daysInMonth; day++) _dayCell(day),
            ],
          ),
        ],
      ),
    );
  }

  Widget _dayCell(int day) {
    final date = DateTime(_month.year, _month.month, day);
    final first = DateTime(widget.firstDate.year, widget.firstDate.month, widget.firstDate.day);
    final disabled = date.isBefore(first) || date.isAfter(widget.lastDate);
    final isSelected = _selected != null &&
        _selected!.year == date.year &&
        _selected!.month == date.month &&
        _selected!.day == date.day;
    return Padding(
      padding: const EdgeInsets.all(2),
      child: Material(
        color: isSelected ? AppColors.accent : Colors.transparent,
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: disabled ? null : () => Navigator.of(context).pop(date),
          child: Center(
            child: Text(
              '$day',
              style: AppTextStyles.bodyMedium.copyWith(
                color: isSelected
                    ? AppColors.accentContrast
                    : (disabled ? AppColors.textMuted.withValues(alpha: 0.4) : AppColors.textPrimary),
                fontWeight: isSelected ? FontWeight.w800 : FontWeight.w500,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TimePickerSheet extends StatefulWidget {
  const _TimePickerSheet({this.initial});
  final TimeOfDay? initial;

  @override
  State<_TimePickerSheet> createState() => _TimePickerSheetState();
}

class _TimePickerSheetState extends State<_TimePickerSheet> {
  late int _hour;
  late int _minute;

  @override
  void initState() {
    super.initState();
    final now = TimeOfDay.now();
    _hour = widget.initial?.hour ?? now.hour;
    final m = widget.initial?.minute ?? (now.minute - now.minute % 15);
    _minute = [0, 15, 30, 45].reduce((a, b) => (m - a).abs() <= (m - b).abs() ? a : b);
  }

  static String _pad2(int n) => n.toString().padLeft(2, '0');

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
      decoration: const BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _NumberWheelColumn(
                value: _hour,
                min: 0,
                max: 23,
                label: _pad2,
                onChanged: (v) => _hour = v,
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Text(':', style: AppTextStyles.headlineSmall),
              ),
              _NumberWheelColumn(
                value: _minute,
                min: 0,
                max: 45,
                step: 15,
                label: _pad2,
                onChanged: (v) => _minute = v,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          PrimaryButton(
            text: MaterialLocalizations.of(context).okButtonLabel,
            onPressed: () =>
                Navigator.of(context).pop(TimeOfDay(hour: _hour, minute: _minute)),
          ),
        ],
      ),
    );
  }
}

/// A single scrollable wheel of numbers — every label a plain Dart string, never run through
/// [MaterialLocalizations].
class _NumberWheelColumn extends StatefulWidget {
  const _NumberWheelColumn({
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    required this.label,
    this.step = 1,
  });

  final int value;
  final int min;
  final int max;
  final int step;
  final ValueChanged<int> onChanged;
  final String Function(int) label;

  @override
  State<_NumberWheelColumn> createState() => _NumberWheelColumnState();
}

class _NumberWheelColumnState extends State<_NumberWheelColumn> {
  late final FixedExtentScrollController _controller;
  late final List<int> _values;

  @override
  void initState() {
    super.initState();
    _values = [for (var v = widget.min; v <= widget.max; v += widget.step) v];
    final idx = _values.indexOf(widget.value).clamp(0, _values.length - 1);
    _controller = FixedExtentScrollController(initialItem: idx);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 72,
      height: 140,
      child: ListWheelScrollView.useDelegate(
        controller: _controller,
        itemExtent: 44,
        perspective: 0.003,
        diameterRatio: 1.4,
        physics: const FixedExtentScrollPhysics(),
        onSelectedItemChanged: (i) => widget.onChanged(_values[i]),
        childDelegate: ListWheelChildBuilderDelegate(
          childCount: _values.length,
          builder: (context, i) => Center(
            child: Text(
              widget.label(_values[i]),
              style: AppTextStyles.headlineSmall
                  .copyWith(fontFeatures: const [FontFeature.tabularFigures()]),
            ),
          ),
        ),
      ),
    );
  }
}
