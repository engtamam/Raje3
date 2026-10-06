import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/coworking_service.dart';
import 'package:raje3_mobile/models/coworking_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «الحجوزات» for ONE resource — opened from its own card's own button, same
/// `booking_details_sheet.dart` pattern (a sheet, never a third tab on the main screen).
class CoworkingBookingsSheet extends StatefulWidget {
  const CoworkingBookingsSheet({super.key, required this.service, required this.resource});
  final CoworkingService service;
  final CoworkingResource resource;

  @override
  State<CoworkingBookingsSheet> createState() => _CoworkingBookingsSheetState();
}

class _CoworkingBookingsSheetState extends State<CoworkingBookingsSheet> {
  List<CoworkingBooking>? _bookings;
  bool _failed = false;
  final Set<String> _cancelling = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _bookings = null;
      _failed = false;
    });
    final rows = await widget.service.listBookings(resourceId: widget.resource.id);
    if (!mounted) return;
    setState(() {
      _bookings = rows;
      _failed = rows == null;
    });
  }

  Future<void> _cancel(CoworkingBooking b) async {
    setState(() => _cancelling.add(b.id));
    await widget.service.cancelBooking(b.id);
    if (!mounted) return;
    setState(() => _cancelling.remove(b.id));
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(width: 40, height: 4,
                decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Expanded(
                  child: Text('حجوزات ${widget.resource.name}', style: AppTextStyles.headlineSmall),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Flexible(child: _body()),
          ],
        ),
      ),
    );
  }

  Widget _body() {
    final colors = context.appColors;
    if (_bookings == null) {
      return const Padding(padding: EdgeInsets.all(AppSpacing.xl), child: AppLoadingIndicator());
    }
    if (_failed) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: EmptyState(icon: Icons.cloud_off_rounded, title: 'تعذر تحميل الحجوزات', actionText: 'إعادة المحاولة', onAction: _load),
      );
    }
    if (_bookings!.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(AppSpacing.xl),
        child: EmptyState(icon: Icons.event_busy_outlined, title: 'لا يوجد حجوزات على هذا المورد'),
      );
    }
    final sorted = [..._bookings!]..sort((a, b) => b.startsAt.compareTo(a.startsAt));
    return ListView.separated(
      shrinkWrap: true,
      itemCount: sorted.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, i) {
        final b = sorted[i];
        final start = DateTime.fromMillisecondsSinceEpoch(b.startsAt * 1000);
        final end = DateTime.fromMillisecondsSinceEpoch(b.endsAt * 1000);
        final cancelled = b.status == 'cancelled';
        return Container(
          decoration: BoxDecoration(
            color: colors.surfaceAlt,
            borderRadius: AppRadius.cardRadius,
          ),
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(b.freelancerPhone, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                    Text(
                      '${_fmt(start)} - ${_fmt(end)}',
                      style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
                    ),
                    Text('${(b.hourlyPriceMinor / 100).toStringAsFixed(0)} ر.س / ساعة',
                        style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                  ],
                ),
              ),
              if (cancelled)
                AppBadge(text: 'ملغى', backgroundColor: colors.surface, textColor: colors.textMuted)
              else
                CapabilityGate(
                  requires: const ['coworking.cancel_booking'],
                  child: KbAnchor(
                    id: 'coworking.bookings_sheet.cancel',
                    child: SecondaryButton(
                      text: 'إلغاء',
                      icon: Icons.close_rounded,
                      onPressed: _cancelling.contains(b.id) ? null : () => _cancel(b),
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  String _fmt(DateTime t) =>
      '${t.year}/${t.month.toString().padLeft(2, '0')}/${t.day.toString().padLeft(2, '0')} '
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}
