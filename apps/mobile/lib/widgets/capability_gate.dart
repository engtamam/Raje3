import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Wraps any control that fires a capability-gated backend action — hides [child] entirely when
/// the signed-in operator's own catalogue does not hold every id in [requires].
///
/// THE CATALOGUE, NOT A ROLE CHECK. `NavProvider.catalog` (see catalog_model.dart's own doc
/// comment) mirrors apps/console/src/catalog.ts's `Catalog` exactly — the gateway has ALREADY
/// filtered it by capability before this app ever sees it, so an action this operator may not
/// use is simply absent, never present-but-disabled. `hasAll` is the one and only question this
/// widget asks; it never invents a decision the backend didn't already make.
///
/// THE SAME IDIOM THE CONSOLE ALREADY USES, JUST REUSABLE. `Services.tsx` and its peers already
/// gate every write button with `action(catalog, id) ? <Btn/> : null`, repeated inline at each
/// call site — this widget is that same check, wrapped once so a Flutter screen composes it
/// (`CapabilityGate(requires: [...], child: ...)`) instead of an `if` before every control.
///
/// SCREEN-LEVEL GATING (a whole tab/section's own `requires`, e.g. `nav_sections.g.dart`) is a
/// SEPARATE, coarser question this widget does not replace — see NavProvider's own
/// `visibleSections` for that. This widget is for the finer one: one button, one action, inside
/// a screen the operator can already open.
class CapabilityGate extends StatelessWidget {
  const CapabilityGate({super.key, required this.requires, required this.child, this.catalog});

  /// One or more catalogue action ids — ALL must be present for [child] to render (same
  /// all-or-nothing contract as `Catalog.hasAll`/`catalog.ts::hasAll`).
  final List<String> requires;
  final Widget child;

  /// Overrides the catalogue this gate checks against, instead of reading `NavProvider` from
  /// [context] — real screens never pass this (they sit inside the app's own `NavProvider`,
  /// same as every existing `context.watch<NavProvider>().catalog.hasAll(...)` call site); it
  /// exists so a widget test can check both branches directly, with no `NavProvider`/`ApiClient`
  /// scaffolding in the tree at all.
  final Catalog? catalog;

  @override
  Widget build(BuildContext context) {
    final effective = catalog ?? context.watch<NavProvider>().catalog;
    if (!effective.hasAll(requires)) return const SizedBox.shrink();
    return child;
  }
}
