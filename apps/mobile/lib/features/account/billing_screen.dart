import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/features/apps/payment_webview_screen.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';
import 'package:go_router/go_router.dart';

/// «الفوترة» — ONE mobile-native screen, never console's own tab strip
/// (`Account.tsx`'s `الاشتراك`/`الفواتير`/الاستخدام split). Owner's own reorganisation
/// (2026-09-22): every real billing fact a shop owner needs — status, what he's subscribed to,
/// what the next renewal actually costs, his invoices, his usage against plan limits — reads as
/// one scrollable status page, most-urgent-first (a past-due banner, if any, is always the very
/// first thing drawn), exactly the "hero status card, then grouped detail" shape 2026 mobile-UX
/// guidance gives a billing/subscription surface (bottom-anchored primary actions, no dual-axis
/// numbers, semantic colour reserved for state — researched live for this pass, see this file's
/// own action buttons). Every backend door below is billing-service's own real self-service
/// contract (`platform/services/billing-service/app/user_actions.py`, read from the vendored
/// submodule's own local source — never guessed), the SAME doors `BillingStatusPane.tsx` already
/// calls; only the layout is reconsidered, per [[mobile-app-brand-vs-design-craft]].
///
/// NO PURCHASE FLOW HERE — buying a new app/capacity stays console-only for now (no native store
/// screen on mobile yet, [[task-app-store-redesign-7-phases]]'s own scope). This screen manages
/// what is ALREADY subscribed: stop/undo-stop renewal, an early "جدد الآن", and invoice pay-links
/// for a past-due shop with no card-on-file (TuwaiqPay has none — same real gap
/// `BillingStatusPane.tsx`'s own header note documents).
class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key});

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  BillingOverview? _overview;
  bool _loading = true;
  String _busySubscriptionId = '';
  String _busyInvoiceId = '';
  String _actionError = '';
  bool _renewingAll = false;
  // Set once the owner has GONE THROUGH a real pay screen this session — TuwaiqPay's webhook
  // arrives by email (the weakest delivery channel we have) and our own reconciliation sweep only
  // catches a stuck invoice every 5 minutes, up to ~15-20 minutes worst case. Without this, an
  // owner who just paid and reopens the app sees the SAME alarming past-due banner he paid to
  // clear, with no explanation — this softens that one specific window, never the badge's own
  // logic (which still reads the server's real status, unmodified).
  bool _justAttemptedPayment = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final overview = await context.read<AuthProvider>().fetchBillingOverview();
    if (!mounted) return;
    setState(() {
      _overview = overview;
      _loading = false;
    });
  }

  Future<void> _cancel(BuildContext context, BillingSubscription sub) async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.billingCancelConfirmTitle),
        content: Text(s.billingCancelConfirmBody),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.cancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(s.billingCancelConfirmAction, style: const TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    setState(() {
      _busySubscriptionId = sub.id;
      _actionError = '';
    });
    final ok = await context.read<AuthProvider>().cancelSubscription(sub.id);
    if (!mounted) return;
    setState(() => _busySubscriptionId = '');
    if (ok) {
      _load();
    } else {
      setState(() => _actionError = s.billingActionFailed);
    }
  }

  Future<void> _undoCancel(BuildContext context, BillingSubscription sub) async {
    final s = S.of(context)!;
    setState(() {
      _busySubscriptionId = sub.id;
      _actionError = '';
    });
    final ok = await context.read<AuthProvider>().undoCancelSubscription(sub.id);
    if (!mounted) return;
    setState(() => _busySubscriptionId = '');
    if (ok) {
      _load();
    } else {
      setState(() => _actionError = s.billingActionFailed);
    }
  }

  /// «جدّد الآن» — TENANT-WIDE, never one app alone (the owner's own call, 2026-09-22): as long as
  /// an app is not cancelled it stays in the shop's one shared monthly cycle, so this renews every
  /// subscription due together in one tap. Opens each real pay URL the group produced, one tab
  /// per invoice (billing-service has no route that mints a single combined one — see
  /// `renewal_provider.py::RenewalProvider.renew_now`'s own docstring).
  Future<void> _renewAllNow(BuildContext context) async {
    setState(() {
      _renewingAll = true;
      _actionError = '';
    });
    final urls = await context.read<AuthProvider>().renewSubscriptionsNow();
    if (!context.mounted) return;
    setState(() => _renewingAll = false);
    if (urls.isEmpty) {
      setState(() => _actionError = S.of(context)!.billingActionFailed);
      return;
    }
    // ONE AT A TIME, IN-APP (owner's own instruction, 2026-09-23: never feel like leaving to
    // something external) — `openPaymentInApp` awaits each WebView's own close (auto or manual)
    // before the next one opens, since only one can show on screen at once.
    for (final url in urls) {
      if (!context.mounted) return;
      await openPaymentInApp(context, url);
    }
    _justAttemptedPayment = true;
    if (context.mounted) _load();
  }

  Future<void> _payInvoice(BuildContext context, BillingInvoice invoice) async {
    final s = S.of(context)!;
    setState(() {
      _busyInvoiceId = invoice.id;
      _actionError = '';
    });
    final url = await context.read<AuthProvider>().invoicePayLink(invoice.id);
    if (!context.mounted) return;
    setState(() => _busyInvoiceId = '');
    if (url != null) {
      await openPaymentInApp(context, url);
      _justAttemptedPayment = true;
      if (context.mounted) _load();
    } else {
      setState(() => _actionError = s.billingPayLinkFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final overview = _overview;
    return KbAnchor(
      id: 'account.billing',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(
          backgroundColor: AppColors.surface0,
          elevation: 0,
          title: Text(s.billingPageTitle, style: AppTextStyles.headlineSmall),
          leading: AppBackButton(
            onPressed: () => context.canPop() ? context.pop() : context.go(RouteNames.accountPath),
          ),
        ),
        body: SafeArea(
          child: _loading
              ? const BrandLoadingIndicator()
              : overview == null
                  ? _ErrorState(onRetry: _load)
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        padding: const EdgeInsets.fromLTRB(
                            AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xxl),
                        children: [
                          _StatusHero(overview: overview, justAttemptedPayment: _justAttemptedPayment),
                          if (_actionError.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.sm),
                            Text(_actionError, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
                          ],
                          if (overview.usage.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.xl),
                            _SectionLabel(text: s.billingUsageSectionTitle),
                            const SizedBox(height: AppSpacing.sm),
                            _UsageCard(gauges: overview.usage),
                          ],
                          if (overview.subscriptions.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.xl),
                            _SectionLabel(text: s.billingMyAppsSectionTitle),
                            const SizedBox(height: AppSpacing.sm),
                            // A GRID, NOT A LONG COLUMN — the owner's own call, 2026-09-22:
                            // a shop can hold many apps, and a single-column list of full-text-
                            // button cards does not scale. Two per row, compact icon actions
                            // instead of text buttons — the same density shift `_Row`'s own
                            // account-list language never needed because that list is short and
                            // fixed, while this one grows with every app the shop buys.
                            GridView.builder(
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: 2,
                                mainAxisSpacing: AppSpacing.sm,
                                crossAxisSpacing: AppSpacing.sm,
                                // Fits the card's REAL content height (icon row + status pill +
                                // one date line) — 0.98 (near-square) left a tall empty gap below
                                // every card, found live via a real screenshot. 1.7 itself still
                                // overflowed by a fraction of a pixel on a real renewal date's
                                // actual rendered height — found live too, same way.
                                childAspectRatio: 1.6,
                              ),
                              itemCount: overview.subscriptions.length,
                              itemBuilder: (context, i) {
                                final sub = overview.subscriptions[i];
                                return _SubscriptionCard(
                                  sub: sub,
                                  plan: overview.plansById[sub.planId],
                                  busy: _busySubscriptionId == sub.id,
                                  onCancel: () => _cancel(context, sub),
                                  onUndoCancel: () => _undoCancel(context, sub),
                                );
                              },
                            ),
                          ],
                          if (overview.renewalGroups.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.xl),
                            _SectionLabel(text: s.billingRenewalPreviewSectionTitle),
                            const SizedBox(height: AppSpacing.sm),
                            ...overview.renewalGroups.map((g) => Padding(
                                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                                  child: _RenewalPreviewCard(group: g),
                                )),
                            // ONE BUTTON FOR THE WHOLE GROUP, never per app (the owner's own
                            // call, 2026-09-22) — renewing early means the whole together-billed
                            // cycle, exactly what the automatic sweep would do on the real date.
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton(
                                style: ToneColors.of(context, AppTone.accent).outlinedStyle(),
                                onPressed: _renewingAll ? null : () => _renewAllNow(context),
                                child: _renewingAll
                                    ? const SizedBox(
                                        width: 16, height: 16,
                                        child: CircularProgressIndicator(strokeWidth: 2))
                                    : Text(s.billingRenewNow),
                              ),
                            ),
                          ],
                          const SizedBox(height: AppSpacing.xl),
                          _SectionLabel(text: s.billingInvoicesSectionTitle),
                          const SizedBox(height: AppSpacing.sm),
                          if (overview.invoices.isEmpty)
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                              child: Text(s.billingInvoicesEmpty,
                                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                            )
                          else
                            ...overview.invoices.map((inv) => Padding(
                                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                                  child: _InvoiceRow(
                                    invoice: inv,
                                    busy: _busyInvoiceId == inv.id,
                                    onPay: () => _payInvoice(context, inv),
                                  ),
                                )),
                        ],
                      ),
                    ),
        ),
      ),
    );
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
          child: Text(s.billingLoadFailed, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
        ),
        const SizedBox(height: AppSpacing.md),
        Center(child: TextButton(onPressed: onRetry, child: Text(s.retry))),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel({required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
      child: Text(text,
          style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary, fontWeight: FontWeight.w700)),
    );
  }
}

/// The very first thing drawn — "all good" or "past due", never buried under a tab. A past-due
/// shop also gets the real `openInvoice` pay-link inline (the same escape hatch
/// `BillingStatusPane.tsx`'s own header note explains is the ONLY recovery path on a gateway with
/// no card-on-file).
class _StatusHero extends StatelessWidget {
  final BillingOverview overview;
  final bool justAttemptedPayment;
  const _StatusHero({required this.overview, this.justAttemptedPayment = false});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final pastDue = overview.subscriptions.any((sub) => sub.status == 'past_due');
    // SOFTENED, NEVER HIDDEN — the badge still reads the server's real status honestly (this is
    // NOT "treat past_due as paid"); only the TONE and sentence change right after the owner has
    // gone through a real pay screen this session, because TuwaiqPay's own webhook can lag up to
    // ~15-20 minutes (see this class's own field comment on `justAttemptedPayment`).
    final pendingConfirmation = pastDue && justAttemptedPayment;
    final tone = pastDue ? (pendingConfirmation ? AppTone.warning : AppTone.danger) : AppTone.success;
    final colors = ToneColors.of(context, tone);
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final message = pendingConfirmation
        ? s.billingPaymentConfirming
        : pastDue
            ? s.billingPastDue
            : s.billingAllGood;

    return KbAnchor(
      id: 'account.billing.status_hero',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: colors.solid,
      child: Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        borderRadius: AppRadius.cardRadius,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [colors.soft.withValues(alpha: dark ? 0.28 : 0.6), surface],
        ),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [colors.solid, colors.solid.withValues(alpha: 0.75)],
              ),
            ),
            child: Icon(
                pendingConfirmation
                    ? Icons.hourglass_top_rounded
                    : pastDue
                        ? Icons.error_rounded
                        : Icons.verified_rounded,
                color: Colors.white, size: 24),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700, color: colors.onSoft),
            ),
          ),
        ],
      ),
      ),
      ),
    );
  }
}

/// Known real entitlement gauges — `LIMIT_KEYS` in `apps/console/src/billingShared.tsx`, the
/// same server keys, kept to the two this shop can actually see today (an unknown future key
/// still renders, just with its raw name rather than a translated label).
String _usageLabel(S s, String key) => switch (key) {
      'staff.seats' => s.billingUsageStaffSeats,
      'branches' => s.billingUsageBranches,
      _ => key,
    };

class _UsageCard extends StatelessWidget {
  final List<BillingUsageGauge> gauges;
  const _UsageCard({required this.gauges});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    return KbAnchor(
      id: 'account.billing.usage_card',
      child: _PlainCard(
        dark: dark,
        child: Column(
          children: [
            for (var i = 0; i < gauges.length; i++) ...[
              if (i > 0) const SizedBox(height: AppSpacing.md),
              _UsageGaugeRow(gauge: gauges[i], label: _usageLabel(s, gauges[i].key)),
            ],
          ],
        ),
      ),
    );
  }
}

class _UsageGaugeRow extends StatelessWidget {
  final BillingUsageGauge gauge;
  final String label;
  const _UsageGaugeRow({required this.gauge, required this.label});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final unlimited = gauge.limit == null;
    final ratio = unlimited || gauge.limit == 0 ? 0.0 : (gauge.current / gauge.limit!).clamp(0.0, 1.0);
    final tone = ratio >= 0.9 ? AppTone.warning : AppTone.accent;
    final colors = ToneColors.of(context, tone);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
            Text(
              unlimited ? s.billingUsageUnlimited : '${gauge.current} / ${gauge.limit}',
              style: AppTextStyles.bodySmall
                  .copyWith(color: AppColors.textSecondary, fontFeatures: const [FontFeature.tabularFigures()]),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: LinearProgressIndicator(
            value: unlimited ? null : ratio,
            minHeight: 6,
            backgroundColor: colors.soft,
            valueColor: AlwaysStoppedAnimation(colors.solid),
          ),
        ),
      ],
    );
  }
}

class _SubscriptionCard extends StatelessWidget {
  final BillingSubscription sub;
  final BillingPlan? plan;
  final bool busy;
  final VoidCallback onCancel;
  final VoidCallback onUndoCancel;

  const _SubscriptionCard({
    required this.sub,
    required this.plan,
    required this.busy,
    required this.onCancel,
    required this.onUndoCancel,
  });

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final locale = Localizations.localeOf(context).languageCode;
    final stopping = sub.cancelAtPeriodEnd;
    final tone = stopping ? AppTone.warning : AppTone.success;
    final colors = ToneColors.of(context, tone);
    final renewsOn = sub.currentPeriodEnd > 0
        ? Formatters.formatDateFull(
            DateTime.fromMillisecondsSinceEpoch(sub.currentPeriodEnd.toInt() * 1000), locale: locale)
        : '';

    // COMPACT, GRID-SHAPED — an icon action, not a full-text button (the owner's own call,
    // 2026-09-22): a shop's app count grows over time, so this card has to stay dense at 2-per-row
    // rather than the earlier single-column, full-width-button shape. The icon's own colour still
    // follows what the tap DOES, never the status badge's tone — undo-stop is a positive action
    // even while the badge itself still reads warning (the subscription hasn't actually renewed
    // yet). NO PER-APP "جدّد الآن" here — removed 2026-09-22, early renewal is a whole-account
    // action now (the single button below the renewal-preview section).
    final actionTone = stopping ? AppTone.success : AppTone.danger;
    final actionColors = ToneColors.of(context, actionTone);
    return KbAnchor(
      id: 'account.billing.subscription_card',
      child: _PlainCard(
        dark: dark,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(plan?.name ?? sub.planId,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: AppSpacing.xs),
                SizedBox(
                  width: 28,
                  height: 28,
                  child: busy
                      ? const Padding(
                          padding: EdgeInsets.all(6),
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : IconButton(
                          padding: EdgeInsets.zero,
                          iconSize: 18,
                          tooltip: stopping ? s.billingUndoStopRenewal : s.billingStopRenewal,
                          style: IconButton.styleFrom(
                            backgroundColor: actionColors.soft,
                            foregroundColor: actionColors.solid,
                          ),
                          onPressed: stopping ? onUndoCancel : onCancel,
                          icon: Icon(stopping ? Icons.refresh_rounded : Icons.pause_rounded),
                        ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
              decoration:
                  BoxDecoration(color: colors.soft, borderRadius: BorderRadius.circular(AppRadius.pill)),
              child: Text(
                stopping ? s.billingStatusStopping : s.billingStatusActive,
                style: AppTextStyles.caption.copyWith(color: colors.onSoft, fontWeight: FontWeight.w700),
              ),
            ),
            if (renewsOn.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(renewsOn,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary)),
            ],
          ],
        ),
      ),
    );
  }
}

class _RenewalPreviewCard extends StatelessWidget {
  final RenewalPreviewGroup group;
  const _RenewalPreviewCard({required this.group});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final locale = Localizations.localeOf(context).languageCode;
    final nextChargeAt = group.nextChargeAt;
    final dateLabel = nextChargeAt != null && nextChargeAt > 0
        ? Formatters.formatDateFull(
            DateTime.fromMillisecondsSinceEpoch(nextChargeAt.toInt() * 1000), locale: locale)
        : null;

    return KbAnchor(
      id: 'account.billing.renewal_preview_card',
      child: _PlainCard(
        dark: dark,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              dateLabel != null ? s.billingRenewalPreviewNextChargeOn(dateLabel) : s.billingRenewalPreviewNoDate,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final line in group.lines)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                        child:
                            Text(line.planName, style: AppTextStyles.bodySmall, overflow: TextOverflow.ellipsis)),
                    Text(Formatters.formatCurrency(line.totalMinor / 100, locale: locale),
                        style: AppTextStyles.bodySmall
                            .copyWith(fontFeatures: const [FontFeature.tabularFigures()])),
                  ],
                ),
              ),
            const Divider(height: AppSpacing.lg),
            _TotalsRow(label: s.billingRenewalPreviewSubtotal, minor: group.subtotalMinor, locale: locale),
            if (group.discountMinor > 0)
              _TotalsRow(
                  label: s.billingRenewalPreviewSavings,
                  minor: -group.discountMinor,
                  locale: locale,
                  color: AppColors.success),
            if (group.taxMinor > 0)
              _TotalsRow(label: s.billingRenewalPreviewTax, minor: group.taxMinor, locale: locale),
            const SizedBox(height: AppSpacing.xs),
            _TotalsRow(
                label: s.billingRenewalPreviewTotal, minor: group.totalMinor, locale: locale, bold: true),
          ],
        ),
      ),
    );
  }
}

class _TotalsRow extends StatelessWidget {
  final String label;
  final int minor;
  final String locale;
  final bool bold;
  final Color? color;
  const _TotalsRow({required this.label, required this.minor, required this.locale, this.bold = false, this.color});

  @override
  Widget build(BuildContext context) {
    final style = AppTextStyles.bodySmall.copyWith(
      color: color ?? AppColors.textSecondary,
      fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
      fontFeatures: const [FontFeature.tabularFigures()],
    );
    final amount = minor / 100;
    final text = minor < 0
        ? '-${Formatters.formatCurrency(amount.abs(), locale: locale)}'
        : Formatters.formatCurrency(amount, locale: locale);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style.copyWith(color: bold ? null : style.color)),
          Text(text, style: style),
        ],
      ),
    );
  }
}

String _invoiceStatusLabel(S s, String status) => switch (status) {
      'paid' => s.billingInvoiceStatusPaid,
      'open' => s.billingInvoiceStatusOpen,
      'partially_paid' => s.billingInvoiceStatusPartiallyPaid,
      'void' => s.billingInvoiceStatusVoid,
      'uncollectible' => s.billingInvoiceStatusUncollectible,
      _ => s.billingInvoiceStatusDraft,
    };

class _InvoiceRow extends StatelessWidget {
  final BillingInvoice invoice;
  final bool busy;
  final VoidCallback onPay;
  const _InvoiceRow({required this.invoice, required this.busy, required this.onPay});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final locale = Localizations.localeOf(context).languageCode;
    final tone = invoice.status == 'paid'
        ? AppTone.success
        : invoice.isPayable
            ? AppTone.warning
            : AppTone.info;
    final colors = ToneColors.of(context, tone);

    return KbAnchor(
      id: 'account.billing.invoice_row',
      child: _PlainCard(
      dark: dark,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(invoice.number.isNotEmpty ? invoice.number : invoice.id,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
                  decoration:
                      BoxDecoration(color: colors.soft, borderRadius: BorderRadius.circular(AppRadius.pill)),
                  child: Text(_invoiceStatusLabel(s, invoice.status),
                      style: AppTextStyles.caption.copyWith(color: colors.onSoft, fontWeight: FontWeight.w700)),
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(Formatters.formatCurrency(invoice.totalMinor / 100, locale: locale),
              style: AppTextStyles.bodyMedium
                  .copyWith(fontWeight: FontWeight.w700, fontFeatures: const [FontFeature.tabularFigures()])),
          if (invoice.isPayable) ...[
            const SizedBox(width: AppSpacing.sm),
            TextButton(
              style: colors.textStyle(),
              onPressed: busy ? null : onPay,
              child: busy
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(s.billingPayNow),
            ),
          ],
        ],
      ),
      ),
    );
  }
}

class _PlainCard extends StatelessWidget {
  final Widget child;
  final bool dark;
  const _PlainCard({required this.child, required this.dark});

  @override
  Widget build(BuildContext context) {
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;
    return RjSheen(
      borderRadius: AppRadius.cardRadius,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: border),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: child,
      ),
    );
  }
}
