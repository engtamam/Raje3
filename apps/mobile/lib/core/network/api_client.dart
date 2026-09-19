import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/network/api_exceptions.dart';
import 'package:raje3_mobile/core/network/api_interceptors.dart';
import 'package:raje3_mobile/core/network/api_response.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';

/// Main API client for all backend communication.
///
/// PLAIN REST, not the "unified execute endpoint" pattern. The reference
/// project this file was ported from (hair-analysis-platform/mobile-app)
/// routed every call through one `POST /api/v1/mobile/execute
/// { module, action, data }` endpoint. That is NOT copied here — see the
/// TODO in apps/mobile/README.md for why (it would need backend changes
/// across our whole services fleet, a decision not yet made). Everything
/// else — the interceptor stack, typed exception mapping, response
/// envelope parsing, the 503-maintenance special case — is the same
/// architecture, just called with a normal REST path + method.
///
/// Usage:
/// ```dart
/// final apiClient = ApiClient(secureStorage: secureStorage);
///
/// final response = await apiClient.get<UserModel>(
///   '/users/me',
///   fromJson: (json) => UserModel.fromJson(json),
/// );
///
/// final uploadResponse = await apiClient.upload<AttachmentModel>(
///   '/attachments',
///   file: imageFile,
///   fromJson: (json) => AttachmentModel.fromJson(json),
/// );
/// ```
class ApiClient {
  late final Dio _dio;
  final SecureStorage secureStorage;
  late final LanguageInterceptor _languageInterceptor;
  late final AuthInterceptor _authInterceptor;
  late final ContextInterceptor _contextInterceptor;

  ApiClient({
    required this.secureStorage,
    Dio? dio,
  }) {
    _dio = dio ?? Dio();
    _configure();
  }

  /// Configure Dio with base options and interceptors.
  void _configure() {
    _dio.options = BaseOptions(
      baseUrl: ApiConstants.baseUrl,
      connectTimeout: const Duration(milliseconds: ApiConstants.connectTimeout),
      receiveTimeout: const Duration(milliseconds: ApiConstants.receiveTimeout),
      sendTimeout: const Duration(milliseconds: ApiConstants.receiveTimeout),
      headers: {
        ApiConstants.contentType: 'application/json',
        ApiConstants.clientTypeHeader: ApiConstants.clientType,
      },
      responseType: ResponseType.json,
      // Allow 2xx-4xx EXCEPT 401 — 401 must trigger AuthInterceptor's
      // onError so it can attempt automatic token refresh.
      validateStatus: (status) => status != null && status < 500 && status != 401,
    );

    // Language interceptor (kept as field so locale can be updated)
    _languageInterceptor = LanguageInterceptor(locale: 'ar');

    // Context interceptor — injects business_id when in business context
    _contextInterceptor = ContextInterceptor();

    // Add interceptors in order: logging first, then language, then context, then auth
    if (kDebugMode) {
      _dio.interceptors.add(LoggingInterceptor(enabled: true));
    }

    _dio.interceptors.add(_languageInterceptor);
    _dio.interceptors.add(_contextInterceptor);

    _authInterceptor = AuthInterceptor(secureStorage: secureStorage, dio: _dio);
    _dio.interceptors.add(_authInterceptor);
  }

  /// Set the callback invoked when token refresh fails (forces logout).
  set onForceLogout(VoidCallback? callback) {
    _authInterceptor.onForceLogout = callback;
  }

  /// Reset auth interceptor state after a successful login.
  ///
  /// Clears the force-logout guard so future 401 errors can properly
  /// trigger force-logout again.
  void resetAuthState() {
    _authInterceptor.resetForceLogout();
  }

  /// Set the active tenant (shop/branch) ID for context-scoped API calls.
  ///
  /// When non-null, [ContextInterceptor] injects `X-Tenant-Id` into every
  /// request header so backend queries scope to that tenant.
  /// Pass `null` to clear the active tenant.
  void setActiveTenantId(String? tenantId) {
    _contextInterceptor.setActiveTenantId(tenantId);
  }

  /// The currently active tenant ID, or null.
  String? get activeTenantId => _contextInterceptor.activeTenantId;

  /// Update the language for all subsequent requests.
  void updateLocale(String locale) {
    _languageInterceptor.updateLocale(locale);
  }

  /// Current locale.
  String get currentLocale => _languageInterceptor.locale;

  /// The underlying Dio instance (for advanced usage / testing).
  Dio get dio => _dio;

  // ─────────────────────────────────────────────────────────────────────────
  // REST verbs — every path is relative to ApiConstants.apiBasePath
  // ─────────────────────────────────────────────────────────────────────────

  String _url(String path) => '${ApiConstants.apiBasePath}$path';

  /// GET request, parsed into a single typed object.
  Future<ApiResponse<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    T Function(Map<String, dynamic>)? fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.get(
        _url(path),
        queryParameters: queryParameters,
        cancelToken: cancelToken,
      );
      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// GET request, parsed into a list of typed objects.
  Future<ApiResponse<List<T>>> getList<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    required T Function(Map<String, dynamic>) fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.get(
        _url(path),
        queryParameters: queryParameters,
        cancelToken: cancelToken,
      );
      return _parseListResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// POST request, parsed into a single typed object.
  Future<ApiResponse<T>> post<T>(
    String path, {
    Map<String, dynamic>? data,
    T Function(Map<String, dynamic>)? fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.post(_url(path), data: data, cancelToken: cancelToken);
      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// PUT request, parsed into a single typed object.
  Future<ApiResponse<T>> put<T>(
    String path, {
    Map<String, dynamic>? data,
    T Function(Map<String, dynamic>)? fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.put(_url(path), data: data, cancelToken: cancelToken);
      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// PATCH request, parsed into a single typed object.
  Future<ApiResponse<T>> patch<T>(
    String path, {
    Map<String, dynamic>? data,
    T Function(Map<String, dynamic>)? fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.patch(_url(path), data: data, cancelToken: cancelToken);
      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// DELETE request.
  Future<ApiResponse<T>> delete<T>(
    String path, {
    Map<String, dynamic>? data,
    T Function(Map<String, dynamic>)? fromJson,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.delete(_url(path), data: data, cancelToken: cancelToken);
      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UPLOAD — single file, multipart/form-data
  // ─────────────────────────────────────────────────────────────────────────

  /// Upload a single file (plus optional extra form fields) to [path].
  ///
  /// [fieldName] — The form field name for the file (default: 'file').
  /// [onSendProgress] — Optional callback for upload progress tracking.
  Future<ApiResponse<T>> upload<T>(
    String path, {
    required File file,
    Map<String, dynamic>? data,
    T Function(Map<String, dynamic>)? fromJson,
    String fieldName = 'file',
    void Function(int sent, int total)? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    try {
      final fileName = file.path.split(Platform.pathSeparator).last;

      final formData = FormData.fromMap({
        ...?data,
        fieldName: await MultipartFile.fromFile(file.path, filename: fileName),
      });

      final response = await _dio.post(
        _url(path),
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          sendTimeout: const Duration(milliseconds: ApiConstants.uploadTimeout),
          receiveTimeout: const Duration(milliseconds: ApiConstants.uploadTimeout),
        ),
        onSendProgress: onSendProgress,
        cancelToken: cancelToken,
      );

      return _parseResponse<T>(response, fromJson);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RESPONSE PARSING
  // ─────────────────────────────────────────────────────────────────────────

  /// Parse a Dio response into a typed ApiResponse.
  ApiResponse<T> _parseResponse<T>(
    Response response,
    T Function(Map<String, dynamic>)? fromJson,
  ) {
    final responseData = response.data as Map<String, dynamic>?;

    if (responseData == null) {
      return ApiResponse<T>.failure(
        messageAr: 'استجابة غير صالحة من الخادم',
        messageEn: 'Invalid response from server',
      );
    }

    // Check for server-side error responses with HTTP 200 but success: false
    if (responseData['success'] == false) {
      // Return as failed ApiResponse rather than throwing
      return ApiResponse<T>.fromJson(
        responseData,
        fromJsonT: fromJson,
      );
    }

    return ApiResponse<T>.fromJson(
      responseData,
      fromJsonT: fromJson,
    );
  }

  /// Parse a Dio response into a list-typed ApiResponse.
  ApiResponse<List<T>> _parseListResponse<T>(
    Response response,
    T Function(Map<String, dynamic>) fromJson,
  ) {
    final responseData = response.data as Map<String, dynamic>?;

    if (responseData == null) {
      return ApiResponse<List<T>>.failure(
        messageAr: 'استجابة غير صالحة من الخادم',
        messageEn: 'Invalid response from server',
      );
    }

    return ApiResponse.fromJsonList<T>(
      responseData,
      fromJsonT: fromJson,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR HANDLING
  // ─────────────────────────────────────────────────────────────────────────

  /// Convert a DioException into the appropriate ApiException subclass.
  ApiException _handleDioError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiTimeoutException();

      case DioExceptionType.connectionError:
        return const NetworkException();

      case DioExceptionType.badResponse:
        return _handleResponseError(error);

      case DioExceptionType.cancel:
        return const ApiException(
          message: 'تم إلغاء الطلب',
          messageAr: 'تم إلغاء الطلب',
          messageEn: 'Request was cancelled',
        );

      case DioExceptionType.badCertificate:
        return const ApiException(
          message: 'خطأ في شهادة الأمان',
          messageAr: 'خطأ في شهادة الأمان',
          messageEn: 'SSL certificate error',
        );

      case DioExceptionType.unknown:
        if (error.error is SocketException) {
          return const NetworkException();
        }
        return ApiException(
          message: error.message ?? 'حدث خطأ غير متوقع',
          messageAr: 'حدث خطأ غير متوقع',
          messageEn: 'An unexpected error occurred',
        );
    }
  }

  /// Handle HTTP error status codes from the response.
  ApiException _handleResponseError(DioException error) {
    final statusCode = error.response?.statusCode;
    final responseData = error.response?.data as Map<String, dynamic>?;

    switch (statusCode) {
      case 401:
        return UnauthorizedException(
          messageAr: responseData?['message_ar'] as String? ??
              'غير مصرح - يرجى تسجيل الدخول مرة أخرى',
          messageEn: responseData?['message_en'] as String? ??
              'Unauthorized - Please login again',
          data: responseData,
        );

      case 403:
        return ForbiddenException(
          messageAr: responseData?['message_ar'] as String? ??
              'ليس لديك صلاحية للقيام بهذا الإجراء',
          messageEn: responseData?['message_en'] as String? ??
              'You do not have permission to perform this action',
          data: responseData,
        );

      case 404:
        return NotFoundException(
          messageAr: responseData?['message_ar'] as String? ??
              'العنصر المطلوب غير موجود',
          messageEn: responseData?['message_en'] as String? ??
              'The requested resource was not found',
          data: responseData,
        );

      case 422:
        return ValidationException.fromResponse(responseData);

      case 429:
        final retryAfter = error.response?.headers.value('retry-after');
        return TooManyRequestsException(
          retryAfterSeconds:
              retryAfter != null ? int.tryParse(retryAfter) : null,
          data: responseData,
        );

      default:
        if (statusCode != null && statusCode >= 500) {
          return ServerException(
            statusCode: statusCode,
            messageAr: responseData?['message_ar'] as String? ??
                'حدث خطأ في الخادم',
            messageEn: responseData?['message_en'] as String? ??
                'Server error occurred',
            data: responseData,
          );
        }
        return ApiException(
          message: responseData?['message_ar'] as String? ??
              'حدث خطأ غير متوقع',
          statusCode: statusCode,
          messageAr: responseData?['message_ar'] as String?,
          messageEn: responseData?['message_en'] as String?,
          data: responseData,
        );
    }
  }
}
