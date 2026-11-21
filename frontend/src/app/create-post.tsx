import { useEffect, useId, useRef, useState } from "react";
import { useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import {
  CommonActions,
  useIsFocused,
  usePreventRemove,
  type NavigationAction,
} from "expo-router/react-navigation";
import * as ImagePicker from "expo-image-picker";
import {
  Keyboard,
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
import {
  useSafeAreaInsets,
  SafeAreaView,
} from "react-native-safe-area-context";
import CategoryIcon from "@/components/CategoryIcon";
import XIcon from "@/assets/icons/x.svg";
import AppModal from "@/components/Modal";
import DateTimeField from "@/components/ui/date-time-field";
import { Colors, Fonts } from "@/constants/theme";
import {
  imageUrl,
  postsApi,
  type Category,
  type PostImageAsset,
} from "@/lib/posts-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { authApi } from "@/lib/auth-api";
import {
  joinPostDescription,
  splitPostDescription,
} from "@/lib/post-description";
import { useAuth } from "@/providers/AuthProvider";
import { onLocationPicked, type PickedLocation } from "@/lib/location-picker";
import Svg, { Circle, Rect, Path } from "react-native-svg";
import PinIcon from "@/assets/icons/location.svg";
import { useLocale } from "@/i18n/LocaleProvider";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg";

import {
  parseLocationEntries,
  type LocationEntry,
} from "@/lib/location-entries";

function AttachmentIcon({ camera = false }: { camera?: boolean }) {
  return (
    <Svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#666"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {camera ? (
        <>
          <Path d="M8 5 9.5 3h5L16 5h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
          <Circle cx={12} cy={13} r={4} />
        </>
      ) : (
        <>
          <Rect x={3} y={3} width={18} height={18} rx={3} />
          <Circle cx={8} cy={8} r={1.5} />
          <Path d="m3 17 5-5 4 4 4-6 5 7" />
        </>
      )}
    </Svg>
  );
}

export default function CreatePostScreen() {
  const { t, categoryLabel } = useLocale();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [photoSheetOpen, setPhotoSheetOpen] = useState(false);
  const pendingPhotoSource = useRef<"camera" | "library" | null>(null);
  const navigation = useNavigation();
  const isFocused = useIsFocused();
  const {
    type,
    editId,
    creationMethod,
    title: initialTitle,
    description: initialDescription,
    features: initialFeatures,
    categoryId,
    place: initialPlace,
    latitude,
    longitude,
    startAt,
    endAt,
    photoAssets,
    locationEntries: initialLocationEntries,
  } = useLocalSearchParams<{
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
    photoAssets?: string;
    locationEntries?: string;
  }>();
  const { user } = useAuth();
  const editing = !!editId;
  const isAiDraft = !editing && creationMethod === "AI_ASSISTED";
  const [existingPhotos, setExistingPhotos] = useState<string[]>([]);
  const [initializing, setInitializing] = useState(editing);
  const [initialError, setInitialError] = useState("");
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const lost = postType === "LOST";
  const [step, setStep] = useState(1);
  const scrollRef = useRef<ScrollView>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [step]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryError, setCategoryError] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [start, setStart] = useState<Date | null>(() =>
    startAt ? new Date(startAt) : null,
  );
  const [end, setEnd] = useState<Date | null>(() =>
    endAt ? new Date(endAt) : null,
  );
  const [place, setPlace] = useState(initialPlace ?? "");
  const [additionalLocations, setAdditionalLocations] = useState<
    LocationEntry[]
  >(() => parseLocationEntries(initialLocationEntries).slice(1));
  const locationScope = useId();
  const locationSequence = useRef(0);
  const locationRequest = useRef<{ requestId: string; rowId: string } | null>(
    null,
  );
  // AI 초안에서 전달된 특징도 일반 작성과 같은 입력란에서 수정할 수 있다.
  const [features, setFeatures] = useState(initialFeatures ?? "");
  const [title, setTitle] = useState(initialTitle ?? "");
  const [description, setDescription] = useState(initialDescription ?? "");
  const [photos, setPhotos] = useState<PostImageAsset[]>(() => {
    if (!photoAssets) return [];
    try {
      const parsed: unknown = JSON.parse(photoAssets);
      return Array.isArray(parsed)
        ? parsed.filter(
            (asset): asset is PostImageAsset =>
              typeof asset === "object" &&
              asset !== null &&
              "uri" in asset &&
              typeof asset.uri === "string",
          )
        : [];
    } catch {
      return [];
    }
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const savedId = useRef<string | null>(null);
  const uploaded = useRef(0);
  const pending = useRef(false);
  const [saved, setSaved] = useState(false);
  const [leaveAction, setLeaveAction] = useState<NavigationAction | null>(null);
  const [submissionComplete, setSubmissionComplete] = useState(false);
  usePreventRemove(
    isFocused &&
      !isAiDraft &&
      !initializing &&
      !initialError &&
      !submissionComplete,
    ({ data }) => {
      if (pending.current) return;
      if (!saved && step === 2) {
        setStep(1);
        return;
      }
      Keyboard.dismiss();
      setLeaveAction(data.action);
    },
  );
  const confirmLeave = () => {
    if (!leaveAction || pending.current) return;
    const action = leaveAction;
    setLeaveAction(null);
    navigation.dispatch(action);
  };
  useEffect(() => {
    if (!submissionComplete) return;
    if (editId) {
      router.dismissTo({
        pathname: "/post/[id]",
        params: { id: editId, refresh: String(Date.now()) },
      });
      return;
    }
    if (!savedId.current) return;
    // Keep Home underneath the published post so back uses the stack pop animation.
    navigation.dispatch(CommonActions.reset({
      index: 1,
      routes: [
        { name: "(tabs)", params: { screen: "index", params: { board: postType, refresh: String(Date.now()) } } },
        { name: "post/[id]", params: { id: savedId.current } },
      ],
    }));
  }, [submissionComplete, editId, postType, router, navigation]);
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
        const target = locationRequest.current;
        if (!target || target.requestId !== location.requestId) return;
        locationRequest.current = null;
        if (target.rowId === "primary") {
          setPicked(location);
          setPlace((current) => (current.trim() ? current : location.address));
        } else {
          setAdditionalLocations((current) =>
            current.map((row) =>
              row.id === target.rowId
                ? {
                    ...row,
                    text: row.text.trim() ? row.text : location.address,
                    pin: location,
                  }
                : row,
            ),
          );
        }
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
          if (!editId) {
            setCategory(
              (current) =>
                current ??
                items.find((item) => item.id === Number(categoryId)) ??
                items.find((item) => item.code === "OTHER") ??
                null,
            );
          }
        }
      })
      .catch(() => {
        if (active) setCategoryError(t("createPost.categoryLoadFailed"));
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
        setCategory(
          items.find((item) => item.id === post.category_id) ??
            items.find((item) => item.code === "OTHER") ??
            null,
        );
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
            error instanceof Error ? error.message : t("common.postLoadFailed"),
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
    if (!saved && step === 2) setStep(1);
    else if (saved) router.replace("/");
    else if (router.canGoBack()) router.back();
    else router.replace("/");
  };
  const openLocationMap = (row: LocationEntry) => {
    Keyboard.dismiss();
    const requestId = `${locationScope}:${++locationSequence.current}`;
    locationRequest.current = { requestId, rowId: row.id };
    router.push({
      pathname: "/create-post-map",
      params: {
        requestId,
        ...(row.pin
          ? {
              latitude: String(row.pin.latitude),
              longitude: String(row.pin.longitude),
            }
          : {}),
      },
    });
  };
  const changeLocationText = (id: string, text: string) => {
    if (id === "primary") setPlace(text);
    else
      setAdditionalLocations((current) =>
        current.map((row) => (row.id === id ? { ...row, text } : row)),
      );
  };
  const removeLocation = (id: string) => {
    if (id === "primary") {
      const [next, ...rest] = additionalLocations;
      if (!next) return;
      setPlace(next.text);
      setPicked(next.pin);
      setAdditionalLocations(rest);
    } else
      setAdditionalLocations((current) =>
        current.filter((row) => row.id !== id),
      );
  };
  const selectPhotoSource = (source: "camera" | "library") => {
    setPhotoSheetOpen(false);
    if (Platform.OS === "ios") pendingPhotoSource.current = source;
    else void pick(source);
  };
  const pick = async (source: "camera" | "library") => {
    if (photos.length + existingPhotos.length >= 5 || saved || busy) return;
    try {
      if (source === "camera" && Platform.OS !== "web") {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          setError(t("ai.cameraPermission"));
          return;
        }
      }
      const result =
        source === "camera"
          ? await ImagePicker.launchCameraAsync({
              mediaTypes: ["images"],
              quality: 0.8,
            })
          : await ImagePicker.launchImageLibraryAsync({
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
      setError(
        t(
          source === "camera"
            ? "ai.cameraFailed"
            : "createPost.photoPermission",
        ),
      );
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
      if (!features.trim()) {
        setError(t("createPost.featuresRequired"));
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
          : await (
              creationMethod === "AI_ASSISTED"
                ? postsApi.createAiAssisted
                : postsApi.create
            )(
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
      setSubmissionComplete(true);
    } catch (error) {
      setError(
        (savedId.current ? t("createPost.uploadIncomplete") : "") +
          (error instanceof Error
            ? error.message
            : t("createPost.submitFailed")),
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
    required = false,
  ) => (
    <View style={styles.field}>
      <Text style={styles.label}>
        {label}
        {required ? <Text style={styles.required}> *</Text> : null}
      </Text>
      <TextInput
        accessibilityLabel={
          required ? t("createPost.requiredField", { field: label }) : label
        }
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
  const submitDisabled =
    busy ||
    (step === 1
      ? !category || !features.trim()
      : !acknowledged || !title.trim() || !description.trim());
  if (initializing || initialError)
    return (
      <SafeAreaView style={styles.root}>
        <Pressable onPress={back} style={styles.back}>
          <ChevronLeftIcon width={24} height={24} color={"#000000"} />
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
            <ChevronLeftIcon width={24} height={24} color={"#000000"} />
          </Pressable>
          <Text style={styles.headerTitle}>
            {editing
              ? t("createPost.editTitle")
              : t("createPost.creatingTitle")}
          </Text>
          <View style={styles.back} />
        </View>
        <ScrollView
          ref={scrollRef}
          style={styles.scroll}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.sectionHeader}>
            <Text style={styles.title}>
              {step === 1
                ? t("createPost.stepOne")
                : lost
                  ? t("createPost.stepTwoLost")
                  : t("createPost.stepTwoFound")}
            </Text>
            <View
              style={styles.steps}
              accessibilityLabel={t("createPost.stepProgress", { step })}
            >
              <View style={[styles.circle, styles.active]}>
                <Text style={[styles.stepText, styles.activeStepText]}>1</Text>
              </View>
              <View
                style={[
                  styles.stepConnector,
                  step === 2 && styles.activeConnector,
                ]}
              />
              <View style={[styles.circle, step === 2 && styles.active]}>
                <Text
                  style={[styles.stepText, step === 2 && styles.activeStepText]}
                >
                  2
                </Text>
              </View>
            </View>
          </View>
          {step === 1 ? (
            <>
              <View style={styles.field}>
                <Text style={styles.label}>
                  {t("createPost.category")}
                  <Text style={styles.required}> *</Text>
                </Text>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={t("createPost.requiredField", {
                    field: t("createPost.category"),
                  })}
                  accessibilityValue={{
                    text: category
                      ? categoryLabel(category.code, category.name)
                      : categoryLabel("OTHER"),
                  }}
                  accessibilityState={{
                    expanded: categoryOpen,
                    disabled: busy || saved,
                  }}
                  disabled={busy || saved}
                  onPress={() => {
                    Keyboard.dismiss();
                    setCategoryOpen(true);
                  }}
                  style={({ pressed }) => [
                    styles.categoryTrigger,
                    pressed && styles.categoryTriggerPressed,
                  ]}
                >
                  <CategoryIcon code={category?.code ?? "OTHER"} size={18} />
                  <Text numberOfLines={1} style={styles.categoryValueText}>
                    {category
                      ? categoryLabel(category.code, category.name)
                      : categoryLabel("OTHER")}
                  </Text>
                </Pressable>
                {categoryError ? (
                  <Text style={styles.hint}>{categoryError}</Text>
                ) : null}
              </View>
              <View style={styles.field}>
                <View style={styles.labelRow}>
                  <Text style={styles.label}>
                    {lost ? t("createPost.lost") : t("createPost.found")}{" "}
                    {t("createPost.dateTime")}{" "}
                  </Text>
                  {start || end ? (
                    <Pressable
                      accessibilityRole="button"
                      disabled={busy || saved}
                      hitSlop={8}
                      onPress={() => {
                        setStart(null);
                        setEnd(null);
                      }}
                    >
                      <Text style={styles.clearTime}>
                        {t("createPost.clearTime")}
                      </Text>
                    </Pressable>
                  ) : null}
                </View>
                <View style={styles.timeRange}>
                  <DateTimeField
                    compact
                    disabled={busy || saved}
                    label={t("createPost.startShort")}
                    value={start}
                    onChange={setStart}
                  />
                  <DateTimeField
                    compact
                    disabled={busy || saved}
                    label={t("createPost.endShort")}
                    value={end}
                    onChange={setEnd}
                  />
                </View>
              </View>
              <View style={styles.field}>
                <Text style={styles.label}>
                  {t(
                    lost
                      ? "createPost.lostLocation"
                      : "createPost.foundLocation",
                  )}
                </Text>
                {[
                  { id: "primary", text: place, pin: picked },
                  ...additionalLocations,
                ].map((row, index) => (
                  <View key={row.id} style={styles.locationEntry}>
                    <View style={styles.locationRow}>
                      <TextInput
                        accessibilityLabel={t("createPost.locationNumber", {
                          index: index + 1,
                        })}
                        value={row.text}
                        onChangeText={(text) =>
                          changeLocationText(row.id, text)
                        }
                        editable={!busy && !saved}
                        placeholder={t("createPost.locationExample")}
                        placeholderTextColor="#BDBDBD"
                        maxLength={255}
                        style={[styles.input, styles.locationInput]}
                      />
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={t(
                          row.pin
                            ? "createPost.changeMapLocation"
                            : "createPost.pickOnMap",
                        )}
                        accessibilityHint={
                          row.pin ? t("createPost.mapMarkedHint") : undefined
                        }
                        disabled={busy || saved}
                        onPress={() => openLocationMap(row)}
                        style={[
                          styles.locationMapButton,
                          row.pin && styles.locationMapDone,
                        ]}
                      >
                        {row.pin ? (
                          <Svg
                            width={16}
                            height={16}
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke={Colors.primary}
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <Path d="m5 12 4 4L19 6" />
                          </Svg>
                        ) : (
                          <PinIcon width={16} height={16} />
                        )}
                        <Text style={styles.locationMapText}>
                          {t(
                            row.pin
                              ? "createPost.mapMarked"
                              : "createPost.addMap",
                          )}
                        </Text>
                      </Pressable>
                      {additionalLocations.length > 0 ? (
                        <Pressable
                          accessibilityRole="button"
                          accessibilityLabel={t("createPost.removeLocation", {
                            index: index + 1,
                          })}
                          disabled={busy || saved}
                          onPress={() => removeLocation(row.id)}
                          style={styles.removeLocation}
                        >
                          <Svg
                            width={16}
                            height={16}
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="#8B938E"
                            strokeWidth={1.8}
                            strokeLinecap="round"
                          >
                            <Path d="m6 6 12 12M18 6 6 18" />
                          </Svg>
                        </Pressable>
                      ) : null}
                    </View>
                    {row.pin && row.pin.address !== row.text ? (
                      <Text numberOfLines={2} style={styles.locationAddress}>
                        {row.pin.address}
                      </Text>
                    ) : null}
                  </View>
                ))}
                <Pressable
                  accessibilityRole="button"
                  disabled={busy || saved}
                  onPress={() =>
                    setAdditionalLocations((current) => [
                      ...current,
                      {
                        id: `extra-${++locationSequence.current}`,
                        text: "",
                        pin: null,
                      },
                    ])
                  }
                  style={styles.addLocation}
                >
                  <Svg
                    width={15}
                    height={15}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={Colors.primary}
                    strokeWidth={1.8}
                    strokeLinecap="round"
                  >
                    <Path d="M12 5v14M5 12h14" />
                  </Svg>
                  <Text style={styles.addLocationText}>
                    {t("createPost.addLocation")}
                  </Text>
                </Pressable>
              </View>
              {input(
                t("createPost.features"),
                features,
                setFeatures,
                t("createPost.featuresExample"),
                true,
                undefined,
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
                true,
              )}
              {input(
                t("createPost.description"),
                description,
                setDescription,
                t("createPost.descriptionPlaceholder"),
                true,
                undefined,
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
                      onPress={() => {
                        Keyboard.dismiss();
                        setPhotoSheetOpen(true);
                      }}
                      style={styles.addPhoto}
                      accessibilityLabel={t("createPost.addPhoto")}
                    >
                      <Text style={styles.addText}>＋</Text>
                      <Text style={styles.hint}>
                        {t("createPost.addPhoto")}
                      </Text>
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
        </ScrollView>
        <View style={styles.footer}>
          <Pressable
            disabled={submitDisabled}
            accessibilityState={{
              disabled: submitDisabled,
              busy,
            }}
            onPress={() => void submit()}
            style={[styles.button, submitDisabled && { opacity: 0.6 }]}
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
        </View>
        <Modal
          visible={categoryOpen}
          transparent
          animationType="fade"
          onRequestClose={() => setCategoryOpen(false)}
        >
          <View style={styles.dim}>
            <Pressable
              style={StyleSheet.absoluteFill}
              accessibilityRole="button"
              accessibilityLabel={t("common.close")}
              onPress={() => setCategoryOpen(false)}
            />
            <View
              style={styles.categoryMenu}
              accessibilityViewIsModal
              onAccessibilityEscape={() => setCategoryOpen(false)}
            >
              <View style={styles.categoryHeader}>
                <Text accessibilityRole="header" style={styles.categoryTitle}>
                  {t("createPost.chooseCategory")}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={t("common.close")}
                  onPress={() => setCategoryOpen(false)}
                  style={({ pressed }) => [
                    styles.categoryClose,
                    pressed && styles.categoryPressed,
                  ]}
                >
                  <XIcon width={22} height={22} color="#69736C" />
                </Pressable>
              </View>
              <ScrollView
                showsVerticalScrollIndicator={false}
                contentContainerStyle={styles.categoryList}
              >
                {categories.map((item) => (
                  <Pressable
                    key={item.id}
                    accessibilityRole="button"
                    accessibilityState={{ selected: category?.id === item.id }}
                    onPress={() => {
                      setCategory(item);
                      setCategoryOpen(false);
                      setError("");
                    }}
                    style={({ pressed }) => [
                      styles.category,
                      category?.id === item.id && styles.categorySelected,
                      pressed && styles.categoryPressed,
                    ]}
                  >
                    <View style={styles.categoryIcon}>
                      <CategoryIcon code={item.code} />
                    </View>
                    <Text style={styles.categoryText}>
                      {categoryLabel(item.code, item.name)}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
      <AppModal
        visible={leaveAction !== null}
        title={t(
          saved
            ? "createPost.savedTitle"
            : editing
              ? "createPost.cancelEditTitle"
              : "createPost.cancelCreateTitle",
        )}
        description={t(
          saved
            ? "createPost.cancelSavedDescription"
            : editing
              ? "createPost.cancelEditDescription"
              : "createPost.cancelCreateDescription",
        )}
        confirmLabel={t("common.leave")}
        cancelLabel={t("common.continueWriting")}
        onConfirm={confirmLeave}
        onClose={() => setLeaveAction(null)}
      />
      <Modal
        visible={photoSheetOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setPhotoSheetOpen(false)}
        onDismiss={() => {
          const source = pendingPhotoSource.current;
          pendingPhotoSource.current = null;
          if (source) void pick(source);
        }}
      >
        <View style={styles.sheetOverlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityRole="button"
            accessibilityLabel={t("ai.closePhotoMenu")}
            onPress={() => setPhotoSheetOpen(false)}
          />
          <View
            style={[
              styles.photoSheet,
              { paddingBottom: Math.max(insets.bottom, 16) },
            ]}
            accessibilityViewIsModal
          >
            <View style={styles.sheetHandle} />
            <Pressable
              accessibilityRole="button"
              onPress={() => selectPhotoSource("camera")}
              style={({ pressed }) => [
                styles.photoOption,
                pressed && styles.photoOptionPressed,
              ]}
            >
              <AttachmentIcon camera />
              <Text style={styles.photoOptionText}>{t("ai.takePhoto")}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => selectPhotoSource("library")}
              style={({ pressed }) => [
                styles.photoOption,
                pressed && styles.photoOptionPressed,
              ]}
            >
              <AttachmentIcon />
              <Text style={styles.photoOptionText}>{t("ai.attachImage")}</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  sheetOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.35)",
  },
  photoSheet: {
    backgroundColor: "white",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  sheetHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#DDD",
    alignSelf: "center",
    marginBottom: 12,
  },
  photoOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingHorizontal: 12,
    minHeight: 58,
    borderRadius: 12,
  },
  photoOptionPressed: { backgroundColor: "#F1F3F2" },
  photoOptionText: {
    color: "#222",
    fontSize: 16,
    fontFamily: Fonts.pretendardMedium,
  },

  locationEntry: { gap: 4 },
  locationRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  locationInput: { flex: 1, minWidth: 0 },
  locationMapButton: {
    minHeight: 48,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: "#D9E4DE",
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  locationMapDone: {
    backgroundColor: Colors.softgreen,
    borderColor: "#C8DFD5",
  },
  locationMapText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 12,
    color: Colors.primary,
  },
  removeLocation: {
    width: 24,
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
  },
  locationAddress: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 11,
    lineHeight: 16,
    color: "#8B938E",
    paddingHorizontal: 2,
  },
  addLocation: {
    alignSelf: "flex-start",
    minHeight: 36,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  addLocationText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
    color: Colors.primary,
  },
  locationNotice: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 11,
    lineHeight: 17,
    color: "#8B938E",
  },
  required: { color: "#E5484D" },
  scroll: { flex: 1 },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingBottom: 2,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  timeRange: { gap: 8 },
  clearTime: {
    color: "#8A928E",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
  },
  mapLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    minHeight: 32,
    paddingHorizontal: 2,
  },
  mapLinkText: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardMedium,
    fontSize: 12,
  },
  activeConnector: { backgroundColor: Colors.primary },
  footer: {
    width: "100%",
    maxWidth: 540,
    alignSelf: "center",
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 12,
    borderTopWidth: 1,
    borderTopColor: "#EEF1EF",
    backgroundColor: "white",
  },
  root: { flex: 1, backgroundColor: "#FFF" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    height: 56,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  headerTitle: {
    fontSize: 18,
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
    gap: 20,
    width: "100%",
    maxWidth: 540,
    alignSelf: "center",
  },
  steps: { flexDirection: "row", alignItems: "center" },
  circle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: "#C6C6C6",
    alignItems: "center",
    justifyContent: "center",
  },
  active: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  title: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 22,
    color: "#111",
    flex: 1,
  },
  field: { gap: 8 },
  label: { fontFamily: Fonts.pretendardMedium, fontSize: 16, color: "#111" },
  hint: { color: "#999", fontSize: 13, fontFamily: Fonts.pretendardRegular },
  input: {
    borderWidth: 1,
    borderColor: "#D6D6D6",
    borderRadius: 12,
    minHeight: 48,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: "#111",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
  },
  multiline: { minHeight: 88, textAlignVertical: "top" },
  categoryTrigger: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#F4F5F4",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  categoryTriggerPressed: { backgroundColor: "#EDEFED" },
  categoryValueText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    color: "#3D4841",
    flexShrink: 1,
  },
  stepConnector: { width: 12, height: 1, backgroundColor: "#C6C6C6" },
  stepText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 11,
    color: "#A5A5A5",
  },
  activeStepText: { color: "white" },
  notice: { gap: 8, marginTop: 0 },
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
    minHeight: 48,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 0,
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
    alignItems: "center",
    padding: 24,
  },
  categoryMenu: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: "white",
    borderRadius: 22,
    padding: 20,
    maxHeight: "80%",
    gap: 8,
  },
  categoryHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingLeft: 4,
    paddingBottom: 6,
  },
  categoryTitle: {
    flex: 1,
    fontSize: 21,
    lineHeight: 28,
    fontFamily: Fonts.pretendardSemiBold,
    color: "#171C19",
  },
  categoryClose: {
    width: 44,
    height: 44,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  categoryList: { gap: 3 },
  category: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderRadius: 12,
  },
  categoryIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: "#F1F3F2",
    justifyContent: "center",
    alignItems: "center",
  },
  categoryText: {
    flexShrink: 1,
    fontFamily: Fonts.pretendardMedium,
    fontSize: 15,
    color: "#303832",
  },
  categorySelected: { backgroundColor: "#F1F6F3" },
  categoryPressed: { backgroundColor: "#EDF1EE" },
});
