export function isValidSignupPassword(password: string): boolean {
  const length = Array.from(password).length;
  return length >= 8 && length <= 20 && /[A-Za-z]/.test(password) && /[0-9]/.test(password);
}
