/// Generic API response wrapper for all backend communication.
///
/// The Hair Analysis backend returns a standardized JSON structure:
/// ```json
/// {
///   "success": true|false,
///   "data": { ... },
///   "message_ar": "رسالة عربية",
///   "message_en": "English message",
///   "meta": { "total": 100, "page": 1, "limit": 20 }
/// }
/// ```
///
/// Usage:
/// ```dart
/// final response = await apiClient.execute<UserModel>(
///   module: 'users',
///   action: 'get_profile',
///   fromJson: (json) => UserModel.fromJson(json),
/// );
/// if (response.success) {
///   final user = response.data;
/// }
/// ```
class ApiResponse<T> {
  /// Whether the API call was successful.
  final bool success;

  /// The parsed response data. Null on failure or if no data returned.
  final T? data;

  /// Arabic message from the server.
  final String? messageAr;

  /// English message from the server.
  final String? messageEn;

  /// Metadata (pagination info, totals, etc.).
  final Map<String, dynamic>? meta;

  const ApiResponse({
    required this.success,
    this.data,
    this.messageAr,
    this.messageEn,
    this.meta,
  });

  /// Returns the appropriate message based on the current locale.
  ///
  /// Defaults to Arabic if locale is 'ar', otherwise English.
  /// Falls back to whichever message is available if the preferred one is null.
  String? localizedMessage(String locale) {
    if (locale == 'ar') {
      return messageAr ?? messageEn;
    }
    return messageEn ?? messageAr;
  }

  /// Convenience getter: returns Arabic message.
  String? get message => messageAr ?? messageEn;

  /// Whether the response contains data.
  bool get hasData => data != null;

  /// Whether the response contains metadata.
  bool get hasMeta => meta != null && meta!.isNotEmpty;

  /// Extract pagination total from meta.
  int? get total => (meta?['total'] as num?)?.toInt();

  /// Extract current page from meta.
  int? get page => (meta?['page'] as num?)?.toInt();

  /// Extract page size limit from meta.
  int? get limit => (meta?['limit'] as num?)?.toInt();

  /// Whether there are more pages available.
  bool get hasMore {
    if (total == null || page == null || limit == null) return false;
    return (page! * limit!) < total!;
  }

  /// Factory constructor to parse the raw JSON response from the API.
  ///
  /// [json] is the decoded response body.
  /// [fromJsonT] is an optional function that converts the `data` field
  /// into the desired type [T]. If not provided, [data] will be null
  /// (useful for void/fire-and-forget calls).
  factory ApiResponse.fromJson(
    Map<String, dynamic> json, {
    T Function(Map<String, dynamic>)? fromJsonT,
  }) {
    T? parsedData;

    if (fromJsonT != null && json['data'] != null) {
      if (json['data'] is Map<String, dynamic>) {
        parsedData = fromJsonT(json['data'] as Map<String, dynamic>);
      }
    }

    // Backend error responses from ErrorHandler nest messages in `error.message`
    // while moduleHandler business-rule failures use top-level `message_ar`/`message_en`.
    // Extract from both locations.
    final errorObj = json['error'] is Map<String, dynamic>
        ? json['error'] as Map<String, dynamic>
        : null;

    return ApiResponse<T>(
      success: json['success'] as bool? ?? false,
      data: parsedData,
      messageAr: json['message_ar'] as String?
          ?? errorObj?['message_ar'] as String?
          ?? errorObj?['message'] as String?,
      messageEn: json['message_en'] as String?
          ?? errorObj?['message_en'] as String?
          ?? errorObj?['message'] as String?,
      meta: json['meta'] as Map<String, dynamic>?,
    );
  }

  /// Factory constructor for parsing responses where data is a list.
  ///
  /// Usage:
  /// ```dart
  /// final response = ApiResponse.fromJsonList<UserModel>(
  ///   json,
  ///   fromJsonT: (item) => UserModel.fromJson(item),
  /// );
  /// final users = response.data; // List<UserModel>
  /// ```
  static ApiResponse<List<T>> fromJsonList<T>(
    Map<String, dynamic> json, {
    required T Function(Map<String, dynamic>) fromJsonT,
  }) {
    List<T>? parsedData;

    if (json['data'] != null && json['data'] is List) {
      parsedData = (json['data'] as List)
          .whereType<Map<String, dynamic>>()
          .map((item) => fromJsonT(item))
          .toList();
    }

    final errorObj = json['error'] is Map<String, dynamic>
        ? json['error'] as Map<String, dynamic>
        : null;

    return ApiResponse<List<T>>(
      success: json['success'] as bool? ?? false,
      data: parsedData,
      messageAr: json['message_ar'] as String?
          ?? errorObj?['message_ar'] as String?
          ?? errorObj?['message'] as String?,
      messageEn: json['message_en'] as String?
          ?? errorObj?['message_en'] as String?
          ?? errorObj?['message'] as String?,
      meta: json['meta'] as Map<String, dynamic>?,
    );
  }

  /// Factory constructor for responses with raw/untyped data.
  ///
  /// Useful when you just need the raw Map without parsing into a model.
  static ApiResponse<Map<String, dynamic>> fromJsonRaw(
    Map<String, dynamic> json,
  ) {
    final errorObj = json['error'] is Map<String, dynamic>
        ? json['error'] as Map<String, dynamic>
        : null;

    // Handle data that can be either a Map or a List.
    // When the SQL function returns a List as data, wrap it so
    // callers can access it via data!['items'] or data!['data'].
    Map<String, dynamic>? parsedData;
    if (json['data'] is Map<String, dynamic>) {
      parsedData = json['data'] as Map<String, dynamic>;
    } else if (json['data'] is List) {
      parsedData = {'items': json['data'], 'data': json['data']};
    }

    return ApiResponse<Map<String, dynamic>>(
      success: json['success'] as bool? ?? false,
      data: parsedData,
      messageAr: json['message_ar'] as String?
          ?? errorObj?['message_ar'] as String?
          ?? errorObj?['message'] as String?,
      messageEn: json['message_en'] as String?
          ?? errorObj?['message_en'] as String?
          ?? errorObj?['message'] as String?,
      meta: json['meta'] as Map<String, dynamic>?,
    );
  }

  /// Create a success response (useful for testing/mocking).
  factory ApiResponse.success({
    T? data,
    String? messageAr,
    String? messageEn,
    Map<String, dynamic>? meta,
  }) {
    return ApiResponse<T>(
      success: true,
      data: data,
      messageAr: messageAr,
      messageEn: messageEn,
      meta: meta,
    );
  }

  /// Create a failure response (useful for testing/mocking).
  factory ApiResponse.failure({
    String? messageAr,
    String? messageEn,
    Map<String, dynamic>? meta,
  }) {
    return ApiResponse<T>(
      success: false,
      data: null,
      messageAr: messageAr,
      messageEn: messageEn,
      meta: meta,
    );
  }

  @override
  String toString() {
    return 'ApiResponse(success: $success, data: $data, '
        'messageAr: $messageAr, messageEn: $messageEn, meta: $meta)';
  }
}
