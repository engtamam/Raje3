import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/auth_service.dart' show BranchTeamMember;
import 'package:raje3_mobile/core/services/bookings_service.dart';
import 'package:raje3_mobile/models/booking_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

import 'booking_status.dart';
import 'new_booking_sheet.dart';

/// Details + actions for one booking — mobile mirror of Bookings.tsx's own `BookingActions`
/// sheet (attend/no-show/cancel), plus an edit entry point that reopens [NewBookingSheet] in
/// edit mode (reuses the exact same conflict/slot logic a fresh booking uses, never a second
/// implementation of "who can cover this basket").
class BookingDetailsSheet extends StatefulWidget {
  final Booking booking;
  final String Function(String serviceId) serviceName;
  final String Function(String operatorId) staffName;
  final BookingsService bookingsService;
  final List<ServiceItem> services;
  final List<BranchTeamMember> staff;

  const BookingDetailsSheet({
    super.key,
    required this.booking,
    required this.serviceName,
    required this.staffName,
    required this.bookingsService,
    required this.services,
    required this.staff,
  });

  @override
  State<BookingDetailsSheet> createState() => _BookingDetailsSheetState();
}

class _BookingDetailsSheetState extends State<BookingDetailsSheet> {
  bool _busy = false;

  Future<void> _act(Future<Booking?> Function() fn) async {
    setState(() => _busy = true);
    final updated = await fn();
    if (!mounted) return;
    setState(() => _busy = false);
    if (updated != null) Navigator.of(context).pop(updated);
  }

  Future<void> _editViaFullSheet() async {
    final result = await showModalBottomSheet<Booking>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => NewBookingSheet(
        branchId: widget.booking.branchId,
        date: DateTime.fromMillisecondsSinceEpoch(widget.booking.startsAt * 1000),
        services: widget.services,
        staff: widget.staff,
        bookingsService: widget.bookingsService,
        editing: widget.booking,
      ),
    );
    if (result != null && mounted) Navigator.of(context).pop(result);
  }

  @override
  Widget build(BuildContext context) {
    final b = widget.booking;
    final colors = context.appColors;
    final tone = bookingStatusTone(b.status, context.isDark);
    final time = TimeOfDay.fromDateTime(DateTime.fromMillisecondsSinceEpoch(b.startsAt * 1000));

    return Container(
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
                  child: Wrap(
                    spacing: 6,
                    children: b.serviceIds
                        .map((id) => AppBadge(text: widget.serviceName(id)))
                        .toList(),
                  ),
                ),
                AppBadge(text: tone.label, backgroundColor: tone.soft, textColor: tone.color),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            _row(Icons.access_time_rounded, '${time.format(context)} · ${b.durationMinutes} د'),
            _row(Icons.person_outline, widget.staffName(b.operatorId)),
            if (b.paymentStatus != 'none')
              _row(Icons.payments_rounded,
                  b.paymentStatus == 'deposit'
                      ? 'عربون ${((b.depositAmountMinor ?? 0) / 100).toStringAsFixed(0)} ر.س'
                      : 'مدفوع'),
            if (b.note.isNotEmpty) _row(Icons.note_outlined, b.note),
            const SizedBox(height: AppSpacing.lg),
            if (b.status == 'booked') ...[
              KbAnchor(
                id: 'bookings.details.status_actions',
                child: CapabilityGate(
                  requires: const ['bookings.create'],
                  child: Row(
                    children: [
                      Expanded(
                        child: SecondaryButton(
                          text: 'تعديل', icon: Icons.edit_outlined,
                          onPressed: _busy ? null : _editViaFullSheet,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: SecondaryButton(
                          text: 'حضر', icon: Icons.check_circle_outline,
                          onPressed: _busy ? null : () => _act(() => widget.bookingsService.attend(b.id)),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              KbAnchor(
                id: 'bookings.details.negative_actions',
                child: CapabilityGate(
                  requires: const ['bookings.create'],
                  child: Row(
                    children: [
                      Expanded(
                        child: SecondaryButton(
                          text: 'لم يحضر', icon: Icons.close_rounded,
                          onPressed: _busy ? null : () => _act(() => widget.bookingsService.noShow(b.id)),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: SecondaryButton(
                          text: 'إلغاء', icon: Icons.delete_outline,
                          onPressed: _busy ? null : () => _act(() => widget.bookingsService.cancel(b.id)),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ] else
              Text('لا إجراءات إضافية — الحجز ${tone.label}',
                  style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
          ],
        ),
      ),
    );
  }

  Widget _row(IconData icon, String text) {
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, size: 16, color: colors.textMuted),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary))),
        ],
      ),
    );
  }
}
