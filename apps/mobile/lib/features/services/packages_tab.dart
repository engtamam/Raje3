import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «الباقات» — mobile mirror of apps/console/src/screens/PackagesTab.tsx's own DATA contract:
/// several active services sold together at one owner-set price. Scope note on this file's own
/// header comment in services_screen.dart: the scheduling half of a package (recurring/limited
/// availability windows) is real on the server and not built here — every package this screen
/// creates is simply always-offerable, the ordinary case.
class PackagesTab extends StatefulWidget {
  const PackagesTab({super.key, required this.service, required this.services});
  final ServicesCatalogueService service;
  final List<ServiceItem> services; // active services, for the picker + name resolution

  @override
  State<PackagesTab> createState() => _PackagesTabState();
}

class _PackagesTabState extends State<PackagesTab> {
  List<ServicePackage>? _packages;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _packages = null;
      _failed = false;
    });
    final result = await widget.service.listPackages(includeRetired: true);
    if (!mounted) return;
    setState(() {
      _packages = result ?? [];
      _failed = result == null;
    });
  }

  Future<void> _openAdd() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _PackageFormSheet(service: widget.service, services: widget.services),
    );
    if (created == true) _load();
  }

  Future<void> _openEdit(ServicePackage pkg) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _PackageFormSheet(service: widget.service, services: widget.services, existing: pkg),
    );
    if (saved == true) _load();
  }

  Future<void> _toggleActive(ServicePackage pkg) async {
    final updated = await widget.service.updatePackage(pkg.id, active: !pkg.active);
    if (!mounted) return;
    if (updated == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(S.of(context)!.servicesActionFailed)));
      return;
    }
    setState(() => _packages = _packages!.map((p) => p.id == pkg.id ? updated : p).toList());
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'services.packages_tab',
      child: Scaffold(
        backgroundColor: Colors.transparent,
        floatingActionButton: widget.services.length >= 2
            ? FloatingActionButton.extended(
                onPressed: _openAdd,
                icon: const Icon(Icons.add_rounded),
                label: Text(s.servicesPackageAdd),
              )
            : null,
        body: _packages == null
            ? const AppLoadingIndicator()
            : _failed
                ? EmptyState(
                    icon: Icons.cloud_off_rounded,
                    title: s.servicesLoadFailedTitle,
                    actionText: s.mobileRequestsRetry,
                    onAction: _load,
                  )
                : _packages!.isEmpty
                    ? EmptyState(
                        icon: Icons.inventory_2_outlined,
                        title: widget.services.length < 2
                            ? s.servicesPackageNeedsTwoServices
                            : s.servicesPackageEmpty,
                      )
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: ListView.separated(
                          padding: const EdgeInsets.fromLTRB(
                              AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xxl),
                          itemCount: _packages!.length,
                          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                          itemBuilder: (context, i) {
                            final pkg = _packages![i];
                            final names = pkg.serviceIds
                                .map((id) => widget.services
                                    .cast<ServiceItem?>()
                                    .firstWhere((s) => s?.id == id, orElse: () => null)
                                    ?.name ??
                                    id)
                                .toList();
                            return _PackageCard(
                              pkg: pkg,
                              serviceNames: names,
                              onTap: () => _openEdit(pkg),
                              onToggleActive: () => _toggleActive(pkg),
                            );
                          },
                        ),
                      ),
      ),
    );
  }
}

class _PackageCard extends StatelessWidget {
  const _PackageCard({
    required this.pkg,
    required this.serviceNames,
    required this.onTap,
    required this.onToggleActive,
  });
  final ServicePackage pkg;
  final List<String> serviceNames;
  final VoidCallback onTap;
  final VoidCallback onToggleActive;

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.localeOf(context).languageCode;
    final colors = context.appColors;
    final dark = context.isDark;
    return Container(
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: colors.borderSubtle),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.cardRadius,
        child: InkWell(
          borderRadius: AppRadius.cardRadius,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: (dark ? AppDarkColors.accent : AppColors.accent).withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                      ),
                      child: Icon(Icons.inventory_2_rounded,
                          size: 18, color: dark ? AppDarkColors.accent : AppColors.accent),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(pkg.name,
                          style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis),
                    ),
                    CapabilityGate(
                      requires: const ['operations.update_package'],
                      child: Switch(
                        value: pkg.active,
                        onChanged: (_) => onToggleActive(),
                        activeThumbColor: dark ? AppDarkColors.accent : AppColors.accent,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(serviceNames.join(' + '),
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: AppSpacing.sm),
                Text(Formatters.formatCurrency(pkg.priceMinor / 100, locale: locale),
                    style: AppTextStyles.bodyMedium
                        .copyWith(fontWeight: FontWeight.w800, color: dark ? AppDarkColors.accent : AppColors.accent)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PackageFormSheet extends StatefulWidget {
  const _PackageFormSheet({required this.service, required this.services, this.existing});
  final ServicesCatalogueService service;
  final List<ServiceItem> services;
  final ServicePackage? existing;

  @override
  State<_PackageFormSheet> createState() => _PackageFormSheetState();
}

class _PackageFormSheetState extends State<_PackageFormSheet> {
  late final _nameController = TextEditingController(text: widget.existing?.name ?? '');
  late final _priceController = TextEditingController(
      text: (widget.existing?.priceMinor ?? 0) > 0
          ? (widget.existing!.priceMinor / 100).toStringAsFixed(2)
          : '');
  late final _descriptionController = TextEditingController(text: widget.existing?.description ?? '');
  late final Set<String> _selected = {...(widget.existing?.serviceIds ?? const [])};
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _priceController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    final name = _nameController.text.trim();
    final priceSar = double.tryParse(_priceController.text.trim());
    if (name.isEmpty) {
      setState(() => _error = s.servicesNameRequired);
      return;
    }
    if (_selected.length < 2) {
      setState(() => _error = s.servicesPackageNeedsTwoServices);
      return;
    }
    if (priceSar == null || priceSar <= 0) {
      setState(() => _error = s.servicesPackagePriceRequired);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final priceMinor = (priceSar * 100).round();
    final result = widget.existing != null
        ? await widget.service.updatePackage(
            widget.existing!.id,
            name: name,
            serviceIds: _selected.toList(),
            priceMinor: priceMinor,
            description: _descriptionController.text.trim(),
          )
        : await widget.service.createPackage(
            name: name,
            serviceIds: _selected.toList(),
            priceMinor: priceMinor,
            description: _descriptionController.text.trim(),
          );
    if (!mounted) return;
    if (result == null) {
      setState(() {
        _saving = false;
        _error = s.servicesActionFailed;
      });
      return;
    }
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final isEdit = widget.existing != null;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: DraggableScrollableSheet(
        initialChildSize: 0.85,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Container(
          decoration: const BoxDecoration(
            color: AppColors.surface1,
            borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          ),
          child: ListView(
            controller: scrollController,
            padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
            children: [
              Text(isEdit ? s.servicesPackageEditTitle : s.servicesPackageAddTitle,
                  style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'services.package_fields',
                child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              AppTextField(labelText: s.servicesPackageNameLabel, controller: _nameController),
              const SizedBox(height: AppSpacing.md),
              AppTextField(
                labelText: s.servicesPriceLabel,
                controller: _priceController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
              ),
              const SizedBox(height: AppSpacing.md),
              AppTextField(
                labelText: s.servicesDescriptionLabel,
                controller: _descriptionController,
                maxLines: 2,
              ),
                ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(s.servicesPackageServicesLabel, style: AppTextStyles.labelMedium),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final item in widget.services)
                    _PackageServiceChip(
                      label: item.name,
                      selected: _selected.contains(item.id),
                      onTap: () => setState(() {
                        _selected.contains(item.id) ? _selected.remove(item.id) : _selected.add(item.id);
                      }),
                    ),
                ],
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              CapabilityGate(
                requires: [widget.existing != null
                    ? 'operations.update_package'
                    : 'operations.create_package'],
                child: PrimaryButton(
                  text: _saving ? s.servicesSaving : s.servicesSave,
                  isLoading: _saving,
                  onPressed: _saving ? null : _submit,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PackageServiceChip extends StatelessWidget {
  const _PackageServiceChip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.sm),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? accent.withValues(alpha: 0.15) : context.appColors.surfaceAlt,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(color: selected ? accent : context.appColors.borderSubtle),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (selected) ...[
              Icon(Icons.check_rounded, size: 12, color: accent),
              const SizedBox(width: 2),
            ],
            Text(label,
                style: AppTextStyles.caption.copyWith(
                    color: selected ? accent : context.appColors.textSecondary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w400)),
          ],
        ),
      ),
    );
  }
}
