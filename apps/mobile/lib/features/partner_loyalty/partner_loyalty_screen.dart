import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/partner_loyalty_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/app_store_model.dart';
import 'package:raje3_mobile/models/partner_loyalty_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «ولاء الشركاء» — mobile mirror of `apps/console/src/screens/Coupons.tsx`'s own real contract
/// (6 live `/api/v1/staff/coupons/*` routes, zero backend work — see parity/account.md). A shop
/// grants ANOTHER registered shop a discount on THAT shop's own subscription with us, applied
/// automatically at its next renewal — WE ARE THE INTERMEDIARY, ALWAYS (`core/coupons.py`'s own
/// module docstring): this screen never learns the beneficiary's identity beyond the phone-check
/// hint and the grant result.
///
/// NOT «شراكة استراتيجية» (`referral-partnership`) — that moves real customers between two shops'
/// own catalogues; this is a subscription-price perk between us and two shops, nothing a customer
/// ever sees.
///
/// SALLA LINKING AND PLATFORM-ADMIN CAP/EXCEPTION SETTINGS STAY CONSOLE-ONLY (owner's own
/// decision, 2026-09-24) — never ported here.
///
/// REACHING THIS SCREEN AT ALL ALREADY IMPLIES THE STRONG TIER — `nav.ts`'s own
/// `operations.coupons_page` resolves to the `operations.grant_coupon_direct` capability
/// (`core/apps.py`'s own two-tier split), so no further per-button capability gate is needed
/// inside: every action here (grant, preferences write) requires the same one capability that
/// already gated the route.
class PartnerLoyaltyScreen extends StatefulWidget {
  const PartnerLoyaltyScreen({super.key});

  @override
  State<PartnerLoyaltyScreen> createState() => _PartnerLoyaltyScreenState();
}

enum _Tab { log, stats }

final List<AppRow> _scopeOptions =
    kAppRows.where((a) => a.key != null && a.key != 'feature.partner_loyalty').toList();

class _PartnerLoyaltyScreenState extends State<PartnerLoyaltyScreen> {
  late final _service = PartnerLoyaltyService(apiClient: context.read<AuthProvider>().apiClient);

  CouponStats? _stats;
  bool _statsFailed = false;
  bool? _visitGrantEnabled;
  bool _prefsSaving = false;
  _Tab _tab = _Tab.log;

  final _phoneController = TextEditingController();
  int _percent = 10;
  bool _general = false;
  final Set<String> _scope = {};
  CouponCheck? _phoneCheck;
  Timer? _debounce;
  bool _submitting = false;
  ({bool ok, String text})? _result;

  List<CouponAttempt>? _log;
  bool _logFailed = false;
  final _searchController = TextEditingController();
  String _statusFilter = 'all'; // all | ok | fail

  @override
  void initState() {
    super.initState();
    _loadStats();
    _loadPrefs();
    _loadLog();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _phoneController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadStats() async {
    final s = await _service.stats();
    if (!mounted) return;
    setState(() {
      _stats = s;
      _statsFailed = s == null;
    });
  }

  Future<void> _loadPrefs() async {
    final v = await _service.preferencesGet();
    if (mounted) setState(() => _visitGrantEnabled = v);
  }

  Future<void> _loadLog() async {
    final rows = await _service.history();
    if (!mounted) return;
    setState(() {
      _log = rows;
      _logFailed = rows == null;
    });
  }

  Future<void> _togglePrefs(bool next) async {
    if (_prefsSaving) return;
    final prev = _visitGrantEnabled;
    setState(() {
      _prefsSaving = true;
      _visitGrantEnabled = next;
    });
    final ok = await _service.preferencesSet(next);
    if (!mounted) return;
    setState(() {
      _prefsSaving = false;
      if (ok == null) _visitGrantEnabled = prev;
    });
  }

  void _onPhoneChanged(String v) {
    _debounce?.cancel();
    if (v.trim().length < 9) {
      setState(() => _phoneCheck = null);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () async {
      final c = await _service.check(v.trim());
      if (mounted) setState(() => _phoneCheck = c);
    });
  }

  int get _cap => _stats?.currentCapPercent ?? 100;

  Future<void> _submitGrant() async {
    final s = S.of(context)!;
    final phone = _phoneController.text.trim();
    if (_submitting || phone.isEmpty || (!_general && _scope.isEmpty)) return;
    setState(() {
      _submitting = true;
      _result = null;
    });
    final (att, _) = await _service.grant(
      phone: phone,
      percent: _percent,
      general: _general,
      appKeys: _scope.toList(),
    );
    if (!mounted) return;
    if (att == null) {
      setState(() {
        _submitting = false;
        _result = (ok: false, text: s.partnerLoyaltyOutcomeBillingUnavailable);
      });
      return;
    }
    setState(() {
      _submitting = false;
      if (att.granted) {
        final failedSome =
            att.perApp.values.any((v) => v != 'attached' && v != 'unchanged');
        _result = (
          ok: true,
          text: failedSome ? s.partnerLoyaltyResultPartial : s.partnerLoyaltyResultSuccess,
        );
        _phoneController.clear();
        _phoneCheck = null;
      } else {
        _result = (ok: false, text: _outcomeText(s, att.outcome));
      }
    });
    unawaited(_loadStats());
    unawaited(_loadLog());
  }

  String _outcomeText(S s, String outcome) {
    switch (outcome) {
      case 'granted':
        return s.partnerLoyaltyOutcomeGranted;
      case 'invalid_percent':
        return s.partnerLoyaltyOutcomeInvalidPercent;
      case 'invalid_scope':
        return s.partnerLoyaltyOutcomeInvalidScope;
      case 'over_cap':
        return s.partnerLoyaltyOutcomeOverCap;
      case 'no_account':
        return s.partnerLoyaltyOutcomeNoAccount;
      case 'not_subscribed':
        return s.partnerLoyaltyOutcomeNotSubscribed;
      case 'billing_unavailable':
        return s.partnerLoyaltyOutcomeBillingUnavailable;
      case 'already_has_better_coupon':
        return s.partnerLoyaltyOutcomeAlreadyHasBetterCoupon;
      case 'coupon_expired':
        return s.partnerLoyaltyOutcomeCouponExpired;
      case 'coupon_exhausted':
        return s.partnerLoyaltyOutcomeCouponExhausted;
      case 'coupon_unknown':
        return s.partnerLoyaltyOutcomeCouponUnknown;
      case 'plan_mismatch':
        return s.partnerLoyaltyOutcomePlanMismatch;
      case 'coupon_disabled':
        return s.partnerLoyaltyOutcomeCouponDisabled;
      case 'coupon_scheduled':
        return s.partnerLoyaltyOutcomeCouponScheduled;
      default:
        return outcome;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;

    return KbAnchor(
      id: 'partner-loyalty',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: RefreshIndicator(
          onRefresh: () async {
            await Future.wait([_loadStats(), _loadPrefs(), _loadLog()]);
          },
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              Container(
                decoration: BoxDecoration(
                  gradient: primaryGradient(dark: dark),
                  borderRadius:
                      const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
                  boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
                ),
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(s.partnerLoyaltyTitle,
                            style: AppTextStyles.displaySmall
                                .copyWith(color: AppColors.accentContrast)),
                        const SizedBox(height: 2),
                        Text(s.partnerLoyaltySubtitle,
                            style: AppTextStyles.bodySmall.copyWith(
                                color: AppColors.accentContrast.withValues(alpha: 0.85))),
                        if (_stats != null) ...[
                          const SizedBox(height: AppSpacing.sm),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.sm, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(AppRadius.pill),
                            ),
                            child: Text(
                              '${s.partnerLoyaltyCapLabel} ${_stats!.currentCapPercent}%',
                              style: AppTextStyles.caption.copyWith(
                                  color: AppColors.accentContrast, fontWeight: FontWeight.w700),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, AppSpacing.md, AppSpacing.md, AppSpacing.xxl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_visitGrantEnabled != null)
                      KbAnchor(
                        id: 'partner-loyalty.prefs_toggle',
                        child: _PrefsCard(
                          enabled: _visitGrantEnabled!,
                          busy: _prefsSaving,
                          onChanged: _togglePrefs,
                          s: s,
                        ),
                      ),
                    const SizedBox(height: AppSpacing.md),
                    KbAnchor(
                      id: 'partner-loyalty.grant_form',
                      child: _GrantForm(
                        phoneController: _phoneController,
                        onPhoneChanged: _onPhoneChanged,
                        phoneCheck: _phoneCheck,
                        percent: _percent,
                        cap: _cap,
                        onPercentChanged: (v) => setState(() => _percent = v),
                        general: _general,
                        onGeneralChanged: (v) => setState(() => _general = v),
                        scope: _scope,
                        onScopeChanged: (key, selected) => setState(() {
                          if (selected) {
                            _scope.add(key);
                          } else {
                            _scope.remove(key);
                          }
                        }),
                        submitting: _submitting,
                        onSubmit: _submitGrant,
                        result: _result,
                        s: s,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    _TabSwitch(tab: _tab, onChanged: (t) => setState(() => _tab = t), s: s),
                    const SizedBox(height: AppSpacing.md),
                    if (_tab == _Tab.log)
                      _LogTab(
                        rows: _log,
                        failed: _logFailed,
                        searchController: _searchController,
                        statusFilter: _statusFilter,
                        onStatusFilterChanged: (v) => setState(() => _statusFilter = v),
                        onSearchChanged: (_) => setState(() {}),
                        s: s,
                      )
                    else
                      _StatsTab(stats: _stats, failed: _statsFailed, s: s),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PrefsCard extends StatelessWidget {
  final bool enabled;
  final bool busy;
  final ValueChanged<bool> onChanged;
  final S s;
  const _PrefsCard(
      {required this.enabled, required this.busy, required this.onChanged, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.borderSubtle),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.partnerLoyaltyPrefsTitle,
                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(s.partnerLoyaltyPrefsDesc,
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
              ],
            ),
          ),
          Switch(value: enabled, onChanged: busy ? null : onChanged),
        ],
      ),
    );
  }
}

class _GrantForm extends StatelessWidget {
  final TextEditingController phoneController;
  final ValueChanged<String> onPhoneChanged;
  final CouponCheck? phoneCheck;
  final int percent;
  final int cap;
  final ValueChanged<int> onPercentChanged;
  final bool general;
  final ValueChanged<bool> onGeneralChanged;
  final Set<String> scope;
  final void Function(String key, bool selected) onScopeChanged;
  final bool submitting;
  final VoidCallback onSubmit;
  final ({bool ok, String text})? result;
  final S s;

  const _GrantForm({
    required this.phoneController,
    required this.onPhoneChanged,
    required this.phoneCheck,
    required this.percent,
    required this.cap,
    required this.onPercentChanged,
    required this.general,
    required this.onGeneralChanged,
    required this.scope,
    required this.onScopeChanged,
    required this.submitting,
    required this.onSubmit,
    required this.result,
    required this.s,
  });

  ({Color color, String text})? _phoneHint(BuildContext context) {
    if (phoneCheck == null) return null;
    if (!phoneCheck!.registered) {
      return (color: AppColors.danger, text: s.partnerLoyaltyPhoneHintUnregistered);
    }
    if (phoneCheck!.alreadyGrantedThisMonth) {
      return (color: AppColors.warning, text: s.partnerLoyaltyPhoneHintAlready);
    }
    return (color: AppColors.success, text: s.partnerLoyaltyPhoneHintOk);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final hint = _phoneHint(context);
    final clampedPercent = percent.clamp(1, cap <= 0 ? 1 : cap);
    final canSubmit = !submitting &&
        phoneController.text.trim().isNotEmpty &&
        (general || scope.isNotEmpty);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.borderSubtle),
        boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.partnerLoyaltyGrantTitle,
              style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: AppSpacing.sm),
          AppTextField(
            controller: phoneController,
            labelText: s.partnerLoyaltyPhoneLabel,
            hintText: '05xxxxxxxx',
            keyboardType: TextInputType.phone,
            textDirection: TextDirection.ltr,
            onChanged: onPhoneChanged,
          ),
          if (hint != null) ...[
            const SizedBox(height: 4),
            Text(hint.text,
                style: AppTextStyles.caption.copyWith(color: hint.color, fontWeight: FontWeight.w600)),
          ],
          const SizedBox(height: AppSpacing.md),
          Text(s.partnerLoyaltyPercentLabel, style: AppTextStyles.bodySmall),
          Row(
            children: [
              Expanded(
                child: SliderTheme(
                  // NO OVERLAY SHAPE — Flutter web's default ripple/focus overlay for Slider
                  // computes a semantics bounding box that, inside a CustomScrollView, blows up
                  // to cover the ENTIRE viewport (found live: it silently swallowed every tap on
                  // this card, including the phone field and scope chips below it). Killing the
                  // overlay removes the oversized node outright; the thumb itself still drags and
                  // reports its value normally.
                  data: SliderTheme.of(context).copyWith(
                    overlayShape: SliderComponentShape.noOverlay,
                  ),
                  child: Slider(
                    value: clampedPercent.toDouble(),
                    min: 1,
                    max: cap <= 1 ? 1 : cap.toDouble(),
                    divisions: cap > 1 ? cap - 1 : null,
                    label: '$clampedPercent%',
                    onChanged: cap <= 1 ? null : (v) => onPercentChanged(v.round()),
                  ),
                ),
              ),
              SizedBox(
                width: 48,
                child: Text('$clampedPercent%',
                    textAlign: TextAlign.center,
                    style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          Text(s.partnerLoyaltyCapLine(cap),
              style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
          const SizedBox(height: AppSpacing.md),
          Text(s.partnerLoyaltyScopeLabel, style: AppTextStyles.bodySmall),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              FilterChip(
                label: Text(s.partnerLoyaltyScopeAll),
                selected: general,
                onSelected: onGeneralChanged,
                selectedColor: accent.withValues(alpha: 0.22),
                checkmarkColor: accent,
              ),
              if (!general)
                for (final app in _scopeOptions)
                  FilterChip(
                    label: Text(app.name),
                    selected: scope.contains(app.key),
                    onSelected: (sel) => onScopeChanged(app.key!, sel),
                    selectedColor: accent.withValues(alpha: 0.22),
                    checkmarkColor: accent,
                  ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          PrimaryButton(
            text: submitting ? s.partnerLoyaltySubmitting : s.partnerLoyaltySubmit,
            isLoading: submitting,
            onPressed: canSubmit ? onSubmit : null,
          ),
          if (result != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: AppSpacing.sm),
              decoration: BoxDecoration(
                color: (result!.ok ? AppColors.success : AppColors.danger).withValues(alpha: 0.12),
                borderRadius: AppRadius.standardRadius,
              ),
              child: Text(result!.text,
                  style: AppTextStyles.bodySmall.copyWith(
                      color: result!.ok ? AppColors.success : AppColors.danger,
                      fontWeight: FontWeight.w600)),
            ),
          ],
        ],
      ),
    );
  }
}

class _TabSwitch extends StatelessWidget {
  final _Tab tab;
  final ValueChanged<_Tab> onChanged;
  final S s;
  const _TabSwitch({required this.tab, required this.onChanged, required this.s});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    Widget seg(String label, _Tab value) {
      final selected = tab == value;
      return Expanded(
        child: InkWell(
          onTap: () => onChanged(value),
          borderRadius: AppRadius.standardRadius,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            decoration: BoxDecoration(
              color: selected ? accent : Colors.transparent,
              borderRadius: AppRadius.standardRadius,
            ),
            alignment: Alignment.center,
            child: Text(label,
                style: AppTextStyles.bodySmall.copyWith(
                    color: selected ? AppColors.accentContrast : colors.textSecondary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
      child: Row(children: [
        seg(s.partnerLoyaltyTabLog, _Tab.log),
        seg(s.partnerLoyaltyTabStats, _Tab.stats),
      ]),
    );
  }
}

class _LogTab extends StatelessWidget {
  final List<CouponAttempt>? rows;
  final bool failed;
  final TextEditingController searchController;
  final String statusFilter;
  final ValueChanged<String> onStatusFilterChanged;
  final ValueChanged<String> onSearchChanged;
  final S s;

  const _LogTab({
    required this.rows,
    required this.failed,
    required this.searchController,
    required this.statusFilter,
    required this.onStatusFilterChanged,
    required this.onSearchChanged,
    required this.s,
  });

  @override
  Widget build(BuildContext context) {
    if (rows == null) {
      return failed
          ? EmptyState(icon: Icons.error_outline_rounded, title: s.partnerLoyaltyLogReadFailed)
          : const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
              child: AppLoadingIndicator(),
            );
    }
    final query = searchController.text.trim();
    final filtered = rows!.where((r) {
      if (query.isNotEmpty && !r.beneficiaryPhoneLast4.contains(query)) return false;
      if (statusFilter == 'ok' && !r.granted) return false;
      if (statusFilter == 'fail' && r.granted) return false;
      return true;
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: AppTextField(
                controller: searchController,
                hintText: s.partnerLoyaltyLogSearchHint,
                keyboardType: TextInputType.phone,
                textDirection: TextDirection.ltr,
                onChanged: onSearchChanged,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: 6,
          children: [
            _StatusChip(
                label: s.partnerLoyaltyLogFilterAll,
                selected: statusFilter == 'all',
                onTap: () => onStatusFilterChanged('all')),
            _StatusChip(
                label: s.partnerLoyaltyLogFilterOk,
                selected: statusFilter == 'ok',
                onTap: () => onStatusFilterChanged('ok')),
            _StatusChip(
                label: s.partnerLoyaltyLogFilterFail,
                selected: statusFilter == 'fail',
                onTap: () => onStatusFilterChanged('fail')),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (filtered.isEmpty)
          EmptyState(
            icon: Icons.handshake_outlined,
            title: s.partnerLoyaltyLogEmptyTitle,
            message: s.partnerLoyaltyLogEmptyDesc,
          )
        else
          for (final r in filtered) _LogRow(row: r, s: s),
      ],
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _StatusChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: accent.withValues(alpha: 0.22),
    );
  }
}

class _LogRow extends StatelessWidget {
  final CouponAttempt row;
  final S s;
  const _LogRow({required this.row, required this.s});

  Color _toneFor(BuildContext context) {
    if (row.outcome == 'granted') return AppColors.success;
    if (row.outcome == 'already_has_better_coupon') return AppColors.warning;
    return AppColors.danger;
  }

  String _outcomeText(String outcome) {
    switch (outcome) {
      case 'granted':
        return s.partnerLoyaltyOutcomeGranted;
      case 'invalid_percent':
        return s.partnerLoyaltyOutcomeInvalidPercent;
      case 'invalid_scope':
        return s.partnerLoyaltyOutcomeInvalidScope;
      case 'over_cap':
        return s.partnerLoyaltyOutcomeOverCap;
      case 'no_account':
        return s.partnerLoyaltyOutcomeNoAccount;
      case 'not_subscribed':
        return s.partnerLoyaltyOutcomeNotSubscribed;
      case 'billing_unavailable':
        return s.partnerLoyaltyOutcomeBillingUnavailable;
      case 'already_has_better_coupon':
        return s.partnerLoyaltyOutcomeAlreadyHasBetterCoupon;
      case 'coupon_expired':
        return s.partnerLoyaltyOutcomeCouponExpired;
      case 'coupon_exhausted':
        return s.partnerLoyaltyOutcomeCouponExhausted;
      case 'coupon_unknown':
        return s.partnerLoyaltyOutcomeCouponUnknown;
      case 'plan_mismatch':
        return s.partnerLoyaltyOutcomePlanMismatch;
      case 'coupon_disabled':
        return s.partnerLoyaltyOutcomeCouponDisabled;
      case 'coupon_scheduled':
        return s.partnerLoyaltyOutcomeCouponScheduled;
      default:
        return outcome;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final date = DateTime.fromMillisecondsSinceEpoch(row.created * 1000);
    final dateText = '${date.day}/${date.month}';
    final scopeText = row.scope == 'all' ? s.partnerLoyaltyScopeAll : row.scope;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.borderSubtle),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('••${row.beneficiaryPhoneLast4}',
                    textDirection: TextDirection.ltr,
                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                Text('$dateText · $scopeText · ${row.percentRequested}%',
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: _toneFor(context).withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
            child: Text(_outcomeText(row.outcome),
                style:
                    AppTextStyles.caption.copyWith(color: _toneFor(context), fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}

class _StatsTab extends StatelessWidget {
  final CouponStats? stats;
  final bool failed;
  final S s;
  const _StatsTab({required this.stats, required this.failed, required this.s});

  @override
  Widget build(BuildContext context) {
    if (stats == null) {
      return failed
          ? EmptyState(
              icon: Icons.error_outline_rounded,
              title: s.partnerLoyaltyReadFailedTitle,
              message: s.partnerLoyaltyReadFailedDesc,
            )
          : const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
              child: AppLoadingIndicator(),
            );
    }
    final colors = context.appColors;
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
                child: _Kpi(
                    label: s.partnerLoyaltyStatsKpiMonth,
                    value: '${stats!.grantsThisMonth}',
                    tone: accent)),
            const SizedBox(width: 6),
            Expanded(
                child: _Kpi(
                    label: s.partnerLoyaltyStatsKpiCap,
                    value: '${stats!.currentCapPercent}%',
                    tone: AppColors.success)),
            const SizedBox(width: 6),
            Expanded(
                child: _Kpi(
                    label: s.partnerLoyaltyStatsKpiCeiling,
                    value: '${stats!.ceilingPercent}%',
                    tone: colors.textMuted)),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: colors.surface,
            borderRadius: AppRadius.standardRadius,
            border: Border.all(color: colors.borderSubtle),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.partnerLoyaltyStatsLadderTitle,
                  style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: AppSpacing.sm),
              _Ladder(stats: stats!, accent: accent),
              const SizedBox(height: AppSpacing.sm),
              Text(
                stats!.nextTierPercent != null
                    ? s.partnerLoyaltyStatsLadderNote(stats!.grantsThisMonth,
                        stats!.nextTierGrantsNeeded ?? 0, stats!.nextTierPercent!)
                    : s.partnerLoyaltyStatsLadderAtTop(stats!.grantsThisMonth),
                textAlign: TextAlign.center,
                style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
              ),
              const Divider(height: AppSpacing.lg),
              Text(
                s.partnerLoyaltyStatsCeilingNote(stats!.ceilingPercent),
                textAlign: TextAlign.center,
                style: AppTextStyles.caption.copyWith(color: colors.textMuted),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: colors.surface,
            borderRadius: AppRadius.standardRadius,
            border: Border.all(color: colors.borderSubtle),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.partnerLoyaltyStatsChartTitle,
                  style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: AppSpacing.md),
              _MiniBarChart(history: stats!.history, accent: accent),
            ],
          ),
        ),
      ],
    );
  }
}

class _Kpi extends StatelessWidget {
  final String label;
  final String value;
  final Color tone;
  const _Kpi({required this.label, required this.value, required this.tone});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.borderSubtle),
      ),
      child: Column(
        children: [
          Text(value,
              style: AppTextStyles.headlineSmall.copyWith(color: tone, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label,
              textAlign: TextAlign.center,
              style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
        ],
      ),
    );
  }
}

/// The ladder rungs — up to and including the ceiling, "done" for anything at or below this
/// shop's current cap. Same reasoning `Coupons.tsx`'s own `rungs` builds from just
/// `current_cap_percent`/`ceiling_percent`, never walking the platform's full tier table for one
/// shop's own screen.
class _Ladder extends StatelessWidget {
  final CouponStats stats;
  final Color accent;
  const _Ladder({required this.stats, required this.accent});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final rungs = <(String, bool, bool)>[
      ('${stats.currentCapPercent}%', true, true),
      if (stats.nextTierPercent != null) ('${stats.nextTierPercent}%', false, false),
      if (stats.nextTierPercent != null && stats.ceilingPercent > stats.nextTierPercent!)
        ('${stats.ceilingPercent}%', false, false),
    ];
    return Row(
      children: [
        for (var i = 0; i < rungs.length; i++) ...[
          if (i > 0)
            Expanded(
              child: Container(height: 2, color: colors.borderSubtle),
            ),
          Column(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: rungs[i].$2 ? accent : colors.surfaceAlt,
                  border: rungs[i].$3 ? Border.all(color: accent, width: 2) : null,
                ),
                child: Text(rungs[i].$1,
                    style: AppTextStyles.caption.copyWith(
                        color: rungs[i].$2 ? AppColors.accentContrast : colors.textSecondary,
                        fontWeight: FontWeight.w700)),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

class _MiniBarChart extends StatelessWidget {
  final List<CouponMonthCount> history;
  final Color accent;
  const _MiniBarChart({required this.history, required this.accent});

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final maxGrants = history.fold<int>(1, (m, h) => h.grants > m ? h.grants : m);
    return SizedBox(
      height: 90,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (final h in history)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Text('${h.grants}', style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                    const SizedBox(height: 2),
                    Container(
                      height: 50 * (h.grants / maxGrants).clamp(0.05, 1.0),
                      decoration: BoxDecoration(
                        color: accent.withValues(alpha: 0.75),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(_monthLabel(h.monthKey),
                        style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  String _monthLabel(String monthKey) {
    final parts = monthKey.split('-');
    if (parts.length != 2) return monthKey;
    const names = [
      'ينا', 'فبر', 'مار', 'أبر', 'ماي', 'يون', 'يول', 'أغس', 'سبت', 'أكت', 'نوف', 'ديس'
    ];
    final m = int.tryParse(parts[1]);
    if (m == null || m < 1 || m > 12) return monthKey;
    return names[m - 1];
  }
}
