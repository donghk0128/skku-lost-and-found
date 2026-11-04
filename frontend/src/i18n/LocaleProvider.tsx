import * as SecureStore from "expo-secure-store";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import {
  categoryLabelFor,
  setTranslationLocale,
  t,
  translate,
  type Locale,
  type TranslateFn,
} from "@/i18n";

const preferenceKey = "lost-found-language";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => Promise<void>;
  t: TranslateFn;
  categoryLabel: (code: string | null | undefined, fallback?: string) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

async function readLocale(): Promise<Locale> {
  const saved =
    Platform.OS === "web"
      ? typeof window === "undefined"
        ? null
        : window.localStorage.getItem(preferenceKey)
      : await SecureStore.getItemAsync(preferenceKey);
  return saved === "en" || saved === "ko" ? saved : "ko";
}

async function persistLocale(locale: Locale) {
  if (Platform.OS === "web") {
    if (typeof window !== "undefined")
      window.localStorage.setItem(preferenceKey, locale);
    return;
  }
  await SecureStore.setItemAsync(preferenceKey, locale);
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("ko");
  const [ready, setReady] = useState(false);
  const [storageError, setStorageError] = useState("");

  useEffect(() => {
    let active = true;
    readLocale()
      .then((savedLocale) => {
        if (!active) return;
        setTranslationLocale(savedLocale);
        setLocaleState(savedLocale);
        setReady(true);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setStorageError(
          error instanceof Error ? error.message : t("language.loadFailed"),
        );
        setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const setLocale = useCallback(async (nextLocale: Locale) => {
    setTranslationLocale(nextLocale);
    setLocaleState(nextLocale);
    setStorageError("");
    try {
      await persistLocale(nextLocale);
    } catch (error) {
      setStorageError(
        error instanceof Error ? error.message : t("language.saveFailed"),
      );
    }
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: ((key, values) => translate(locale, key, values)) as TranslateFn,
      categoryLabel: (code: string | null | undefined, fallback = "") =>
        categoryLabelFor(locale, code, fallback),
    }),
    [locale, setLocale],
  );
  if (!ready) return null;

  return (
    <LocaleContext.Provider value={value}>
      <View style={styles.root}>
        {storageError ? (
          <Text accessibilityRole="alert" style={styles.storageError}>
            {t("language.loadFailed")} {storageError}
          </Text>
        ) : null}
        {children}
      </View>
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error("useLocale must be used within LocaleProvider.");
  }
  return context;
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  storageError: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    color: "#B54747",
    backgroundColor: "#FFF4F4",
    fontSize: 12,
  },
});
