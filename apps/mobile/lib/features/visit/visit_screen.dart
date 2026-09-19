import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «تسجيل زيارة» — the mobile mirror of apps/console/src/screens/Visit.tsx's own recording
/// flow, trimmed to what a phone screen needs: phone lookup, pick services (with quantity, per
/// task-visit-booking-quantity.md's "2× غسيل خارجي" rule), optional note, save.
///
/// Real endpoints (services/operations/app/api/v1/field.py):
///   - GET  /api/v1/field/customers/by-phone?phone=...   exact lookup
///   - GET  /api/v1/field/catalogue                       services + packages + fields
///   - POST /api/v1/field/visits                          VisitIn — records the visit
/// All three are shared, cross-client-type routes, so calls go through [ApiClient.dio]
/// directly rather than the `{success, data}` envelope (see catalog_service.dart's own note).
class VisitScreen extends StatefulWidget {
  const VisitScreen({super.key});

  @override
  State<VisitScreen> createState() => _VisitScreenState();
}

class _VisitScreenState extends State<VisitScreen> {
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
    _loadCatalogue();
  }

  @override
  void dispose() {
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
      final response =
          await _api.apiClient.dio.get<dynamic>('/api/v1/field/catalogue');
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
        _catalogueError = 'تعذّر تحميل الخدمات. اسحب للأسفل لإعادة المحاولة.';
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
        _customerName = customer is Map<String, dynamic>
            ? (customer['name'] as String?)
            : null;
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
            ? 'أدخل رقم جوال العميل'
            : 'اختر خدمة واحدة على الأقل';
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
          _savedMessage = 'تم تسجيل الزيارة.';
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
          _saveError = reason ?? 'تعذّر تسجيل الزيارة.';
        });
      }
    } on DioException {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saveError = 'تعذّر تسجيل الزيارة. تحقق من الاتصال وحاول مرة أخرى.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('تسجيل زيارة')),
      body: _loadingCatalogue
          ? const Center(child: CircularProgressIndicator())
          : _catalogueError != null
              ? _RetryBody(message: _catalogueError!, onRetry: _loadCatalogue)
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  children: [
                    Text('رقم جوال العميل', style: AppTextStyles.bodyMedium),
                    const SizedBox(height: AppSpacing.md / 2),
                    TextField(
                      controller: _phoneController,
                      keyboardType: TextInputType.phone,
                      style: const TextStyle(fontSize: 20),
                      decoration: InputDecoration(
                        hintText: '05xxxxxxxx',
                        border: const OutlineInputBorder(),
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
                                icon: const Icon(Icons.search),
                                onPressed: _lookupPhone,
                              ),
                      ),
                      onSubmitted: (_) => _lookupPhone(),
                    ),
                    if (_lookedUp)
                      Padding(
                        padding: const EdgeInsets.only(top: AppSpacing.md / 2),
                        child: Text(
                          _customerName != null && _customerName!.isNotEmpty
                              ? 'عميل معروف: $_customerName'
                              : 'عميل جديد',
                          style: AppTextStyles.bodyMedium
                              .copyWith(color: AppColors.textSecondary),
                        ),
                      ),
                    const SizedBox(height: AppSpacing.md),
                    Text('الخدمات', style: AppTextStyles.bodyMedium.copyWith(
                        fontWeight: FontWeight.bold)),
                    const SizedBox(height: AppSpacing.md / 2),
                    for (final service in _services) _ServiceRow(
                      service: service,
                      quantity: _selected[service['id'] as String? ?? ''],
                      onToggle: (selected) =>
                          _toggleService(service['id'] as String? ?? '', selected),
                      onQuantityChange: (delta) =>
                          _changeQuantity(service['id'] as String? ?? '', delta),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text('ملاحظة (اختياري)', style: AppTextStyles.bodyMedium),
                    const SizedBox(height: AppSpacing.md / 2),
                    TextField(
                      controller: _noteController,
                      maxLines: 3,
                      decoration: const InputDecoration(border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    if (_saveError != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.md / 2),
                        child: Text(_saveError!,
                            style: AppTextStyles.bodyMedium.copyWith(color: Colors.red)),
                      ),
                    if (_savedMessage != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.md / 2),
                        child: Text(_savedMessage!,
                            style: AppTextStyles.bodyMedium.copyWith(color: AppColors.success)),
                      ),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton(
                        onPressed: _saving ? null : _save,
                        child: _saving
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('حفظ الزيارة'),
                      ),
                    ),
                  ],
                ),
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
    return Card(
      color: AppColors.surface1,
      margin: const EdgeInsets.only(bottom: AppSpacing.md / 2),
      child: CheckboxListTile(
        value: selected,
        onChanged: (v) => onToggle(v ?? false),
        title: Text(name, style: AppTextStyles.bodyMedium),
        secondary: selected
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline),
                    onPressed: () => onQuantityChange(-1),
                  ),
                  Text('$quantity', style: AppTextStyles.bodyMedium),
                  IconButton(
                    icon: const Icon(Icons.add_circle_outline),
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
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message, style: AppTextStyles.bodyMedium),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}
