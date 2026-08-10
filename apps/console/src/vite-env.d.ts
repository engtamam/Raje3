/// <reference types="vite/client" />

/** The one setting this app reads from its environment: where the API is. Declared so a typo in
 *  the name is a compile error rather than an `undefined` that silently becomes a relative URL. */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
