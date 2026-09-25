import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/ratings_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/rating_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// The mobile-native reduction of the console's own «الرباعية» bubble-plot: quality (average
/// rating) against engagement (ratings/visits%), bubble size = visit volume, the SAME real
/// fields `staff_performance` already returns — no separate fetch. Fixed thresholds (3.5★,
/// 50% engagement) split the plane into four real, named zones rather than a bare scatter a
/// phone screen has no room to caption with axis numbers alone.
class StaffQuadrantCard extends StatelessWidget {
  const StaffQuadrantCard({super.key, required this.staff, required this.service});
  final List<StaffPerformance> staff;
  final RatingsService service;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    final canDrillDown = catalog.hasAll(['operations.list_operator_step_stats']);
    final points = staff.where((x) => x.visits > 0).toList();
    if (points.isEmpty) return const SizedBox.shrink();
    final maxVisits = points.map((p) => p.visits).reduce((a, b) => a > b ? a : b);

    return KbAnchor(
      id: 'rating.quadrant',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.ratingQuadrantTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: 2),
            Text(s.ratingQuadrantHint,
                style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted)),
            const SizedBox(height: AppSpacing.sm),
            AspectRatio(
              aspectRatio: 1.1,
              child: _QuadrantPlot(
                points: points,
                maxVisits: maxVisits,
                onTapPoint: (p) => _openDetail(context, p, canDrillDown),
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: 4,
              children: [
                _LegendDot(color: _quadrantColor(context, _Quadrant.stars), label: s.ratingQuadrantStars),
                _LegendDot(
                    color: _quadrantColor(context, _Quadrant.underused), label: s.ratingQuadrantUnderused),
                _LegendDot(
                    color: _quadrantColor(context, _Quadrant.needsCoaching),
                    label: s.ratingQuadrantNeedsCoaching),
                _LegendDot(color: _quadrantColor(context, _Quadrant.atRisk), label: s.ratingQuadrantAtRisk),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openDetail(BuildContext context, StaffPerformance p, bool canDrillDown) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _OperatorTrainingSheet(
        performance: p,
        service: canDrillDown ? service : null,
      ),
    );
  }
}

enum _Quadrant { stars, underused, needsCoaching, atRisk }

_Quadrant _quadrantOf(StaffPerformance p) {
  final engagement = p.visits > 0 ? p.ratings / p.visits * 100 : 0.0;
  final highQuality = p.averageRating >= 3.5;
  final highEngagement = engagement >= 50;
  if (highQuality && highEngagement) return _Quadrant.stars;
  if (highQuality && !highEngagement) return _Quadrant.underused;
  if (!highQuality && highEngagement) return _Quadrant.needsCoaching;
  return _Quadrant.atRisk;
}

Color _quadrantColor(BuildContext context, _Quadrant q) {
  final dark = context.isDark;
  switch (q) {
    case _Quadrant.stars:
      return dark ? AppDarkColors.success : AppColors.success;
    case _Quadrant.underused:
      return dark ? AppDarkColors.info : AppColors.info;
    case _Quadrant.needsCoaching:
      return dark ? AppDarkColors.warning : AppColors.warning;
    case _Quadrant.atRisk:
      return dark ? AppDarkColors.danger : AppColors.danger;
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(label, style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary)),
      ],
    );
  }
}

class _QuadrantPlot extends StatefulWidget {
  const _QuadrantPlot({required this.points, required this.maxVisits, required this.onTapPoint});
  final List<StaffPerformance> points;
  final int maxVisits;
  final ValueChanged<StaffPerformance> onTapPoint;

  @override
  State<_QuadrantPlot> createState() => _QuadrantPlotState();
}

class _QuadrantPlotState extends State<_QuadrantPlot> {
  StaffPerformance? _selected;

  double _radiusFor(int visits) {
    final t = widget.maxVisits > 0 ? visits / widget.maxVisits : 0.0;
    return 7 + 11 * t.clamp(0, 1);
  }

  Offset _positionFor(Size size, StaffPerformance p) {
    final engagement = (p.visits > 0 ? p.ratings / p.visits * 100 : 0.0).clamp(0, 100);
    final rating = p.averageRating.clamp(0, 5);
    final dx = engagement / 100 * size.width;
    final dy = size.height - (rating / 5 * size.height);
    return Offset(dx, dy);
  }

  @override
  Widget build(BuildContext context) {
    final gridColor = context.appColors.borderSubtle;
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return GestureDetector(
          onTapUp: (details) {
            StaffPerformance? closest;
            double closestDist = double.infinity;
            for (final p in widget.points) {
              final pos = _positionFor(size, p);
              final d = (pos - details.localPosition).distance;
              if (d < closestDist) {
                closestDist = d;
                closest = p;
              }
            }
            if (closest != null && closestDist < 28) {
              setState(() => _selected = closest);
              widget.onTapPoint(closest);
            }
          },
          child: CustomPaint(
            size: size,
            painter: _QuadrantPainter(
              points: widget.points,
              gridColor: gridColor,
              radiusFor: _radiusFor,
              positionFor: _positionFor,
              colorFor: (p) => _quadrantColor(context, _quadrantOf(p)),
              selected: _selected,
            ),
          ),
        );
      },
    );
  }
}

class _QuadrantPainter extends CustomPainter {
  _QuadrantPainter({
    required this.points,
    required this.gridColor,
    required this.radiusFor,
    required this.positionFor,
    required this.colorFor,
    required this.selected,
  });

  final List<StaffPerformance> points;
  final Color gridColor;
  final double Function(int visits) radiusFor;
  final Offset Function(Size size, StaffPerformance p) positionFor;
  final Color Function(StaffPerformance p) colorFor;
  final StaffPerformance? selected;

  @override
  void paint(Canvas canvas, Size size) {
    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;
    canvas.drawLine(Offset(size.width / 2, 0), Offset(size.width / 2, size.height), gridPaint);
    canvas.drawLine(Offset(0, size.height * 0.3), Offset(size.width, size.height * 0.3), gridPaint);

    for (final p in points) {
      final pos = positionFor(size, p);
      final r = radiusFor(p.visits);
      final isSelected = selected?.operatorId == p.operatorId;
      final paint = Paint()..color = colorFor(p).withValues(alpha: isSelected ? 1 : 0.82);
      canvas.drawCircle(pos, r, paint);
      if (isSelected) {
        final ring = Paint()
          ..color = colorFor(p)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2;
        canvas.drawCircle(pos, r + 3, ring);
      }
      final initial = p.operatorName.isNotEmpty ? p.operatorName.substring(0, 1) : '?';
      final tp = TextPainter(
        text: TextSpan(
          text: initial,
          style: TextStyle(color: Colors.white, fontSize: r, fontWeight: FontWeight.w800),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, pos - Offset(tp.width / 2, tp.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant _QuadrantPainter oldDelegate) =>
      oldDelegate.points != points || oldDelegate.selected != selected;
}

class _OperatorTrainingSheet extends StatefulWidget {
  const _OperatorTrainingSheet({required this.performance, required this.service});
  final StaffPerformance performance;
  final RatingsService? service;

  @override
  State<_OperatorTrainingSheet> createState() => _OperatorTrainingSheetState();
}

class _OperatorTrainingSheetState extends State<_OperatorTrainingSheet> {
  List<OperatorStepStat>? _stats;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    final service = widget.service;
    if (service != null) {
      service.operatorStepStats(widget.performance.operatorId).then((v) {
        if (mounted) setState(() => v != null ? _stats = v : _failed = true);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final p = widget.performance;
    final engagement = p.visits > 0 ? (p.ratings / p.visits * 100).round() : 0;
    final sorted = [...?_stats]
      ..sort((a, b) {
        final c = b.timesFlaggedCritical.compareTo(a.timesFlaggedCritical);
        return c != 0 ? c : b.timesFlagged.compareTo(a.timesFlagged);
      });
    final top = sorted.take(4).toList();

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(p.operatorName, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Icon(Icons.star_rounded, size: 15, color: const Color(0xFFF6B93B)),
                const SizedBox(width: 4),
                Text(p.averageRating.toStringAsFixed(1), style: AppTextStyles.bodySmall),
                const SizedBox(width: AppSpacing.md),
                Text(s.ratingVisitsShort(p.visits),
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
                const SizedBox(width: AppSpacing.md),
                Text(s.ratingEngagementPercent(engagement),
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(s.ratingTrainingTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: AppSpacing.sm),
            if (widget.service == null)
              Text(s.ratingTrainingNoAccess,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted))
            else if (_failed)
              Text(s.ratingLoadFailedTitle, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger))
            else if (_stats == null)
              const Padding(padding: EdgeInsets.all(AppSpacing.md), child: AppLoadingIndicator(size: 24))
            else if (top.isEmpty)
              Text(s.ratingTrainingClean,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.successOnSoft))
            else
              for (final stat in top)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: stat.stepSeverity == 'critical' ? AppColors.dangerSoft : AppColors.warningSoft,
                          borderRadius: BorderRadius.circular(AppRadius.sm),
                        ),
                        child: Text(
                          stat.stepSeverity == 'critical'
                              ? stat.timesFlaggedCritical.toString()
                              : stat.timesFlagged.toString(),
                          style: AppTextStyles.caption.copyWith(
                            color: stat.stepSeverity == 'critical' ? AppColors.dangerOnSoft : AppColors.warningOnSoft,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(child: Text(stat.stepText, style: AppTextStyles.bodySmall)),
                    ],
                  ),
                ),
          ],
        ),
      ),
    );
  }
}
