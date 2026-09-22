import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
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
                        _TeamCard(branchId: _branch!.id, members: _team ?? const [], onChanged: _load),
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
          KbAnchor(
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
          const Divider(height: AppSpacing.xl),
          KbAnchor(
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
  final VoidCallback onChanged;
  const _TeamCard({required this.branchId, required this.members, required this.onChanged});

  static String _roleLabel(S s, String role) => switch (role) {
        'operator' => s.branchesRoleOperator,
        'supervisor' => s.branchesRoleSupervisor,
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
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                  child: Row(
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: (dark ? AppDarkColors.accentSoft : AppColors.accentSoft),
                        ),
                        child: Icon(Icons.person_rounded,
                            size: 16, color: dark ? AppDarkColors.accent : AppColors.accent),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Text(m.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.bodyMedium),
                      ),
                      Text(_roleLabel(s, m.role),
                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                    ],
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
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.9),
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
              // screens/Team.tsx), never a dead-end sentence with nowhere to act on it. Mobile has
              // no native store screen yet (RouteNames.appsPath still renders `_NotYetOnMobile`),
              // so this opens the real one the console already has, same server, same session.
              if (_lastError == HireErrorCode.seatLimit) ...[
                const SizedBox(height: AppSpacing.sm),
                TextButton.icon(
                  onPressed: () => openUrl('${ApiConstants.baseUrl}/app/', context),
                  icon: const Icon(Icons.storefront_rounded, size: 18),
                  label: Text(s.branchesIncreaseCapacity),
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
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
            ],
          ),
          ),
        ),
      ),
    );
  }
}
