import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

/// The marker `return_url` we send TuwaiqPay with every pay-link — a real host we control, never
/// clicked or resolved by the customer. Console's own BillingStatusPane.tsx passes
/// `window.location.href` for the same reason (TuwaiqPay redirects the browser back here once
/// payment finishes); the app has no open page to return to, so it navigates back to a fixed,
/// recognisable marker this screen's own NavigationDelegate watches for instead.
const String paymentReturnMarker = 'https://raje3.app/mobile-payment-return';

/// Opens a TuwaiqPay hosted checkout page INSIDE the app (owner's own instruction, 2026-09-23:
/// never feel like leaving to something external) and pops itself the instant the page redirects
/// to [paymentReturnMarker] — the owner never has to notice they left the app, tap a "done"
/// button, or manually come back; the screen closes itself. Returns once the WebView is closed
/// (either by that auto-detect, or the owner's own back/close tap) — the caller always reloads
/// its own due-invoice list after, since the real outcome is confirmed by the server's webhook
/// independently of this screen either way.
Future<void> openPaymentInApp(BuildContext context, String checkoutUrl) {
  // `https` ONLY — a payment page is never loaded over a scheme that could be intercepted or
  // downgraded. The server is the one authority on this URL, but a client that trusted whatever
  // scheme it was handed would still be the one place a tampered or malformed link got acted on.
  final scheme = Uri.tryParse(checkoutUrl)?.scheme;
  if (scheme != 'https') return Future<void>.value();
  if (kIsWeb) {
    // webview_flutter has no web engine — Flutter web already runs inside a browser tab, so a
    // plain external navigation is the closest equivalent and never a broken embed.
    return openUrl(checkoutUrl, context);
  }
  return Navigator.of(context).push(MaterialPageRoute<void>(
    builder: (_) => PaymentWebViewScreen(checkoutUrl: checkoutUrl),
  ));
}

class PaymentWebViewScreen extends StatefulWidget {
  const PaymentWebViewScreen({super.key, required this.checkoutUrl});
  final String checkoutUrl;

  @override
  State<PaymentWebViewScreen> createState() => _PaymentWebViewScreenState();
}

class _PaymentWebViewScreenState extends State<PaymentWebViewScreen> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _failed = false;

  void _startLoad() {
    setState(() {
      _loading = true;
      _failed = false;
    });
    _controller.loadRequest(Uri.parse(widget.checkoutUrl));
  }

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(NavigationDelegate(
        // `onNavigationRequest`, not `onPageStarted` — intercepted BEFORE the WebView ever
        // dispatches the request, so the placeholder marker domain (never a real page) is never
        // actually fetched at all, the documented pattern for a payment-redirect watch.
        onNavigationRequest: (request) {
          if (request.url.startsWith(paymentReturnMarker)) {
            if (Navigator.of(context).canPop()) Navigator.of(context).pop();
            return NavigationDecision.prevent;
          }
          return NavigationDecision.navigate;
        },
        onPageStarted: (_) { if (mounted) setState(() { _loading = true; _failed = false; }); },
        onPageFinished: (_) { if (mounted) setState(() => _loading = false); },
        // A dropped connection or a gateway outage while the checkout page itself is loading — as
        // opposed to a decline or a 3DS refusal, which the gateway's OWN page renders and this
        // delegate never sees. `isForMainFrame` so one failed tracking-pixel sub-resource on an
        // otherwise-working checkout page never blanks the whole screen.
        onWebResourceError: (error) {
          if (mounted && error.isForMainFrame != false) {
            setState(() { _loading = false; _failed = true; });
          }
        },
      ))
      ..loadRequest(Uri.parse(widget.checkoutUrl));
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.billingPayNow),
        leading: IconButton(icon: const Icon(Icons.close_rounded), onPressed: () => Navigator.of(context).pop()),
      ),
      body: _failed
          ? _LoadFailedState(message: s.paymentPageLoadFailed, retryLabel: s.retry, onRetry: _startLoad)
          : Stack(
              children: [
                WebViewWidget(controller: _controller),
                if (_loading) const Center(child: AppLoadingIndicator()),
              ],
            ),
    );
  }
}

class _LoadFailedState extends StatelessWidget {
  const _LoadFailedState({required this.message, required this.retryLabel, required this.onRetry});
  final String message;
  final String retryLabel;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded, size: 40),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(onPressed: onRetry, child: Text(retryLabel)),
          ],
        ),
      ),
    );
  }
}
