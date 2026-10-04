import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/whatsapp_order_model.dart';

/// «طلبات التوصيل عبر الواتساب» — every real route
/// services/operations/app/api/v1/whatsapp_orders.py exposes, same shape
/// apps/console/src/screens/WhatsAppOrders.tsx already calls through its catalogue
/// (`whatsapp_order.*` action ids). Raw `apiClient.dio` calls, same "plain JSON, never this
/// app's own {success, data} envelope" posture [MobileRequestsService] already takes.
class WhatsAppOrdersService {
  final ApiClient apiClient;

  WhatsAppOrdersService({required this.apiClient});

  static const String _base = '/api/v1/staff/whatsapp-orders';

  Future<List<WhatsAppOrder>?> list() async {
    try {
      final response = await apiClient.dio.get<dynamic>(_base);
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['orders'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => WhatsAppOrder.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<({bool paused, String reason})?> getPause(String branchId) async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('$_base/pause', queryParameters: {'branch_id': branchId});
      final body = response.data;
      if (body is! Map) return null;
      return (paused: body['paused'] as bool? ?? false, reason: body['reason'] as String? ?? '');
    } on DioException {
      return null;
    }
  }

  Future<({bool paused, String reason})?> setPause(
      String branchId, {required bool paused, String reason = ''}) async {
    try {
      final response = await apiClient.dio.post<dynamic>('$_base/pause', data: {
        'branch_id': branchId,
        'paused': paused,
        'reason': reason,
      });
      final body = response.data;
      if (body is! Map) return null;
      return (paused: body['paused'] as bool? ?? false, reason: body['reason'] as String? ?? '');
    } on DioException {
      return null;
    }
  }

  /// Step 9's own on/off switch — `core/order_share_toggle.py`'s «مشاركة الطلب مع المندوب»
  /// preference, per tenant. Absent-means-on on the server, mirrored here as a plain default.
  Future<bool?> getShareToggle() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/share-toggle');
      final body = response.data;
      if (body is! Map) return null;
      return body['enabled'] as bool? ?? true;
    } on DioException {
      return null;
    }
  }

  Future<bool?> setShareToggle(bool enabled) async {
    try {
      final response =
          await apiClient.dio.post<dynamic>('$_base/share-toggle', data: {'enabled': enabled});
      final body = response.data;
      if (body is! Map) return null;
      return body['enabled'] as bool? ?? enabled;
    } on DioException {
      return null;
    }
  }

  Future<WhatsAppOrder?> startPreparing(String orderId) => _postAction('$_base/$orderId/preparing', const {});

  Future<WhatsAppOrder?> markReady(String orderId) => _postAction('$_base/$orderId/ready', const {});

  Future<WhatsAppOrder?> startDelivery(String orderId) =>
      _postAction('$_base/$orderId/out-for-delivery', const {});

  Future<WhatsAppOrder?> markDelivered(String orderId) => _postAction('$_base/$orderId/delivered', const {});

  Future<WhatsAppOrder?> cancel(String orderId, String reason) =>
      _postAction('$_base/$orderId/cancel', {'reason': reason});

  Future<WhatsAppOrder?> resolveMismatch(String orderId) =>
      _postAction('$_base/$orderId/resolve-mismatch', const {});

  Future<WhatsAppOrder?> _postAction(String path, Map<String, dynamic> data) async {
    try {
      final response = await apiClient.dio.post<dynamic>(path, data: data);
      final body = response.data;
      if (body is! Map) return null;
      return WhatsAppOrder.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }
}
