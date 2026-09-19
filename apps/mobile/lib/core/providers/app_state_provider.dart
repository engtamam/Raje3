import 'package:flutter/foundation.dart';

/// Provider that manages global transient app state.
///
/// Holds cross-cutting state that multiple widgets need access to
/// but that does not require persistence (resets on app restart).
///
/// Includes:
/// - Bottom navigation tab index
/// - Network connectivity status
/// - Unread notification count (for badge)
/// - Cart item count (for badge)
///
/// Setup:
/// ```dart
/// ChangeNotifierProvider(
///   create: (_) => AppStateProvider(),
/// )
/// ```
///
/// Usage:
/// ```dart
/// final appState = context.watch<AppStateProvider>();
///
/// // Bottom nav
/// BottomNavigationBar(
///   currentIndex: appState.currentTabIndex,
///   onTap: (index) => appState.currentTabIndex = index,
/// );
///
/// // Notification badge
/// Badge(
///   isLabelVisible: appState.unreadNotifications > 0,
///   label: Text('${appState.unreadNotifications}'),
///   child: Icon(Icons.notifications),
/// );
/// ```
class AppStateProvider extends ChangeNotifier {
  int _currentTabIndex = 0;
  bool _isOnline = true;
  int _unreadNotifications = 0;
  int _unreadBusinessNotifications = 0;
  int _cartItemCount = 0;

  // ─────────────────────────────────────────────────────────────────────────
  // BOTTOM NAVIGATION
  // ─────────────────────────────────────────────────────────────────────────

  /// The currently selected bottom navigation tab index.
  int get currentTabIndex => _currentTabIndex;

  /// Set the active bottom navigation tab.
  ///
  /// Notifies listeners so the bottom nav bar and associated
  /// page content update together.
  set currentTabIndex(int index) {
    if (_currentTabIndex != index) {
      _currentTabIndex = index;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CONNECTIVITY
  // ─────────────────────────────────────────────────────────────────────────

  /// Whether the device currently has network connectivity.
  bool get isOnline => _isOnline;

  /// Whether the device is offline.
  bool get isOffline => !_isOnline;

  /// Update the connectivity status.
  ///
  /// Typically called by a connectivity listener set up in main.dart.
  set isOnline(bool value) {
    if (_isOnline != value) {
      _isOnline = value;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // NOTIFICATION BADGE
  // ─────────────────────────────────────────────────────────────────────────

  /// Number of unread personal notifications.
  int get unreadNotifications => _unreadNotifications;

  /// Number of unread business notifications.
  int get unreadBusinessNotifications => _unreadBusinessNotifications;

  /// Whether there are any unread personal notifications.
  bool get hasUnreadNotifications => _unreadNotifications > 0;

  /// Whether there are any unread business notifications.
  bool get hasUnreadBusinessNotifications => _unreadBusinessNotifications > 0;

  /// Update the unread personal notification count.
  set unreadNotifications(int count) {
    if (_unreadNotifications != count) {
      _unreadNotifications = count;
      notifyListeners();
    }
  }

  /// Update the unread business notification count.
  set unreadBusinessNotifications(int count) {
    if (_unreadBusinessNotifications != count) {
      _unreadBusinessNotifications = count;
      notifyListeners();
    }
  }

  /// Increment the personal unread count by one (e.g., when a push arrives).
  void incrementNotifications() {
    _unreadNotifications++;
    notifyListeners();
  }

  /// Decrement the personal unread count by one (e.g., when user reads one).
  void decrementNotifications() {
    if (_unreadNotifications > 0) {
      _unreadNotifications--;
      notifyListeners();
    }
  }

  /// Decrement the business unread count by one.
  void decrementBusinessNotifications() {
    if (_unreadBusinessNotifications > 0) {
      _unreadBusinessNotifications--;
      notifyListeners();
    }
  }

  /// Reset the personal unread count to zero.
  void clearNotificationBadge() {
    if (_unreadNotifications != 0) {
      _unreadNotifications = 0;
      notifyListeners();
    }
  }

  /// Reset the business unread count to zero.
  void clearBusinessNotificationBadge() {
    if (_unreadBusinessNotifications != 0) {
      _unreadBusinessNotifications = 0;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CART BADGE
  // ─────────────────────────────────────────────────────────────────────────

  /// Number of items in the shopping cart.
  int get cartItemCount => _cartItemCount;

  /// Whether the cart has any items.
  bool get hasCartItems => _cartItemCount > 0;

  /// Update the cart item count.
  set cartItemCount(int count) {
    if (_cartItemCount != count) {
      _cartItemCount = count;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RESET
  // ─────────────────────────────────────────────────────────────────────────

  /// Reset all transient state to defaults.
  ///
  /// Called on logout to clean up state.
  void reset() {
    _currentTabIndex = 0;
    _isOnline = true;
    _unreadNotifications = 0;
    _unreadBusinessNotifications = 0;
    _cartItemCount = 0;
    notifyListeners();
  }
}
