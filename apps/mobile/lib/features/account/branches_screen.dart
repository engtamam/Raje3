import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/utils/maps_link.dart';
import 'package:raje3_mobile/features/apps/apps_store_screen.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «الفروع» — pushed from «منشأتي». Owner's own reorganisation (2026-09-22): every fact true of a
/// SINGLE branch (address, واتساب, الفريق) lives here, never in «منشأتي», which now carries only
/// whole-establishment facts. Real backend contract (services/operations/app/api/v1/staff.py),
/// read live, never guessed: `GET /staff/branches` always returns at least the auto-created main
/// branch — there is no "no branches yet" state on this product, so this screen never designs one.
/// `PATCH` can rename/close/reopen/relocate a branch; there is NO delete route anywhere — the
/// "+ إضافة فرع" action is the only branch-count-changing control this screen ever shows.
class BranchesScreen extends StatefulWidget {
  const BranchesScreen({super.key});

  @override
  State<BranchesScreen> createState() => _BranchesScreenState();
}

class _BranchesScreenState extends State<BranchesScreen> {
  BranchesResult? _result;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final result = await context.read<AuthProvider>().fetchBranches();
    if (!mounted) return;
    setState(() {
      _result = result;
      _loading = false;
    });
  }

  Future<void> _openAddBranch() async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _AddBranchSheet(),
    );
    if (added == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final result = _result;
    return KbAnchor(
      id: 'account.shop.branches',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(
          backgroundColor: AppColors.surface0,
          elevation: 0,
          title: Text(s.branchesPageTitle, style: AppTextStyles.headlineSmall),
          leading: AppBackButton(
            onPressed: () => context.canPop()
                ? context.pop()
                : context.go(RouteNames.shopIdentityPath),
          ),
        ),
        floatingActionButton: (result != null && !_loading)
            ? KbAnchor(
                id: 'account.shop.branches.add_button',
                child: FloatingActionButton.extended(
                  onPressed: result.mayAddBranch
                      ? _openAddBranch
                      : () => _showLimitReached(context),
                  icon: const Icon(Icons.add_rounded),
                  label: Text(s.branchesAddBranch),
                ),
              )
            : null,
        body: SafeArea(
          child: _loading
              ? const BrandLoadingIndicator()
              : RefreshIndicator(
                  onRefresh: _load,
                  child: result == null
                      ? _ErrorState(onRetry: _load)
                      : ListView.builder(
                          padding: const EdgeInsets.fromLTRB(
                              AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xxl),
                          itemCount: result.branches.length,
                          itemBuilder: (context, index) => Padding(
                            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                            child: _Reveal(
                              index: index,
                              child: _BranchRow(branch: result.branches[index]),
                            ),
                          ),
                        ),
                ),
        ),
      ),
    );
  }

  void _showLimitReached(BuildContext context) {
    final s = S.of(context)!;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(s.branchesLimitReached),
      // A REAL DESTINATION, NOT A DEAD-END SENTENCE — console's own «فريقي» offers the same link
      // at the same refusal (STORE_PATH). The native capacity stepper now lives right here
      // (AppsStoreScreen's own «السعة» section, parity/app_store.md §6) — no more console URL.
      action: SnackBarAction(
        label: s.branchesIncreaseCapacity,
        onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => const AppsStoreScreen(initialStoreTab: true),
        )),
      ),
    ));
  }
}

class _ErrorState extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorState({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return ListView(
      children: [
        const SizedBox(height: AppSpacing.xxl),
        const Icon(Icons.wifi_off_rounded, size: 40, color: AppColors.textMuted),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: Text(s.branchesLoadFailed, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
        ),
        const SizedBox(height: AppSpacing.md),
        Center(child: TextButton(onPressed: onRetry, child: Text(s.retry))),
      ],
    );
  }
}

/// Same gradient-wash row language `account_screen.dart`'s own `_Row` established — duplicated
/// rather than shared (one small private widget, two call sites) since this row carries a status
/// chip and a WhatsApp dot `_Row` has no shape for.
class _BranchRow extends StatelessWidget {
  final Branch branch;
  const _BranchRow({required this.branch});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final tone = branch.active ? AppTone.accent : AppTone.warning;
    final colors = ToneColors.of(context, tone);
    final chevronColor = dark ? AppDarkColors.textMuted : AppColors.textMuted;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

    return KbAnchor(
      id: 'account.shop.branches.branch_row',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: colors.solid,
      child: Material(
      color: Colors.transparent,
      borderRadius: AppRadius.cardRadius,
      child: InkWell(
        onTap: () => context.push(RouteNames.branchDetailPathFor(branch.id)),
        borderRadius: AppRadius.cardRadius,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: AppRadius.cardRadius,
            border: Border.all(color: border),
            gradient: LinearGradient(
              begin: AlignmentDirectional.centerStart,
              end: AlignmentDirectional.centerEnd,
              colors: [colors.soft.withValues(alpha: dark ? 0.22 : 0.55), surface],
            ),
            boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppRadius.md),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [colors.solid, colors.solid.withValues(alpha: 0.75)],
                    ),
                  ),
                  child: Icon(
                    branch.isMain ? Icons.storefront_rounded : Icons.store_mall_directory_rounded,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(branch.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                      if (branch.city.isNotEmpty)
                        Text(branch.city,
                            style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 3),
                  decoration: BoxDecoration(
                    color: colors.soft,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                  child: Text(
                    branch.active ? s.branchesActiveChip : s.branchesClosedChip,
                    style: AppTextStyles.caption.copyWith(color: colors.onSoft, fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: AppSpacing.xs),
                Icon(
                  Directionality.of(context) == TextDirection.rtl
                      ? Icons.chevron_left_rounded
                      : Icons.chevron_right_rounded,
                  color: chevronColor,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
      ),
      ),
      ),
    );
  }
}

class _AddBranchSheet extends StatefulWidget {
  const _AddBranchSheet();

  @override
  State<_AddBranchSheet> createState() => _AddBranchSheetState();
}

class _AddBranchSheetState extends State<_AddBranchSheet> {
  final _nameController = TextEditingController();
  final _cityController = TextEditingController();
  final _mapsLinkController = TextEditingController();
  bool _saving = false;
  bool _resolvingLink = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _cityController.dispose();
    _mapsLinkController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = s.branchesNameRequired);
      return;
    }
    final mapsLink = _mapsLinkController.text.trim();
    double? lat;
    double? lng;
    if (mapsLink.isNotEmpty) {
      final resolving = isShortGoogleMapsLink(mapsLink);
      if (resolving) setState(() => _resolvingLink = true);
      final parsed = await resolveGoogleMapsLink(mapsLink);
      if (!mounted) return;
      if (resolving) setState(() => _resolvingLink = false);
      if (parsed == null) {
        setState(() => _error = resolving ? s.branchesMapsLinkShort : s.branchesMapsLinkInvalid);
        return;
      }
      lat = parsed.lat;
      lng = parsed.lng;
    }
    _save(name: name, lat: lat, lng: lng);
  }

  Future<void> _save({required String name, double? lat, double? lng}) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    setState(() {
      _saving = true;
      _error = null;
    });
    final result = await auth.addBranch(
          name: name,
          city: _cityController.text.trim(),
          lat: lat,
          lng: lng,
        );
    if (!mounted) return;
    if (result.branch != null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _error = switch (result.error) {
        BranchErrorCode.locationRequired => s.branchesLocationRequired,
        BranchErrorCode.limitReached => s.branchesLimitReached,
        _ => s.branchesSaveFailed,
      };
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
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
            Text(s.branchesAddBranch, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'account.shop.branches.add_sheet.name_field',
              child: TextField(
                controller: _nameController,
                decoration: InputDecoration(isDense: true, hintText: s.branchesNameLabel),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            KbAnchor(
              id: 'account.shop.branches.add_sheet.city_field',
              child: TextField(
                controller: _cityController,
                decoration: InputDecoration(isDense: true, hintText: s.branchesCityLabel),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(s.branchesLocationHint,
                style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: AppSpacing.xs),
            KbAnchor(
              id: 'account.shop.branches.add_sheet.maps_link_field',
              child: TextField(
                controller: _mapsLinkController,
                textDirection: TextDirection.ltr,
                keyboardType: TextInputType.url,
                decoration: InputDecoration(isDense: true, hintText: s.branchesMapsLinkLabel),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
            ],
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'account.shop.branches.add_sheet.submit',
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: (_saving || _resolvingLink) ? null : _submit,
                  child: (_saving || _resolvingLink)
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(s.save),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Duplicated from `account_screen.dart`'s own `_Reveal` — one small private widget, another call
/// site that does not yet justify a shared abstraction.
class _Reveal extends StatelessWidget {
  final int index;
  final Widget child;
  const _Reveal({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    final delay = index.clamp(0, 8) * 50;
    return TweenAnimationBuilder<double>(
      key: ValueKey('branches-reveal-$index'),
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 280 + delay),
      curve: Curves.easeOutCubic,
      builder: (context, t, _) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 10), child: child),
      ),
    );
  }
}
