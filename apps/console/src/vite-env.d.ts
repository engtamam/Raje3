/// <reference types="vite/client" />

/** The one setting this app reads from its environment: where the API is. Declared so a typo in
 *  the name is a compile error rather than an `undefined` that silently becomes a relative URL. */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** Meta's Embedded Signup configuration id. Configuration, never a constant: it differs between
   *  our test app and the live one, and a literal would need a rebuild to change. */
  readonly VITE_META_CONFIG_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
