/** Правила сложности пароля — зеркало backend/app/core/security.py::password_strength_error,
 * чтобы подсказка на экране совпадала с тем, что реально проверит сервер. */

const SPECIAL = /[!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~]/;

export interface PasswordRule {
  key: string;
  label: string;
  test: (password: string) => boolean;
}

export const PASSWORD_RULES: PasswordRule[] = [
  { key: "length", label: "не короче 8 символов", test: (p) => p.length >= 8 },
  { key: "lower", label: "строчная буква", test: (p) => /[a-zа-яё]/.test(p) },
  { key: "upper", label: "заглавная буква", test: (p) => /[A-ZА-ЯЁ]/.test(p) },
  { key: "digit", label: "цифра", test: (p) => /\d/.test(p) },
  { key: "special", label: "спецсимвол (например, !?#@$%)", test: (p) => SPECIAL.test(p) },
];

export function isPasswordStrong(password: string): boolean {
  return PASSWORD_RULES.every((rule) => rule.test(password));
}

/** Разумная проверка формата email на клиенте; окончательно формат проверяет сервер. */
export function isEmailLike(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
