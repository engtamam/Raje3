import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/coworking_model.dart';

/// «الاستضافة المهنية» — every route
/// services/coworking/app/api/v1/admin.py serves, same `coworking.manage` capability that route
/// requires for every write. RAW `apiClient.dio` calls, same convention every other mobile
/// service in this app already holds to.
class CoworkingService {
  final ApiClient apiClient;

  CoworkingService({required this.apiClient});

  static const _base = '/api/v1/coworking';

  /// `GET /resources` — already branch-scoped server-side (unassigned always included).
  Future<List<CoworkingResource>?> listResources() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/resources');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['resources'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CoworkingResource.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /resources` — `branch_id: ""` is a real, valid "unassigned" answer, never omitted.
  Future<String?> createResource({
    required String name,
    required String branchId,
    String description = '',
  }) async {
    try {
      await apiClient.dio.post<dynamic>('$_base/resources', data: {
        'name': name,
        'branch_id': branchId,
        'description': description,
      });
      return null;
    } on DioException catch (e) {
      return _reason(e);
    }
  }

  Future<String?> updateResource(
    String id, {
    String? name,
    bool? active,
    String? branchId,
    String? description,
  }) async {
    try {
      await apiClient.dio.patch<dynamic>('$_base/resources/${Uri.encodeComponent(id)}', data: {
        if (name != null) 'name': name,
        if (active != null) 'active': active,
        if (branchId != null) 'branch_id': branchId,
        if (description != null) 'description': description,
      });
      return null;
    } on DioException catch (e) {
      return _reason(e);
    }
  }

  /// `PUT /resources/{id}/availability` — `weekly` keys are weekday ints (0=Monday), sent as the
  /// server's own `dict[int, list[...]]` shape (Dio encodes int map keys to strings on the wire,
  /// same JSON round-trip the server itself already expects — see `weekly_to_storage`).
  Future<String?> setAvailability(
    String id, {
    required Map<int, List<CoworkingWindow>> weekly,
    required int hourlyPriceMinor,
  }) async {
    try {
      await apiClient.dio.put<dynamic>('$_base/resources/${Uri.encodeComponent(id)}/availability', data: {
        'weekly': weekly.map((day, windows) => MapEntry('$day', windows.map((w) => w.toJson()).toList())),
        'exceptions': const {},
        'hourly_price_minor': hourlyPriceMinor,
      });
      return null;
    } on DioException catch (e) {
      return _reason(e);
    }
  }

  /// `POST /resources/{id}/image` — JSON base64, same shape operations' own catalogue upload
  /// already uses.
  Future<String?> uploadImage(String id, {required List<int> bytes, required String contentType}) async {
    try {
      await apiClient.dio.post<dynamic>('$_base/resources/${Uri.encodeComponent(id)}/image', data: {
        'content_type': contentType,
        'data_base64': base64Encode(bytes),
      });
      return null;
    } on DioException catch (e) {
      return _reason(e);
    }
  }

  /// `GET /resources/{id}/image` — raw bytes, `null` when there is none / on failure.
  Future<List<int>?> fetchImage(String id) async {
    try {
      final response = await apiClient.dio.get<List<int>>(
        '$_base/resources/${Uri.encodeComponent(id)}/image',
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data;
    } on DioException {
      return null;
    }
  }

  /// `GET /joins` — shop-wide, never branch-filtered (see admin.py's own module doc).
  Future<List<CoworkingJoin>?> listJoins({String? status}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/joins',
          queryParameters: {if (status != null) 'status': status});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['joins'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CoworkingJoin.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<bool> approveJoin(String phone) => _joinAction(phone, 'approve');
  Future<bool> rejectJoin(String phone) => _joinAction(phone, 'reject');
  Future<bool> blockPhone(String phone) => _joinAction(phone, 'block');
  Future<bool> unblockPhone(String phone) => _joinAction(phone, 'unblock');

  Future<bool> _joinAction(String phone, String action) async {
    try {
      await apiClient.dio.post<dynamic>('$_base/joins/${Uri.encodeComponent(phone)}/$action');
      return true;
    } on DioException {
      return false;
    }
  }

  /// `GET /bookings` — already branch-scoped server-side.
  Future<List<CoworkingBooking>?> listBookings({String? resourceId, String? status}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/bookings', queryParameters: {
        if (resourceId != null) 'resource_id': resourceId,
        if (status != null) 'status': status,
      });
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['bookings'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CoworkingBooking.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<bool> cancelBooking(String id) async {
    try {
      await apiClient.dio.post<dynamic>('$_base/bookings/${Uri.encodeComponent(id)}/cancel');
      return true;
    } on DioException {
      return false;
    }
  }

  /// `GET /pause` — the shop-wide "stop taking new bookings" switch.
  Future<bool?> isPaused() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/pause');
      final body = response.data;
      if (body is! Map) return null;
      return body['paused'] as bool?;
    } on DioException {
      return null;
    }
  }

  Future<bool?> setPaused(bool paused) async {
    try {
      final response = await apiClient.dio.put<dynamic>('$_base/pause', data: {'paused': paused});
      final body = response.data;
      if (body is! Map) return null;
      return body['paused'] as bool?;
    } on DioException {
      return null;
    }
  }

  String? _reason(DioException e) {
    final data = e.response?.data;
    if (data is Map && data['reason'] is String && (data['reason'] as String).isNotEmpty) {
      return data['reason'] as String;
    }
    return 'تعذر تنفيذ الطلب';
  }
}
