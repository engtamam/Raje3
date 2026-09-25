import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «الإجراءات» — mobile mirror of apps/console/src/screens/ProcedureStepsTab.tsx's own real
/// contract: a shop-wide shared library of checklist lines (`/api/v1/staff/procedure-steps`),
/// referenced by id from any service's own `procedure_step_ids` (ordered). SERVICE-FIRST, THE
/// LIBRARY SECOND, same reasoning the console's own header comment gives — the owner's mental
/// model is "what does غسيل السيارة involve", not "what steps exist"; assigning an existing step
/// to a service is the common action, so the service list is the default view and the shared
/// library sits one link away.
///
/// Was already half-built before this tab existed — `_ServiceEditSheet` in `services_screen.dart`
/// already lets one service toggle/create/retire steps inline. This tab adds the three things
/// that only make sense at the library's own level: reordering a service's own steps (drag),
/// browsing/managing the WHOLE shared library independent of any one service (with a real
/// "مستخدمة بـN خدمات" usage count), and printing an ordered checklist (one service, or several
/// merged and deduped) as a real document.
class ProceduresTab extends StatefulWidget {
  const ProceduresTab({required this.service, required this.services, required this.onChanged});
  final ServicesCatalogueService service;
  final List<ServiceItem> services;
  final VoidCallback onChanged;

  @override
  State<ProceduresTab> createState() => _ProceduresTabState();
}

class _ProceduresTabState extends State<ProceduresTab> {
  List<ProcedureStep>? _steps;
  final Set<String> _selected = {};
  bool _bulkPrinting = false;
  String? _bulkPrintError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final result = await widget.service.procedureSteps(includeRetired: true);
    if (mounted) setState(() => _steps = result ?? const []);
  }

  /// Computed client-side from the one services list the parent screen already fetched — never a
  /// second round trip per step, same reasoning `ProcedureStepsTab.tsx`'s own `usageCount` gives.
  Map<String, int> get _usageCount {
    final counts = <String, int>{};
    for (final svc in widget.services) {
      for (final id in svc.procedureStepIds) {
        counts[id] = (counts[id] ?? 0) + 1;
      }
    }
    return counts;
  }

  Future<void> _printSelected() async {
    if (_bulkPrinting || _selected.isEmpty) return;
    final s = S.of(context)!;
    setState(() {
      _bulkPrinting = true;
      _bulkPrintError = null;
    });
    final names = widget.services
        .where((x) => _selected.contains(x.id))
        .map((x) => x.name)
        .join(' + ');
    final bytes = await widget.service.exportProcedureChecklist(serviceIds: _selected.toList());
    if (!mounted) return;
    if (bytes == null || bytes.isEmpty) {
      setState(() {
        _bulkPrinting = false;
        _bulkPrintError = s.proceduresPrintFailed;
      });
      return;
    }
    await _shareBytes(bytes, names.isEmpty ? s.proceduresTitle : names, s);
    if (mounted) {
      setState(() {
        _bulkPrinting = false;
        _selected.clear();
      });
    }
  }

  void _openLibrary() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _LibrarySheet(
        service: widget.service,
        steps: _steps ?? const [],
        usageCount: _usageCount,
        onChanged: () {
          _load();
          widget.onChanged();
        },
      ),
    );
  }

  void _openService(ServiceItem svc) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ServiceStepsSheet(
        service: widget.service,
        target: svc,
        allSteps: _steps ?? const [],
        usageCount: _usageCount,
        onSaved: () {
          _load();
          widget.onChanged();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final dark = context.isDark;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;

    if (_steps == null) {
      return const Center(child: AppLoadingIndicator());
    }

    final active = widget.services.where((x) => x.active).toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(s.proceduresSubtitle,
                    style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
              ),
              const SizedBox(width: AppSpacing.sm),
              // A GLOSSY GRADIENT PILL, NOT A TEXT LINK — this is the doorway into the whole
              // shared library, the one action on this tab worth a real affordance instead of a
              // plain hyperlink-style button.
              RjSheen(
                borderRadius: BorderRadius.circular(AppRadius.pill),
                child: Material(
                  color: Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  child: InkWell(
                    onTap: _openLibrary,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(colors: [accent, accent.withValues(alpha: 0.78)]),
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.menu_book_rounded, size: 15, color: Colors.white),
                          const SizedBox(width: 6),
                          Text(s.proceduresLibraryLink,
                              style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        if (_selected.isNotEmpty)
          KbAnchor(
            id: 'services.procedures_bulk_actions',
            child: Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: accent.withValues(alpha: 0.12),
                borderRadius: AppRadius.standardRadius,
                border: Border.all(color: accent.withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_bulkPrintError != null) ...[
                    Text(_bulkPrintError!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
                    const SizedBox(height: 4),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: Text(s.proceduresSelectedCount(_selected.length),
                            style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                      ),
                      TextButton(
                        onPressed: () => setState(() => _selected.clear()),
                        child: Text(s.mobileRequestsRejectCancel),
                      ),
                      const SizedBox(width: 4),
                      FilledButton.icon(
                        onPressed: _bulkPrinting ? null : _printSelected,
                        icon: _bulkPrinting
                            ? const SizedBox(
                                width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.print_rounded, size: 16),
                        label: Text(s.proceduresPrint),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            ),
          ),
        Expanded(
          child: active.isEmpty
              ? EmptyState(icon: Icons.checklist_rounded, title: s.proceduresEmptyTitle)
              // A 3-COLUMN GRID, NOT A FULL-WIDTH LIST — owner's own call, 2026-09-23: a shop
              // with a real catalogue scrolled a long way just to reach one service's checklist.
              // Selection (for bulk print) moves from an inline ring to a corner check badge, the
              // same idiom a phone's own photo picker uses for a multi-select grid.
              : GridView.builder(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    mainAxisSpacing: AppSpacing.sm,
                    crossAxisSpacing: AppSpacing.sm,
                    childAspectRatio: 0.86,
                  ),
                  itemCount: active.length,
                  itemBuilder: (context, i) {
                    final svc = active[i];
                    final n = svc.procedureStepIds.length;
                    final hasCritical = svc.procedureStepIds.any(
                        (id) => (_steps ?? const []).any((st) => st.id == id && st.severity == 'critical'));
                    final selected = _selected.contains(svc.id);
                    final stripe = hasCritical ? AppColors.danger : accent.withValues(alpha: n > 0 ? 0.7 : 0.25);
                    return RjSheen(
                      borderRadius: AppRadius.cardRadius,
                      tint: hasCritical ? AppColors.danger : accent,
                      child: Material(
                        color: colors.surface,
                        borderRadius: AppRadius.cardRadius,
                        child: InkWell(
                          borderRadius: AppRadius.cardRadius,
                          onTap: () => _openService(svc),
                          onLongPress: () => setState(() {
                            if (selected) {
                              _selected.remove(svc.id);
                            } else {
                              _selected.add(svc.id);
                            }
                          }),
                          child: Stack(
                            children: [
                              Container(
                                decoration: BoxDecoration(
                                  border: Border.all(color: selected ? accent : colors.borderSubtle, width: selected ? 1.4 : 1),
                                  borderRadius: AppRadius.cardRadius,
                                  boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.stretch,
                                  children: [
                                    // A THIN COLOR STRIP ACROSS THE TOP — critical/normal reads at
                                    // a glance, same "identity carried by the object itself" idiom
                                    // the poster cards on الخدمات already use.
                                    Container(
                                      height: 4,
                                      decoration: BoxDecoration(
                                        color: stripe,
                                        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
                                      ),
                                    ),
                                    Expanded(
                                      child: Padding(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(svc.name,
                                                maxLines: 2,
                                                overflow: TextOverflow.ellipsis,
                                                style: AppTextStyles.caption
                                                    .copyWith(fontWeight: FontWeight.w700, height: 1.2)),
                                            Row(
                                              children: [
                                                Container(
                                                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                                  decoration: BoxDecoration(
                                                    gradient: n > 0
                                                        ? LinearGradient(colors: [accent, accent.withValues(alpha: 0.75)])
                                                        : null,
                                                    color: n > 0 ? null : colors.surfaceAlt,
                                                    borderRadius: BorderRadius.circular(AppRadius.pill),
                                                  ),
                                                  child: Text('$n',
                                                      style: AppTextStyles.caption.copyWith(
                                                          fontSize: 10.5,
                                                          fontWeight: FontWeight.w800,
                                                          color: n > 0 ? Colors.white : colors.textSecondary)),
                                                ),
                                                if (hasCritical) ...[
                                                  const SizedBox(width: 4),
                                                  Icon(Icons.priority_high_rounded, size: 11, color: AppColors.danger),
                                                ],
                                              ],
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              if (selected)
                                PositionedDirectional(
                                  top: 6,
                                  end: 6,
                                  child: _SelectRing(selected: true),
                                ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

Future<void> _shareBytes(List<int> bytes, String label, S s) async {
  final dir = await getTemporaryDirectory();
  final file = File('${dir.path}/procedures_${DateTime.now().millisecondsSinceEpoch}.pdf');
  await file.writeAsBytes(bytes);
  await Share.shareXFiles([XFile(file.path)], text: label);
}

class _SeverityDot extends StatelessWidget {
  const _SeverityDot({required this.severity});
  final String severity;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: severity == 'critical' ? AppColors.danger : context.appColors.textMuted.withValues(alpha: 0.5),
      ),
    );
  }
}

/// A compact two-segment pill — «عادي»/«حرج» — never a desktop `DropdownButton` (reads as a web
/// form control dropped onto a phone). Critical fills danger-red when picked; normal fills the
/// app's own accent; unpicked side stays a plain label. The one severity control this whole tab
/// uses, everywhere a severity needs picking.
class _SeverityToggle extends StatelessWidget {
  const _SeverityToggle({required this.value, required this.onChanged});
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final normalOn = value != 'critical';
    return Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadius.pill)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _severitySeg(context, label: S.of(context)!.servicesStepSeverityNormal, on: normalOn, color: accent,
              onTap: () => onChanged('normal')),
          _severitySeg(context, label: S.of(context)!.servicesStepSeverityCritical, on: !normalOn, color: AppColors.danger,
              onTap: () => onChanged('critical')),
        ],
      ),
    );
  }

  Widget _severitySeg(BuildContext context, {required String label, required bool on, required Color color, required VoidCallback onTap}) {
    return Material(
      color: on ? color : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          child: Text(label,
              style: AppTextStyles.caption.copyWith(
                  color: on ? Colors.white : context.appColors.textSecondary,
                  fontWeight: on ? FontWeight.w800 : FontWeight.w500)),
        ),
      ),
    );
  }
}

/// The selection indicator this whole tab uses instead of a bare Material `Checkbox` — a filled
/// accent circle with a check once selected, an empty ring otherwise. Reads as a native mobile
/// multi-select affordance (the same shape iOS/Android photo pickers use), not a form checkbox.
class _SelectRing extends StatelessWidget {
  const _SelectRing({required this.selected});
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      width: 22,
      height: 22,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: selected ? accent : Colors.transparent,
        border: Border.all(color: selected ? accent : context.appColors.borderSubtle, width: 1.6),
      ),
      child: selected ? const Icon(Icons.check_rounded, size: 15, color: Colors.white) : null,
    );
  }
}

/// A bottom sheet wrapper matching this file's own three sheets' shared chrome — a drag handle,
/// a title/subtitle, scrollable content, and (when given) a pinned footer.
class _SheetShell extends StatelessWidget {
  const _SheetShell({required this.title, this.subtitle, required this.child, this.footer, this.maxHeightFactor = 0.9});
  final String title;
  final String? subtitle;
  final Widget child;
  final Widget? footer;
  final double maxHeightFactor;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * maxHeightFactor),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 10),
            Container(
              width: 36, height: 4,
              decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(2)),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: AppTextStyles.headlineSmall),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(subtitle!, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ],
              ),
            ),
            Flexible(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.md),
                child: child,
              ),
            ),
            if (footer != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
                child: footer,
              ),
          ],
        ),
      ),
    );
  }
}

/// ── per-service sheet: ordered steps, drag to reorder, add/remove, print ──────────────────────
class _ServiceStepsSheet extends StatefulWidget {
  const _ServiceStepsSheet({
    required this.service, required this.target, required this.allSteps,
    required this.usageCount, required this.onSaved,
  });
  final ServicesCatalogueService service;
  final ServiceItem target;
  final List<ProcedureStep> allSteps;
  final Map<String, int> usageCount;
  final VoidCallback onSaved;

  @override
  State<_ServiceStepsSheet> createState() => _ServiceStepsSheetState();
}

class _ServiceStepsSheetState extends State<_ServiceStepsSheet> {
  late List<String> _order = [...widget.target.procedureStepIds];
  // A LOCAL COPY, GROWN AS THE PICKER CREATES NEW STEPS — same reasoning as `_LibrarySheet`'s own
  // `_localSteps`: `widget.allSteps` is a snapshot from when this sheet opened, so a step created
  // via `_openPicker`'s own "new step" row would have no entry in `_byId` and render as a blank
  // row (`step == null`) the instant it was added, purely from this sheet's own point of view.
  late List<ProcedureStep> _allSteps = [...widget.allSteps];
  bool _saving = false;
  bool _printing = false;
  String? _error;
  String? _printError;

  bool get _dirty {
    if (_order.length != widget.target.procedureStepIds.length) return true;
    for (var i = 0; i < _order.length; i++) {
      if (_order[i] != widget.target.procedureStepIds[i]) return true;
    }
    return false;
  }

  Map<String, ProcedureStep> get _byId => {for (final st in _allSteps) st.id: st};

  Future<void> _save() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final updated = await widget.service.update(widget.target.id, procedureStepIds: _order);
    if (!mounted) return;
    setState(() => _saving = false);
    if (updated == null) {
      setState(() => _error = s.proceduresSaveFailed);
      return;
    }
    widget.onSaved();
    Navigator.of(context).pop();
  }

  Future<void> _print() async {
    if (_printing || _order.isEmpty) return;
    final s = S.of(context)!;
    setState(() {
      _printing = true;
      _printError = null;
    });
    final bytes = await widget.service.exportProcedureChecklist(serviceIds: [widget.target.id]);
    if (!mounted) return;
    setState(() => _printing = false);
    if (bytes == null || bytes.isEmpty) {
      setState(() => _printError = s.proceduresPrintFailed);
      return;
    }
    await _shareBytes(bytes, widget.target.name, s);
  }

  Future<void> _openPicker() async {
    final picked = await showModalBottomSheet<List<String>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _StepPickerSheet(
        service: widget.service,
        allSteps: _allSteps,
        usageCount: widget.usageCount,
        excludeIds: _order,
        onCreated: (step) => setState(() => _allSteps = [..._allSteps, step]),
      ),
    );
    if (picked != null && picked.isNotEmpty) {
      setState(() => _order = [..._order, ...picked]);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;

    return _SheetShell(
      title: widget.target.name,
      subtitle: s.proceduresDrawerSubtitle,
      maxHeightFactor: 0.85,
      footer: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            Text(_error!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            const SizedBox(height: 6),
          ],
          if (_printError != null) ...[
            Text(_printError!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            const SizedBox(height: 6),
          ],
          KbAnchor(
            id: 'services.procedures_drawer_footer',
            child: Row(
            children: [
              TextButton.icon(
                onPressed: _printing ? null : _print,
                icon: _printing
                    ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.print_rounded, size: 16),
                label: Text(s.proceduresPrint),
              ),
              const Spacer(),
              TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(s.mobileRequestsRejectCancel)),
              const SizedBox(width: 4),
              CapabilityGate(
                requires: const ['operations.update_service'],
                child: FilledButton(
                  onPressed: (!_dirty || _saving) ? null : _save,
                  child: _saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(s.servicesSave),
                ),
              ),
            ],
            ),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_order.isEmpty)
            Expanded(
              child: Center(
                child: Text(s.proceduresDrawerEmpty,
                    textAlign: TextAlign.center, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
              ),
            )
          else
            // NO `shrinkWrap` — same reasoning as `_LibrarySheet`'s own list: a shrink-wrapped
            // list forces an intrinsic-height pass, and this row's own `Row(crossAxisAlignment:
            // stretch)` colour stripe has no defined intrinsic height, which is what threw a
            // repeating layout assertion the moment a real row rendered inside one.
            Expanded(
              child: ReorderableListView.builder(
                buildDefaultDragHandles: false,
                itemCount: _order.length,
                onReorder: (oldIndex, newIndex) {
                  setState(() {
                    if (newIndex > oldIndex) newIndex -= 1;
                    final id = _order.removeAt(oldIndex);
                    _order.insert(newIndex, id);
                  });
                },
                itemBuilder: (context, i) {
                  final id = _order[i];
                  final step = _byId[id];
                  if (step == null) return SizedBox.shrink(key: ValueKey(id));
                  final used = widget.usageCount[id] ?? 0;
                  final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
                  final critical = step.severity == 'critical';
                  return Container(
                    key: ValueKey(id),
                    margin: const EdgeInsets.only(bottom: 6),
                    decoration: BoxDecoration(
                      color: colors.surface,
                      border: Border.all(color: critical ? AppColors.danger.withValues(alpha: 0.35) : colors.borderSubtle),
                      borderRadius: AppRadius.standardRadius,
                      boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
                    ),
                    // `IntrinsicHeight` — same fix, same reasoning as `_LibrarySheet`'s own row:
                    // a `Row(crossAxisAlignment: stretch)` inside an unbounded-height list item
                    // needs its height measured from content first before it can stretch a
                    // sibling into it.
                    child: IntrinsicHeight(
                      child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Container(
                          width: 3,
                          decoration: BoxDecoration(
                            color: critical ? AppColors.danger : accent.withValues(alpha: 0.5),
                            borderRadius: const BorderRadiusDirectional.horizontal(start: Radius.circular(AppRadius.sm)),
                          ),
                        ),
                        ReorderableDragStartListener(
                          index: i,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 10),
                            child: Icon(Icons.drag_indicator_rounded, size: 18, color: colors.textMuted),
                          ),
                        ),
                        const SizedBox(width: 2),
                        Expanded(
                          child: Text(step.text, maxLines: 1, overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.bodySmall),
                        ),
                        if (used > 1) ...[
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadius.pill)),
                            child: Text(s.proceduresUsedIn(used),
                                style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                          ),
                          const SizedBox(width: 4),
                        ],
                        KbAnchor(
                          id: 'services.procedures_drawer_remove_step',
                          child: IconButton(
                          visualDensity: VisualDensity.compact,
                          icon: const Icon(Icons.close_rounded, size: 17),
                          color: colors.textMuted,
                          onPressed: () => setState(() => _order.removeWhere((x) => x == id)),
                          ),
                        ),
                      ],
                      ),
                    ),
                  );
                },
              ),
            ),
          const SizedBox(height: AppSpacing.sm),
          OutlinedButton.icon(
            onPressed: _openPicker,
            icon: const Icon(Icons.add_rounded, size: 18),
            label: Text(s.proceduresDrawerAddButton),
          ),
        ],
      ),
    );
  }
}

/// ── the picker: search + multiselect + create-new, nested inside the service sheet ─────────────
class _StepPickerSheet extends StatefulWidget {
  const _StepPickerSheet({
    required this.service, required this.allSteps, required this.usageCount, required this.excludeIds,
    required this.onCreated,
  });
  final ServicesCatalogueService service;
  final List<ProcedureStep> allSteps;
  final Map<String, int> usageCount;
  final List<String> excludeIds;
  final ValueChanged<ProcedureStep> onCreated;

  @override
  State<_StepPickerSheet> createState() => _StepPickerSheetState();
}

class _StepPickerSheetState extends State<_StepPickerSheet> {
  final _searchController = TextEditingController();
  final _newTextController = TextEditingController();
  String _newSeverity = 'normal';
  final Set<String> _selected = {};
  late List<ProcedureStep> _extra = [];
  bool _creating = false;

  @override
  void dispose() {
    _searchController.dispose();
    _newTextController.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final text = _newTextController.text.trim();
    if (text.isEmpty) return;
    setState(() => _creating = true);
    final created = await widget.service.createProcedureStep(text: text, severity: _newSeverity);
    if (!mounted) return;
    setState(() => _creating = false);
    if (created == null) return;
    setState(() {
      _extra = [..._extra, created];
      _selected.add(created.id);
      _newTextController.clear();
    });
    widget.onCreated(created);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final excluded = widget.excludeIds.toSet();
    final all = [...widget.allSteps, ..._extra];
    final query = _searchController.text.trim().toLowerCase();
    final results = all
        .where((st) => st.active && !excluded.contains(st.id))
        .where((st) => query.isEmpty || st.text.toLowerCase().contains(query))
        .toList();

    return _SheetShell(
      title: s.proceduresPickTitle,
      maxHeightFactor: 0.85,
      footer: KbAnchor(
        id: 'services.procedures_picker_footer',
        child: Row(
        children: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(s.proceduresPickClose)),
          const Spacer(),
          FilledButton(
            onPressed: _selected.isEmpty ? null : () => Navigator.of(context).pop(_selected.toList()),
            child: Text('${s.proceduresPickApply} (${_selected.length})'),
          ),
        ],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          KbAnchor(
            id: 'services.procedures_picker_search',
            child: AppTextField(hintText: s.proceduresPickSearch, controller: _searchController, onChanged: (_) => setState(() {})),
          ),
          const SizedBox(height: AppSpacing.sm),
          Expanded(
            child: results.isEmpty
                ? Center(
                    child: Text(s.proceduresPickEmpty,
                        textAlign: TextAlign.center, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                  )
                : ListView.builder(
                    itemCount: results.length,
                    itemBuilder: (context, i) {
                      final st = results[i];
                      final used = widget.usageCount[st.id] ?? 0;
                      final selected = _selected.contains(st.id);
                      return Material(
                        color: selected ? colors.surfaceAlt : Colors.transparent,
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(AppRadius.sm),
                          onTap: () => setState(() {
                            if (selected) {
                              _selected.remove(st.id);
                            } else {
                              _selected.add(st.id);
                            }
                          }),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 6),
                            child: Row(
                              children: [
                                _SelectRing(selected: selected),
                                const SizedBox(width: 10),
                                _SeverityDot(severity: st.severity),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(st.text, maxLines: 1, overflow: TextOverflow.ellipsis, style: AppTextStyles.bodySmall),
                                ),
                                if (used > 0) ...[
                                  Icon(Icons.link_rounded, size: 12, color: colors.textMuted),
                                  const SizedBox(width: 2),
                                  Text('$used', style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                                ],
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          const Divider(height: AppSpacing.lg),
          KbAnchor(
            id: 'services.procedures_picker_create',
            child: Row(
            children: [
              Expanded(
                child: AppTextField(
                  hintText: s.proceduresPickCreatePlaceholder,
                  controller: _newTextController,
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 8),
              _SeverityToggle(value: _newSeverity, onChanged: (v) => setState(() => _newSeverity = v)),
              const SizedBox(width: 6),
              CapabilityGate(
                requires: const ['operations.create_procedure_step'],
                child: IconButton(
                  onPressed: (_creating || _newTextController.text.trim().isEmpty) ? null : _create,
                  icon: _creating
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.add_rounded),
                ),
              ),
            ],
            ),
          ),
        ],
      ),
    );
  }
}

/// ── the shared library: create/edit text+severity/retire, independent of any one service ───────
class _LibrarySheet extends StatefulWidget {
  const _LibrarySheet({required this.service, required this.steps, required this.usageCount, required this.onChanged});
  final ServicesCatalogueService service;
  final List<ProcedureStep> steps;
  final Map<String, int> usageCount;
  final VoidCallback onChanged;

  @override
  State<_LibrarySheet> createState() => _LibrarySheetState();
}

class _LibrarySheetState extends State<_LibrarySheet> {
  final _newTextController = TextEditingController();
  String _newSeverity = 'normal';
  bool _showRetired = false;
  String? _busyId;
  String? _error;

  // A LOCAL COPY, MUTATED OPTIMISTICALLY ON SUCCESS — `widget.steps` is a snapshot taken once
  // when `showModalBottomSheet` built this sheet; calling `widget.onChanged()` refreshes the
  // PARENT's own state but never rebuilds an already-open sheet (different element tree), so a
  // step created here would render as "still empty" until the sheet was closed and reopened. This
  // list is what the sheet actually renders from; `widget.onChanged()` still runs so the parent's
  // own cache (and the main list's step-count badges) stay correct once this sheet closes.
  late List<ProcedureStep> _localSteps = [...widget.steps];

  @override
  void dispose() {
    _newTextController.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    final s = S.of(context)!;
    final text = _newTextController.text.trim();
    if (text.isEmpty) return;
    setState(() => _error = null);
    final created = await widget.service.createProcedureStep(text: text, severity: _newSeverity);
    if (!mounted) return;
    if (created == null) {
      setState(() => _error = s.proceduresLibrarySaveFailed);
      return;
    }
    _newTextController.clear();
    setState(() => _localSteps = [..._localSteps, created]);
    widget.onChanged();
  }

  Future<void> _patch(String id, {String? text, String? severity, bool? active}) async {
    final s = S.of(context)!;
    setState(() {
      _busyId = id;
      _error = null;
    });
    final updated = await widget.service.updateProcedureStep(id, text: text, severity: severity, active: active);
    if (!mounted) return;
    setState(() => _busyId = null);
    if (updated == null) {
      setState(() => _error = s.proceduresLibrarySaveFailed);
      return;
    }
    setState(() => _localSteps = _localSteps.map((st) => st.id == id ? updated : st).toList());
    widget.onChanged();
  }

  Future<void> _renameStep(ProcedureStep step) async {
    final s = S.of(context)!;
    final controller = TextEditingController(text: step.text);
    final next = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.proceduresPickTitle),
        content: KbAnchor(
          id: 'services.procedures_library_rename_dialog',
          child: TextField(controller: controller, autofocus: true, maxLines: 2),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(s.mobileRequestsRejectCancel)),
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()),
              child: Text(s.servicesSave)),
        ],
      ),
    );
    controller.dispose();
    if (next == null || next.isEmpty || next == step.text) return;
    await _patch(step.id, text: next);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final visible = _localSteps.where((st) => _showRetired || st.active).toList();
    final canEditSteps =
        context.watch<NavProvider>().catalog.hasAll(['operations.update_procedure_step']);

    return _SheetShell(
      title: s.proceduresLibraryTitle,
      subtitle: s.proceduresLibrarySubtitle,
      maxHeightFactor: 0.9,
      // NO `mainAxisSize: min` HERE — this Column holds a `Flexible(ListView...)` further down,
      // and a min-sized Column fighting a Flexible child inside it is exactly the shape that
      // throws a silent, no-message layout assertion on every frame the instant the list goes
      // from empty (no Flexible needed) to non-empty (found live: creating the very first step
      // froze the sheet in a repeating render-error loop, only once the list had something to
      // actually flex around). The shell above already bounds this Column's height (`Flexible` +
      // `maxHeightFactor`), so growing to fill it here is correct, not a regression.
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          KbAnchor(
            id: 'services.procedures_library_add',
            child: Row(
            children: [
              Expanded(
                child: AppTextField(
                  hintText: s.proceduresLibraryNewPlaceholder,
                  controller: _newTextController,
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 8),
              _SeverityToggle(value: _newSeverity, onChanged: (v) => setState(() => _newSeverity = v)),
              const SizedBox(width: 6),
              CapabilityGate(
                requires: const ['operations.create_procedure_step'],
                child: FilledButton(
                  onPressed: _newTextController.text.trim().isEmpty ? null : _add,
                  child: Text(s.proceduresLibraryAdd),
                ),
              ),
            ],
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 6),
            Text(_error!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
          ],
          const SizedBox(height: AppSpacing.sm),
          Material(
            color: Colors.transparent,
            child: CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _showRetired,
              onChanged: (v) => setState(() => _showRetired = v ?? false),
              title: Text(s.proceduresLibraryShowRetired, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
            ),
          ),
          Expanded(
            // NO `shrinkWrap` HERE — a shrink-wrapped list forces Flutter to compute each row's
            // INTRINSIC height, and a `Row(crossAxisAlignment: stretch)` row (the colour-stripe
            // pattern this card uses) has no well-defined intrinsic height on its own — a
            // documented Flutter footgun that threw a repeating, message-less layout assertion
            // the instant a real row like this rendered inside a shrink-wrapped list (found live:
            // the very first step created here froze the sheet). `Expanded` gives the list a
            // real bounded height instead, so it scrolls normally with no intrinsic pass at all.
            child: visible.isEmpty
                ? Center(
                    child: Text(s.proceduresLibraryEmpty,
                        textAlign: TextAlign.center, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                  )
                : ListView.separated(
                    itemCount: visible.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 6),
                    itemBuilder: (context, i) {
                      final st = visible[i];
                      final used = widget.usageCount[st.id] ?? 0;
                      final busy = _busyId == st.id;
                      final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
                      final critical = st.severity == 'critical';
                      return Opacity(
                        opacity: st.active ? 1 : 0.55,
                        child: Container(
                            decoration: BoxDecoration(
                              color: colors.surface,
                              border: Border.all(color: critical ? AppColors.danger.withValues(alpha: 0.35) : colors.borderSubtle),
                              borderRadius: AppRadius.standardRadius,
                            ),
                            // `IntrinsicHeight`, NOT a bare `Row(crossAxisAlignment: stretch)` —
                            // this is the exact bug the repeating layout assertion traced back to
                            // (procedures_tab.dart:1061 in the crash log): a plain `Row` in a
                            // list item gets UNBOUNDED height (it sizes to its own content), and
                            // `stretch` needs a BOUNDED height to stretch the colour-stripe
                            // `Container` into — a contradiction Flutter can only resolve by
                            // throwing, every single frame. `IntrinsicHeight` measures the
                            // content column first, giving the Row a real height `stretch` can
                            // then use — the standard fix for a "stripe beside variable content"
                            // layout.
                            child: IntrinsicHeight(
                              child: Row(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Container(
                                  width: 4,
                                  decoration: BoxDecoration(
                                    color: critical ? AppColors.danger : accent.withValues(alpha: 0.5),
                                    borderRadius: const BorderRadiusDirectional.horizontal(start: Radius.circular(AppRadius.sm)),
                                  ),
                                ),
                                Expanded(
                                  child: Padding(
                                    padding: const EdgeInsets.all(8),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Expanded(
                                              child: InkWell(
                                                onTap: (busy || !st.active || !canEditSteps) ? null : () => _renameStep(st),
                                                child: Padding(
                                                  padding: const EdgeInsets.symmetric(vertical: 4),
                                                  child: Text(st.text,
                                                      maxLines: 1,
                                                      overflow: TextOverflow.ellipsis,
                                                      style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
                                                ),
                                              ),
                                            ),
                                            if (!st.active)
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                                decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadius.pill)),
                                                child: Text(s.proceduresLibraryRetired,
                                                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                                              ),
                                          ],
                                        ),
                                        const SizedBox(height: 6),
                                        Row(
                                          children: [
                                            IgnorePointer(
                                              ignoring: busy || !st.active || !canEditSteps,
                                              child: Opacity(
                                                opacity: (busy || !st.active || !canEditSteps) ? 0.5 : 1,
                                                child: _SeverityToggle(
                                                  value: st.severity,
                                                  onChanged: (v) => _patch(st.id, severity: v),
                                                ),
                                              ),
                                            ),
                                            if (used > 0) ...[
                                              const SizedBox(width: 8),
                                              Icon(Icons.link_rounded, size: 12, color: colors.textMuted),
                                              const SizedBox(width: 2),
                                              Text('$used', style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                                            ],
                                            const Spacer(),
                                            InkWell(
                                              borderRadius: BorderRadius.circular(AppRadius.pill),
                                              onTap: (busy || !canEditSteps) ? null : () => _patch(st.id, active: !st.active),
                                              child: Padding(
                                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                                child: Row(
                                                  mainAxisSize: MainAxisSize.min,
                                                  children: [
                                                    Icon(st.active ? Icons.archive_outlined : Icons.restore_rounded,
                                                        size: 14, color: st.active ? AppColors.danger : accent),
                                                    const SizedBox(width: 4),
                                                    Text(st.active ? s.proceduresLibraryRetire : s.proceduresLibraryReactivate,
                                                        style: AppTextStyles.caption.copyWith(
                                                            fontWeight: FontWeight.w700,
                                                            color: st.active ? AppColors.danger : accent)),
                                                  ],
                                                ),
                                              ),
                                            ),
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
                      );
                    },
                  ),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline_rounded, size: 13, color: colors.textMuted),
              const SizedBox(width: 4),
              Expanded(
                child: Text(s.proceduresSeverityHint, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
