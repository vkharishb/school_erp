export const MOBILE_ERROR = "Please enter a valid 10-digit mobile number.";
export const EMAIL_ERROR = "Please enter a valid email address.";

export function isValidIndianMobile(value: string): boolean {
  return /^\d{10}$/.test(value.trim());
}

export function normalizeIndianMobile(value: string): string {
  const mobile = value.trim();

  if (!isValidIndianMobile(mobile)) {
    throw new Error(MOBILE_ERROR);
  }

  return `+91${mobile}`;
}

export function isValidEmail(value: string): boolean {
  const email = value.trim();

  if (!email || email.length > 254) {
    return false;
  }

  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
