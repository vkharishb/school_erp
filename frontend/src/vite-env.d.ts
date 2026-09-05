/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_SCHOOL_NAME?: string;
  readonly VITE_PRODUCT_NAME?: string;
  readonly VITE_TECH_PARTNER?: string;
  readonly VITE_LOGIN_TAGLINE?: string;
  readonly VITE_LOGIN_WELCOME?: string;
  readonly VITE_RELEASE_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
