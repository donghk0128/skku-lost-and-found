import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";
import { AccountButton, AccountError, AccountScreen, accountStyles as s } from "@/components/account-screen";
import { PostRow } from "@/components/post-board";
import { accountApi } from "@/lib/account-api";
import { postsApi, type Category, type Post } from "@/lib/posts-api";
import { Colors } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export default function AccountPosts({ favorites = false }: { favorites?: boolean }) {
  const { t } = useLocale();
  const [type, setType] = useState<"LOST" | "FOUND">("LOST");
  return <AccountScreen title={t(favorites ? "account.favorites" : "account.myPosts")} scroll={false}>
    {!favorites && <View accessibilityRole="tablist" style={{ flexDirection: "row", gap: 12 }}>
      {(["LOST", "FOUND"] as const).map(value => <Pressable key={value} accessibilityRole="tab" accessibilityState={{ selected: type === value }} onPress={() => setType(value)}
        style={{ flex: 1, padding: 16, alignItems: "center", borderRadius: 14, backgroundColor: type === value ? Colors.softgreen : "#F4F6F5" }}>
        <Text style={[s.label, type === value && { color: Colors.primary }]}>{t(value === "LOST" ? "account.lostPosts" : "account.foundPosts")}</Text>
      </Pressable>)}
    </View>}
    <AccountPostList key={`${favorites}-${type}`} favorites={favorites} type={type} />
  </AccountScreen>;
}

function AccountPostList({ favorites, type }: { favorites: boolean; type: "LOST" | "FOUND" }) {
  const { locale, t } = useLocale();
  const [items, setItems] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requests = useRef({ generation: 0, busy: false });
  useEffect(() => {
    let active = true;
    postsApi.categories().then(rows => { if (active) setCategories(rows); }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const load = useCallback(async (offset: number) => {
    if (requests.current.busy && offset > 0) return;
    const version = offset === 0 ? ++requests.current.generation : requests.current.generation;
    requests.current.busy = true; setLoading(true); setError("");
    try {
      const page = favorites ? await accountApi.favorites(offset) : await accountApi.myPosts(type, offset);
      if (version !== requests.current.generation) return;
      setItems(current => offset === 0 ? page.items : [...current, ...page.items.filter(item => !current.some(row => row.id === item.id))]);
      setTotal(page.total);
    } catch (e) {
      if (version === requests.current.generation) setError(e instanceof Error ? e.message : t("common.postLoadFailed"));
    } finally {
      if (version === requests.current.generation) { requests.current.busy = false; setLoading(false); }
    }
  }, [favorites, type, t]);

  useFocusEffect(useCallback(() => {
    const state = requests.current;
    void load(0);
    return () => { state.generation++; state.busy = false; };
  }, [load]));

  return <FlatList data={items} extraData={locale} keyExtractor={item => item.id} style={{ flex: 1 }}
    contentContainerStyle={{ flexGrow: 1, paddingBottom: 28 }}
    renderItem={({ item }) => <PostRow post={item} category={categories.find(category => category.id === item.category_id)} showAuthor={favorites} showType={favorites} />}
    refreshing={loading && items.length > 0} onRefresh={() => void load(0)}
    onEndReached={() => { if (!loading && !error && items.length < total) void load(items.length); }} onEndReachedThreshold={0.3}
    ListEmptyComponent={!loading && !error ? <Text style={[s.copy, { textAlign: "center", paddingVertical: 48 }]}>{t(favorites ? "account.noFavorites" : "account.noPosts")}</Text> : null}
    ListFooterComponent={<View style={{ paddingVertical: 24, gap: 12 }}>
      {loading ? <ActivityIndicator color={Colors.primary} /> : null}
      <AccountError message={error} />
      {error ? <AccountButton label={t("common.retry")} secondary onPress={() => void load(items.length)} /> : null}
    </View>}
  />;
}
