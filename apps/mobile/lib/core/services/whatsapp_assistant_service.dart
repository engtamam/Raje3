import 'package:dio/dio.dart';

import 'package:raje3_mobile/core/network/api_client.dart';

/// «المساعد الذكي عبر واتساب» — mirrors `services/operations/app/api/v1/staff.py`'s own
/// `/ai-toggle`, `/ai-notes`, `/msg-word-limit`, `/whatsapp-auto-register` routes exactly, the
/// SAME four real doors the console's own `AccountPanes.tsx` cards already call (zero backend
/// work for this mobile build). The receipt numbers `WhatsAppAssistant.tsx` shows alongside them
/// (conversations, AI bookings, wallet credit remaining) are deliberately NOT mirrored here — the
/// owner's own call, 2026-09-24: Meta now runs the AI directly, so a manually-metered usage
/// number is a stale concept this screen has no business resurrecting.
///
/// `ai_notes`/`msg_word_limit` can come back 404 on a deployment with that feature flag off
/// (console's own comment: "absent from the catalog entirely") — read as `null`, same posture as
/// every other optional read in this service, never a crash.
class WhatsappAssistantService {
  WhatsappAssistantService({required this.apiClient});
  final ApiClient apiClient;

  Future<bool?> fetchAiEnabled() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/ai-toggle');
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? body['enabled'] != false : null;
    } on DioException {
      return null;
    }
  }

  Future<bool> setAiEnabled(bool enabled) async {
    try {
      final response = await apiClient.dio
          .put<dynamic>('/api/v1/staff/ai-toggle', data: {'enabled': enabled});
      return response.statusCode == 200;
    } on DioException {
      return false;
    }
  }

  Future<String?> fetchAiNotes() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/ai-notes');
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? (body['text'] as String? ?? '') : null;
    } on DioException {
      return null;
    }
  }

  /// Returns the saved text on success, or null on refusal (e.g. over the character cap, which
  /// the server enforces regardless of whatever this screen also checks client-side).
  Future<String?> saveAiNotes(String text) async {
    try {
      final response =
          await apiClient.dio.put<dynamic>('/api/v1/staff/ai-notes', data: {'text': text});
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? (body['text'] as String? ?? text) : text;
    } on DioException {
      return null;
    }
  }

  Future<int?> fetchWordLimit() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/msg-word-limit');
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? (body['limit'] as num?)?.toInt() : null;
    } on DioException {
      return null;
    }
  }

  Future<int?> saveWordLimit(int limit) async {
    try {
      final response = await apiClient.dio
          .put<dynamic>('/api/v1/staff/msg-word-limit', data: {'limit': limit});
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? (body['limit'] as num?)?.toInt() ?? limit : limit;
    } on DioException {
      return null;
    }
  }

  Future<bool?> fetchAutoRegister() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/whatsapp-auto-register');
      if (response.statusCode != 200) return null;
      final body = response.data;
      return body is Map ? body['enabled'] == true : null;
    } on DioException {
      return null;
    }
  }

  Future<bool> setAutoRegister(bool enabled) async {
    try {
      final response = await apiClient.dio.put<dynamic>(
          '/api/v1/staff/whatsapp-auto-register', data: {'enabled': enabled});
      return response.statusCode == 200;
    } on DioException {
      return false;
    }
  }
}
