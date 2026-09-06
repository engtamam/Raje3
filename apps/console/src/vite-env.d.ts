/// <reference types="vite/client" />

/** The one setting this app reads from its environment: where the API is. Declared so a typo in
 *  the name is a compile error rather than an `undefined` that silently becomes a relative URL. */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** Meta's Embedded Signup configuration id. Configuration, never a constant: it differs between
   *  our test app and the live one, and a literal would need a rebuild to change. */
  readonly VITE_META_CONFIG_ID?: string;
  /** Meta's app id. Its ABSENCE is the switch: with no id there is nothing to load, and the
   *  connect button says the connection is not enabled yet instead of asking for a refresh. */
  readonly VITE_META_APP_ID?: string;
  /** The Graph version FB.init is pinned to — Meta retires versions on its own schedule, and it
   *  must be the one the onboarding adapter speaks. Absent, the console falls back to the version
   *  named in `meta.ts`, which the gate holds equal to the deployment's. */
  readonly VITE_META_GRAPH_VERSION?: string;
  /** Renders (or hides) the assistant-backed "?" icon (AssistantHint.tsx) — INDEPENDENT of any
   *  future chat-widget switch (Phase 6). Absent or anything but the literal string "true" hides
   *  it entirely, not just disables it: a switched-off feature should leave no trace on the screen. */
  readonly VITE_ASSISTANT_HELP_ICON_ENABLED?: string;
  /** Renders (or hides) the assistant chat (AssistantChat.tsx, «خدمة العملاء» tab on «الدعم
   *  الفني») — INDEPENDENT of the "?" icon's own switch. Same all-or-nothing rule: anything but
   *  the literal string "true" hides it entirely. */
  readonly VITE_ASSISTANT_CHAT_ENABLED?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** The published legal documents, generated from deploy/seed/legal/*.yaml at build/dev time —
 *  see scripts/legalDocsPlugin.ts. */
declare module 'virtual:legal-docs' {
  import type { LegalDoc } from '../scripts/legalDocsPlugin';
  const docs: LegalDoc[];
  export default docs;
}
