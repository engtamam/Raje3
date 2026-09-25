import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/apps/apps_store_screen.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/date_time_picker_sheet.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// One branch's own detail — address, واتساب, الفريق. Real contract, read live:
/// `PATCH /staff/branches/{id}` renames/closes/reopens/relocates; the MAIN branch's own toggle is
/// disabled with the real 409 sentence shown as static copy rather than let a tap fail
/// (staff.py::update_branch's own `MAIN_BRANCH` refusal). WhatsApp status is branch-scoped
/// (`GET /whatsapp/connect?branch_id=`) except in centralized mode, where only the main branch
/// ever connects — apps/console/src/screens/Connect.tsx's own `ConnectByBranch` carries the same
/// real conditional this screen mirrors, never copied visually.
class BranchDetailScreen extends StatefulWidget {
  final String branchId;
  const BranchDetailScreen({super.key, required this.branchId});

  @override
  State<BranchDetailScreen> createState() => _BranchDetailScreenState();
}

class _BranchDetailScreenState extends State<BranchDetailScreen> {
  Branch? _branch;
  bool _isPerBranchMode = false;
  BranchConnectStatus? _connectStatus;
  List<BranchTeamMember>? _team;
  List<Branch> _allBranches = const [];
  bool _loading = true;
  bool _loadFailed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final auth = context.read<AuthProvider>();
    final results = await Future.wait([
      auth.fetchBranches(),
      auth.fetchIsPerBranchMode(),
      auth.fetchOperators(),
    ]);
    if (!mounted) return;
    final branchesResult = results[0] as BranchesResult?;
    final isPerBranch = results[1] as bool;
    final operators = results[2] as List<BranchTeamMember>?;
    final branch = branchesResult?.branches.firstWhere(
      (b) => b.id == widget.branchId,
      orElse: () => const Branch(id: '', name: '', active: true, lat: 0, lng: 0, city: ''),
    );
    if (branch == null || branch.id.isEmpty) {
      setState(() {
        _loading = false;
        _loadFailed = true;
      });
      return;
    }
    // Centralized mode connects WhatsApp on the main branch only — a non-main branch never has
    // its own connection to ask about, same real rule Connect.tsx's own ConnectByBranch follows.
    final wantsConnectStatus = isPerBranch || branch.isMain;
    final connectStatus =
        wantsConnectStatus ? await auth.fetchBranchConnectStatus(branch.id) : null;
    if (!mounted) return;
    setState(() {
      _branch = branch;
      _isPerBranchMode = isPerBranch;
      _connectStatus = connectStatus;
      _team = operators?.where((m) => m.branchId == branch.id).toList();
      _allBranches = (branchesResult?.branches ?? const []).where((b) => b.active).toList();
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'account.shop.branches.detail',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(
          backgroundColor: AppColors.surface0,
          elevation: 0,
          title: Text(_branch?.name ?? s.branchesPageTitle, style: AppTextStyles.headlineSmall),
          leading: AppBackButton(
            onPressed: () => context.canPop()
                ? context.pop()
                : context.go(RouteNames.branchesPath),
          ),
        ),
        body: SafeArea(
          child: _loading
              ? const BrandLoadingIndicator()
              : _loadFailed || _branch == null
                  ? _ErrorState(onRetry: _load)
                  : ListView(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      children: [
                        _BranchInfoCard(branch: _branch!, onSaved: _load),
                        const SizedBox(height: AppSpacing.lg),
                        if (_isPerBranchMode || _branch!.isMain)
                          _WhatsAppCard(branchId: _branch!.id, status: _connectStatus),
                        if (_isPerBranchMode || _branch!.isMain) const SizedBox(height: AppSpacing.lg),
                        _TeamCard(
                          branchId: _branch!.id,
                          members: _team ?? const [],
                          allBranches: _allBranches,
                          onChanged: _load,
                        ),
                      ],
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
          child: Text(s.branchesLoadFailed, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
        ),
        const SizedBox(height: AppSpacing.md),
        Center(child: TextButton(onPressed: onRetry, child: Text(s.retry))),
      ],
    );
  }
}

class _BranchInfoCard extends StatefulWidget {
  final Branch branch;
  final VoidCallback onSaved;
  const _BranchInfoCard({required this.branch, required this.onSaved});

  @override
  State<_BranchInfoCard> createState() => _BranchInfoCardState();
}

class _BranchInfoCardState extends State<_BranchInfoCard> {
  late TextEditingController _nameController;
  late TextEditingController _cityController;
  bool _saving = false;
  bool _busyToggle = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.branch.name);
    _cityController = TextEditingController(text: widget.branch.city);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  Future<void> _saveDetails() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final result = await context.read<AuthProvider>().patchBranch(
          widget.branch.id,
          name: _nameController.text.trim(),
          city: _cityController.text.trim(),
        );
    if (!mounted) return;
    setState(() => _saving = false);
    if (result.branch != null) {
      widget.onSaved();
    } else {
      setState(() => _error = s.branchesSaveFailed);
    }
  }

  Future<void> _toggleActive(bool next) async {
    setState(() => _busyToggle = true);
    final result = await context.read<AuthProvider>().patchBranch(widget.branch.id, active: next);
    if (!mounted) return;
    setState(() => _busyToggle = false);
    if (result.branch != null) widget.onSaved();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

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
          Text(s.branchesNameLabel,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.xs),
          KbAnchor(
            id: 'account.shop.branches.detail.name_field',
            child: TextField(
              controller: _nameController,
              decoration: const InputDecoration(isDense: true, counterText: ''),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(s.branchesCityLabel,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.xs),
          KbAnchor(
            id: 'account.shop.branches.detail.city_field',
            child: TextField(
              controller: _cityController,
              decoration: const InputDecoration(isDense: true, counterText: ''),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
          ],
          const SizedBox(height: AppSpacing.md),
          CapabilityGate(
            requires: const ['operations.update_branch'],
            child: KbAnchor(
              id: 'account.shop.branches.detail.save_button',
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saving ? null : _saveDetails,
                  child: _saving
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(s.save),
                ),
              ),
            ),
          ),
          const Divider(height: AppSpacing.xl),
          CapabilityGate(
            requires: const ['operations.update_branch'],
            child: KbAnchor(
              id: 'account.shop.branches.detail.status_toggle',
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(s.branchesStatusLabel,
                            style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                        if (widget.branch.isMain)
                          Text(s.branchesMainCannotClose,
                              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                      ],
                    ),
                  ),
                  if (_busyToggle)
                    const SizedBox(
                        width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  else
                    Switch(
                      value: widget.branch.active,
                      onChanged: widget.branch.isMain ? null : _toggleActive,
                    ),
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

class _WhatsAppCard extends StatelessWidget {
  final String branchId;
  final BranchConnectStatus? status;
  const _WhatsAppCard({required this.branchId, required this.status});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

    // THREE REAL STATES ONLY — connect.py's own note on why "connected but can't send" stays a
    // distinct third state rather than lumped with a plain "connected".
    final AppTone tone;
    final String label;
    final IconData icon;
    if (status == null || status!.notStarted) {
      tone = AppTone.info;
      label = s.branchesWhatsappNotStarted;
      icon = Icons.link_off_rounded;
    } else if (status!.canSend) {
      tone = AppTone.success;
      label = s.branchesWhatsappConnected;
      icon = Icons.check_circle_rounded;
    } else {
      tone = AppTone.warning;
      label = s.branchesWhatsappCannotSend;
      icon = Icons.warning_rounded;
    }
    final colors = ToneColors.of(context, tone);

    return KbAnchor(
      id: 'account.shop.branches.detail.whatsapp_card',
      child: RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: colors.solid,
      child: Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: border),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [colors.solid, colors.solid.withValues(alpha: 0.75)],
              ),
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Icon(icon, color: Colors.white, size: 22),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.branchesWhatsappTitle,
                    style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(label, style: AppTextStyles.bodySmall.copyWith(color: colors.onSoft)),
                if (status != null && status!.message.isNotEmpty && !status!.notStarted)
                  Text(status!.message,
                      style: AppTextStyles.caption.copyWith(color: AppColors.textMuted)),
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

class _TeamCard extends StatelessWidget {
  final String branchId;
  final List<BranchTeamMember> members;
  final List<Branch> allBranches;
  final VoidCallback onChanged;
  const _TeamCard({
    required this.branchId,
    required this.members,
    required this.allBranches,
    required this.onChanged,
  });

  static String _roleLabel(S s, String role) => switch (role) {
        'operator' => s.branchesRoleOperator,
        'supervisor' => s.branchesRoleSupervisor,
        'marketer' => s.branchesRoleMarketer,
        'manager' => s.branchesRoleManager,
        _ => role,
      };

  Future<void> _openAddMember(BuildContext context) async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AddMemberSheet(branchId: branchId),
    );
    if (added == true) onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final border = dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle;

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
          Row(
            children: [
              Expanded(
                child: Text(s.branchesTeamTitle,
                    style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
              ),
              KbAnchor(
                id: 'account.shop.branches.detail.add_member_button',
                child: TextButton.icon(
                  onPressed: () => _openAddMember(context),
                  icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
                  label: Text(s.branchesAddMember),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (members.isEmpty)
            Text(s.branchesTeamEmpty,
                style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary))
          else
            ...members.map((m) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Material(
                    color: Colors.transparent,
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(AppRadius.sm),
                      onTap: () async {
                        final changed = await showModalBottomSheet<bool>(
                          context: context,
                          isScrollControlled: true,
                          backgroundColor: Colors.transparent,
                          builder: (_) => _EditMemberSheet(member: m, allBranches: allBranches),
                        );
                        if (changed == true) onChanged();
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: AppSpacing.xs, vertical: AppSpacing.xs),
                        child: Row(
                          children: [
                            Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: m.active
                                    ? (dark ? AppDarkColors.accentSoft : AppColors.accentSoft)
                                    : (dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft),
                              ),
                              child: Icon(
                                m.active ? Icons.person_rounded : Icons.person_off_rounded,
                                size: 16,
                                color: m.active
                                    ? (dark ? AppDarkColors.accent : AppColors.accent)
                                    : (dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft),
                              ),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(m.name,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: AppTextStyles.bodyMedium),
                                  if (m.visibleAll)
                                    Text(s.branchesVisibleAllHint,
                                        style: AppTextStyles.caption
                                            .copyWith(color: AppColors.textMuted))
                                  else if (m.visibleBranchIds.length > 1)
                                    Text(s.branchesVisibleSomeHint(m.visibleBranchIds.length),
                                        style: AppTextStyles.caption
                                            .copyWith(color: AppColors.textMuted)),
                                ],
                              ),
                            ),
                            Text(_roleLabel(s, m.role),
                                style: AppTextStyles.bodySmall
                                    .copyWith(color: AppColors.textSecondary)),
                            const SizedBox(width: 4),
                            Icon(
                                Directionality.of(context) == TextDirection.rtl
                                    ? Icons.chevron_left_rounded
                                    : Icons.chevron_right_rounded,
                                size: 18, color: AppColors.textMuted),
                          ],
                        ),
                      ),
                    ),
                  ),
                )),
        ],
      ),
      ),
    );
  }
}

class _AddMemberSheet extends StatefulWidget {
  final String branchId;
  const _AddMemberSheet({required this.branchId});

  @override
  State<_AddMemberSheet> createState() => _AddMemberSheetState();
}

class _AddMemberSheetState extends State<_AddMemberSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  StaffRole _role = StaffRole.operator;
  bool _obscure = true;
  bool _saving = false;
  String? _error;
  HireErrorCode? _lastError;

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final result = await context.read<AuthProvider>().hireMember(
          name: _nameController.text.trim(),
          phone: _phoneController.text.trim(),
          password: _passwordController.text,
          role: _role,
          branchId: widget.branchId,
        );
    if (!mounted) return;
    if (result.error == HireErrorCode.none) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _lastError = result.error;
      _error = switch (result.error) {
        HireErrorCode.seatLimit => s.branchesSeatLimit,
        HireErrorCode.busy => s.branchesSaveFailed,
        HireErrorCode.notHired =>
          result.message.isNotEmpty ? result.message : s.branchesHireFailed,
        _ => s.branchesHireFailed,
      };
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        // SCROLLABLE, NOT A BARE Column — found live: on a short viewport (the keyboard open on a
        // small phone, or a narrow desktop test window) this form's own fields plus the role
        // picker overflowed the sheet's fixed height with no way to reach the save button.
        child: SingleChildScrollView(
          child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.branchesAddMember, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'account.shop.branches.detail.add_member.name_field',
                child: TextFormField(
                  controller: _nameController,
                  decoration: InputDecoration(isDense: true, hintText: s.branchesMemberNameLabel),
                  validator: (v) => Validators.validateName(v)?.text(context),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'account.shop.branches.detail.add_member.phone_field',
                child: TextFormField(
                  controller: _phoneController,
                  textDirection: TextDirection.ltr,
                  keyboardType: TextInputType.phone,
                  decoration: InputDecoration(isDense: true, hintText: s.branchesMemberPhoneLabel),
                  validator: (v) => Validators.validatePhone(v)?.text(context),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'account.shop.branches.detail.add_member.password_field',
                child: TextFormField(
                  controller: _passwordController,
                  obscureText: _obscure,
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: s.branchesMemberPasswordLabel,
                    suffixIcon: IconButton(
                      icon: Icon(_obscure ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                          size: 20),
                      onPressed: () => setState(() => _obscure = !_obscure),
                    ),
                  ),
                  validator: (v) => Validators.validatePassword(v)?.text(context),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(s.branchesMemberRoleLabel,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
              const SizedBox(height: AppSpacing.xs),
              KbAnchor(
                id: 'account.shop.branches.detail.add_member.role_field',
                child: SegmentedButton<StaffRole>(
                  segments: [
                    ButtonSegment(value: StaffRole.operator, label: Text(s.branchesRoleOperator)),
                    ButtonSegment(value: StaffRole.supervisor, label: Text(s.branchesRoleSupervisor)),
                    ButtonSegment(value: StaffRole.marketer, label: Text(s.branchesRoleMarketer)),
                    ButtonSegment(value: StaffRole.manager, label: Text(s.branchesRoleManager)),
                  ],
                  selected: {_role},
                  onSelectionChanged: (v) => setState(() => _role = v.first),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(_error!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
              ],
              // A REAL DESTINATION, RIGHT WHERE THE REFUSAL LANDS — console's own «فريقي» offers
              // the exact same link at the exact same refusal (STORE_PATH, apps/console/src/
              // screens/Team.tsx). The native capacity stepper now lives in AppsStoreScreen's own
              // «السعة» section (parity/app_store.md §6) — no more console URL.
              if (_lastError == HireErrorCode.seatLimit) ...[
                const SizedBox(height: AppSpacing.sm),
                TextButton.icon(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => const AppsStoreScreen(initialStoreTab: true),
                  )),
                  icon: const Icon(Icons.storefront_rounded, size: 18),
                  label: Text(s.branchesIncreaseCapacity),
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              CapabilityGate(
                requires: const ['operations.hire_member'],
                child: KbAnchor(
                id: 'account.shop.branches.detail.add_member.submit',
                child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saving ? null : _submit,
                  child: _saving
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(s.save),
                ),
                ),
              ),
              ),
            ],
          ),
          ),
        ),
      ),
    );
  }
}

/// Which branches this member may SEE, beyond his own station — `staff.py`'s own three real
/// answers (`branch_scope`'s own docstring): just his station, a named set, or everything.
enum _Visibility { ownOnly, some, all }

/// Rename, role, station, branch-visibility, stop/reactivate, working hours — ONE route
/// (`PATCH /staff/operators/{id}`) for everything except working hours (its own two routes) and
/// stop/reactivate's own real refusal shapes (`NOT_STOPPED`/`REHIRE_REQUIRED`).
class _EditMemberSheet extends StatefulWidget {
  final BranchTeamMember member;
  final List<Branch> allBranches;
  const _EditMemberSheet({required this.member, required this.allBranches});

  @override
  State<_EditMemberSheet> createState() => _EditMemberSheetState();
}

class _EditMemberSheetState extends State<_EditMemberSheet> {
  late final TextEditingController _nameController;
  late StaffRole _role;
  late String _branchId;
  late _Visibility _visibility;
  late Set<String> _visibleSet;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final m = widget.member;
    _nameController = TextEditingController(text: m.name);
    _role = staffRoleFromValue(m.role) ?? StaffRole.operator;
    _branchId = m.branchId;
    _visibility = m.visibleAll
        ? _Visibility.all
        : (m.visibleBranchIds.isNotEmpty ? _Visibility.some : _Visibility.ownOnly);
    _visibleSet = m.visibleBranchIds.toSet();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final reason = await context.read<AuthProvider>().editOperator(
          widget.member.id,
          name: _nameController.text.trim(),
          role: _role,
          branchId: _branchId,
          visibleAll: _visibility == _Visibility.all,
          visibleBranchIds: _visibility == _Visibility.some ? _visibleSet.toList() : const [],
        );
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _error = reason.isNotEmpty ? reason : s.branchesSaveFailed;
    });
  }

  Future<void> _confirmStop() async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(s.branchesStopMemberTitle),
        content: Text(s.branchesStopMemberBody(widget.member.name)),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(s.cancel)),
          TextButton(onPressed: () => Navigator.of(context).pop(true),
              child: Text(s.branchesStopMemberConfirm, style: const TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _saving = true);
    final reason = await context.read<AuthProvider>().editOperator(widget.member.id, active: false);
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _error = reason.isNotEmpty ? reason : s.branchesSaveFailed;
    });
  }

  Future<void> _tryReactivate() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final reason = await context.read<AuthProvider>().editOperator(widget.member.id, active: true);
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      // REHIRE_REQUIRED IS NOT A GENERIC FAILURE — the server's own real rule: a stopped person's
      // identity membership was already revoked, so "reactivate" is not a flip, it's a new hire.
      _error = reason == 'REHIRE_REQUIRED' ? s.branchesRehireRequired
              : (reason.isNotEmpty ? reason : s.branchesSaveFailed);
    });
  }

  Future<void> _openWorkingHours() async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _WorkingHoursSheet(member: widget.member),
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(S.of(context)!.branchesHoursSaved)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final m = widget.member;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text(s.branchesEditMember, style: AppTextStyles.headlineSmall)),
                  if (!m.active)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppColors.dangerSoft,
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                      child: Text(s.branchesMemberStopped,
                          style: AppTextStyles.caption
                              .copyWith(color: AppColors.dangerOnSoft, fontWeight: FontWeight.w700)),
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'account.shop.branches.detail.edit_member.name_field',
                child: TextField(
                  controller: _nameController,
                  decoration: InputDecoration(isDense: true, hintText: s.branchesMemberNameLabel),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(s.branchesMemberRoleLabel,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
              const SizedBox(height: AppSpacing.xs),
              KbAnchor(
                id: 'account.shop.branches.detail.edit_member.role_field',
                child: SegmentedButton<StaffRole>(
                  segments: [
                    ButtonSegment(value: StaffRole.operator, label: Text(s.branchesRoleOperator)),
                    ButtonSegment(value: StaffRole.supervisor, label: Text(s.branchesRoleSupervisor)),
                    ButtonSegment(value: StaffRole.marketer, label: Text(s.branchesRoleMarketer)),
                    ButtonSegment(value: StaffRole.manager, label: Text(s.branchesRoleManager)),
                  ],
                  selected: {_role},
                  onSelectionChanged: (v) => setState(() => _role = v.first),
                ),
              ),
              if (widget.allBranches.length > 1) ...[
                const SizedBox(height: AppSpacing.md),
                Text(s.branchesMemberStationLabel,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                KbAnchor(
                  id: 'account.shop.branches.detail.edit_member.station_field',
                  child: DropdownButtonFormField<String>(
                    initialValue: _branchId,
                    isExpanded: true,
                    decoration: const InputDecoration(isDense: true),
                    items: [
                      for (final b in widget.allBranches)
                        DropdownMenuItem(value: b.id, child: Text(b.name)),
                    ],
                    onChanged: (v) => setState(() => _branchId = v ?? _branchId),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(s.branchesMemberVisibilityLabel,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                KbAnchor(
                  id: 'account.shop.branches.detail.edit_member.visibility_field',
                  child: SegmentedFilter<_Visibility>(
                    value: _visibility,
                    onChanged: (v) => setState(() => _visibility = v),
                    options: [
                      SegmentedFilterOption(
                          value: _Visibility.ownOnly, label: s.branchesVisibilityOwnOnly),
                      SegmentedFilterOption(value: _Visibility.some, label: s.branchesVisibilitySome),
                      SegmentedFilterOption(value: _Visibility.all, label: s.branchesVisibilityAll),
                    ],
                  ),
                ),
                if (_visibility == _Visibility.some) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final b in widget.allBranches)
                        FilterChip(
                          label: Text(b.name),
                          selected: _visibleSet.contains(b.id),
                          onSelected: (sel) => setState(() {
                            if (sel) {
                              _visibleSet.add(b.id);
                            } else {
                              _visibleSet.remove(b.id);
                            }
                          }),
                        ),
                    ],
                  ),
                ],
              ],
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'account.shop.branches.detail.edit_member.working_hours_button',
                child: OutlinedButton.icon(
                  onPressed: _openWorkingHours,
                  icon: const Icon(Icons.schedule_rounded, size: 18),
                  label: Text(s.branchesWorkingHours),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              CapabilityGate(
                requires: const ['operations.update_operator'],
                child: KbAnchor(
                  id: 'account.shop.branches.detail.edit_member.save',
                  child: SizedBox(
                    width: double.infinity,
                    child: PrimaryButton(
                      text: s.save,
                      isLoading: _saving,
                      onPressed: _saving ? null : _submit,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              CapabilityGate(
                requires: const ['operations.update_operator'],
                child: KbAnchor(
                  id: 'account.shop.branches.detail.edit_member.stop_reactivate',
                  child: SizedBox(
                    width: double.infinity,
                    child: TextButton.icon(
                      onPressed: _saving ? null : (m.active ? _confirmStop : _tryReactivate),
                      icon: Icon(m.active ? Icons.person_off_outlined : Icons.person_add_alt_1_outlined,
                          color: m.active ? AppColors.danger : null),
                      label: Text(
                        m.active ? s.branchesStopMember : s.branchesReactivateMember,
                        style: TextStyle(color: m.active ? AppColors.danger : null),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The whole week, Monday(0)→Sunday(6), every save — `PUT .../working-hours` never merges a
/// partial day. "مسح" returns him to inheriting the shop's own default hours entirely.
class _WorkingHoursSheet extends StatefulWidget {
  final BranchTeamMember member;
  const _WorkingHoursSheet({required this.member});

  @override
  State<_WorkingHoursSheet> createState() => _WorkingHoursSheetState();
}

class _WorkingHoursSheetState extends State<_WorkingHoursSheet> {
  static const _defaultStart = 9 * 60;
  static const _defaultEnd = 21 * 60;

  late Map<int, DayHours> _days;
  bool _saving = false;
  bool _clearing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final existing = widget.member.workingHours?.weekly ?? const {};
    _days = {
      for (var i = 0; i < 7; i++)
        i: existing['$i'] ??
            const DayHours(closed: false, startMinute: _defaultStart, endMinute: _defaultEnd),
    };
  }

  static String _minutesToLabel(int minutes) {
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
  }

  Future<void> _pickTime(int day, {required bool isStart}) async {
    final current = _days[day]!;
    final initial =
        TimeOfDay(hour: (isStart ? current.startMinute : current.endMinute) ~/ 60,
            minute: (isStart ? current.startMinute : current.endMinute) % 60);
    final picked = await pickTimeSheet(context, initial: initial);
    if (picked == null) return;
    final minutes = picked.hour * 60 + picked.minute;
    setState(() {
      _days[day] = isStart ? current.copyWith(startMinute: minutes) : current.copyWith(endMinute: minutes);
    });
  }

  Future<void> _save() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final hours = WorkingHours(weekly: {for (final e in _days.entries) '${e.key}': e.value});
    final reason = await context.read<AuthProvider>().setWorkingHours(widget.member.id, hours);
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _error = reason == 'EXCEEDS_SHOP_HOURS'
          ? s.branchesHoursExceedsShop
          : (reason.isNotEmpty ? reason : s.branchesSaveFailed);
    });
  }

  Future<void> _clear() async {
    setState(() => _clearing = true);
    final ok = await context.read<AuthProvider>().clearWorkingHours(widget.member.id);
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pop(true);
    } else {
      setState(() {
        _clearing = false;
        _error = S.of(context)!.branchesSaveFailed;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dayLabels = [
      s.branchesDayMonday, s.branchesDayTuesday, s.branchesDayWednesday, s.branchesDayThursday,
      s.branchesDayFriday, s.branchesDaySaturday, s.branchesDaySunday,
    ];
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.branchesWorkingHours, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.xs),
              Text(s.branchesHoursHint,
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
              const SizedBox(height: AppSpacing.md),
              for (var i = 0; i < 7; i++)
                KbAnchor(
                  id: 'account.shop.branches.detail.working_hours.time_pickers',
                  child: Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: Row(
                    children: [
                      SizedBox(width: 64, child: Text(dayLabels[i], style: AppTextStyles.bodySmall)),
                      Switch(
                        value: !_days[i]!.closed,
                        onChanged: (open) =>
                            setState(() => _days[i] = _days[i]!.copyWith(closed: !open)),
                      ),
                      if (!_days[i]!.closed) ...[
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () => _pickTime(i, isStart: true),
                            child: Text(_minutesToLabel(_days[i]!.startMinute)),
                          ),
                        ),
                        const SizedBox(width: 6),
                        const Text('—'),
                        const SizedBox(width: 6),
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () => _pickTime(i, isStart: false),
                            child: Text(_minutesToLabel(_days[i]!.endMinute)),
                          ),
                        ),
                      ] else
                        Expanded(
                          child: Text(s.branchesDayClosed,
                              textAlign: TextAlign.center,
                              style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
                        ),
                    ],
                  ),
                  ),
                ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              CapabilityGate(
                requires: const ['operations.set_staff_hours'],
                child: KbAnchor(
                  id: 'account.shop.branches.detail.working_hours.save',
                  child: SizedBox(
                    width: double.infinity,
                    child: PrimaryButton(
                      text: s.save,
                      isLoading: _saving,
                      onPressed: (_saving || _clearing) ? null : _save,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              CapabilityGate(
                requires: const ['operations.clear_staff_hours'],
                child: KbAnchor(
                  id: 'account.shop.branches.detail.working_hours.clear',
                  child: SizedBox(
                    width: double.infinity,
                    child: TextButton(
                      onPressed: (_saving || _clearing) ? null : _clear,
                      child: Text(s.branchesHoursClear),
                  ),
                ),
              ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
