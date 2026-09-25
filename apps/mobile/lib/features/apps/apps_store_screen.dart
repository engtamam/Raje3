import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show BillingOverview, BillingPlan, BillingSubscription;
import 'package:raje3_mobile/features/apps/payment_webview_screen.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/app_store_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «تطبيقاتي» / متجر التطبيقات — mirrors AppLauncher.tsx's own two-shelf design EXACTLY
/// (parity/app_store.md, studied from the real console source line by line before writing a
/// single widget here): «تطبيقاتي» is pure navigation with zero money on screen, «المتجر» is
/// the one and only place anything is sold. `BillingPlan`/`BillingSubscription` are the SAME
/// classes «الفوترة» (billing_screen.dart) reads — one model set, not a second copy — and
/// paying an already-owed invoice is billing_screen.dart's own job alone; this screen only
/// sells what is not yet owned.
class AppsStoreScreen extends StatefulWidget {
  const AppsStoreScreen({super.key, this.initialStoreTab = false});

  /// Land directly on «متجر التطبيقات» — used when a real refusal (seat/branch limit reached)
  /// sends the owner here to actually buy capacity, never the plain "تطبيقاتي" navigation shelf.
  final bool initialStoreTab;

  @override
  State<AppsStoreScreen> createState() => _AppsStoreScreenState();
}

class _AppsStoreScreenState extends State<AppsStoreScreen> {
  Owned? _owned;
  List<BillingPlan>? _plans;
  List<BillingSubscription>? _subs;
  late bool _tab = widget.initialStoreTab; // false = "my apps" shelf, true = "store" shelf
  final Set<String> _cart = {};
  CartPreview? _cartPreview;
  bool _cartPreviewBusy = false;
  bool _checkingOut = false;
  String _error = '';
  String _capacityBusyPlanId = '';
  String _capacityError = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    final results = await Future.wait([auth.fetchOwnership(), auth.fetchPurchasablePlans(), auth.fetchBillingOverview()]);
    if (!mounted) return;
    setState(() {
      _owned = results[0] as Owned?;
      _plans = results[1] as List<BillingPlan>?;
      _subs = (results[2] as BillingOverview?)?.subscriptions;
    });
  }

  BillingPlan? _planFor(String key) {
    if (key.isEmpty) return null;
    for (final p in _plans ?? const <BillingPlan>[]) {
      if (p.appKey == key) return p;
    }
    return null;
  }

  BillingSubscription? _subFor(String planId) {
    for (final s in _subs ?? const <BillingSubscription>[]) {
      if (s.planId == planId && s.status != 'canceled') return s;
    }
    return null;
  }

  /// billingShared.tsx::kindOf — a capacity row carries no `feature.*` limit at all.
  List<BillingPlan> get _capacityPlans => (_plans ?? const <BillingPlan>[]).where((p) => p.isCapacity).toList();

  Future<void> _buyFirstCapacityUnit(BillingPlan plan) async {
    setState(() { _capacityBusyPlanId = plan.id; _capacityError = ''; });
    final ok = await _subscribeOrCheckout(plan);
    if (!mounted) return;
    setState(() => _capacityBusyPlanId = '');
    if (ok) await _load();
  }

  /// ONE PLAN, EITHER PATH — a real pay-link for anything that actually costs something today
  /// (TuwaiqPay has no card-on-file, only a hosted checkout link: `checkoutLink`, opened in-app
  /// exactly like an invoice pay-link — `payment_webview_screen.dart`'s own doc), or the plain
  /// no-payment call for a free/trial plan (`BillingPlan.needsPayment`, mirrors the console's own
  /// `subscribeFlow.ts::needsNoPayment` and the server's own `may_subscribe`). Sets `_error`/
  /// `_capacityError` itself; the caller only decides whether to reload on success.
  Future<bool> _subscribeOrCheckout(BillingPlan plan) async {
    final auth = context.read<AuthProvider>();
    if (!plan.needsPayment) {
      final (ok, status) = await auth.subscribeToApp(planId: plan.id);
      if (!mounted) return false;
      if (!ok) _setPurchaseError(plan, _refusalMessage(status));
      return ok;
    }
    final (url, status) = await auth.checkoutLink(planId: plan.id);
    if (!mounted) return false;
    if (url == null) {
      _setPurchaseError(plan, _refusalMessage(status));
      return false;
    }
    await openPaymentInApp(context, url);
    // THE REAL OUTCOME IS THE SERVER'S — same posture as billing_screen.dart's own pay-link
    // flows: this screen never assumes success just because the WebView closed, it reloads and
    // reads back whatever billing actually settled to (still locked, on TuwaiqPay's own webhook
    // lag — billing_screen.dart shows the same "confirming" grace-window sentence on «الفوترة»).
    return true;
  }

  void _setPurchaseError(BillingPlan plan, String message) {
    if (plan.isCapacity) {
      setState(() => _capacityError = message);
    } else {
      setState(() => _error = message);
    }
  }

  Future<void> _changeCapacityQuantity(BillingPlan plan, BillingSubscription sub, int quantity) async {
    setState(() { _capacityBusyPlanId = plan.id; _capacityError = ''; });
    final ok = await context.read<AuthProvider>()
        .changeCapacityQuantity(subscriptionId: sub.id, planId: plan.id, quantity: quantity);
    if (!mounted) return;
    setState(() => _capacityBusyPlanId = '');
    if (ok) {
      await _load();
    } else {
      setState(() => _capacityError = S.of(context)!.appStoreRefusalGeneric);
    }
  }

  Future<void> _removeLastCapacityUnit(BillingSubscription sub) async {
    setState(() => _capacityBusyPlanId = sub.planId);
    final ok = await context.read<AuthProvider>().cancelSubscription(sub.id);
    if (!mounted) return;
    setState(() => _capacityBusyPlanId = '');
    if (ok) {
      await _load();
    } else {
      setState(() => _capacityError = S.of(context)!.appStoreRefusalGeneric);
    }
  }

  void _toggleCart(String planId) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_cart.contains(planId)) {
        _cart.remove(planId);
      } else {
        _cart.add(planId);
      }
    });
    _refreshCartPreview();
  }

  Future<void> _refreshCartPreview() async {
    if (_cart.isEmpty) {
      setState(() { _cartPreview = null; _cartPreviewBusy = false; });
      return;
    }
    setState(() => _cartPreviewBusy = true);
    final preview = await context.read<AuthProvider>().checkoutPreview(_cart.toList());
    if (!mounted) return;
    setState(() { _cartPreview = preview; _cartPreviewBusy = false; });
  }

  int get _cartListTotal {
    var total = 0;
    for (final id in _cart) {
      final plan = (_plans ?? const <BillingPlan>[]).where((p) => p.id == id).firstOrNull;
      total += plan?.monthlyAmountMinor ?? 0;
    }
    return total;
  }

  Future<void> _openCheckout() async {
    setState(() { _checkingOut = true; _error = ''; });
    final (url, ok, status) = await context.read<AuthProvider>().checkoutCart(_cart.toList());
    if (!mounted) return;
    if (!ok) {
      setState(() { _checkingOut = false; _error = _refusalMessage(status); });
      return;
    }
    if (url != null) {
      // A REAL PRICE, A REAL LINK — the same in-app WebView every other payment on this app opens
      // (billing_screen.dart's own pattern). The cart is left alone until we know the payment
      // actually settled; `_load()` below reads that back from the server, never assumed here.
      await openPaymentInApp(context, url);
    }
    if (!mounted) return;
    setState(() { _checkingOut = false; _cart.clear(); _cartPreview = null; });
    await _load();
  }

  Future<void> _quickSubscribe(BillingPlan plan) async {
    setState(() => _error = '');
    final ok = await _subscribeOrCheckout(plan);
    if (!mounted) return;
    if (ok) await _load();
  }

  /// Same honest posture referral_partnership_screen.dart's own `_refusalMessage` takes — the
  /// server strips every refusal's TEXT in transit, but the HTTP status survives and names the
  /// real family of causes for it, never a single guessed sentence.
  String _refusalMessage(int? status) {
    final s = S.of(context)!;
    switch (status) {
      case 402: return s.appStoreRefusal402;
      case 403: return s.appStoreRefusal403;
      case 404: return s.appStoreRefusal404;
      case 409: return s.appStoreRefusal409;
      default: return s.appStoreRefusalGeneric;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final colors = context.appColors;

    // «تطبيقاتي» = owned AND has somewhere real to open — launcherCatalog.ts::myApps only ever
    // lists a row with a real section/openPath; an owned row with neither has nothing to
    // navigate to and stays exclusive to «متجر التطبيقات» until it gets a mobile screen.
    final rows = _tab
        ? kAppRows
        : kAppRows.where((r) => r.route != null && (r.key == null || _owned?.owns(r.key!) == true)).toList();

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: RefreshIndicator(
        onRefresh: _load,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Container(
                decoration: BoxDecoration(
                  gradient: primaryGradient(dark: dark),
                  borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
                  boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
                ),
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(s.appStoreTitle, style: AppTextStyles.displaySmall.copyWith(color: AppColors.accentContrast)),
                        const SizedBox(height: 2),
                        Text(s.appStoreSubtitle,
                            style: AppTextStyles.bodySmall.copyWith(color: AppColors.accentContrast.withValues(alpha: 0.85))),
                        const SizedBox(height: AppSpacing.md),
                        Container(
                          padding: const EdgeInsets.all(2),
                          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
                          child: Row(
                            children: [
                              Expanded(child: _TabPill(label: s.appStoreTabMine, selected: !_tab, onTap: () => setState(() => _tab = false))),
                              Expanded(child: _TabPill(label: s.appStoreTabAll, selected: _tab, onTap: () => setState(() => _tab = true))),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            if (_owned == null)
              const SliverFillRemaining(hasScrollBody: false, child: BrandLoadingIndicator())
            else
              SliverPadding(
                // EXTRA TOP PADDING — the poster card's own add-to-cart button now overlaps its
                // BOTTOM corner (a real elevated FAB, not an inline icon), so the row above it
                // needs the same clearance the row below already gets from `mainAxisSpacing`.
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.lg, AppSpacing.md, AppSpacing.xxl),
                sliver: SliverGrid(
                  // «متجر التطبيقات» (_tab true) cards carry an extra price row + «التفاصيل» pill
                  // the «تطبيقاتي» ones don't (showBilling: _tab below) — a single aspect ratio
                  // sized for the taller variant left the shorter one mostly empty gradient (the
                  // owner's own catch, 2026-09-24: "البطاقة كبيرة وفاضية والكلام صغير جدا").
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2, mainAxisSpacing: AppSpacing.lg, crossAxisSpacing: AppSpacing.sm,
                    childAspectRatio: _tab ? 0.95 : 1.55,
                  ),
                  delegate: SliverChildBuilderDelegate(
                    (context, i) {
                      final row = rows[i];
                      final plan = row.key != null ? _planFor(row.key!) : null;
                      final owned = row.key == null ? true : _owned?.owns(row.key!);
                      final sub = plan != null ? _subFor(plan.id) : null;
                      return TweenAnimationBuilder<double>(
                        // STAGGERED REVEAL — each tile fades/rises in a beat after the last, never
                        // all forty at once (2026-09-23 design research, parity/app_store.md's own
                        // sibling note on this screen's premium-motion checklist).
                        tween: Tween(begin: 0, end: 1),
                        duration: Duration(milliseconds: 320 + i * 45),
                        curve: Curves.easeOutCubic,
                        builder: (context, v, child) => Opacity(
                          opacity: v,
                          child: Transform.translate(offset: Offset(0, (1 - v) * 16), child: child),
                        ),
                        child: _AppCard(
                          row: row,
                          owned: owned,
                          plan: plan,
                          sub: sub,
                          showBilling: _tab,
                          inCart: plan != null && _cart.contains(plan.id),
                          onToggleCart: plan != null && owned != true ? () => _toggleCart(plan.id) : null,
                          onOpen: () {
                            if (row.route != null) {
                              context.go('/${row.route}');
                            } else {
                              _showDetails(row, plan, owned, sub);
                            }
                          },
                          onTapDetails: () => _showDetails(row, plan, owned, sub),
                        ),
                      );
                    },
                    childCount: rows.length,
                  ),
                ),
              ),
            // «السعة» — ONLY under «متجر التطبيقات», never «تطبيقاتي» (AppLauncher.tsx's own
            // rule: a seat/branch add-on is not a section a role opens, so it has no home on the
            // navigation shelf at all — parity/app_store.md §6).
            if (_tab && _capacityPlans.isNotEmpty)
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
                sliver: SliverList.list(children: [
                  Text(s.appStoreCapacityTitle, style: AppTextStyles.labelMedium),
                  const SizedBox(height: AppSpacing.sm),
                  if (_capacityError.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: Text(_capacityError, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
                    ),
                  for (final plan in _capacityPlans)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: _CapacityCard(
                        plan: plan,
                        sub: _subFor(plan.id),
                        busy: _capacityBusyPlanId == plan.id,
                        onBuyFirst: () => _buyFirstCapacityUnit(plan),
                        onChangeQuantity: (sub, q) => _changeCapacityQuantity(plan, sub, q),
                        onRemoveLast: _removeLastCapacityUnit,
                      ),
                    ),
                ]),
              ),
          ],
        ),
      ),
      bottomNavigationBar: _tab && _cart.isNotEmpty
          ? _CartBar(
              plans: _cart.map((id) => (_plans ?? const <BillingPlan>[]).where((p) => p.id == id).firstOrNull).whereType<BillingPlan>().toList(),
              listTotal: _cartListTotal,
              preview: _cartPreview,
              previewBusy: _cartPreviewBusy,
              busy: _checkingOut,
              error: _error,
              onRemove: _toggleCart,
              onCheckout: _openCheckout,
            )
          : (_error.isNotEmpty
              ? SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    child: Text(_error, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                  ),
                )
              : null),
    );
  }

  void _showDetails(AppRow row, BillingPlan? plan, bool? owned, BillingSubscription? sub) {
    final auth = context.read<AuthProvider>();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AppDetailsSheet(
        row: row, plan: plan, owned: owned, sub: sub,
        onSubscribe: plan != null ? () => _quickSubscribe(plan) : null,
        onCancel: sub != null ? () async { final ok = await auth.cancelSubscription(sub.id); if (ok) await _load(); } : null,
        onUndoCancel: sub != null && sub.cancelAtPeriodEnd
            ? () async { final ok = await auth.undoCancelSubscription(sub.id); if (ok) await _load(); }
            : null,
      ),
    );
  }
}

class _TabPill extends StatelessWidget {
  const _TabPill({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? Colors.white.withValues(alpha: 0.22) : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 9),
          child: Text(label, textAlign: TextAlign.center,
              style: AppTextStyles.bodySmall.copyWith(color: Colors.white, fontWeight: selected ? FontWeight.w800 : FontWeight.w500)),
        ),
      ),
    );
  }
}

const Map<String, IconData> _appIcons = {
  'megaphone': Icons.campaign_rounded,
  'gift': Icons.card_giftcard_rounded,
  'calendar': Icons.calendar_month_rounded,
  'sparkles': Icons.auto_awesome_rounded,
  'star': Icons.star_rounded,
  'user-plus': Icons.person_add_rounded,
  'check-circle': Icons.check_circle_rounded,
  'message-circle': Icons.chat_bubble_rounded,
  'users': Icons.handshake_rounded,
  'hand-heart': Icons.volunteer_activism_rounded,
  'bot': Icons.smart_toy_rounded,
  'truck': Icons.local_shipping_rounded,
};

String _riyals(int minor) => '${(minor / 100).toStringAsFixed(minor % 100 == 0 ? 0 : 2)} ﷼';

/// ONE DISTINCT COLOR PER APP — a card of a small icon on an otherwise-empty white surface reads
/// as generic and lifeless (the owner's own words, 2026-09-23: "ايقونه ميتة"). Hashing the app's
/// own id into a hue — the same technique services_screen.dart's own poster placeholder already
/// uses for photo-less service cards — makes a shelf of a dozen apps read as a dozen distinct
/// products at a glance, never one purple tile repeated twelve times.
Color _appAccent(String id) {
  final hue = (id.codeUnits.fold<int>(0, (a, b) => a + b) * 47) % 360;
  return HSLColor.fromAHSL(1, hue.toDouble(), 0.62, 0.46).toColor();
}

/// THE POSTER TILE — the whole card is a bold colour field, never a small icon on a mostly-empty
/// card. Real type scale: the app name and price are the loudest things on the card, not a
/// caption squeezed under a wall of dead space. Add-to-cart is a real, elevated circular button
/// overlapping the card's own corner — the same unmistakable affordance every real marketplace
/// product card uses (Amazon/Noon/Shein's own "+" corner button), never a small ghost outline
/// nobody notices. The VIP app alone carries a continuous light-sweep via RjSheen (never all
/// cards at once — that reads as noise, not luxury).
class _AppCard extends StatefulWidget {
  const _AppCard({
    required this.row, required this.owned, required this.plan, required this.sub,
    required this.showBilling, required this.inCart, required this.onToggleCart,
    required this.onOpen, required this.onTapDetails,
  });
  final AppRow row;
  final bool? owned;
  final BillingPlan? plan;
  final BillingSubscription? sub;
  final bool showBilling;
  final bool inCart;
  final VoidCallback? onToggleCart;
  final VoidCallback onOpen;
  final VoidCallback onTapDetails;

  @override
  State<_AppCard> createState() => _AppCardState();
}

class _AppCardState extends State<_AppCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final locked = widget.owned == false;
    final icon = _appIcons[widget.row.icon] ?? Icons.apps_rounded;
    final vip = widget.row.vip;
    final accent = _appAccent(widget.row.id);

    final card = AnimatedScale(
      scale: _pressed ? 0.96 : 1,
      duration: const Duration(milliseconds: 120),
      curve: Curves.easeOut,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: AppRadius.cardRadius,
          gradient: vip
              ? const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [Color(0xFF1A1207), Color(0xFF2F210C), Color(0xFF4A3512)])
              : LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [accent, HSLColor.fromColor(accent).withLightness(0.28).toColor()]),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        clipBehavior: Clip.none,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 52, height: 52,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: vip ? const Color(0x33D4AF37) : Colors.white.withValues(alpha: 0.22),
                          border: Border.all(color: Colors.white.withValues(alpha: 0.35), width: 1.5),
                        ),
                        alignment: Alignment.center,
                        child: Icon(icon, color: vip ? const Color(0xFFF4E2A4) : Colors.white, size: 28),
                      ),
                      const Spacer(),
                      if (locked)
                        Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.black.withValues(alpha: 0.28)),
                          child: const Icon(Icons.lock_rounded, size: 16, color: Colors.white),
                        )
                      else if (widget.owned == true)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                          decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.28), borderRadius: BorderRadius.circular(AppRadius.pill)),
                          child: Text(
                            widget.sub?.status == 'trialing' ? S.of(context)!.appStoreTrialing : S.of(context)!.appStoreActive,
                            style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w800),
                          ),
                        ),
                    ],
                  ),
                  const Spacer(),
                  Text(
                    widget.row.name, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w900, color: Colors.white, height: 1.15),
                  ),
                  if (widget.showBilling && widget.plan != null) ...[
                    const SizedBox(height: 6),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(_riyals(widget.plan!.monthlyAmountMinor),
                            style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w900, color: Colors.white)),
                        const SizedBox(width: 3),
                        Text(S.of(context)!.appStorePerMonthShort,
                            style: AppTextStyles.bodySmall.copyWith(color: Colors.white.withValues(alpha: 0.85), fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ],
                  if (widget.showBilling) ...[
                    const SizedBox(height: 8),
                    GestureDetector(
                      onTap: widget.onTapDetails,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(AppRadius.pill)),
                        child: Text(S.of(context)!.appStoreDetails,
                            style: AppTextStyles.bodySmall.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            // THE ADD-TO-CART BUTTON — a real, elevated, unmistakable circular FAB overlapping the
            // card's own bottom-end corner, exactly the affordance real marketplace product cards
            // use, never a small ghost outline.
            if (widget.onToggleCart != null)
              PositionedDirectional(
                bottom: -10, end: 10,
                child: GestureDetector(
                  onTap: widget.onToggleCart,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    width: 40, height: 40,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: widget.inCart ? AppColors.success : Colors.white,
                      boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 10, offset: Offset(0, 3))],
                    ),
                    alignment: Alignment.center,
                    child: Icon(widget.inCart ? Icons.check_rounded : Icons.add_shopping_cart_rounded,
                        color: widget.inCart ? Colors.white : accent, size: 20),
                  ),
                ),
              ),
          ],
        ),
      ),
    );

    final tappable = GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: () { HapticFeedback.lightImpact(); widget.onOpen(); },
      child: card,
    );

    return vip ? RjSheen(borderRadius: AppRadius.cardRadius, tint: const Color(0xFFD4AF37), child: tappable) : tappable;
  }
}

/// ONE CARD PER CAPACITY KIND (موظفين/فروع) — mirrors billingShared.tsx::CapacityAddonCard: the
/// FIRST unit goes through `_subscribeOrCheckout` like any other app (a real pay-link if the plan
/// actually costs something — TuwaiqPay has no card-on-file, only a hosted checkout link); every
/// unit after that is the same subscription's own `quantity` moved up or down, no new payment
/// involved (billing-service's own change-quantity route, already covered by whatever card/link
/// paid for the first unit). Removing the last unit needs a confirm step first — it cancels the
/// whole subscription, same as any other app.
class _CapacityCard extends StatefulWidget {
  const _CapacityCard({
    required this.plan, required this.sub, required this.busy,
    required this.onBuyFirst, required this.onChangeQuantity, required this.onRemoveLast,
  });
  final BillingPlan plan;
  final BillingSubscription? sub;
  final bool busy;
  final VoidCallback onBuyFirst;
  final void Function(BillingSubscription sub, int quantity) onChangeQuantity;
  final void Function(BillingSubscription sub) onRemoveLast;

  @override
  State<_CapacityCard> createState() => _CapacityCardState();
}

class _CapacityCardState extends State<_CapacityCard> {
  bool _confirming = false;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final qty = widget.sub?.quantity ?? 0;

    if (_confirming && widget.sub != null) {
      return CapabilityGate(
        requires: const ['billing.self'],
        child: KbAnchor(
        id: 'apps.capacity_confirm_remove',
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)), borderRadius: AppRadius.standardRadius, color: AppColors.danger.withValues(alpha: 0.06)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.appStoreCapacityConfirmRemove(widget.plan.name), style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700, color: AppColors.danger)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: OutlinedButton(
                  onPressed: widget.busy ? null : () { setState(() => _confirming = false); widget.onRemoveLast(widget.sub!); },
                  style: OutlinedButton.styleFrom(foregroundColor: AppColors.danger, side: const BorderSide(color: AppColors.danger)),
                  child: Text(widget.busy ? s.appStoreCheckingOut : s.appStoreCancelRenewal),
                )),
                const SizedBox(width: 8),
                Expanded(child: OutlinedButton(onPressed: () => setState(() => _confirming = false), child: Text(s.mobileRequestsRejectCancel))),
              ]),
            ],
          ),
        ),
        ),
      );
    }

    return CapabilityGate(
      requires: const ['billing.self'],
      child: KbAnchor(
      id: 'apps.capacity_stepper',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(color: colors.surface, border: Border.all(color: colors.borderSubtle), borderRadius: AppRadius.standardRadius),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(widget.plan.name, style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                  Text('${_riyals(widget.plan.monthlyAmountMinor)} ${s.appStorePerMonthShort}', style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                ],
              ),
            ),
            IconButton(
              onPressed: (widget.busy || qty == 0)
                  ? null
                  : () => qty > 1
                      ? widget.onChangeQuantity(widget.sub!, qty - 1)
                      : setState(() => _confirming = true),
              icon: const Icon(Icons.remove_circle_outline_rounded),
            ),
            Text('$qty', style: AppTextStyles.labelMedium.copyWith(fontWeight: FontWeight.w800)),
            IconButton(
              onPressed: widget.busy
                  ? null
                  : () => qty == 0 ? widget.onBuyFirst() : widget.onChangeQuantity(widget.sub!, qty + 1),
              icon: const Icon(Icons.add_circle_outline_rounded),
            ),
          ],
        ),
      ),
      ),
    );
  }
}

class _CartBar extends StatelessWidget {
  const _CartBar({
    required this.plans, required this.listTotal, required this.preview, required this.previewBusy,
    required this.busy, required this.error, required this.onRemove, required this.onCheckout,
  });
  final List<BillingPlan> plans;
  final int listTotal;
  final CartPreview? preview;
  final bool previewBusy;
  final bool busy;
  final String error;
  final ValueChanged<String> onRemove;
  final VoidCallback onCheckout;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final shownTotal = preview?.totalMinor ?? listTotal;
    return SafeArea(
      child: Container(
        margin: const EdgeInsets.all(AppSpacing.sm),
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: colors.borderSubtle),
          boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Container(
                  width: 36, height: 36,
                  decoration: BoxDecoration(color: AppColors.accent.withValues(alpha: 0.12), shape: BoxShape.circle),
                  alignment: Alignment.center,
                  child: const Icon(Icons.shopping_bag_rounded, color: AppColors.accent, size: 18),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(s.appStoreCartCount(plans.length), style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w800)),
                ),
                TweenAnimationBuilder<int>(
                  tween: IntTween(begin: 0, end: shownTotal),
                  duration: const Duration(milliseconds: 500),
                  curve: Curves.easeOutCubic,
                  builder: (context, v, _) => Text(_riyals(v), style: AppTextStyles.labelMedium.copyWith(fontWeight: FontWeight.w800)),
                ),
              ],
            ),
            if (error.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(error, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            ],
            const SizedBox(height: 8),
            CapabilityGate(
              requires: const ['billing.self'],
              child: SizedBox(
                width: double.infinity,
                child: PrimaryButton(
                  text: busy ? s.appStoreCheckingOut : s.appStoreCheckout,
                  onPressed: busy ? null : onCheckout,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AppDetailsSheet extends StatelessWidget {
  const _AppDetailsSheet({
    required this.row, required this.plan, required this.owned, required this.sub,
    this.onSubscribe, this.onCancel, this.onUndoCancel,
  });
  final AppRow row;
  final BillingPlan? plan;
  final bool? owned;
  final BillingSubscription? sub;
  final VoidCallback? onSubscribe;
  final VoidCallback? onCancel;
  final VoidCallback? onUndoCancel;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final icon = _appIcons[row.icon] ?? Icons.apps_rounded;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        decoration: const BoxDecoration(color: AppColors.surface1, borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card))),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 10),
            Container(width: 36, height: 4, decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(2))),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 52, height: 52,
                          decoration: BoxDecoration(shape: BoxShape.circle, gradient: LinearGradient(colors: [AppColors.accent, AppColors.accent.withValues(alpha: 0.7)])),
                          alignment: Alignment.center,
                          child: Icon(icon, color: Colors.white, size: 26),
                        ),
                        const SizedBox(width: 12),
                        Expanded(child: Text(row.name, style: AppTextStyles.headlineSmall)),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(row.what, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                    if (plan != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(_riyals(plan!.monthlyAmountMinor), style: AppTextStyles.headlineSmall),
                          const SizedBox(width: 4),
                          Text(s.appStorePerMonth, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      if (owned == true) ...[
                        if (sub?.cancelAtPeriodEnd == true) ...[
                          if (onUndoCancel != null)
                            CapabilityGate(
                              requires: const ['billing.self'],
                              child: KbAnchor(
                                id: 'apps.details_undo_cancel',
                                child: SizedBox(width: double.infinity, child: OutlinedButton(onPressed: onUndoCancel, child: Text(s.appStoreUndoCancel))),
                              ),
                            ),
                        ] else if (onCancel != null)
                          CapabilityGate(
                            requires: const ['billing.self'],
                            child: KbAnchor(
                              id: 'apps.details_cancel',
                              child: SizedBox(
                                width: double.infinity,
                                child: OutlinedButton(
                                  onPressed: () => showDialog<void>(
                                    context: context,
                                    builder: (dialogContext) => AlertDialog(
                                      content: Text(s.appStoreConfirmCancel),
                                      actions: [
                                        TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
                                        TextButton(
                                          onPressed: () { Navigator.of(dialogContext).pop(); onCancel!(); },
                                          child: Text(s.appStoreCancelRenewal, style: const TextStyle(color: AppColors.danger)),
                                        ),
                                      ],
                                    ),
                                  ),
                                  child: Text(s.appStoreCancelRenewal, style: const TextStyle(color: AppColors.danger)),
                                ),
                              ),
                            ),
                          ),
                      ] else if (onSubscribe != null)
                        CapabilityGate(
                          requires: const ['billing.self'],
                          child: SizedBox(width: double.infinity, child: PrimaryButton(text: s.appStoreSubscribe, onPressed: onSubscribe)),
                        ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

extension _FirstOrNullPlan<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
