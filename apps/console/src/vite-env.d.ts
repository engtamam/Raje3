/// <reference types="vite/client" />

/** The one setting this app reads from its environment: where the API is. Declared so a typo in
 *  the name is a compile error rather than an `undefined` that silently becomes a relative URL. */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  // NO VITE_META_* HERE ANY MORE. Meta's App ID / Facebook Login Config ID / Graph version used
  // to be build-time env, baked into the bundle. They are now a runtime read — see meta.ts's own
  // docstring and `GET /api/v1/whatsapp/config` — set entirely from the admin secrets panel, no
  // console rebuild required.
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
