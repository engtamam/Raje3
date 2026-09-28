import 'package:flutter/material.dart';

import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// The WhatsApp Flow preview ENGINE — ported from the console's own `WaFlowScreens`
/// (`rj-ui/WhatsAppPreview.tsx`). Renders THE REAL FLOW JSON — the exact document `flow_json.py`
/// generates and Meta itself parses — so any Flow this product registers previews correctly the
/// moment it exists, with zero new preview code per Flow.
///
/// SCOPE, ON PURPOSE, same as the console's own: a PREVIEW, not a second implementation of the
/// Flow protocol — no RSA/AES envelope, no session id, no server round trip per screen
/// (`routing_model` is walked locally to simulate `data_exchange`). What renders is pixel-real;
/// what happens when you tap through it is a faithful walkthrough, never a live booking.
///
/// COVERS THE SAME COMPONENT VOCABULARY the console's own engine does: TextHeading, TextSubheading,
/// TextBody, TextCaption, RadioButtonsGroup, CheckboxGroup, TextInput, TextArea, Footer. An unknown
/// component type renders nothing rather than breaking the screen.
class WaFlowScreens extends StatefulWidget {
  const WaFlowScreens({super.key, required this.flow, required this.onDone});
  final FlowJson flow;
  final VoidCallback onDone;

  @override
  State<WaFlowScreens> createState() => _WaFlowScreensState();
}

class _WaFlowScreensState extends State<WaFlowScreens> {
  late String _screenId;

  @override
  void initState() {
    super.initState();
    _screenId = widget.flow.screens.isNotEmpty ? widget.flow.screens.first.id : '';
  }

  FlowScreen? get _screen => widget.flow.screens.where((s) => s.id == _screenId).firstOrNull;

  void _advance() {
    final next = (widget.flow.routingModel[_screenId] ?? const []).firstOrNull;
    if (next != null) {
      setState(() => _screenId = next);
    } else {
      widget.onDone();
    }
  }

  @override
  Widget build(BuildContext context) {
    final screen = _screen;
    if (screen == null) return const SizedBox.shrink();
    return _FlowScreenCard(screen: screen, onAdvance: _advance, onComplete: widget.onDone);
  }
}

class _FlowScreenCard extends StatefulWidget {
  const _FlowScreenCard({required this.screen, required this.onAdvance, required this.onComplete});
  final FlowScreen screen;
  final VoidCallback onAdvance;
  final VoidCallback onComplete;

  @override
  State<_FlowScreenCard> createState() => _FlowScreenCardState();
}

class _FlowScreenCardState extends State<_FlowScreenCard> {
  final Map<String, dynamic> _values = {};

  void _change(String name, dynamic value) => setState(() => _values[name] = value);

  FlowComponent? get _footer =>
      widget.screen.children.where((c) => c.type == 'Footer').firstOrNull ??
      widget.screen.children.expand((c) => c.children).where((c) => c.type == 'Footer').firstOrNull;

  @override
  Widget build(BuildContext context) {
    final footer = _footer;
    return Container(
      width: 300,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppRadius.cardRadius,
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.screen.title != null)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Text(widget.screen.title!.toUpperCase(),
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF667781), letterSpacing: 0.5)),
            ),
          for (final c in widget.screen.children)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: _FlowComponentView(node: c, values: _values, onChange: _change),
            ),
          if (footer != null)
            SizedBox(
              width: double.infinity,
              child: KbAnchor(
                id: 'campaigns.wa_flow_preview.footer_button',
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: const Color(0xFF25D366)),
                  onPressed: () => widget.screen.terminal ? widget.onComplete() : widget.onAdvance(),
                  child: Text(footer.label ?? ''),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _FlowComponentView extends StatelessWidget {
  const _FlowComponentView({required this.node, required this.values, required this.onChange});
  final FlowComponent node;
  final Map<String, dynamic> values;
  final void Function(String name, dynamic value) onChange;

  @override
  Widget build(BuildContext context) {
    switch (node.type) {
      case 'Form':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final c in node.children)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: _FlowComponentView(node: c, values: values, onChange: onChange),
              ),
          ],
        );
      case 'TextHeading':
        return Text(node.text ?? '', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF111B21)));
      case 'TextSubheading':
        return Text(node.text ?? '', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF111B21)));
      case 'TextBody':
        return Text(node.text ?? '', style: const TextStyle(fontSize: 13, color: Color(0xFF3B4A54), height: 1.4));
      case 'TextCaption':
      case 'RichText':
        return Text(node.text ?? '', style: const TextStyle(fontSize: 12, color: Color(0xFF667781), height: 1.4));
      case 'Image':
        return Container(
          height: 96, width: double.infinity,
          decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.05), borderRadius: BorderRadius.circular(8)),
          child: const Icon(Icons.image_outlined, color: Color(0xFF667781)),
        );
      case 'RadioButtonsGroup':
      case 'Dropdown': {
        final name = node.name ?? 'selection';
        final current = values[name] as String?;
        return _OptionGroup(
          label: node.label,
          options: node.dataSource,
          multi: false,
          selected: current != null ? {current} : {},
          onToggle: (id) => onChange(name, id),
        );
      }
      case 'CheckboxGroup': {
        final name = node.name ?? 'selection';
        final current = (values[name] as List?)?.cast<String>().toSet() ?? <String>{};
        return _OptionGroup(
          label: node.label,
          options: node.dataSource,
          multi: true,
          selected: current,
          onToggle: (id) {
            final next = {...current};
            next.contains(id) ? next.remove(id) : next.add(id);
            onChange(name, next.toList());
          },
        );
      }
      case 'TextInput':
      case 'TextArea':
        return _FlowTextField(
          label: node.label,
          multiline: node.type == 'TextArea',
          maxLength: node.maxLength,
          onChanged: (v) => onChange(node.name ?? 'input_value', v),
        );
      case 'OptIn': {
        final name = node.name ?? 'opt_in';
        final current = values[name] == true;
        return InkWell(
          onTap: () => onChange(name, !current),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Checkbox(value: current, onChanged: (v) => onChange(name, v ?? false), activeColor: const Color(0xFF25D366)),
            Expanded(child: Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(node.label ?? '', style: const TextStyle(fontSize: 13, color: Color(0xFF111B21))),
            )),
          ]),
        );
      }
      case 'CalendarPicker':
        return _FlowDateField(label: node.label, onPicked: (d) => onChange(node.name ?? 'date', d));
      case 'Footer':
        return const SizedBox.shrink();
      default:
        return const SizedBox.shrink();
    }
  }
}

class _OptionGroup extends StatelessWidget {
  const _OptionGroup({required this.label, required this.options, required this.multi, required this.selected, required this.onToggle});
  final String? label;
  final List<Map<String, dynamic>> options;
  final bool multi;
  final Set<String> selected;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(label!, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF3B4A54))),
        ),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.black.withValues(alpha: 0.1)),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (int i = 0; i < options.length; i++)
                InkWell(
                  onTap: () => onToggle(options[i]['id'].toString()),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                    decoration: BoxDecoration(
                      border: i > 0 ? const Border(top: BorderSide(color: Color(0x11000000))) : null,
                    ),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Icon(
                        multi
                            ? (selected.contains(options[i]['id'].toString()) ? Icons.check_box : Icons.check_box_outline_blank)
                            : (selected.contains(options[i]['id'].toString()) ? Icons.radio_button_checked : Icons.radio_button_off),
                        size: 18, color: const Color(0xFF25D366),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${options[i]['title'] ?? ''}', style: const TextStyle(fontSize: 13, color: Color(0xFF111B21))),
                          if (options[i]['description'] != null)
                            Text('${options[i]['description']}', style: const TextStyle(fontSize: 11, color: Color(0xFF667781))),
                        ]),
                      ),
                    ]),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _FlowTextField extends StatelessWidget {
  const _FlowTextField({required this.label, required this.multiline, required this.maxLength, required this.onChanged});
  final String? label;
  final bool multiline;
  final int? maxLength;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(label!, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF3B4A54))),
        ),
        KbAnchor(
          id: 'campaigns.wa_flow_preview.text_field',
          child: TextField(
            maxLines: multiline ? 3 : 1,
            maxLength: maxLength,
            onChanged: onChanged,
            style: const TextStyle(fontSize: 13, color: Color(0xFF111B21)),
            decoration: InputDecoration(
              isDense: true,
              filled: true,
              fillColor: Colors.white,
              counterText: '',
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: Colors.black.withValues(alpha: 0.1))),
            ),
          ),
        ),
      ],
    );
  }
}

class _FlowDateField extends StatefulWidget {
  const _FlowDateField({required this.label, required this.onPicked});
  final String? label;
  final ValueChanged<String> onPicked;

  @override
  State<_FlowDateField> createState() => _FlowDateFieldState();
}

class _FlowDateFieldState extends State<_FlowDateField> {
  DateTime? _picked;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (widget.label != null) Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(widget.label!, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF3B4A54))),
        ),
        SecondaryButton(
          text: _picked == null
              ? ct(context, 'pickEndDate')
              : '${_picked!.year}-${_picked!.month.toString().padLeft(2, '0')}-${_picked!.day.toString().padLeft(2, '0')}',
          icon: Icons.calendar_today_outlined,
          onPressed: () async {
            final d = await showDatePicker(
              context: context, initialDate: DateTime.now(),
              firstDate: DateTime.now(), lastDate: DateTime.now().add(const Duration(days: 365)),
            );
            if (d != null) {
              setState(() => _picked = d);
              widget.onPicked('${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}');
            }
          },
        ),
      ],
    );
  }
}
