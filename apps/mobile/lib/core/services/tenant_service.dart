import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/network/api_response.dart';
import 'package:raje3_mobile/models/tenant_model.dart';

/// Service layer for tenant (shop/branch) management.
///
/// ADAPTED from the reference project's `ContextService` — same idea
/// (a "tenant" is what the user is currently operating as/on), generalized
/// from their "individual vs. business" split to a plain list of tenants
/// the signed-in account can act as, and moved off the unified execute
/// endpoint onto plain REST (see api_client.dart's own doc comment).
class TenantService {
  final ApiClient apiClient;

  TenantService({required this.apiClient});

  /// Retrieve all tenants (shops/branches) available to the authenticated user.
  Future<ApiResponse<List<TenantModel>>> getTenants() async {
    return await apiClient.getList<TenantModel>(
      '/tenants',
      fromJson: (json) => TenantModel.fromJson(json),
    );
  }

  /// Switch the active tenant.
  Future<ApiResponse<TenantModel>> switchTenant(String tenantId) async {
    return await apiClient.post<TenantModel>(
      '/tenants/active',
      data: {'tenant_id': tenantId},
      fromJson: (json) => TenantModel.fromJson(json),
    );
  }
}
