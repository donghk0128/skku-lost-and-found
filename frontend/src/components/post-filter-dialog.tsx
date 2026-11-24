import { useRef, useState } from "react";
import { Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import DateTimeField from "@/components/ui/date-time-field";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import { keywordConditionsApi } from "@/lib/keyword-conditions-api";
import { emptyPostFilters, hasPostFilters, MAX_FILTER_TERMS, normalizePostFilters, uniquePhrases, type PostFilters } from "@/lib/post-filters";
import type { Category } from "@/lib/posts-api";

type TermKind = "title_terms" | "content_terms" | "location_terms";
type Kind = "q" | TermKind | "event_at";
const kinds: Kind[] = ["q", "title_terms", "content_terms", "location_terms", "event_at"];
const labels = { q: "filters.allText", title_terms: "filters.title", content_terms: "filters.content", location_terms: "filters.location", event_at: "filters.eventAt" } as const;
const blankPending = () => ({ title_terms: "", content_terms: "", location_terms: "" });

export default function PostFilterDialog({ initial, categories, postType, onApply, onClose }: {
  initial: PostFilters; categories: Category[]; postType: "LOST" | "FOUND";
  onApply: (filters: PostFilters) => void; onClose: () => void;
}) {
  const { t, categoryLabel } = useLocale();
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState(() => normalizePostFilters(initial));
  const [sections, setSections] = useState<Kind[]>(() => kinds.filter(kind => Boolean(initial[kind]?.length)));
  const [pending, setPending] = useState(blankPending);
  const [menuOpen, setMenuOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedSignature, setSavedSignature] = useState("");
  const savingRef = useRef(false);
  // Include an unfinished input when applying/saving; never silently drop it.
  const resolved = normalizePostFilters({ ...draft,
    title_terms: [...draft.title_terms, pending.title_terms],
    content_terms: [...draft.content_terms, pending.content_terms],
    location_terms: [...draft.location_terms, pending.location_terms],
  });
  const signature = JSON.stringify({ postType, resolved });
  const saved = savedSignature === signature;
  const validate = () => {
    if ([resolved.title_terms, resolved.content_terms, resolved.location_terms].some(terms => terms.length > MAX_FILTER_TERMS)) {
      setError(t("filters.termLimit", { count: MAX_FILTER_TERMS }));
      return false;
    }
    setError("");
    return true;
  };
  const close = () => { if (!savingRef.current) onClose(); };
  const removeSection = (kind: Kind) => {
    setSections(current => current.filter(value => value !== kind));
    if (kind === "q" || kind === "event_at") setDraft(current => ({ ...current, [kind]: null }));
    else {
      setDraft(current => ({ ...current, [kind]: [] }));
      setPending(current => ({ ...current, [kind]: "" }));
    }
  };
  const addTerm = (kind: TermKind) => {
    if (!pending[kind].trim()) return;
    const terms = uniquePhrases([...draft[kind], pending[kind]]);
    if (terms.length > MAX_FILTER_TERMS) {
      setError(t("filters.termLimit", { count: MAX_FILTER_TERMS }));
      return;
    }
    setDraft(current => ({ ...current, [kind]: terms }));
    setPending(current => ({ ...current, [kind]: "" }));
    setError("");
  };
  const save = async () => {
    if (savingRef.current || saved || !hasPostFilters(resolved) || !validate()) return;
    Keyboard.dismiss();
    savingRef.current = true;
    setSaving(true);
    try {
      await keywordConditionsApi.save(postType, resolved);
      setSavedSignature(signature);
    } catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { savingRef.current = false; setSaving(false); }
  };
  return <Modal visible transparent animationType="fade" statusBarTranslucent onRequestClose={close}>
    <KeyboardAvoidingView style={s.overlay} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <Pressable style={StyleSheet.absoluteFill} accessibilityRole="button" accessibilityLabel={t("common.cancel")} onPress={close} />
      <View style={[s.dialog, { maxHeight: "92%", marginTop: insets.top, marginBottom: insets.bottom }]} accessibilityViewIsModal onAccessibilityEscape={close}>
        <View style={s.header}>
          <Text style={s.title}>{t("home.filter")}</Text>
          <View style={s.actions}>
            <Pressable disabled={saving} accessibilityRole="button" onPress={() => {
              setDraft(emptyPostFilters()); setSections([]); setPending(blankPending()); setError("");
            }} style={s.smallButton}><Text style={s.link}>{t("filters.reset")}</Text></Pressable>
            <Pressable disabled={saving} accessibilityRole="button" accessibilityLabel={t("common.cancel")} onPress={close} style={s.smallButton}><Text style={s.close}>×</Text></Pressable>
          </View>
        </View>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.content}>
          <Text style={s.hint}>{t("filters.ruleHint")}</Text>
          <View style={s.section}>
            <Text style={s.label}>{t("home.categoryFilter")}</Text>
            <View style={s.chips}>
              {[{ id: null, code: "", name: t("home.allCategories") }, ...categories].map(category => <Pressable
                key={String(category.id)} accessibilityRole="button" disabled={saving}
                accessibilityState={{ selected: draft.category_id === category.id }}
                onPress={() => setDraft(current => ({ ...current, category_id: category.id }))}
                style={[s.chip, draft.category_id === category.id && s.selectedChip]}>
                <Text style={s.chipText}>{category.id === null ? category.name : categoryLabel(category.code, category.name)}</Text>
              </Pressable>)}
            </View>
          </View>
          {sections.map(kind => <View key={kind} style={s.section}>
            <View style={s.sectionHeader}>
              <Text style={s.label}>{t(labels[kind])}</Text>
              <Pressable disabled={saving} accessibilityRole="button" accessibilityLabel={t("filters.removeCondition", { field: t(labels[kind]) })} onPress={() => removeSection(kind)} style={s.smallButton}><Text style={s.remove}>×</Text></Pressable>
            </View>
            {kind === "q" ? <TextInput value={draft.q ?? ""} onChangeText={q => setDraft(current => ({ ...current, q }))}
              editable={!saving} accessibilityLabel={t("filters.allText")} maxLength={100} style={s.input} placeholder={t("filters.phrasePlaceholder")} placeholderTextColor="#929B97" />
              : kind === "event_at" ? <>
                <DateTimeField value={draft.event_at ? new Date(draft.event_at) : null} disabled={saving} label={t("filters.eventAt")} onChange={date => setDraft(current => ({ ...current, event_at: date.toISOString() }))} />
                <Text style={s.hint}>{t("filters.timeHint")}</Text>
              </> : <>
                <View style={s.chips}>{draft[kind].map(term => <Pressable key={term} accessibilityRole="button" disabled={saving}
                  accessibilityLabel={t("filters.removePhrase", { phrase: term })}
                  onPress={() => setDraft(current => ({ ...current, [kind]: current[kind].filter(value => value !== term) }))} style={[s.chip, s.selectedChip]}>
                  <Text style={s.chipText}>{term}  ×</Text>
                </Pressable>)}</View>
                <View style={s.termRow}>
                  <TextInput value={pending[kind]} onChangeText={value => setPending(current => ({ ...current, [kind]: value }))}
                    editable={!saving} accessibilityLabel={t("filters.phraseFor", { field: t(labels[kind]) })}
                    maxLength={kind === "location_terms" ? 255 : 100} autoCapitalize="none" autoCorrect={false}
                    placeholder={t("filters.phrasePlaceholder")} placeholderTextColor="#929B97" style={[s.input, { flex: 1 }]}
                    returnKeyType="done" onSubmitEditing={() => addTerm(kind)} />
                  <Pressable disabled={saving || !pending[kind].trim()} accessibilityRole="button" accessibilityLabel={t("filters.addPhraseFor", { field: t(labels[kind]) })} onPress={() => addTerm(kind)} style={s.addPhrase}><Text style={s.link}>{t("filters.add")}</Text></Pressable>
                </View>
              </>}
          </View>)}
          <Pressable disabled={saving} accessibilityRole="button" onPress={() => setMenuOpen(current => !current)} style={s.addCondition}><Text style={s.link}>＋ {t("filters.addCondition")}</Text></Pressable>
          {menuOpen ? <View style={s.menu}>{kinds.map(kind => <Pressable key={kind} accessibilityRole="button" disabled={sections.includes(kind) || saving}
            accessibilityState={{ disabled: sections.includes(kind) || saving }} onPress={() => { setSections(current => [...current, kind]); setMenuOpen(false); }} style={[s.menuItem, sections.includes(kind) && s.disabled]}>
            <Text style={s.chipText}>{t(labels[kind])}{sections.includes(kind) ? " ✓" : ""}</Text>
          </Pressable>)}</View> : null}
        </ScrollView>
        <View style={s.footer}>
          {error ? <Text accessibilityRole="alert" style={s.error}>{error}</Text> : null}
          {saved ? <Text accessibilityLiveRegion="polite" style={s.success}>{t("filters.saved")}</Text> : null}
          <View style={s.footerButtons}>
            <Pressable accessibilityRole="button" disabled={saving || saved || !hasPostFilters(resolved)} onPress={() => void save()}
              style={[s.save, (saving || saved || !hasPostFilters(resolved)) && s.disabled]}>
              <Text style={s.saveText}>{saving ? t("common.loading") : t("filters.save")}</Text>
            </Pressable>
            <Pressable accessibilityRole="button" disabled={saving} onPress={() => { if (validate()) { Keyboard.dismiss(); onApply(resolved); } }} style={s.apply}><Text style={s.applyText}>{t("filters.apply")}</Text></Pressable>
          </View>
        </View>
      </View>
    </KeyboardAvoidingView>
  </Modal>;
}

const s = StyleSheet.create({
  overlay: { flex: 1, padding: 16, justifyContent: "center", alignItems: "center", backgroundColor: "rgba(0,0,0,0.35)" },
  dialog: { width: "100%", maxWidth: 560, backgroundColor: "white", borderRadius: 20, overflow: "hidden", flexShrink: 1 },
  header: { padding: 20, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderBottomWidth: 1, borderColor: "#EEF1EF" },
  title: { fontFamily: Fonts.pretendardSemiBold, fontSize: 20, color: "#182A22" },
  actions: { flexDirection: "row", alignItems: "center", gap: 10 },
  smallButton: { minWidth: 36, minHeight: 36, alignItems: "center", justifyContent: "center" },
  close: { fontSize: 26, color: "#617069" },
  content: { padding: 20, gap: 20 },
  hint: { fontFamily: Fonts.pretendardRegular, fontSize: 12, lineHeight: 19, color: "#748078" },
  section: { gap: 10 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { fontFamily: Fonts.pretendardSemiBold, fontSize: 14, color: "#26392F" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { minHeight: 36, paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderColor: "#E1E7E3", borderRadius: 18 },
  selectedChip: { backgroundColor: Colors.softgreen, borderColor: Colors.primary },
  chipText: { fontFamily: Fonts.pretendardRegular, fontSize: 13, color: "#26392F" },
  input: { minHeight: 44, minWidth: 0, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: "#DCE3DF", borderRadius: 10, color: "#26392F", fontFamily: Fonts.pretendardRegular, fontSize: 14 },
  termRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  addPhrase: { minHeight: 44, paddingHorizontal: 12, justifyContent: "center" },
  link: { color: Colors.primary, fontFamily: Fonts.pretendardMedium, fontSize: 13 },
  remove: { fontSize: 22, color: "#8A9690" },
  addCondition: { minHeight: 44, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#D5E2DA", borderStyle: "dashed", borderRadius: 10 },
  menu: { borderWidth: 1, borderColor: "#E1E7E3", borderRadius: 12, padding: 6 },
  menuItem: { minHeight: 44, justifyContent: "center", paddingHorizontal: 12 },
  disabled: { opacity: 0.4 },
  footer: { padding: 16, gap: 10, borderTopWidth: 1, borderColor: "#EEF1EF" },
  footerButtons: { flexDirection: "row", gap: 10, justifyContent: "flex-end" },
  save: { flex: 2, minHeight: 46, borderRadius: 12, backgroundColor: Colors.softgreen, alignItems: "center", justifyContent: "center", padding: 10 },
  saveText: { color: Colors.primary, fontFamily: Fonts.pretendardMedium, fontSize: 12, textAlign: "center" },
  apply: { flex: 1, minHeight: 46, borderRadius: 12, backgroundColor: Colors.primary, alignItems: "center", justifyContent: "center", padding: 10 },
  applyText: { color: "white", fontFamily: Fonts.pretendardSemiBold, fontSize: 13 },
  error: { color: "#B54747", fontSize: 12, fontFamily: Fonts.pretendardRegular },
  success: { color: Colors.primary, fontSize: 12, fontFamily: Fonts.pretendardRegular },
});
