import en from "@/i18n/en";
import ko from "@/i18n/ko";

type TranslationKey = keyof typeof en;
type TranslationValues = Record<string, string | number>;
export type Locale = "en" | "ko";

const catalogs: Record<Locale, Record<TranslationKey, string>> = {
  en,
  ko,
};
let activeLocale: Locale = "ko";

export function setTranslationLocale(locale: Locale) {
  activeLocale = locale;
}

const categoryKeys: Record<string, TranslationKey> = {
  ELECTRONICS: "category.electronics",
  WALLET: "category.wallet",
  ID_CARD: "category.idCard",
  BAG: "category.bag",
  CLOTHING: "category.clothing",
  KEY: "category.key",
  BOOK_STATIONERY: "category.bookStationery",
  OTHER: "category.other",
};

export type TranslateFn = (
  key: TranslationKey,
  values?: TranslationValues,
) => string;

export function translate(
  locale: Locale,
  key: TranslationKey,
  values: TranslationValues = {},
): string {
  return catalogs[locale][key].replace(
    /\{\{(\w+)\}\}/g,
    (placeholder, name: string) => {
      const value = values[name];
      return value === undefined ? placeholder : String(value);
    },
  );
}

export function t(key: TranslationKey, values: TranslationValues = {}): string {
  return translate(activeLocale, key, values);
}

export function categoryLabelFor(
  locale: Locale,
  code: string | null | undefined,
  fallback = "",
): string {
  const key = code ? categoryKeys[code] : undefined;
  return key ? translate(locale, key) : fallback || code || "";
}
