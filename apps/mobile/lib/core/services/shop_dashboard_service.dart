import 'package:dio/dio.dart';

import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/shop_dashboard_model.dart';

/// «محلّي» — mirrors `apps/console/src/screens/Shop.tsx`'s own real routes exactly, spread across
/// three services (insights/reminders/whatsapp-assistant), same as the console itself calls them.
/// Zero backend work for this mobile build.
class ShopDashboardService {
  ShopDashboardService({required this.apiClient});
  final ApiClient apiClient;

  Future<TodayStatus?> today() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/today');
      final body = response.data;
      if (body is! Map) return null;
      return TodayStatus.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<WaConnectStatus?> connectStatus() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/whatsapp/connect');
      final body = response.data;
      if (body is! Map) return null;
      return WaConnectStatus.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// Returns `(dashboard, mustChooseBranchIds)` — a real `409 MANY_BRANCHES` refusal surfaces as
  /// the second element non-empty, `dashboard` null, matching the console's own `mustChoose` state.
  Future<(ShopDashboard?, List<String>)> dashboard({String branchId = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/insights/dashboard',
          queryParameters: {if (branchId.isNotEmpty) 'branch_id': branchId});
      final body = response.data;
      if (body is! Map) return (null, const <String>[]);
      return (ShopDashboard.fromJson(Map<String, dynamic>.from(body)), const <String>[]);
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        final body = e.response?.data;
        if (body is Map && body['error'] == 'MANY_BRANCHES') {
          final ids = ((body['branches'] as List?) ?? const []).map((x) => x.toString()).toList();
          return (null, ids);
        }
      }
      return (null, const <String>[]);
    }
  }

  Future<bool> refresh() async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/insights/refresh');
      final body = response.data;
      return body is Map;
    } on DioException {
      return false;
    }
  }

  Future<bool> dismissNextStep(String id) async {
    try {
      await apiClient.dio.post<dynamic>('/api/v1/insights/next-step/dismiss', data: {'id': id});
      return true;
    } on DioException {
      return false;
    }
  }

  Future<Branches?> branches() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/insights/branches');
      final body = response.data;
      if (body is! Map) return null;
      return Branches.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<ShopImpact?> myImpact() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/assistant/growth/my-impact');
      final body = response.data;
      if (body is! Map) return null;
      return ShopImpact.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `services/insights/app/user_actions.py`'s own `operator_rows`/`operator_unknown`/
  /// `operator_can_rank` live inside the same dashboard `values` bag — no separate route.
  List<OperatorRow>? operatorRows(ShopDashboard d) {
    final v = d.values['operator_rows'];
    if (v == null) return null;
    return (v as List)
        .whereType<Map>()
        .map((m) => OperatorRow.fromJson(Map<String, dynamic>.from(m)))
        .toList(growable: false);
  }

  int operatorUnknown(ShopDashboard d) => (d.values['operator_unknown'] as num?)?.toInt() ?? 0;
  bool operatorCanRank(ShopDashboard d) => d.values['operator_can_rank'] as bool? ?? true;
}
