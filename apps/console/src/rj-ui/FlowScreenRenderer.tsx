// A visual MOCK of one WhatsApp Flow JSON screen — same registry pattern as BlockRenderer.tsx
// (packages/ui): one renderer per component `type`, an unknown type degrades to nothing rather
// than crashing (a schema version bump on Meta's side introduces a component this file has not
// learned yet). This is NOT Meta's own Flow renderer — WhatsApp itself is the only place a Flow
// truly runs — it is an approximation so a shop owner can see roughly what each screen looks like
// before buying the app that sends it, the same "let him try before he buys" reasoning behind
// every other locked-preview surface in this console.
//
// RESOLVING ${data.x} — a screen's `layout.children` reference the screen's own `data` schema by
// placeholder (`"${data.title}"`), which is exactly what the live endpoint fills in per-request.
// Preview has no live request to answer with, so it substitutes each field's own `__example__`
// value from the SAME Flow JSON — the same example the schema itself carries for Meta's own
// upload-time validation, not values invented here.
import type { ReactNode } from 'react';

export interface FlowScreen {
  id: string;
  title: string;
  terminal?: boolean;
  data: Record<string, { __example__?: unknown; type?: string; optional?: boolean }>;
  layout: { type: string; children: FlowComponent[] };
}
export interface FlowComponent {
  type: string;
  [key: string]: unknown;
}
export interface FlowJson {
  version: string;
  data_api_version: string;
  screens: FlowScreen[];
  routing_model?: Record<string, string[]>;
}

/** "${data.title}" → the screen's data.title.__example__, resolved recursively for arrays/objects
 *  (a RadioButtonsGroup's `data-source` is itself "${data.options}", an array of {id, title}). Any
 *  string without the `${data.…}` shape passes through unchanged (a literal label). */
function resolve(value: unknown, data: FlowScreen['data']): unknown {
  if (typeof value === 'string') {
    const m = /^\$\{data\.([a-zA-Z0-9_]+)\}$/.exec(value);
    if (m) return data[m[1]]?.__example__ ?? '';
    return value;
  }
  return value;
}

type Renderer = (c: FlowComponent, data: FlowScreen['data']) => ReactNode;

const RENDERERS: Record<string, Renderer> = {
  TextHeading: (c, data) => (
    <h3 className="text-base font-semibold text-text-primary">{String(resolve(c.text, data))}</h3>
  ),

  TextBody: (c, data) => (
    <p className="text-sm text-text-secondary">{String(resolve(c.text, data))}</p>
  ),

  TextInput: (c, data) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-text-secondary">{String(resolve(c.label, data))}</label>
      <div className="rounded-input border border-border-subtle bg-surface-0 px-3 py-2 text-sm text-text-muted">
        {String(resolve(c.label, data))}
      </div>
    </div>
  ),

  RadioButtonsGroup: (c, data) => {
    const options = resolve(c['data-source'], data);
    const rows = Array.isArray(options) ? options : [];
    return (
      <div className="flex flex-col gap-2">
        {rows.map((opt, i) => {
          const o = opt as { id?: string; title?: string };
          return (
            <div key={o.id ?? i}
                className="flex items-center gap-2 rounded-input border border-border-subtle bg-surface-0 px-3 py-2 text-sm">
              <span aria-hidden className="grid h-4 w-4 shrink-0 place-items-center rounded-full border border-border-strong">
                {i === 0 ? <span className="h-2 w-2 rounded-full bg-accent" /> : null}
              </span>
              {o.title ?? String(o.id ?? '')}
            </div>
          );
        })}
      </div>
    );
  },

  CheckboxGroup: (c, data) => {
    const options = resolve(c['data-source'], data);
    const rows = Array.isArray(options) ? options : [];
    return (
      <div className="flex flex-col gap-2">
        {rows.map((opt, i) => {
          const o = opt as { id?: string; title?: string };
          return (
            <div key={o.id ?? i}
                className="flex items-center gap-2 rounded-input border border-border-subtle bg-surface-0 px-3 py-2 text-sm">
              <span aria-hidden className="grid h-4 w-4 shrink-0 place-items-center rounded-[4px] border border-border-strong">
                {i === 0 ? <span className="h-2 w-2 rounded-[1px] bg-accent" /> : null}
              </span>
              {o.title ?? String(o.id ?? '')}
            </div>
          );
        })}
      </div>
    );
  },

  CalendarPicker: () => (
    <div className="rounded-input border border-border-subtle bg-surface-0 p-3 text-center text-sm text-text-muted">
      📅 تقويم لاختيار التاريخ
    </div>
  ),

  Footer: (c, data) => (
    <button type="button" disabled
           className="w-full rounded-input bg-accent px-4 py-2.5 text-center text-sm font-semibold text-accent-contrast opacity-90">
      {String(resolve(c.label, data))}
    </button>
  ),
};

/** Render one Flow JSON screen. Unknown component types render nothing (forward-compatible with a
 *  Meta schema bump this file has not learned yet — same posture BlockView already holds). */
export function FlowScreenView({ screen }: { screen: FlowScreen }): ReactNode {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-bold text-text-primary">{screen.title}</h2>
      {screen.layout.children.map((c, i) => {
        const R = RENDERERS[c.type];
        return R ? <div key={i}>{R(c, screen.data)}</div> : null;
      })}
    </div>
  );
}

/** Every component `type` this client currently knows how to render — same "let a future block
 *  kind degrade to nothing rather than crash" contract `KNOWN_BLOCK_TYPES` already documents. */
export const KNOWN_FLOW_COMPONENT_TYPES = Object.keys(RENDERERS);
