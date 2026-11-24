import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, Alert, FlatList, Linking, Platform, Switch, Text, View } from "react-native";
import { AccountButton, AccountError, AccountScreen, accountStyles as s } from "@/components/account-screen";
import { Colors } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import { keywordConditionsApi, type KeywordCondition } from "@/lib/keyword-conditions-api";
import { postsApi, type Category } from "@/lib/posts-api";
import { enablePush } from "@/lib/push-client";

export default function KeywordConditionsScreen() {
  const { t, locale, categoryLabel } = useLocale();
  const [items, setItems] = useState<KeywordCondition[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mutating, setMutating] = useState<string | null>(null);
  const requests = useRef({ generation: 0, busy: false });
  useEffect(() => {
    let active = true;
    postsApi.categories().then(rows => { if (active) setCategories(rows); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  const load = useCallback(async (offset: number) => {
    if (requests.current.busy && offset > 0) return;
    const generation = offset === 0 ? ++requests.current.generation : requests.current.generation;
    requests.current.busy = true; setLoading(true); setError("");
    try {
      const page = await keywordConditionsApi.list(offset);
      if (generation !== requests.current.generation) return;
      setItems(current => offset === 0 ? page.items : [...current, ...page.items.filter(item => !current.some(row => row.id === item.id))]);
      setTotal(page.total);
    } catch (e) {
      if (generation === requests.current.generation) setError(e instanceof Error ? e.message : t("common.requestFailed"));
    } finally {
      if (generation === requests.current.generation) { requests.current.busy = false; setLoading(false); }
    }
  }, [t]);
  useFocusEffect(useCallback(() => {
    const state = requests.current;
    void load(0);
    return () => { state.generation++; state.busy = false; };
  }, [load]));

  async function toggle(item: KeywordCondition, enabled: boolean) {
    setMutating(item.id); setError("");
    try {
      if (enabled && Platform.OS !== "web") {
        const permission = await enablePush();
        if (permission !== "granted") {
          if (permission === "denied") Alert.alert(t("push.permissionTitle"), t("push.permissionDenied"), [
            { text: t("common.cancel"), style: "cancel" },
            { text: t("push.openSettings"), onPress: () => { void Linking.openSettings(); } },
          ]);
          else setError(t("push.unavailable"));
          return;
        }
      }
      const updated = await keywordConditionsApi.setNotification(item.id, enabled);
      setItems(current => current.map(row => row.id === item.id ? updated : row));
    } catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { setMutating(null); }
  }

  async function remove(id: string) {
    setMutating(id); setError("");
    try {
      await keywordConditionsApi.remove(id);
      setItems(current => current.filter(row => row.id !== id));
      setTotal(current => current - 1);
    } catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { setMutating(null); }
  }

  function confirmRemove(id: string) {
    if (Platform.OS === "web") {
      if (window.confirm(t("push.deleteConfirm"))) void remove(id);
    } else Alert.alert(t("push.delete"), t("push.deleteConfirm"), [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("push.delete"), style: "destructive", onPress: () => { void remove(id); } },
    ]);
  }

  return <AccountScreen title={t("account.keywords")} scroll={false}>
    <Text style={s.copy}>{t("filters.savedIntro")}</Text>
    <Text style={s.copy}>{t("push.mobileOnly")}</Text>
    <FlatList style={{ flex: 1 }} data={items} extraData={[locale, categories]} keyExtractor={item => item.id}
      contentContainerStyle={{ flexGrow: 1, paddingBottom: 24, gap: 12 }}
      renderItem={({ item }) => {
        const filters = item.conditions;
        const category = categories.find(row => row.id === filters.category_id);
        return <View style={s.card}>
          <Text style={s.label}>{t(item.post_type === "LOST" ? "account.lostPosts" : "account.foundPosts")}</Text>
          {filters.q ? <Text style={s.copy}>{t("filters.allText")}: {filters.q}</Text> : null}
          {filters.category_id !== null ? <Text style={s.copy}>{t("home.categoryFilter")}: {category ? categoryLabel(category.code, category.name) : `#${filters.category_id}`}</Text> : null}
          {([ ["title_terms", "filters.title"], ["content_terms", "filters.content"], ["location_terms", "filters.location"] ] as const).map(([field, label]) =>
            filters[field].length ? <Text key={field} style={s.copy}>{t(label)}: {filters[field].join(` ${t("filters.or")} `)}</Text> : null)}
          {filters.event_at ? <Text style={s.copy}>{t("filters.eventAt")}: {new Date(filters.event_at).toLocaleString(locale === "ko" ? "ko-KR" : "en-US")}</Text> : null}
          <Text style={[s.copy, { fontSize: 12, color: "#87928C" }]}>{new Date(item.created_at).toLocaleString(locale === "ko" ? "ko-KR" : "en-US")}</Text>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={s.label}>{t("push.newPostAlerts")}</Text>
            <Switch value={item.notification_enabled} disabled={mutating !== null}
              accessibilityLabel={t("push.newPostAlerts")}
              onValueChange={enabled => { void toggle(item, enabled); }} />
          </View>
          <AccountButton label={t("push.delete")} secondary disabled={mutating !== null}
            onPress={() => confirmRemove(item.id)} />
        </View>;
      }}
      refreshing={loading && items.length > 0} onRefresh={() => void load(0)}
      onEndReached={() => { if (!loading && !error && items.length < total) void load(items.length); }} onEndReachedThreshold={0.3}
      ListEmptyComponent={!loading && !error ? <Text style={[s.copy, { textAlign: "center", paddingVertical: 48 }]}>{t("filters.noSaved")}</Text> : null}
      ListFooterComponent={<View style={{ paddingVertical: 16, gap: 12 }}>
        {loading ? <ActivityIndicator color={Colors.primary} /> : null}
        <AccountError message={error} />
        {error ? <AccountButton label={t("common.retry")} secondary onPress={() => void load(items.length)} /> : null}
      </View>} />
  </AccountScreen>;
}
