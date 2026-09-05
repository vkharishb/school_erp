export type BrandingConfig = {
  schoolName: string;
  productName: string;
  tagline: string;
  welcomeMessage: string;
  releaseVersion: string;
};

const env = import.meta.env;

export const branding: BrandingConfig = {
  schoolName: env.VITE_SCHOOL_NAME?.trim() || "School",
  productName: env.VITE_PRODUCT_NAME?.trim() || "School ERP",
  tagline:
    env.VITE_LOGIN_TAGLINE?.trim() ||
    "Smart learning. Simple administration. Secure operations.",
  welcomeMessage:
    env.VITE_LOGIN_WELCOME?.trim() ||
    "One secure workspace for students, teachers, fees, attendance and academics.",
  releaseVersion:
    env.VITE_RELEASE_VERSION?.trim() || "V1.1.DEV.15",
};
