import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_colorpicker/flutter_colorpicker.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «منشأتي» — pushed from «حسابي» (RouteNames.shopIdentityPath), own back button, no bottom bar.
/// Per the owner's own reorganisation (2026-09-22): this screen carries ONLY facts that are true
/// for the WHOLE establishment, never a single branch or a single person — «ربط واتساب»/«الفريق»
/// both moved OUT to «الفروع» (a branch's own WhatsApp connection, and a branch's own staff — see
/// [[mobile-app-brand-vs-design-craft]]'s own note on why «كل فرع فيه فريقه»).
///
/// THE BRAND CARD'S REAL CONTRACT WAS READ LIVE, NEVER GUESSED — `tenant.view_self`/
/// `tenant.update_branding` are `tenant-service`'s own actions (no source in this repo), so the
/// exact shape came from inspecting the authenticated console session itself
/// (`GET /api/v1/tenant` → `{name, branding: {logo_url, accent}, ...}`,
/// `PUT /api/v1/tenant/branding` → `{"branding": {...merged}}`) rather than invented.
///
/// ONE INITIAL LOAD, NOT TWO — found live (the owner's own catch): the brand card and the vehicle
/// card each fetched and each showed their OWN full-section spinner independently, so opening this
/// screen showed two generic circles stacked one under the other before either card had data. This
/// screen now fetches both in parallel itself and shows exactly one loading state — the app's own
/// wordmark, never a generic spinner, same "راجِع IS the logo" rule `login_screen.dart`'s own
/// `_buildLogo()` already established — then hands each card its already-loaded value. A card's
/// own SAVE is still its own small inline spinner (a 18px circle inside a button reads fine at
/// that size; the wordmark does not).
class ShopIdentityScreen extends StatefulWidget {
  const ShopIdentityScreen({super.key});

  @override
  State<ShopIdentityScreen> createState() => _ShopIdentityScreenState();
}

class _ShopIdentityScreenState extends State<ShopIdentityScreen> {
  TenantIdentity? _tenant;
  bool? _tracksVehicle;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    final results = await Future.wait([auth.fetchTenant(), auth.fetchTracksVehicle()]);
    if (!mounted) return;
    setState(() {
      _tenant = results[0] as TenantIdentity?;
      _tracksVehicle = results[1] as bool?;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'account.shop',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(
          backgroundColor: AppColors.surface0,
          elevation: 0,
          title: Text(s.shopIdentityPageTitle, style: AppTextStyles.headlineSmall),
          leading: AppBackButton(
            // `canPop` GUARDED, NOT A BARE `context.pop()` — found live: opening this screen by a
            // direct URL (a deep link, a browser reload sitting on `/account/shop`, a resumed
            // app) leaves an empty navigation stack, and `pop()` on an empty stack throws
            // `GoError: There is nothing to pop` instead of doing anything. Falls back to the
            // real parent route it always has regardless of how it was reached.
            onPressed: () => context.canPop()
                ? context.pop()
                : context.go(RouteNames.accountPath),
          ),
        ),
        body: SafeArea(
          child: _loading
              ? const BrandLoadingIndicator()
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  children: [
                    _BrandCard(initialTenant: _tenant),
                    const SizedBox(height: AppSpacing.lg),
                    _VehicleTrackingCard(initialTracksVehicle: _tracksVehicle),
                    const SizedBox(height: AppSpacing.lg),
                    const _BranchesRow(),
                  ],
                ),
        ),
      ),
    );
  }
}

/// «هويتك» — the name, logo and accent colour his customer actually sees, real read/write against
/// `tenant-service` (see this file's own header note for the exact confirmed contract). The
/// preview band mirrors console's own `BrandCard`: it is the actual header his customer's page
/// draws, at this width, never a swatch beside a button.
class _BrandCard extends StatefulWidget {
  final TenantIdentity? initialTenant;
  const _BrandCard({required this.initialTenant});

  @override
  State<_BrandCard> createState() => _BrandCardState();
}

class _BrandCardState extends State<_BrandCard> with WidgetsBindingObserver {
  static const _defaultAccent = '#B08A3E';
  static const _logoPx = 256;

  late TenantIdentity? _tenant;
  late TextEditingController _nameController;
  late TextEditingController _accentController;
  String _logoDataUri = '';
  bool _saving = false;
  bool _pickingImage = false;
  String? _error;
  String? _saved;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _tenant = widget.initialTenant;
    _nameController = TextEditingController(text: _tenant?.name ?? '');
    _accentController = TextEditingController(
      text: (_tenant?.accent.isNotEmpty == true ? _tenant!.accent : _defaultAccent).toUpperCase(),
    );
    _logoDataUri = _tenant?.logoUrl ?? '';
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _nameController.dispose();
    _accentController.dispose();
    super.dispose();
  }

  // KNOWN image_picker_for_web LIMITATION, WORKED AROUND HERE — the plugin only learns the file
  // dialog was CANCELLED via the <input type="file">'s own `cancel` DOM event
  // (image_picker_for_web's own `_getSelectedXFiles`), which many browsers never fire. Without
  // this, cancelling the OS/browser file picker left `_pickingImage` stuck true forever — the
  // exact "still just brings a loading circle" report, found live. The browser tab regaining
  // focus (Flutter surfaces this on web as `AppLifecycleState.resumed`) reliably means the
  // native dialog closed one way or another, so a short grace period after that — long enough
  // for a real `onchange` to already have landed — safely unsticks the button if no file arrived.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed || !_pickingImage) return;
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted && _pickingImage) setState(() => _pickingImage = false);
    });
  }

  Future<void> _refresh() async {
    final auth = context.read<AuthProvider>();
    final tenant = await auth.fetchTenant();
    if (!mounted) return;
    setState(() {
      _tenant = tenant;
      _nameController.text = tenant?.name ?? '';
      _accentController.text =
          (tenant?.accent.isNotEmpty == true ? tenant!.accent : _defaultAccent).toUpperCase();
      _logoDataUri = tenant?.logoUrl ?? '';
    });
  }

  Color? get _accentColor {
    final hex = _accentController.text.trim();
    final match = RegExp(r'^#?([0-9a-fA-F]{6})$').firstMatch(hex);
    if (match == null) return null;
    return Color(int.parse('FF${match.group(1)}', radix: 16));
  }

  /// Opens a real palette — found live (2026-09-28), reported by the owner: this field was a
  /// plain hex text box with no way to open one at all, unlike console's own
  /// `<input type="color">` (the browser's native wheel). Seeds the wheel with whatever hex is
  /// already typed (falling back to the current default) so opening it never resets a color he
  /// already chose; only writes the hex field back on "تم" — a cancelled dialog changes nothing.
  Future<void> _openColorPicker() async {
    final s = S.of(context)!;
    var picked = _accentColor ?? const Color(0xFFB08A3E);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.shopIdentityColorLabel),
        content: SingleChildScrollView(
          child: ColorPicker(
            pickerColor: picked,
            onColorChanged: (c) => picked = c,
            enableAlpha: false,
            labelTypes: const [],
          ),
        ),
        actions: [
          KbAnchor(
            id: 'account.shop.color_picker.cancel',
            child: TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(MaterialLocalizations.of(dialogContext).cancelButtonLabel),
            ),
          ),
          KbAnchor(
            id: 'account.shop.color_picker.confirm',
            child: TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(MaterialLocalizations.of(dialogContext).okButtonLabel),
            ),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _accentController.text =
          '#${picked.toARGB32().toRadixString(16).substring(2).toUpperCase()}';
    });
  }

  Future<void> _pickLogo() async {
    final s = S.of(context)!;
    setState(() {
      _pickingImage = true;
      _error = null;
      _saved = null;
    });
    try {
      final picker = ImagePicker();
      final file = await picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: _logoPx.toDouble(),
        maxHeight: _logoPx.toDouble(),
        imageQuality: 85,
      );
      if (file == null) {
        setState(() => _pickingImage = false);
        return;
      }
      final bytes = await file.readAsBytes();
      final mime = file.mimeType ?? 'image/jpeg';
      setState(() {
        _logoDataUri = 'data:$mime;base64,${base64Encode(bytes)}';
        _pickingImage = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _pickingImage = false;
        _error = s.shopIdentityLogoPickFailed;
      });
    }
  }

  Future<void> _save() async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    final accent = _accentColor;
    if (accent == null) {
      setState(() => _error = s.shopIdentityInvalidColor);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
      _saved = null;
    });

    final newName = _nameController.text.trim();
    // THE NAME GOES FIRST, SAME ORDER CONSOLE'S OWN `submit` USES — it is the field he actually
    // came to fix, so a branding failure must not also leave the name unsaved.
    if (newName.isNotEmpty && newName != (_tenant?.name ?? '')) {
      final nameOk = await auth.setShopName(newName);
      if (!nameOk) {
        if (!mounted) return;
        setState(() {
          _saving = false;
          _error = s.shopIdentitySaveFailed;
        });
        return;
      }
    }

    final accentHex =
        '#${accent.toARGB32().toRadixString(16).substring(2).toUpperCase()}';
    final brandingOk = await auth.setBranding(
      current: _tenant?.rawBranding ?? const {},
      logoUrl: _logoDataUri,
      accent: accentHex,
    );
    if (!mounted) return;
    if (!brandingOk) {
      setState(() {
        _saving = false;
        _error = s.shopIdentitySaveFailed;
      });
      return;
    }
    setState(() => _saved = s.shopIdentitySaved);
    await _refresh();
    if (!mounted) return;
    setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

    final previewColor = _accentColor ?? const Color(0xFFB08A3E);
    final previewName =
        _nameController.text.trim().isNotEmpty ? _nameController.text.trim() : s.shopIdentityDefaultName;

    return RjSheen(
      borderRadius: AppRadius.cardRadius,
      child: Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: border),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.shopIdentityBrandTitle,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.md),

          // THE ACTUAL BAND HIS CUSTOMER'S PAGE DRAWS, at this width — not a colour swatch beside
          // a button (console's own `BrandCard` note on the bug this shape replaced).
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg, horizontal: AppSpacing.md),
            decoration: BoxDecoration(color: previewColor, borderRadius: AppRadius.cardRadius),
            child: Column(
              children: [
                if (_logoDataUri.isNotEmpty)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(AppRadius.md),
                    child: Container(
                      width: 56,
                      height: 56,
                      color: Colors.white.withValues(alpha: 0.15),
                      child: _buildLogoImage(),
                    ),
                  ),
                if (_logoDataUri.isNotEmpty) const SizedBox(height: AppSpacing.sm),
                Text(previewName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.bodyMedium
                        .copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(s.shopIdentityCustomerPagePreview,
                    style: AppTextStyles.caption.copyWith(color: Colors.white.withValues(alpha: 0.75))),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          Text(s.shopIdentityNameLabel,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.xs),
          KbAnchor(
            id: 'account.shop.brand_name_field',
            child: TextField(
              controller: _nameController,
              maxLength: 120,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(isDense: true, counterText: ''),
            ),
          ),
          const SizedBox(height: AppSpacing.md),

          KbAnchor(
            id: 'account.shop.brand_logo',
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickingImage ? null : _pickLogo,
                    icon: _pickingImage
                        ? const SizedBox(
                            width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.image_rounded, size: 18),
                    label:
                        Text(_logoDataUri.isEmpty ? s.shopIdentityUploadLogo : s.shopIdentityChangeLogo),
                  ),
                ),
                if (_logoDataUri.isNotEmpty) ...[
                  const SizedBox(width: AppSpacing.sm),
                  IconButton(
                    onPressed: () => setState(() => _logoDataUri = ''),
                    icon: const Icon(Icons.close_rounded),
                    tooltip: s.shopIdentityRemoveLogo,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          Text(s.shopIdentityColorLabel,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.xs),
          KbAnchor(
            id: 'account.shop.brand_color_field',
            child: Row(
              children: [
                InkWell(
                  onTap: _openColorPicker,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  child: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: _accentColor ?? Colors.transparent,
                      borderRadius: BorderRadius.circular(AppRadius.md),
                      border: Border.all(color: border, width: _accentColor == null ? 1.5 : 1),
                    ),
                    child: _accentColor == null
                        ? const Icon(Icons.close_rounded, color: Colors.redAccent, size: 18)
                        : null,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: TextField(
                    controller: _accentController,
                    textDirection: TextDirection.ltr,
                    maxLength: 7,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(isDense: true, counterText: ''),
                  ),
                ),
                TextButton(
                  onPressed: () => setState(() => _accentController.text = _defaultAccent),
                  child: Text(s.shopIdentityResetColor),
                ),
              ],
            ),
          ),

          if (_error != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
          ],
          if (_saved != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_saved!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          ],

          const SizedBox(height: AppSpacing.md),
          CapabilityGate(
            requires: const ['tenant.update_branding'],
            child: KbAnchor(
              id: 'account.shop.brand_save',
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(s.shopIdentitySave),
                ),
              ),
            ),
          ),
        ],
      ),
      ),
    );
  }

  Widget _buildLogoImage() {
    try {
      final base64Part = _logoDataUri.split(',').last;
      return Image.memory(base64Decode(base64Part), fit: BoxFit.contain);
    } catch (_) {
      return const SizedBox.shrink();
    }
  }
}

/// «هل محلك يعمل على السيارات؟» — `GET`/`PUT /api/v1/staff/vehicles`, the exact real read
/// `apps/mobile/lib/features/visit/visit_screen.dart`'s own plate field already assumed existed
/// somewhere (found live while building this screen: the toggle it depends on had no home on
/// mobile at all until now). Two-way, unlike branch mode — a shop that tries it and stops working
/// on cars simply says so again (route's own docstring).
class _VehicleTrackingCard extends StatefulWidget {
  final bool? initialTracksVehicle;
  const _VehicleTrackingCard({required this.initialTracksVehicle});

  @override
  State<_VehicleTrackingCard> createState() => _VehicleTrackingCardState();
}

class _VehicleTrackingCardState extends State<_VehicleTrackingCard> {
  late bool? _tracksVehicle;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tracksVehicle = widget.initialTracksVehicle;
  }

  Future<void> _flip(bool next) async {
    final s = S.of(context)!;
    setState(() {
      _busy = true;
      _error = null;
    });
    final auth = context.read<AuthProvider>();
    final applied = await auth.setTracksVehicle(next);
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (applied != null) {
        _tracksVehicle = applied;
      } else {
        _error = s.shopIdentityVehicleSaveFailed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

    return CapabilityGate(
      requires: const ['operations.set_shop_vehicles'],
      child: KbAnchor(
      id: 'account.shop.vehicle_toggle',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      child: Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: border),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      (dark ? AppDarkColors.accent : AppColors.accent),
                      (dark ? AppDarkColors.accent : AppColors.accent).withValues(alpha: 0.75),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(AppRadius.md),
                ),
                child: const Icon(Icons.directions_car_filled_rounded, color: Colors.white, size: 22),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.shopIdentityVehicleTitle,
                        style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(s.shopIdentityVehicleDesc,
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                  ],
                ),
              ),
              if (_busy)
                const SizedBox(
                  width: 20, height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Switch(
                  value: _tracksVehicle ?? false,
                  onChanged: (next) => _flip(next),
                ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
          ],
        ],
      ),
      ),
      ),
      ),
    );
  }
}

/// Entry point into «الفروع» — every branch-scoped fact (address, واتساب, الفريق) lives there now,
/// never in this screen (this file's own header note on why).
class _BranchesRow extends StatelessWidget {
  const _BranchesRow();

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;

    return KbAnchor(
      id: 'account.shop.branches_row',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: accent,
      child: Material(
      color: Colors.transparent,
      borderRadius: AppRadius.cardRadius,
      child: InkWell(
        onTap: () => context.push(RouteNames.branchesPath),
        borderRadius: AppRadius.cardRadius,
        child: Ink(
          decoration: BoxDecoration(
            color: surface,
            borderRadius: AppRadius.cardRadius,
            border: Border.all(color: border),
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
                      colors: [accent, accent.withValues(alpha: 0.75)],
                    ),
                  ),
                  child: const Icon(Icons.storefront_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(s.shopIdentityBranchesRow,
                      style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                ),
                Icon(
                  Directionality.of(context) == TextDirection.rtl
                      ? Icons.chevron_left_rounded
                      : Icons.chevron_right_rounded,
                  color: dark ? AppDarkColors.textMuted : AppColors.textMuted,
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
