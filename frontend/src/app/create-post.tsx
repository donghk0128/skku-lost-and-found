import { useEffect, useRef, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import {
  Alert,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import DateTimeField from "@/components/ui/date-time-field";
import { Colors, Fonts } from "@/constants/theme";
import { imageUrl, postsApi, type Category } from "@/lib/posts-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { authApi } from "@/lib/auth-api";
import {
  joinPostDescription,
  splitPostDescription,
} from "@/lib/post-description";
import { useAuth } from "@/providers/AuthProvider";
import { onLocationPicked, type PickedLocation } from "@/lib/location-picker";
import PinIcon from "@/assets/icons/location.svg";
import { useLocale } from "@/i18n/LocaleProvider";

export default function CreatePostScreen() {
  const { t, categoryLabel } = useLocale();
  const router = useRouter();
  const { type, editId, creationMethod, title: initialTitle, description: initialDescription, features: initialFeatures, categoryId, place: initialPlace, latitude, longitude, startAt, endAt } = useLocalSearchParams<{
    type?: string;
    editId?: string;
    creationMethod?: string;
    title?: string;
    description?: string;
    features?: string;
    categoryId?: string;
    place?: string;
    latitude?: string;
    longitude?: string;
    startAt?: string;
    endAt?: string;
  }>();
  const { user } = useAuth();
  const editing = !!editId;
  const [existingPhotos, setExistingPhotos] = useState<string[]>([]);
  const [initializing, setInitializing] = useState(editing);
  const [initialError, setInitialError] = useState("");
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const lost = postType === "LOST";
  const [step, setStep] = useState(1);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryError, setCategoryError] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [start, setStart] = useState<Date | null>(() => startAt ? new Date(startAt) : null);
  const [end, setEnd] = useState<Date | null>(() => endAt ? new Date(endAt) : null);
  const [place, setPlace] = useState(initialPlace ?? "");
  // AI 초안에서 전달된 특징도 일반 작성과 같은 입력란에서 수정할 수 있다.
  const [features, setFeatures] = useState(initialFeatures ?? "");
  const [title, setTitle] = useState(initialTitle ?? "");
  const [description, setDescription] = useState(initialDescription ?? "");
  const [photos, setPhotos] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const savedId = useRef<string | null>(null);
  const uploaded = useRef(0);
  const pending = useRef(false);
  const [saved, setSaved] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [picked, setPicked] = useState<PickedLocation | null>(() => {
    if (!initialPlace || !latitude || !longitude) return null;
    const parsedLatitude = Number(latitude);
    const parsedLongitude = Number(longitude);
    if (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)) {
      return null;
    }
    return {
      address: initialPlace,
      latitude: parsedLatitude,
      longitude: parsedLongitude,
    };
  });

  useEffect(
    () =>
      onLocationPicked((location) => {
        setPicked(location);
        setPlace((current) => current.trim() ? current : location.address);
      }),
    [],
  );

  useEffect(() => {
    let active = true;
    postsApi
      .categories()
      .then((items) => {
        if (active) {
          setCategories(items);
          if (!editId && categoryId) {
            setCategory(items.find((item) => item.id === Number(categoryId)) ?? null);
          }
        }
      })
      .catch(() => {
        if (active)
          setCategoryError(
            t("createPost.categoryLoadFailed"),
          );
      });
    return () => {
      active = false;
    };
  }, [categoryId, editId]);
  useEffect(() => {
    if (!editId) return;
    let active = true;
    Promise.all([
      postsApi.detail(editId),
      postsApi.categories(),
      postsApi.images(editId),
    ])
      .then(([post, items, images]) => {
        if (!active) return;
        if (post.author_id !== user?.id)
          throw new Error(t("createPost.editOnlyOwn"));
        setCategory(items.find((item) => item.id === post.category_id) ?? null);
        const content = splitPostDescription(post.description);
        setFeatures(content.features);
        setTitle(post.title);
        setDescription(content.body);
        setPlace(post.location_text ?? "");
        setPicked(
          post.latitude !== null && post.longitude !== null
            ? {
                address: post.location_text ?? "",
                latitude: post.latitude,
                longitude: post.longitude,
              }
            : null,
        );
        setStart(post.event_start_at ? new Date(post.event_start_at) : null);
        setEnd(post.event_end_at ? new Date(post.event_end_at) : null);
        setExistingPhotos(images.map((image) => imageUrl(image.content_url)));
        setAcknowledged(true);
        setInitializing(false);
      })
      .catch((error) => {
        if (active) {
          setInitialError(
            error instanceof Error
              ? error.message
              : t("common.postLoadFailed"),
          );
          setInitializing(false);
        }
      });
    return () => {
      active = false;
    };
  }, [editId, user?.id]);
  const back = () => {
    if (busy) return;
    if (saved) {
      Alert.alert(
        t("createPost.savedTitle"),
        t("createPost.leaveUpload"),
        [
          { text: t("common.continueWriting"), style: "cancel" },
          { text: t("common.leave"), onPress: () => router.replace("/") },
        ],
      );
    } else if (step === 2) setStep(1);
    else if (router.canGoBack()) router.back();
    else router.replace("/");
  };
  const pick = async () => {
    if (photos.length + existingPhotos.length >= 5 || saved || busy) return;
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsMultipleSelection: true,
        selectionLimit: 5 - existingPhotos.length - photos.length,
        quality: 0.8,
      });
      if (result.canceled) return;
      if (
        result.assets.some(
          (asset) => asset.fileSize && asset.fileSize > 5 * 1024 * 1024,
        )
      ) {
        setError(t("createPost.photoTooLarge"));
        return;
      }
      if (
        result.assets.some(
          (asset) =>
            asset.mimeType &&
            !["image/jpeg", "image/png", "image/webp"].includes(asset.mimeType),
        )
      ) {
        setError(t("createPost.unsupportedPhoto"));
        return;
      }
      setPhotos((current) =>
        [...current, ...result.assets].slice(0, 5 - existingPhotos.length),
      );
      setError("");
    } catch {
      setError(t("createPost.photoPermission"));
    }
  };
  const submit = async () => {
    if (pending.current) return;
    setError("");
    if (step === 1) {
      if (!category) {
        setError(t("createPost.selectCategory"));
        return;
      }
      if ((start === null) !== (end === null)) {
        setError(t("createPost.selectBothTimes"));
        return;
      }
      if (start && end && start > end) {
        setError(t("createPost.invalidTimeRange"));
        return;
      }
      setStep(2);
      return;
    }
    if (!acknowledged) {
      setError(t("createPost.acknowledgeNotice"));
      return;
    }
    if (!title.trim() || !description.trim()) {
      setError(t("createPost.titleAndBodyRequired"));
      return;
    }
    pending.current = true;
    setBusy(true);
    try {
      const session = await readSession();
      if (!session) throw new Error(t("common.loginRequired"));
      // Refresh before writing so an expired access token does not interrupt uploads.
      const refreshed = await authApi.refresh(session.refresh_token);
      session.access_token = refreshed.access_token;
      await writeSession(session);
      if (!savedId.current) {
        setProgress(
          editing ? t("createPost.editing") : t("createPost.submitting"),
        );
        const commonBody = {
          title: title.trim(),
          description: joinPostDescription(description, features),
          category_id: category?.id ?? null,
          location_text: place.trim() || null,
          event_start_at: start?.toISOString() ?? null,
          event_end_at: end?.toISOString() ?? null,
        };
        const coordinates = picked
          ? {
              latitude: Number(picked.latitude.toFixed(6)),
              longitude: Number(picked.longitude.toFixed(6)),
            }
          : {};
        const post = editId
          ? await postsApi.update(
              editId,
              {
                ...commonBody,
                ...coordinates,
                ...(!picked ? { latitude: null, longitude: null } : {}),
              },
              session.access_token,
            )
          : await (creationMethod === "AI_ASSISTED"
              ? postsApi.createAiAssisted
              : postsApi.create)(
              {
                post_type: postType,
                ...commonBody,
                category_id: commonBody.category_id ?? undefined,
                location_text: commonBody.location_text ?? undefined,
                event_start_at: commonBody.event_start_at ?? undefined,
                event_end_at: commonBody.event_end_at ?? undefined,
                ...coordinates,
              },
              session.access_token,
            );
        savedId.current = post.id;
        setSaved(true);
      } else {
        // Reconcile confirmed uploads before retrying a partially completed batch.
        const images = await postsApi.images(savedId.current);
        uploaded.current = Math.max(0, images.length - existingPhotos.length);
      }
      for (let index = uploaded.current; index < photos.length; index++) {
        setProgress(
          t("createPost.uploadingPhoto", {
            current: index + 1,
            total: photos.length,
          }),
        );
        await postsApi.upload(
          savedId.current,
          photos[index],
          session.access_token,
        );
        uploaded.current = index + 1;
      }
      if (editId) {
        router.dismissTo({
          pathname: "/post/[id]",
          params: { id: editId, refresh: String(Date.now()) },
        });
        return;
      }
      router.dismissAll();
      router.replace({
        pathname: "/",
        params: { board: postType, refresh: String(Date.now()) },
      });
    } catch (error) {
      setError(
        (savedId.current
          ? t("createPost.uploadIncomplete")
          : "") +
          (error instanceof Error ? error.message : t("createPost.submitFailed")),
      );
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  const input = (
    label: string,
    value: string,
    change: (value: string) => void,
    placeholder: string,
    multiline = false,
    maxLength?: number,
  ) => (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={change}
        editable={!busy && !saved}
        placeholder={placeholder}
        placeholderTextColor="#BDBDBD"
        multiline={multiline}
        maxLength={maxLength}
        style={[styles.input, multiline && styles.multiline]}
      />
    </View>
  );
  if (initializing || initialError)
    return (
      <SafeAreaView style={styles.root}>
        <Pressable onPress={back} style={styles.back}>
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={{ padding: 28 }}>
          {initialError || t("createPost.initialLoading")}
        </Text>
      </SafeAreaView>
    );
  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.header}>
          <Pressable
            disabled={busy}
            onPress={back}
            accessibilityLabel={t("common.back")}
            style={styles.back}
          >
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <Text style={styles.headerTitle}>
            {editing ? t("createPost.editTitle") : t("createPost.creatingTitle")}
          </Text>
          <View style={styles.back} />
        </View>
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View
            style={styles.steps}
            accessibilityLabel={t("createPost.stepProgress", { step })}
          >
            <View style={[styles.circle, step === 1 && styles.active]}>
              <Text
                style={[styles.stepText, step === 1 && styles.activeStepText]}
              >
                1
              </Text>
            </View>
            <View style={styles.stepConnector} />
            <View style={[styles.circle, step === 2 && styles.active]}>
              <Text
                style={[styles.stepText, step === 2 && styles.activeStepText]}
              >
                2
              </Text>
            </View>
          </View>
          <Text style={styles.title}>
            {step === 1
              ? t("createPost.stepOne")
              : lost
                ? t("createPost.stepTwoLost")
                : t("createPost.stepTwoFound")}
          </Text>
          {step === 1 ? (
            <>
              <View style={styles.field}>
                <Text style={styles.label}>{t("createPost.category")}</Text>
                <Pressable
                  onPress={() => setCategoryOpen(true)}
                  style={styles.select}
                >
                  <Text style={styles.selectText}>
                    {category
                      ? categoryLabel(category.code, category.name)
                      : t("createPost.select")}{" "}
                    ⌄
                  </Text>
                </Pressable>
                {categoryError ? (
                  <Text style={styles.hint}>{categoryError}</Text>
                ) : null}
              </View>
              <View style={styles.field}>
                <Text style={styles.label}>
                  {lost ? t("createPost.lost") : t("createPost.found")}{" "}
                  {t("createPost.dateTime")}{" "}
                  <Text style={styles.hint}>{t("createPost.optional")}</Text>
                </Text>
                <DateTimeField
                  label={t("createPost.startTime")}
                  value={start}
                  onChange={setStart}
                />
                <Text style={styles.hint}>~</Text>
                <DateTimeField
                  label={t("createPost.endTime")}
                  value={end}
                  onChange={setEnd}
                />
              </View>
              {input(
                lost
                  ? t("createPost.lostLocation")
                  : t("createPost.foundLocation"),
                place,
                setPlace,
                t("createPost.locationExample"),
                false,
                255,
              )}
              <Pressable
                onPress={() => {
                  router.push({
                    pathname: "/create-post-map",
                    params: {
                      ...(picked
                        ? {
                            latitude: String(picked.latitude),
                            longitude: String(picked.longitude),
                          }
                        : {}),
                    },
                  });
                }}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 14,
                  borderWidth: 1,
                  borderColor: Colors.primary,
                  borderRadius: 16,
                  paddingVertical: 12,
                }}
              >
                <PinIcon />
                <Text style={{ color: Colors.primary }}>
                  {t(
                    picked
                      ? "createPost.changeMapLocation"
                      : "createPost.pickOnMap",
                  )}
                </Text>
              </Pressable>
              {picked ? (
                <Text style={styles.hint}>{picked.address}</Text>
              ) : null}
              {input(
                t("createPost.features"),
                features,
                setFeatures,
                t("createPost.featuresExample"),
                true,
              )}
            </>
          ) : (
            <>
              {input(
                t("createPost.titleLabel"),
                title,
                setTitle,
                t("createPost.titlePlaceholder"),
                false,
                100,
              )}
              {input(
                t("createPost.description"),
                description,
                setDescription,
                t("createPost.descriptionPlaceholder"),
                true,
              )}
              <View style={styles.field}>
                <Text style={styles.label}>
                  {t("createPost.photos")}{" "}
                  <Text style={styles.hint}>
                    {t("createPost.photoLimit", {
                      count: existingPhotos.length + photos.length,
                    })}
                  </Text>
                </Text>
                <ScrollView horizontal contentContainerStyle={styles.photos}>
                  {!saved && existingPhotos.length + photos.length < 5 ? (
                    <Pressable
                      disabled={busy}
                      onPress={() => void pick()}
                      style={styles.addPhoto}
                      accessibilityLabel={t("createPost.addPhoto")}
                    >
                      <Text style={styles.addText}>＋</Text>
                      <Text style={styles.hint}>{t("createPost.addPhoto")}</Text>
                    </Pressable>
                  ) : null}
                  {existingPhotos.map((uri) => (
                    <Image key={uri} source={{ uri }} style={styles.photo} />
                  ))}
                  {photos.map((photo, index) => (
                    <View key={`${photo.uri}-${index}`}>
                      <Image source={{ uri: photo.uri }} style={styles.photo} />
                      {!saved ? (
                        <Pressable
                          disabled={busy}
                          onPress={() =>
                            setPhotos((items) =>
                              items.filter((_, position) => position !== index),
                            )
                          }
                          style={styles.remove}
                          accessibilityLabel={t("createPost.removePhoto", {
                            index: index + 1,
                          })}
                        >
                          <Text style={{ color: "white" }}>×</Text>
                        </Pressable>
                      ) : null}
                    </View>
                  ))}
                </ScrollView>
                {editing ? (
                  <Text style={styles.hint}>
                    {t("createPost.keepExistingPhotos")}
                  </Text>
                ) : null}
              </View>
            </>
          )}
          {error ? (
            <Text accessibilityRole="alert" style={styles.error}>
              ⓘ {error}
            </Text>
          ) : null}
          {step === 2 ? (
            <View style={styles.notice}>
              <Text style={styles.noticeText}>
                {t("createPost.contentNotice")}
              </Text>
              <Pressable
                accessibilityRole="checkbox"
                accessibilityLabel={t("createPost.acknowledged")}
                accessibilityState={{
                  checked: acknowledged,
                  disabled: busy || saved,
                }}
                disabled={busy || saved}
                onPress={() => {
                  setAcknowledged((current) => !current);
                  setError("");
                }}
                style={styles.checkRow}
              >
                <View style={[styles.checkbox, acknowledged && styles.checked]}>
                  {acknowledged ? (
                    <Text style={styles.checkmark}>✓</Text>
                  ) : null}
                </View>
                <Text style={styles.checkLabel}>
                  {t("createPost.acknowledged")}
                </Text>
              </Pressable>
            </View>
          ) : null}
          <Pressable
            disabled={busy || (step === 2 && !acknowledged)}
            accessibilityState={{
              disabled: busy || (step === 2 && !acknowledged),
              busy,
            }}
            onPress={() => void submit()}
            style={[
              styles.button,
              (busy || (step === 2 && !acknowledged)) && { opacity: 0.6 },
            ]}
            accessibilityRole="button"
          >
            <Text style={styles.buttonText}>
              {busy
                ? progress || t("common.processing")
                : step === 1
                  ? t("createPost.next")
                  : saved
                    ? t("createPost.retryUpload")
                    : editing
                      ? t("createPost.finishEdit")
                      : t("createPost.submit")}
            </Text>
          </Pressable>
        </ScrollView>
        <Modal
          visible={categoryOpen}
          transparent
          animationType="fade"
          onRequestClose={() => setCategoryOpen(false)}
        >
          <Pressable style={styles.dim} onPress={() => setCategoryOpen(false)}>
            <View style={styles.categoryMenu}>
              <Text style={styles.label}>{t("createPost.chooseCategory")}</Text>
              <ScrollView>
                {categories.map((item) => (
                  <Pressable
                    key={item.id}
                    onPress={() => {
                      setCategory(item);
                      setCategoryOpen(false);
                      setError("");
                    }}
                    style={styles.category}
                  >
                    <Text>{categoryLabel(item.code, item.name)}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          </Pressable>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FFF" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    height: 64,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 36, color: "#111" },
  headerTitle: {
    fontSize: 18,
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
  },
  content: {
    padding: 28,
    paddingBottom: 48,
    gap: 28,
    width: "100%",
    maxWidth: 540,
    alignSelf: "center",
  },
  steps: { flexDirection: "row", alignItems: "center" },
  circle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "#C6C6C6",
    alignItems: "center",
    justifyContent: "center",
  },
  active: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  title: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 27,
    color: "#111",
    marginVertical: 16,
  },
  field: { gap: 14 },
  label: { fontFamily: Fonts.pretendardMedium, fontSize: 16, color: "#111" },
  hint: { color: "#999", fontSize: 13, fontFamily: Fonts.pretendardRegular },
  input: {
    borderWidth: 1,
    borderColor: "#D6D6D6",
    borderRadius: 18,
    minHeight: 56,
    padding: 18,
    color: "#111",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
  },
  multiline: { minHeight: 100, textAlignVertical: "top" },
  select: {
    alignSelf: "flex-start",
    backgroundColor: "#F4F4F4",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderRadius: 20,
  },
  selectText: { color: "#555", fontSize: 16 },
  stepConnector: { width: 16, height: 1, backgroundColor: "#C6C6C6" },
  stepText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    color: "#A5A5A5",
  },
  activeStepText: { color: "white" },
  notice: { gap: 8, marginTop: 12 },
  noticeText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 13,
    lineHeight: 21,
    color: "#222",
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    minHeight: 44,
  },
  checkbox: {
    width: 21,
    height: 21,
    borderRadius: 5,
    backgroundColor: "#D9D9D9",
    alignItems: "center",
    justifyContent: "center",
  },
  checked: { backgroundColor: Colors.primary },
  checkmark: { color: "white", fontSize: 15 },
  checkLabel: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
    color: "#999",
  },
  button: {
    backgroundColor: Colors.primary,
    height: 54,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 24,
  },
  buttonText: {
    color: "white",
    fontSize: 17,
    fontFamily: Fonts.pretendardMedium,
  },
  error: {
    color: "#B54747",
    lineHeight: 22,
    fontFamily: Fonts.pretendardRegular,
  },
  photos: { gap: 12 },
  addPhoto: {
    width: 96,
    height: 96,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#DDD",
    alignItems: "center",
    justifyContent: "center",
  },
  addText: { fontSize: 30, color: "#777" },
  photo: { width: 96, height: 96, borderRadius: 14 },
  remove: {
    position: "absolute",
    right: 2,
    top: 2,
    backgroundColor: "#444",
    borderRadius: 12,
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  dim: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    padding: 32,
  },
  categoryMenu: {
    backgroundColor: "white",
    borderRadius: 20,
    padding: 24,
    maxHeight: "70%",
    gap: 16,
  },
  category: { paddingVertical: 16, borderBottomWidth: 1, borderColor: "#EEE" },
});
