import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «تسجيل زيارة» — copied from the reference project's
/// `lib/features/crm/add_client_screen.dart` (animated fade/slide entry,
/// icon-titled section cards, sticky bottom save bar), then adapted:
/// its CRM client fields (name, gender, acquisition source, consent
/// switches, …) are gone — this records a service visit, not a client
/// profile, per apps/console/src/screens/Visit.tsx's own flow (that file's
/// header comment: plate first, then customer, then services, then save).
///
/// Real endpoints (services/operations/app/api/v1/field.py):
///   - GET  /api/v1/field/customers/by-phone?phone=...   exact lookup
///   - GET  /api/v1/field/catalogue                       services + packages
///   - POST /api/v1/field/visits                          VisitIn — records the visit
/// All three are shared, cross-client-type routes, so calls go through
/// [ApiClient.dio] directly rather than the `{success, data}` envelope
/// (see catalog_service.dart's own note).
class VisitScreen extends StatefulWidget {
  const VisitScreen({super.key});

  @override
  State<VisitScreen> createState() => _VisitScreenState();
}

class _VisitScreenState extends State<VisitScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entryController;
  final _phoneController = TextEditingController();
  final _noteController = TextEditingController();

  bool _loadingCatalogue = true;
  String? _catalogueError;
  List<Map<String, dynamic>> _services = [];

  bool _lookingUp = false;
  String? _customerName;
  bool _lookedUp = false;

  /// service_id -> quantity. Only ids present here are sent.
  final Map<String, int> _selected = {};

  bool _saving = false;
  String? _saveError;
  String? _savedMessage;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      vsync: this,
      duration: AppMotion.slow,
    );
    _entryController.forward();
    _loadCatalogue();
  }

  @override
  void dispose() {
    _entryController.dispose();
    _phoneController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  AuthProvider get _api => context.read<AuthProvider>();

  Future<void> _loadCatalogue() async {
    setState(() {
      _loadingCatalogue = true;
      _catalogueError = null;
    });
    try {
      final response = await _api.apiClient.dio.get<dynamic>('/api/v1/field/catalogue');
      final body = response.data;
      final services = body is Map<String, dynamic>
          ? (body['services'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .toList()
          : <Map<String, dynamic>>[];
      if (!mounted) return;
      setState(() {
        _services = services;
        _loadingCatalogue = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _catalogueError = S.of(context)!.visitCatalogueLoadErrorFallback;
        _loadingCatalogue = false;
      });
    }
  }

  Future<void> _lookupPhone() async {
    final phone = _phoneController.text.trim();
    if (phone.length < 3) return;
    setState(() {
      _lookingUp = true;
      _lookedUp = false;
      _customerName = null;
    });
    try {
      final response = await _api.apiClient.dio.get<dynamic>(
        '/api/v1/field/customers/by-phone',
        queryParameters: {'phone': phone},
      );
      final body = response.data;
      final customer = body is Map<String, dynamic> ? body['customer'] : null;
      if (!mounted) return;
      setState(() {
        _customerName = customer is Map<String, dynamic> ? customer['name'] as String? : null;
        _lookedUp = true;
        _lookingUp = false;
      });
    } on DioException {
      if (!mounted) return;
      setState(() {
        _lookingUp = false;
        _lookedUp = false;
      });
    }
  }

  void _toggleService(String serviceId, bool selected) {
    setState(() {
      if (selected) {
        _selected[serviceId] = 1;
      } else {
        _selected.remove(serviceId);
      }
    });
  }

  void _changeQuantity(String serviceId, int delta) {
    setState(() {
      final current = _selected[serviceId] ?? 1;
      final next = (current + delta).clamp(1, 20);
      _selected[serviceId] = next;
    });
  }

  Future<void> _save() async {
    final phone = _phoneController.text.trim();
    if (phone.length < 3 || _selected.isEmpty) {
      setState(() {
        _saveError = phone.length < 3
            ? S.of(context)!.visitEnterCustomerPhone
            : S.of(context)!.visitSelectAtLeastOneService;
      });
      return;
    }
    setState(() {
      _saving = true;
      _saveError = null;
      _savedMessage = null;
    });
    try {
      final response = await _api.apiClient.dio.post<dynamic>(
        '/api/v1/field/visits',
        data: {
          'phone': phone,
          'service_ids': _selected.keys.toList(),
          'quantities': _selected,
          'note': _noteController.text.trim(),
          'idempotency_key': DateTime.now().microsecondsSinceEpoch.toString(),
          'occurred_at': DateTime.now().millisecondsSinceEpoch ~/ 1000,
        },
      );
      final body = response.data;
      final recorded = body is Map<String, dynamic> ? body['recorded'] != false : true;
      if (!mounted) return;
      if (recorded) {
        setState(() {
          _saving = false;
          _savedMessage = S.of(context)!.visitSavedMessage;
          _selected.clear();
          _phoneController.clear();
          _noteController.clear();
          _lookedUp = false;
          _customerName = null;
        });
      } else {
        final reason = body is Map<String, dynamic> ? body['reason'] as String? : null;
        setState(() {
          _saving = false;
          _saveError = reason ?? S.of(context)!.visitSaveErrorFallback;
        });
      }
    } on DioException {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saveError = S.of(context)!.visitSaveErrorNetworkFallback;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: Text(S.of(context)!.visitTitle)),
      body: _loadingCatalogue
          ? const Center(child: CircularProgressIndicator())
          : _catalogueError != null
              ? _RetryBody(message: _catalogueError!, onRetry: _loadCatalogue)
              : AnimatedBuilder(
                  animation: _entryController,
                  builder: (context, _) {
                    final anim = CurvedAnimation(
                      parent: _entryController,
                      curve: Curves.easeOut,
                    ).value;
                    return Opacity(
                      opacity: anim,
                      child: Transform.translate(
                        offset: Offset(0, 16 * (1 - anim)),
                        child: _buildForm(),
                      ),
                    );
                  },
                ),
    );
  }

  Widget _buildForm() {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildCustomerSection(),
                const SizedBox(height: AppSpacing.md),
                _buildServicesSection(),
                const SizedBox(height: AppSpacing.md),
                _buildNoteSection(),
                if (_saveError != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(_saveError!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.danger)),
                ],
                if (_savedMessage != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(_savedMessage!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.success)),
                ],
                const SizedBox(height: AppSpacing.xxl),
              ],
            ),
          ),
        ),
        _buildBottomBar(),
      ],
    );
  }

  // ── Customer (phone lookup) ──────────────────────────────────────────────

  Widget _buildCustomerSection() {
    return _buildSection(
      title: S.of(context)!.visitCustomerSectionTitle,
      icon: Icons.person_rounded,
      children: [
        Text(S.of(context)!.visitCustomerPhoneFieldLabel, style: AppTextStyles.bodySmall),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _phoneController,
          keyboardType: TextInputType.phone,
          style: AppTextStyles.bodyMedium.copyWith(fontSize: 18),
          decoration: InputDecoration(
            hintText: '05xxxxxxxx',
            filled: true,
            fillColor: AppColors.surface0,
            border: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.borderSubtle),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.borderSubtle),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.md,
            ),
            suffixIcon: _lookingUp
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : IconButton(
                    icon: const Icon(Icons.search, color: AppColors.accent),
                    onPressed: _lookupPhone,
                  ),
          ),
          onSubmitted: (_) => _lookupPhone(),
        ),
        if (_lookedUp) ...[
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Icon(
                _customerName != null && _customerName!.isNotEmpty
                    ? Icons.badge_rounded
                    : Icons.person_add_rounded,
                size: 16,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: AppSpacing.xs),
              Text(
                _customerName != null && _customerName!.isNotEmpty
                    ? S.of(context)!.visitKnownCustomer(_customerName!)
                    : S.of(context)!.visitNewCustomer,
                style: AppTextStyles.bodySmall,
              ),
            ],
          ),
        ],
      ],
    );
  }

  // ── Services (with quantity, per "2× غسيل خارجي" rule) ───────────────────

  Widget _buildServicesSection() {
    return _buildSection(
      title: S.of(context)!.visitServicesSectionTitle,
      icon: Icons.content_cut_rounded,
      children: [
        if (_services.isEmpty)
          Text(S.of(context)!.visitNoServicesYet, style: AppTextStyles.bodySmall)
        else
          for (final service in _services)
            _ServiceRow(
              service: service,
              quantity: _selected[service['id'] as String? ?? ''],
              onToggle: (selected) => _toggleService(service['id'] as String? ?? '', selected),
              onQuantityChange: (delta) => _changeQuantity(service['id'] as String? ?? '', delta),
            ),
      ],
    );
  }

  // ── Note ──────────────────────────────────────────────────────────────────

  Widget _buildNoteSection() {
    return _buildSection(
      title: S.of(context)!.visitNoteSectionTitle,
      icon: Icons.note_rounded,
      children: [
        TextField(
          controller: _noteController,
          maxLines: 3,
          style: AppTextStyles.bodyMedium,
          decoration: InputDecoration(
            filled: true,
            fillColor: AppColors.surface0,
            border: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.borderSubtle),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.borderSubtle),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: AppRadius.standardRadius,
              borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
            ),
            contentPadding: const EdgeInsets.all(AppSpacing.md),
          ),
        ),
      ],
    );
  }

  // ── Bottom bar ────────────────────────────────────────────────────────────

  Widget _buildBottomBar() {
    return Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.md,
        MediaQuery.of(context).padding.bottom + AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        border: const Border(top: BorderSide(color: AppColors.borderSubtle)),
      ),
      child: SizedBox(
        width: double.infinity,
        height: 52,
        child: ElevatedButton(
          onPressed: _saving ? null : _save,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.accent,
            foregroundColor: AppColors.accentContrast,
            shape: RoundedRectangleBorder(borderRadius: AppRadius.standardRadius),
            elevation: 0,
          ),
          child: _saving
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accentContrast),
                )
              : Text(S.of(context)!.visitSaveButtonLabel),
        ),
      ),
    );
  }

  // ── Shared section card ──────────────────────────────────────────────────

  Widget _buildSection({
    required String title,
    required IconData icon,
    required List<Widget> children,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 18, color: AppColors.accent),
            const SizedBox(width: AppSpacing.sm),
            Text(
              title,
              style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w600),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.surface1,
            borderRadius: AppRadius.cardRadius,
            border: Border.all(color: AppColors.borderSubtle),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: children,
          ),
        ),
      ],
    );
  }
}

class _ServiceRow extends StatelessWidget {
  final Map<String, dynamic> service;
  final int? quantity;
  final ValueChanged<bool> onToggle;
  final ValueChanged<int> onQuantityChange;

  const _ServiceRow({
    required this.service,
    required this.quantity,
    required this.onToggle,
    required this.onQuantityChange,
  });

  @override
  Widget build(BuildContext context) {
    final name = service['name'] as String? ?? '';
    final selected = quantity != null;
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      decoration: BoxDecoration(
        color: selected ? AppColors.accentSoft : AppColors.surface0,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: selected ? AppColors.accent : AppColors.borderSubtle),
      ),
      child: CheckboxListTile(
        value: selected,
        onChanged: (v) => onToggle(v ?? false),
        activeColor: AppColors.accent,
        title: Text(name, style: AppTextStyles.bodyMedium),
        secondary: selected
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline, color: AppColors.accent),
                    onPressed: () => onQuantityChange(-1),
                  ),
                  Text('$quantity', style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                  IconButton(
                    icon: const Icon(Icons.add_circle_outline, color: AppColors.accent),
                    onPressed: () => onQuantityChange(1),
                  ),
                ],
              )
            : null,
      ),
    );
  }
}

class _RetryBody extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _RetryBody({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(onPressed: onRetry, child: Text(S.of(context)!.retry)),
          ],
        ),
      ),
    );
  }
}
