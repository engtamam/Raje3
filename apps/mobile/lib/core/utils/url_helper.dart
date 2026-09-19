// Helpers for launching external URLs, phone, SMS, email, and WhatsApp.
// Also includes a template variable resolver used by the marketing module.

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// Open a URL in the device's default browser.
///
/// Returns true if the URL was opened successfully, false otherwise.
/// Shows a SnackBar on failure if a [BuildContext] is provided.
Future<bool> openUrl(String? url, [BuildContext? context]) async {
  if (url == null || url.isEmpty) {
    if (context != null && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('الرابط غير متوفر')),
      );
    }
    return false;
  }

  final uri = Uri.tryParse(url);
  if (uri == null) return false;

  try {
    return await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    if (context != null && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تعذر فتح الرابط')),
      );
    }
    return false;
  }
}

/// Open WhatsApp with a pre-filled message.
///
/// URL format: `https://wa.me/+966XXXXXXXXX` (no message)
///          or `https://wa.me/+966XXXXXXXXX?text=Hello` (with message)
Future<bool> openWhatsApp(String phone, [String? message]) async {
  final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
  final uri = Uri.https('wa.me', '/$cleanPhone', {
    if (message != null) 'text': message,
  });
  return openUrl(uri.toString());
}

/// Open the phone dialer with a pre-filled number.
Future<bool> openPhoneDialer(String phone) async {
  final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
  final uri = Uri(scheme: 'tel', path: cleanPhone);
  try {
    return await launchUrl(uri);
  } catch (_) {
    return false;
  }
}

/// Open the SMS app with a pre-filled number and optional message.
Future<bool> openSms(String phone, [String? message]) async {
  final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
  final uri = Uri(
    scheme: 'sms',
    path: cleanPhone,
    queryParameters: message != null ? {'body': message} : null,
  );
  try {
    return await launchUrl(uri);
  } catch (_) {
    return false;
  }
}

/// Open the email client with a pre-filled address and optional subject/body.
Future<bool> openEmail(String email, {String? subject, String? body}) async {
  final uri = Uri(
    scheme: 'mailto',
    path: email,
    queryParameters: {
      if (subject != null) 'subject': subject,
      if (body != null) 'body': body,
    },
  );
  try {
    return await launchUrl(uri);
  } catch (_) {
    return false;
  }
}

/// Resolve a template body by replacing `{{variable_name}}` placeholders
/// with values from [variables].
///
/// Mirrors the SQL `marketing_business_template_preview` logic:
/// `REPLACE(body, '{{' || var_name || '}}', value)`
String resolveTemplate(String template, Map<String, String> variables) {
  var result = template;
  for (final entry in variables.entries) {
    result = result.replaceAll('{{${entry.key}}}', entry.value);
  }
  return result;
}
