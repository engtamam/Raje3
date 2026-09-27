import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/app_features_service.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show BillingOverview, BillingPlan, BillingSubscription, DiscountInfo;
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
  String _cartNotice = '';
  String _capacityBusyPlanId = '';
  String _capacityError = '';
  Map<String, DiscountInfo> _discountApplied = const {};
  Map<String, DiscountInfo> _discountPotential = const {};
  double? _unitsPerHalala;
  bool _aiEnabled = true;

  /// billingShared.tsx's own PREREQ_KEYS/DEPENDENT_KEYS — client-side cascade rule, same one
  /// `useAppBilling.ts::cascadeTargets` follows: cancelling the shop's LAST prerequisite (تسجيل
  /// زيارة/الحجوزات) takes down every app that names one of them in `plan.requires_any`.
  static const _prereqKeys = ['feature.visit', 'feature.bookings'];
  static const _dependentKeys = ['feature.loyalty', 'feature.rating', 'feature.insights.engine', 'feature.campaigns'];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    final (applied, potential) = await auth.fetchDiscountPreview();
    final (unitsPerHalala, aiEnabled) = await auth.fetchAiUnitsPerHalala();
    final results = await Future.wait([auth.fetchOwnership(), auth.fetchPurchasablePlans(), auth.fetchBillingOverview()]);
    if (!mounted) return;
    setState(() {
      _owned = results[0] as Owned?;
      _plans = results[1] as List<BillingPlan>?;
      _subs = (results[2] as BillingOverview?)?.subscriptions;
      _discountApplied = applied;
      _discountPotential = potential;
      _unitsPerHalala = unitsPerHalala;
      _aiEnabled = aiEnabled;
    });
  }

  /// `null` unless [_aiEnabled] AND the plan carries a real allowance — billingShared's own
  /// `!includedCreditMinor` guard, plus the platform-wide AI switch gate `AppLauncher.tsx`'s own
  /// `billing.aiEnabled ? includedAiCreditOf(plan) : undefined` applies.
  int? _includedCreditFor(BillingPlan? plan) => (_aiEnabled ? plan?.includedCreditMinor : null);

  /// The real app name behind a discount's `owning_key` — resolved from [kAppRows], never
  /// invented (mirrors AppLauncher.tsx's own `appNameOf`).
  String _appNameForKey(String key) => kAppRows.where((r) => r.key == key).map((r) => r.name).firstOrNull ?? key;

  /// billingShared.tsx's own `REQUIRES_ANY_KEYS` short names, falling back to the raw key for one
  /// this screen doesn't name yet — never a blank space where a real requirement should read.
  String _requiresAnyLabel(S s, String key) {
    switch (key) {
      case 'feature.visit': return s.appStoreRequiresAnyVisit;
      case 'feature.bookings': return s.appStoreRequiresAnyBookings;
      case 'feature.contacts': return s.appStoreRequiresAnyContacts;
      case 'feature.mobile_requests': return s.appStoreRequiresAnyMobileRequests;
      default: return key;
    }
  }

  /// billingShared.tsx's own `missingRequirement` — empty when the plan has no dependency, or the
  /// shop already holds one of the keys it names.
  String _missingRequirement(S s, BillingPlan plan) {
    final need = plan.requiresAny;
    if (need.isEmpty || _owned == null) return '';
    if (need.any((k) => _owned!.owns(k) == true)) return '';
    final names = need.map((k) => _requiresAnyLabel(s, k)).join(' ${s.appStoreOr} ');
    return s.appStoreMissingRequirement(names);
  }

  /// useAppBilling.ts's own `cascadeTargets` — the OTHER active app subscriptions that would lose
  /// their last prerequisite if [cancelling] goes through, so they must be named and cancelled
  /// alongside it, never silently orphaned still charging for a feature with no foundation left.
  List<BillingSubscription> _cascadeTargets(BillingSubscription cancelling) {
    final plans = _plans ?? const <BillingPlan>[];
    final subs = _subs ?? const <BillingSubscription>[];
    final cancelledPlan = plans.where((p) => p.id == cancelling.planId).firstOrNull;
    final cancelledKey = cancelledPlan?.appKey ?? '';
    if (!_prereqKeys.contains(cancelledKey)) return const [];
    final stillHasPrereq = _prereqKeys.where((k) => k != cancelledKey).any((k) {
      final p = plans.where((pp) => pp.appKey == k).firstOrNull;
      if (p == null) return false;
      return subs.any((s) => s.planId == p.id && s.id != cancelling.id && s.status != 'canceled' && !s.cancelAtPeriodEnd);
    });
    if (stillHasPrereq) return const [];
    return subs.where((s) {
      if (s.id == cancelling.id || s.status == 'canceled' || s.cancelAtPeriodEnd) return false;
      final p = plans.where((pp) => pp.id == s.planId).firstOrNull;
      return p != null && _dependentKeys.contains(p.appKey);
    }).toList(growable: false);
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

  /// useAppBilling.ts's own `toggleCart` — ADDING a plan whose own `plan.requires_any` is not
  /// already held OR already in the cart auto-adds the first plan that grants one of those keys.
  /// The owner's own instruction: never a text-only suggestion, the dependency travels in the
  /// same cart. Removing a plan never removes what it auto-added — the shop chose it, or it
  /// stays because something else still needs it.
  void _toggleCart(String planId) {
    HapticFeedback.selectionClick();
    if (_cart.contains(planId)) {
      setState(() { _cart.remove(planId); _cartNotice = ''; });
      _refreshCartPreview();
      return;
    }
    final plan = (_plans ?? const <BillingPlan>[]).where((p) => p.id == planId).firstOrNull;
    var notice = '';
    setState(() {
      _cart.add(planId);
      final need = plan?.requiresAny ?? const <String>[];
      if (need.isNotEmpty) {
        final satisfied = need.any((k) => _owned?.owns(k) == true) ||
            need.any((k) => _cart.any((id) {
                  final p = (_plans ?? const <BillingPlan>[]).where((pp) => pp.id == id).firstOrNull;
                  return p?.appKey == k;
                }));
        if (!satisfied) {
          final provider = need
              .map((k) => (_plans ?? const <BillingPlan>[]).where((p) => p.appKey == k).firstOrNull)
              .whereType<BillingPlan>()
              .firstOrNull;
          if (provider != null) {
            _cart.add(provider.id);
            notice = S.of(context)!.appStoreAutoAdded(provider.name, plan!.name);
          }
        }
      }
      _cartNotice = notice;
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

  /// Same honest posture mutual_benefit_screen.dart's own `_refusalMessage` takes — the
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
    // A ROW THAT ALSO NEEDS A CAPABILITY (e.g. 'referrals' — `referrals.manage`) is checked ON
    // TOP of the normal ownership check below, never instead of it — an owned-but-role-
    // restricted row must still stay invisible on «تطبيقاتي» to a caller without that
    // capability, same rule `CapabilityGate` applies everywhere else in this app. See the
    // STORE shelf's own note just below for why it is deliberately NOT checked there too.
    final catalog = context.watch<NavProvider>().catalog;
    bool visibleForCapability(AppRow r) => r.id != 'referrals' || catalog.hasAll(['referrals.manage']);
    // STORE SHELF NEVER FILTERED BY visibleForCapability — a real gap found live: a shop owner
    // whose own role had not yet been granted `referrals.manage` could never even see the app to
    // buy it, on the one shelf whose entire job is selling every listed app to whoever can pay
    // for it (`subscription.activate`, its own real gate, already sits on the actual subscribe
    // button below). Managing an app once bought and discovering it to buy are two different
    // permissions — only «تطبيقاتي» (owned apps you can actually open) still applies it.
    final rows = (_tab
            ? kAppRows
            : kAppRows.where((r) => r.route != null && (r.key == null || _owned?.owns(r.key!) == true))
                .where(visibleForCapability))
        .toList();

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
                      // ONLY WHEN GENUINELY UNMET — same "absence is never invented" rule
                      // billingShared.tsx's own `missingRequirement` already takes (mirrored here
                      // for a real, clickable badge instead of only a details-sheet sentence).
                      final needsAny = _tab && plan != null && owned != true
                              && !plan.requiresAny.any((k) => _owned?.owns(k) == true)
                          ? plan.requiresAny
                          : const <String>[];
                      final requiresAnyRows = needsAny
                          .map((k) => kAppRows.where((r) => r.key == k).firstOrNull)
                          .whereType<AppRow>()
                          .toList();
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
                          discountPercent: plan != null ? _discountApplied[plan.id]?.percent : null,
                          includedCreditMinor: _includedCreditFor(plan),
                          unitsPerHalala: _unitsPerHalala,
                          showBilling: _tab,
                          inCart: plan != null && _cart.contains(plan.id),
                          onToggleCart: plan != null && owned != true ? () => _toggleCart(plan.id) : null,
                          // OWNED, NEVER JUST ROUTED — a locked card with a real `route` used to
                          // navigate straight into the live feature screen with zero ownership
                          // check anywhere (found live 2026-09-26 auditing this screen): no
                          // route-level gate exists (`app_router.dart`'s own `for (final section
                          // in kNavSections)` registers every section's route unconditionally),
                          // and the destination screens themselves never self-check ownership
                          // either. A single tap on «متجر التطبيقات» fully bypassed the paywall
                          // for anything with a mobile screen. The «تطبيقاتي» shelf was never
                          // exposed to this (it already filters to owned rows only), only the
                          // store tab, which lists every row regardless of ownership.
                          onOpen: () {
                            if (row.route != null && owned != false) {
                              context.go('/${row.route}');
                            } else {
                              _showDetails(row, plan, owned, sub);
                            }
                          },
                          onTapDetails: () => _showDetails(row, plan, owned, sub),
                          requiresAny: requiresAnyRows,
                          onRequirementTap: (r) {
                            final rPlan = r.key != null ? _planFor(r.key!) : null;
                            final rOwned = r.key == null ? true : _owned?.owns(r.key!);
                            final rSub = rPlan != null ? _subFor(rPlan.id) : null;
                            _showDetails(r, rPlan, rOwned, rSub);
                          },
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
              notice: _cartNotice,
              discounts: _discountApplied,
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
    final cascade = sub != null ? _cascadeTargets(sub) : const <BillingSubscription>[];
    final cascadeNames = cascade
        .map((s) => (_plans ?? const <BillingPlan>[]).where((p) => p.id == s.planId).firstOrNull?.name)
        .whereType<String>()
        .toList(growable: false);
    final discount = plan != null ? _discountApplied[plan.id] : null;
    final potential = plan != null && discount == null ? _discountPotential[plan.id] : null;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AppDetailsSheet(
        row: row, plan: plan, owned: owned, sub: sub,
        inlineFeatures: row.key != null ? _owned?.featuresFor(row.key!) : null,
        apiClient: auth.apiClient,
        missingRequirement: plan != null ? _missingRequirement(S.of(context)!, plan) : '',
        cascadeNames: cascadeNames,
        discountPercent: discount?.percent,
        discountAppName: discount != null ? _appNameForKey(discount.owningKey) : null,
        potentialDiscountPercent: potential?.percent,
        potentialDiscountAppName: potential != null ? _appNameForKey(potential.owningKey) : null,
        includedCreditMinor: _includedCreditFor(plan),
        unitsPerHalala: _unitsPerHalala,
        onSubscribe: plan != null && _missingRequirement(S.of(context)!, plan).isEmpty ? () => _quickSubscribe(plan) : null,
        onCancel: sub != null
            ? () async {
                final ok = await auth.cancelSubscription(sub.id);
                if (ok) {
                  for (final target in cascade) {
                    await auth.cancelSubscription(target.id);
                  }
                }
                if (ok) await _load();
              }
            : null,
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
  'briefcase': Icons.work_rounded,
};

/// Every icon key any backend `core/features.py` currently emits — mirrors the console's own
/// `rj-ui/AppFeatureList.tsx::APP_ICONS` exactly, key for key. `help_outline_rounded` is the
/// honest fallback for a key this app has not learned yet — a sparse-looking tile is a far
/// smaller failure than a blank crash on a card meant to be selling something.
const Map<String, IconData> _appFeatureIcons = {
  'clock': Icons.access_time_rounded,
  'users': Icons.groups_rounded,
  'alert-triangle': Icons.warning_amber_rounded,
  'check-badge': Icons.verified_rounded,
  'move': Icons.open_with_rounded,
  'shield-check': Icons.shield_rounded,
  'bell': Icons.notifications_rounded,
  'check-circle': Icons.check_circle_rounded,
  'car': Icons.directions_car_filled_rounded,
  'receipt': Icons.receipt_long_rounded,
  'search': Icons.search_rounded,
  'user-plus': Icons.person_add_rounded,
  'gift': Icons.card_giftcard_rounded,
  'star': Icons.star_rounded,
  'message-circle': Icons.chat_bubble_rounded,
  'calendar': Icons.calendar_month_rounded,
  'cloud': Icons.cloud_rounded,
  'layers': Icons.layers_rounded,
  'megaphone': Icons.campaign_rounded,
  'sparkles': Icons.auto_awesome_rounded,
  'truck': Icons.local_shipping_rounded,
  'map-pin': Icons.location_on_rounded,
  'hand-heart': Icons.volunteer_activism_rounded,
  'bot': Icons.smart_toy_rounded,
};

IconData _appFeatureIcon(String key) => _appFeatureIcons[key] ?? Icons.help_outline_rounded;

/// The five real tones, soft/on-soft — mirrors `rj-ui/AppFeatureList.tsx::TONE_CLASSES` and
/// `rj-ui/Badge`'s own five-tone vocabulary (never a second palette invented for this screen).
/// Light/dark pairs read straight off this theme's own `AppColors`/`AppDarkColors` tokens —
/// the same tone reads correctly in either mode with zero per-brightness logic here.
(Color, Color) _appFeatureToneColors(BuildContext context, String tone) {
  final dark = context.isDark;
  switch (tone) {
    case 'teal':
    case 'success':
      return dark ? (AppDarkColors.successSoft, AppDarkColors.successOnSoft) : (AppColors.successSoft, AppColors.successOnSoft);
    case 'violet':
    case 'accent':
      return dark ? (AppDarkColors.accentSoft, AppDarkColors.accentOnSoft) : (AppColors.accentSoft, AppColors.accentOnSoft);
    case 'amber':
    case 'warning':
      return dark ? (AppDarkColors.warningSoft, AppDarkColors.warningOnSoft) : (AppColors.warningSoft, AppColors.warningOnSoft);
    case 'rose':
    case 'danger':
      return dark ? (AppDarkColors.dangerSoft, AppDarkColors.dangerOnSoft) : (AppColors.dangerSoft, AppColors.dangerOnSoft);
    case 'blue':
    case 'info':
      return dark ? (AppDarkColors.infoSoft, AppDarkColors.infoOnSoft) : (AppColors.infoSoft, AppColors.infoOnSoft);
    default:
      return (context.appColors.surfaceAlt, context.appColors.textSecondary);
  }
}

/// The feature grid itself — a staggered fade/rise reveal, the SAME `TweenAnimationBuilder`
/// choreography the store's own tile shelf already uses (2026-09-23 premium-motion pass), so a
/// card that lists what an app actually does reads with the same craft as the shelf that sold it.
/// Two columns, never a single scrolling `<ul>`: parity/app_store.md's own review of the
/// console's showcase-grid redesign (`AppDetailsModal.tsx::FeatureTile`) found the plain bulleted
/// list read as a receipt, not a pitch — the showcase tiles are what this mirrors, not the plain
/// `AppFeatureList.tsx` used everywhere else in that console.
class _AppFeatureGrid extends StatelessWidget {
  const _AppFeatureGrid({required this.features}) : _skeletonCount = 0;
  const _AppFeatureGrid.skeleton() : features = const [], _skeletonCount = 4;

  final List<AppFeature> features;
  final int _skeletonCount;

  @override
  Widget build(BuildContext context) {
    final count = _skeletonCount > 0 ? _skeletonCount : features.length;
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: count,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2, mainAxisSpacing: AppSpacing.sm, crossAxisSpacing: AppSpacing.sm,
        childAspectRatio: 1.35,
      ),
      itemBuilder: (context, i) {
        final tile = _skeletonCount > 0 ? const _FeatureTileSkeleton() : _FeatureTile(feature: features[i]);
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: Duration(milliseconds: 260 + i * 55),
          curve: Curves.easeOutCubic,
          builder: (context, v, child) => Opacity(
            opacity: v,
            child: Transform.translate(offset: Offset(0, (1 - v) * 14), child: child),
          ),
          child: tile,
        );
      },
    );
  }
}

class _FeatureTile extends StatelessWidget {
  const _FeatureTile({required this.feature});
  final AppFeature feature;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = _appFeatureToneColors(context, feature.tone);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadius.standardRadius),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 30, height: 30,
            decoration: BoxDecoration(color: fg.withValues(alpha: 0.16), shape: BoxShape.circle),
            alignment: Alignment.center,
            child: Icon(_appFeatureIcon(feature.icon), size: 15, color: fg),
          ),
          const SizedBox(height: 6),
          Text(feature.title, maxLines: 2, overflow: TextOverflow.ellipsis,
              style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w800, color: fg, height: 1.2)),
          const SizedBox(height: 2),
          Text(feature.detail, maxLines: 2, overflow: TextOverflow.ellipsis,
              style: AppTextStyles.caption.copyWith(color: fg.withValues(alpha: 0.85), height: 1.25)),
        ],
      ),
    );
  }
}

class _FeatureTileSkeleton extends StatelessWidget {
  const _FeatureTileSkeleton();

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(width: 30, height: 30, decoration: BoxDecoration(color: colors.borderSubtle, shape: BoxShape.circle)),
          const SizedBox(height: 6),
          Container(height: 11, width: 70, decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
          const SizedBox(height: 4),
          Container(height: 9, width: 100, decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
        ],
      ),
    );
  }
}

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
    this.discountPercent, this.includedCreditMinor, this.unitsPerHalala,
    required this.showBilling, required this.inCart, required this.onToggleCart,
    required this.onOpen, required this.onTapDetails,
    this.requiresAny = const [], this.onRequirementTap,
  });
  final AppRow row;
  final bool? owned;
  final BillingPlan? plan;
  final BillingSubscription? sub;
  /// THE APP(S) THIS ONE NEEDS FIRST — resolved rows, never raw `feature.*` keys, so each badge
  /// is a real, tappable jump to that app's own details (`AppLauncher.tsx`'s own `AppTile.
  /// requiresAny` mirrored here). Only ever populated when genuinely unmet.
  final List<AppRow> requiresAny;
  final void Function(AppRow)? onRequirementTap;
  /// billingShared's own applied-discount percent for this plan — a small ribbon on the card
  /// face itself, never something the shop only learns after opening details.
  final int? discountPercent;
  final int? includedCreditMinor;
  final double? unitsPerHalala;
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
    final colors = context.appColors;
    final dark = context.isDark;
    final locked = widget.owned == false;
    final icon = _appIcons[widget.row.icon] ?? Icons.apps_rounded;
    final vip = widget.row.vip;
    final accent = _appAccent(widget.row.id);
    const gold = Color(0xFFD4AF37);

    final card = AnimatedScale(
      scale: _pressed ? 0.97 : 1,
      duration: const Duration(milliseconds: 120),
      curve: Curves.easeOut,
      child: Container(
        decoration: BoxDecoration(
          color: vip ? null : colors.surface,
          gradient: vip
              ? const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [Color(0xFF1A1207), Color(0xFF2F210C), Color(0xFF4A3512)])
              : null,
          borderRadius: AppRadius.cardRadius,
          border: vip ? Border.all(color: gold.withValues(alpha: 0.4)) : Border.all(color: colors.borderSubtle),
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
                      // A REAL APP ICON, ON A NEUTRAL CARD — the previous pass painted the WHOLE
                      // tile in a per-app hashed hue (a "colourful sticker" look, never what a
                      // real store shelf does). The accent now lives ONLY on the icon badge, a
                      // soft ring, and the small touches below — the card itself is the same
                      // clean surface every other card in this app already uses.
                      Container(
                        width: 52, height: 52,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: vip ? gold.withValues(alpha: 0.18) : accent.withValues(alpha: 0.14),
                          border: Border.all(color: vip ? gold.withValues(alpha: 0.5) : accent.withValues(alpha: 0.35), width: 1.5),
                        ),
                        alignment: Alignment.center,
                        child: Icon(icon, color: vip ? const Color(0xFFF4E2A4) : accent, size: 26),
                      ),
                      const Spacer(),
                      if (locked)
                        Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(shape: BoxShape.circle, color: colors.surfaceAlt),
                          child: Icon(Icons.lock_rounded, size: 16, color: colors.textMuted),
                        )
                      else if (widget.owned == true)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                          decoration: BoxDecoration(
                            color: vip ? gold.withValues(alpha: 0.22) : AppColors.successSoft,
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                          ),
                          child: Text(
                            widget.sub?.status == 'trialing' ? S.of(context)!.appStoreTrialing : S.of(context)!.appStoreActive,
                            style: AppTextStyles.caption.copyWith(
                                color: vip ? const Color(0xFFF4E2A4) : AppColors.successOnSoft, fontWeight: FontWeight.w800),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    widget.row.name, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.headlineSmall.copyWith(
                        fontWeight: FontWeight.w800, height: 1.2,
                        color: vip ? Colors.white : colors.textPrimary),
                  ),
                  const Spacer(),
                  if (widget.showBilling && widget.plan != null) ...[
                    const SizedBox(height: 6),
                    if (widget.discountPercent != null)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(_riyals(widget.plan!.monthlyAmountMinor),
                              style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted, decoration: TextDecoration.lineThrough)),
                          const SizedBox(width: 5),
                          Text(S.of(context)!.appStoreDiscountedShort(widget.discountPercent!),
                              style: AppTextStyles.headlineSmall.copyWith(fontWeight: FontWeight.w900, color: AppColors.success)),
                        ],
                      )
                    else
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(_riyals(widget.plan!.monthlyAmountMinor),
                              style: AppTextStyles.headlineSmall.copyWith(
                                  fontWeight: FontWeight.w900, color: vip ? Colors.white : colors.textPrimary)),
                          const SizedBox(width: 3),
                          Text(S.of(context)!.appStorePerMonthShort,
                              style: AppTextStyles.bodySmall.copyWith(
                                  color: vip ? Colors.white.withValues(alpha: 0.75) : colors.textMuted, fontWeight: FontWeight.w600)),
                        ],
                      ),
                  ],
                  if (widget.includedCreditMinor != null) ...[
                    const SizedBox(height: 6),
                    _AiUnitsChip(includedCreditMinor: widget.includedCreditMinor!, unitsPerHalala: widget.unitsPerHalala, compact: true),
                  ],
                  // THE DEPENDENCY, RIGHT ON THE CARD FACE — small, real, tappable icon badges for
                  // each app that would satisfy it, never a locked card with no next step named.
                  if (widget.requiresAny.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 4, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Icon(Icons.link_rounded, size: 12, color: colors.textMuted),
                        for (var i = 0; i < widget.requiresAny.length; i++) ...[
                          if (i > 0)
                            Text(S.of(context)!.appStoreRequiresOr,
                                style: AppTextStyles.caption.copyWith(color: colors.textMuted, fontSize: 10)),
                          GestureDetector(
                            onTap: () => widget.onRequirementTap?.call(widget.requiresAny[i]),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                              decoration: BoxDecoration(
                                color: colors.surfaceAlt,
                                borderRadius: BorderRadius.circular(AppRadius.pill),
                                border: Border.all(color: colors.borderSubtle),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(_appIcons[widget.requiresAny[i].icon] ?? Icons.apps_rounded,
                                      size: 10, color: colors.textSecondary),
                                  const SizedBox(width: 3),
                                  Text(widget.requiresAny[i].name,
                                      style: AppTextStyles.caption.copyWith(fontSize: 10, color: colors.textSecondary, fontWeight: FontWeight.w700)),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                  if (widget.showBilling) ...[
                    const SizedBox(height: 8),
                    GestureDetector(
                      onTap: widget.onTapDetails,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                        decoration: BoxDecoration(
                          color: vip ? Colors.white.withValues(alpha: 0.18) : accent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Text(S.of(context)!.appStoreDetails,
                            style: AppTextStyles.bodySmall.copyWith(
                                color: vip ? Colors.white : accent, fontWeight: FontWeight.w800)),
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
                      color: widget.inCart ? AppColors.success : colors.surface,
                      border: widget.inCart ? null : Border.all(color: colors.borderSubtle),
                      boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 10, offset: Offset(0, 3))],
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

    return vip ? RjSheen(borderRadius: AppRadius.cardRadius, tint: gold, child: tappable) : tappable;
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
        // `billing.self` IS A CAPABILITY, NOT A CATALOGUE ACTION ID — `hasAll` checks action ids
        // (billing_screen.dart's own `billing.cancel`/`billing.undo_cancel` usage is the real
        // convention), so this literal string never matched anything and silently hid every
        // purchase/cancel/checkout control on this screen. Found live 2026-09-26 verifying the
        // gap-closure work above; fixed here with the real action id each button actually calls.
        requires: const ['billing.cancel'],
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
      requires: const ['subscription.activate'],
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
    required this.busy, required this.error, required this.notice, required this.discounts,
    required this.onRemove, required this.onCheckout,
  });
  final List<BillingPlan> plans;
  final int listTotal;
  final CartPreview? preview;
  final bool previewBusy;
  final bool busy;
  final String error;
  /// useAppBilling.ts's own `cartNotice` — the auto-add sentence, shown once and cleared the
  /// next time the cart changes (the caller's own `_toggleCart` resets it).
  final String notice;
  /// Known discounts, keyed by plan id — shown per item as a badge, never folded silently into
  /// the total with nothing explaining where it came from (CartBar.tsx's own rule).
  final Map<String, DiscountInfo> discounts;
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
            // ONE LINE PER PLAN, WITH ITS OWN DISCOUNT BADGE WHEN IT HAS ONE — never a bare
            // count folded into a single number; CartBar.tsx's own rule.
            const SizedBox(height: 6),
            for (final p in plans)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(p.name, style: AppTextStyles.caption.copyWith(color: colors.textSecondary), overflow: TextOverflow.ellipsis),
                    ),
                    if (discounts[p.id] != null)
                      Padding(
                        padding: const EdgeInsetsDirectional.only(end: 6),
                        child: Text(s.appStoreCartItemDiscount(discounts[p.id]!.percent),
                            style: AppTextStyles.caption.copyWith(color: AppColors.success, fontWeight: FontWeight.w700)),
                      ),
                    GestureDetector(
                      onTap: () => onRemove(p.id),
                      child: Icon(Icons.close_rounded, size: 14, color: colors.textMuted),
                    ),
                  ],
                ),
              ),
            // THE REAL BREAKDOWN, ONCE THE SERVER HAS ANSWERED — subtotal/discount/tax, each its
            // own line straight off `CartPreview`, never a locally-summed total pretending to be
            // final (useAppBilling.ts's own rule: the server's number always wins).
            if (preview != null) ...[
              const SizedBox(height: 6),
              Divider(height: 1, color: colors.borderSubtle),
              const SizedBox(height: 6),
              _CartLine(label: s.appStoreCartSubtotal, value: preview!.subtotalMinor, colors: colors),
              if (preview!.discountMinor > 0)
                _CartLine(label: s.appStoreCartDiscount, value: -preview!.discountMinor, colors: colors, good: true),
              if (preview!.taxMinor > 0) _CartLine(label: s.appStoreCartTax, value: preview!.taxMinor, colors: colors),
              _CartLine(label: s.appStoreCartTotal, value: preview!.totalMinor, colors: colors, bold: true),
              const SizedBox(height: 4),
              Text(s.appStoreCartDiscountCaveat, style: AppTextStyles.caption.copyWith(color: colors.textMuted, fontSize: 10)),
            ],
            if (notice.isNotEmpty) ...[
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                decoration: BoxDecoration(color: AppColors.accent.withValues(alpha: 0.08), borderRadius: AppRadius.standardRadius),
                child: Row(
                  children: [
                    const Icon(Icons.info_outline_rounded, size: 14, color: AppColors.accent),
                    const SizedBox(width: 6),
                    Expanded(child: Text(notice, style: AppTextStyles.caption.copyWith(color: AppColors.accent))),
                  ],
                ),
              ),
            ],
            if (error.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(error, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            ],
            const SizedBox(height: 8),
            CapabilityGate(
              requires: const ['subscription.checkout_cart_link'],
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

class _CartLine extends StatelessWidget {
  final String label;
  final int value;
  final AppThemeColors colors;
  final bool good;
  final bool bold;
  const _CartLine({required this.label, required this.value, required this.colors, this.good = false, this.bold = false});

  @override
  Widget build(BuildContext context) {
    final color = good ? AppColors.success : (bold ? null : colors.textSecondary);
    final style = bold
        ? AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w800, color: color)
        : AppTextStyles.caption.copyWith(color: color);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style),
          Text('${value < 0 ? '-' : ''}${_riyals(value.abs())}', textDirection: TextDirection.ltr, style: style),
        ],
      ),
    );
  }
}

class _AppDetailsSheet extends StatefulWidget {
  const _AppDetailsSheet({
    required this.row, required this.plan, required this.owned, required this.sub,
    required this.apiClient, this.inlineFeatures,
    this.missingRequirement = '', this.cascadeNames = const [],
    this.discountPercent, this.discountAppName,
    this.potentialDiscountPercent, this.potentialDiscountAppName,
    this.includedCreditMinor, this.unitsPerHalala,
    this.onSubscribe, this.onCancel, this.onUndoCancel,
  });
  final AppRow row;
  final BillingPlan? plan;
  final bool? owned;
  final BillingSubscription? sub;
  final ApiClient apiClient;
  /// ALREADY KNOWN (operations' own inline row) — skips the fetch entirely, same rule
  /// `AppFeaturesService`'s own docstring follows.
  final List<AppFeature>? inlineFeatures;
  /// billingShared.tsx's own `missingRequirement` — the sentence naming what to activate first,
  /// empty when this plan has no dependency or the shop already holds it.
  final String missingRequirement;
  /// useAppBilling.ts's own `cascadeTargets`, resolved to real names — the other apps this cancel
  /// would take down with it, named in the confirm dialog, never a silent side effect.
  final List<String> cascadeNames;
  final int? discountPercent;
  final String? discountAppName;
  final int? potentialDiscountPercent;
  final String? potentialDiscountAppName;
  final int? includedCreditMinor;
  final double? unitsPerHalala;
  final VoidCallback? onSubscribe;
  final VoidCallback? onCancel;
  final VoidCallback? onUndoCancel;

  @override
  State<_AppDetailsSheet> createState() => _AppDetailsSheetState();
}

class _AppDetailsSheetState extends State<_AppDetailsSheet> {
  List<AppFeature>? _fetched;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    final path = widget.row.featuresPath;
    if (widget.inlineFeatures != null || path == null) return;
    AppFeaturesService(apiClient: widget.apiClient).fetch(path).then((rows) {
      if (!mounted) return;
      setState(() {
        if (rows == null) {
          _failed = true;
        } else {
          _fetched = rows;
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final plan = widget.plan;
    final sub = widget.sub;
    final missingRequirement = widget.missingRequirement;
    final cascadeNames = widget.cascadeNames;
    final discountPercent = widget.discountPercent;
    final discountAppName = widget.discountAppName;
    final potentialDiscountPercent = widget.potentialDiscountPercent;
    final potentialDiscountAppName = widget.potentialDiscountAppName;
    final includedCreditMinor = widget.includedCreditMinor;
    final unitsPerHalala = widget.unitsPerHalala;
    final owned = widget.owned;
    final onSubscribe = widget.onSubscribe;
    final onCancel = widget.onCancel;
    final onUndoCancel = widget.onUndoCancel;
    final features = widget.inlineFeatures ?? _fetched;
    final loadingFeatures = widget.inlineFeatures == null && row.featuresPath != null && _fetched == null && !_failed;
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
                    if (loadingFeatures) ...[
                      const SizedBox(height: AppSpacing.md),
                      const _AppFeatureGrid.skeleton(),
                    ] else if (features != null && features.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.md),
                      _AppFeatureGrid(features: features),
                    ],
                    if (plan != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      if (discountPercent != null)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(_riyals(plan.monthlyAmountMinor),
                                style: AppTextStyles.bodySmall.copyWith(color: colors.textMuted, decoration: TextDecoration.lineThrough)),
                            const SizedBox(width: 6),
                            Text(
                              discountAppName != null
                                  ? s.appStoreDiscountBadgeWithApp(discountPercent, discountAppName)
                                  : s.appStoreDiscountedShort(discountPercent),
                              style: AppTextStyles.headlineSmall.copyWith(color: AppColors.success, fontWeight: FontWeight.w800),
                            ),
                          ],
                        )
                      else
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(_riyals(plan.monthlyAmountMinor), style: AppTextStyles.headlineSmall),
                            const SizedBox(width: 4),
                            Text(s.appStorePerMonth, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                          ],
                        ),
                      // THE GOLD TEASER — same luxury treatment shop_screen.dart's own whatsapp_ai_teaser
                      // gets: a real, computed cross-sell rule, never plain text, because it names money
                      // the shop is one subscription away from saving.
                      if (potentialDiscountPercent != null && potentialDiscountAppName != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _OfferChip(percent: potentialDiscountPercent, appName: potentialDiscountAppName),
                      ],
                      // THE INCLUDED-AI-CREDIT CHIP — a GIFT riding on top of the plan, its own
                      // royal violet-indigo identity, never folded into the price line above.
                      if (includedCreditMinor != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _AiUnitsChip(includedCreditMinor: includedCreditMinor, unitsPerHalala: unitsPerHalala),
                      ],
                      const SizedBox(height: AppSpacing.sm),
                      if (owned == true) ...[
                        if (sub?.cancelAtPeriodEnd == true) ...[
                          if (onUndoCancel != null)
                            CapabilityGate(
                              requires: const ['billing.undo_cancel'],
                              child: KbAnchor(
                                id: 'apps.details_undo_cancel',
                                child: SizedBox(width: double.infinity, child: OutlinedButton(onPressed: onUndoCancel, child: Text(s.appStoreUndoCancel))),
                              ),
                            ),
                        ] else if (onCancel != null)
                          CapabilityGate(
                            requires: const ['billing.cancel'],
                            child: KbAnchor(
                              id: 'apps.details_cancel',
                              child: SizedBox(
                                width: double.infinity,
                                child: OutlinedButton(
                                  onPressed: () => showDialog<void>(
                                    context: context,
                                    builder: (dialogContext) => AlertDialog(
                                      content: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(s.appStoreConfirmCancel),
                                          if (cascadeNames.isNotEmpty) ...[
                                            const SizedBox(height: 8),
                                            Text(
                                              s.appStoreCascadeWarning(cascadeNames.join('، ')),
                                              style: const TextStyle(color: AppColors.danger, fontWeight: FontWeight.w700),
                                            ),
                                          ],
                                        ],
                                      ),
                                      actions: [
                                        TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
                                        TextButton(
                                          onPressed: () { Navigator.of(dialogContext).pop(); onCancel(); },
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
                      ] else if (missingRequirement.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.all(AppSpacing.sm),
                          decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                          child: Row(
                            children: [
                              Icon(Icons.info_outline_rounded, size: 16, color: colors.textMuted),
                              const SizedBox(width: 6),
                              Expanded(child: Text(missingRequirement, style: AppTextStyles.caption.copyWith(color: colors.textSecondary))),
                            ],
                          ),
                        )
                      else if (onSubscribe != null)
                        CapabilityGate(
                          requires: const ['subscription.activate'],
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

/// billingShared.tsx's own `OfferChip` — a gold-on-charcoal teaser with a continuous light-sweep
/// (`RjSheen`), the same identity `_AppCard`'s own VIP tile already carries, so a real cross-sell
/// offer reads as unmistakably premium rather than one more grey info box.
/// AppDetailsModal.tsx's own `AiUnitsChip` — a royal violet→indigo gradient (never the plain
/// purple box the old screen used), a real gift riding on top of the plan's own price, absence
/// never a zero: the caller only ever builds this when `includedCreditMinor` is a real positive
/// number, so this widget itself has no "nothing to show" branch to get wrong.
class _AiUnitsChip extends StatelessWidget {
  final int includedCreditMinor;
  final double? unitsPerHalala;
  final bool compact;
  const _AiUnitsChip({required this.includedCreditMinor, required this.unitsPerHalala, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    // Wallet.tsx's own `unitsLabel` — a real unit count when the live rate is known, riyals
    // otherwise, never a raw halala number nobody can read.
    final label = unitsPerHalala != null
        ? s.appStoreAiUnitsCount((includedCreditMinor * unitsPerHalala!).round())
        : _riyals(includedCreditMinor);
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 12, vertical: compact ? 5 : 10),
      decoration: BoxDecoration(
        borderRadius: compact ? BorderRadius.circular(AppRadius.pill) : AppRadius.standardRadius,
        gradient: const LinearGradient(colors: [Color(0xFF4C1D95), Color(0xFF6D28D9), Color(0xFF7C3AED)]),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: compact ? 20 : 32,
            height: compact ? 20 : 32,
            decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.white24),
            alignment: Alignment.center,
            child: Icon(Icons.bolt_rounded, size: compact ? 12 : 16, color: Colors.white),
          ),
          SizedBox(width: compact ? 5 : 10),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(label,
                    style: (compact ? AppTextStyles.caption : AppTextStyles.bodyMedium)
                        .copyWith(color: Colors.white, fontWeight: FontWeight.w800),
                    overflow: TextOverflow.ellipsis),
                if (!compact)
                  Text(s.appStoreAiUnitsIncluded,
                      style: AppTextStyles.caption.copyWith(color: Colors.white70)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _OfferChip extends StatelessWidget {
  final int percent;
  final String appName;
  const _OfferChip({required this.percent, required this.appName});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return RjSheen(
      borderRadius: AppRadius.standardRadius,
      tint: const Color(0xFFD4AF37),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: AppRadius.standardRadius,
          gradient: const LinearGradient(colors: [Color(0xFF1A1207), Color(0xFF2F210C), Color(0xFF4A3512)]),
          border: Border.all(color: const Color(0x80D4AF37)),
        ),
        child: Row(
          children: [
            Container(
              width: 32, height: 32,
              decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0x33D4AF37)),
              alignment: Alignment.center,
              child: const Icon(Icons.auto_awesome_rounded, size: 16, color: Color(0xFFF4E2A4)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s.appStoreOfferTitle(percent),
                      style: AppTextStyles.bodySmall.copyWith(color: const Color(0xFFF4E2A4), fontWeight: FontWeight.w800)),
                  Text(s.appStoreOfferDesc(appName),
                      style: AppTextStyles.caption.copyWith(color: const Color(0xD9D4AF37))),
                ],
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
