import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/knowledge/kb_service.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// The mobile "؟" — the exact same job as the console's `Hint`/`AssistantHint`, on the exact same
/// data ([KbService], no network): tap opens the explanation for [anchor] inline, tap again
/// closes it. Missing entry reads as a quiet "ما فيه شرح لهذا بعد", never an error — a KB entry
/// not yet authored is expected, not broken.
class KbHintButton extends StatefulWidget {
  final String anchor;
  const KbHintButton({super.key, required this.anchor});

  @override
  State<KbHintButton> createState() => _KbHintButtonState();
}

class _KbHintButtonState extends State<KbHintButton> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final kb = context.read<KbService>();
    final catalog = context.watch<NavProvider>().catalog;
    final entry = kb.byAnchor(widget.anchor, catalog);
    final lang = Localizations.localeOf(context).languageCode;

    return Wrap(
      children: [
        SizedBox(
          width: 44,
          height: 44,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: () => setState(() => _open = !_open),
              child: Center(
                child: Container(
                  width: 24,
                  height: 24,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(shape: BoxShape.circle, color: AppColors.surface2),
                  child: const Text('؟', style: AppTextStyles.caption),
                ),
              ),
            ),
          ),
        ),
        if (_open)
          SizedBox(
            width: double.infinity,
            child: Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: entry == null
                  ? Text(s.kbHintNoEntry, style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted))
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(entry.text(lang).$2, style: AppTextStyles.bodySmall),
                        if (entry.cta != null)
                          TextButton(
                            onPressed: () => context.push(entry.cta!.route),
                            child: Text(entry.cta!.label),
                          ),
                      ],
                    ),
            ),
          ),
      ],
    );
  }
}
