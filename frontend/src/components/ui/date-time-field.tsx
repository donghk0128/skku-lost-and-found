import { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import XIcon from "@/assets/icons/x.svg";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

type Props = {
  value: Date | null;
  onChange: (value: Date) => void;
  label?: string;
  compact?: boolean;
  disabled?: boolean;
};
const pad = (value: number) => String(value).padStart(2, "0");

/** A local date/time field. Changes are committed only when the user confirms. */
export default function DateTimeField({
  value,
  onChange,
  label,
  compact = false,
  disabled = false,
}: Props) {
  const { locale, t } = useLocale();
  const fieldLabel = label ?? t("datetime.eventTime");
  const weekdays = [
    t("datetime.weekdaySun"),
    t("datetime.weekdayMon"),
    t("datetime.weekdayTue"),
    t("datetime.weekdayWed"),
    t("datetime.weekdayThu"),
    t("datetime.weekdayFri"),
    t("datetime.weekdaySat"),
  ];
  // Retain the current content until the native fade-out finishes.
  const [mode, setMode] = useState<"date" | "time">("date");
  const [pickerVisible, setPickerVisible] = useState(false);
  const [hasSelection, setHasSelection] = useState(false);
  const [draft, setDraft] = useState(() => new Date());
  const [month, setMonth] = useState(() => new Date());
  const open = (nextMode: "date" | "time") => {
    const initial = new Date(value ?? new Date());
    initial.setSeconds(0, 0);
    setHasSelection(false);
    setDraft(initial);
    setMonth(new Date(initial.getFullYear(), initial.getMonth(), 1));
    setMode(nextMode);
    setPickerVisible(true);
  };
  const changeMonth = (offset: number) =>
    setMonth(
      (current) =>
        new Date(current.getFullYear(), current.getMonth() + offset, 1),
    );
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1).getDay();
  const dayCount = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const selectedDay =
    draft.getFullYear() === month.getFullYear() &&
    draft.getMonth() === month.getMonth()
      ? draft.getDate()
      : null;
  const chooseDay = (day: number) => {
    setHasSelection(true);
    setDraft(
      (current) =>
        new Date(
          month.getFullYear(),
          month.getMonth(),
          day,
          current.getHours(),
          current.getMinutes(),
        ),
    );
  };
  const chooseTime = (unit: "hour" | "minute", number: number) => {
    setHasSelection(true);
    setDraft((current) => {
      const next = new Date(current);
      if (unit === "hour") next.setHours(number);
      else next.setMinutes(number);
      return next;
    });
  };
  return (
    <View style={[styles.field, compact && styles.compactField]}>
      {compact ? <Text style={styles.compactLabel}>{fieldLabel}</Text> : null}
      <View style={styles.inputs}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("datetime.selectDateAccessibility", {
            label: fieldLabel,
          })}
          disabled={disabled}
          onPress={() => open("date")}
          style={[
            styles.trigger,
            compact && styles.compactTrigger,
            disabled && styles.disabled,
          ]}
        >
          <Text
            numberOfLines={1}
            style={[
              styles.triggerText,
              compact && styles.compactText,
              !value && styles.placeholder,
            ]}
          >
            {value
              ? `${value.getFullYear()}.${pad(value.getMonth() + 1)}.${pad(value.getDate())}`
              : t("datetime.dateShort")}
          </Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("datetime.selectTimeAccessibility", {
            label: fieldLabel,
          })}
          disabled={disabled}
          onPress={() => open("time")}
          style={[
            styles.trigger,
            compact && styles.compactTrigger,
            disabled && styles.disabled,
          ]}
        >
          <Text
            numberOfLines={1}
            style={[
              styles.triggerText,
              compact && styles.compactText,
              !value && styles.placeholder,
            ]}
          >
            {value
              ? `${pad(value.getHours())}:${pad(value.getMinutes())}`
              : t("datetime.timeShort")}
          </Text>
        </Pressable>
      </View>
      <Modal
        visible={pickerVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setPickerVisible(false)}
        statusBarTranslucent
      >
        <View style={styles.overlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityLabel={t("datetime.cancelSelection")}
            onPress={() => setPickerVisible(false)}
          />
          <View style={styles.dialog} accessibilityViewIsModal>
            <ScrollView
              showsVerticalScrollIndicator={false}
              contentContainerStyle={styles.dialogContent}
            >
              <View style={styles.header}>
                {mode === "date" ? (
                  <View style={styles.monthControls}>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={t("datetime.previousMonth")}
                      onPress={() => changeMonth(-1)}
                      style={({ pressed }) => [
                        styles.monthControl,
                        pressed && styles.pressed,
                      ]}
                    >
                      <ChevronLeftIcon width={18} height={18} color="#303A35" />
                    </Pressable>
                    <Text style={styles.month}>
                      {month.getFullYear()}/{pad(month.getMonth() + 1)}
                    </Text>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={t("datetime.nextMonth")}
                      onPress={() => changeMonth(1)}
                      style={({ pressed }) => [
                        styles.monthControl,
                        pressed && styles.pressed,
                      ]}
                    >
                      <View style={styles.nextArrow}>
                        <ChevronLeftIcon
                          width={18}
                          height={18}
                          color="#303A35"
                        />
                      </View>
                    </Pressable>
                  </View>
                ) : (
                  <Text style={styles.month}>
                    {pad(draft.getHours())}:{pad(draft.getMinutes())}
                  </Text>
                )}
                <View style={styles.headerActions}>
                  {hasSelection ? (
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => {
                        onChange(new Date(draft));
                        setPickerVisible(false);
                      }}
                      style={({ pressed }) => [
                        styles.confirmAction,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text style={styles.confirmText}>
                        {t("datetime.done")}
                      </Text>
                    </Pressable>
                  ) : null}
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={t("datetime.close")}
                    onPress={() => setPickerVisible(false)}
                    style={({ pressed }) => [
                      styles.closeAction,
                      pressed && styles.pressed,
                    ]}
                  >
                    <XIcon width={22} height={22} color="#535F58" />
                  </Pressable>
                </View>
              </View>
              {mode === "date" ? (
                <>
                  <View style={styles.grid}>
                    {weekdays.map((day, index) => (
                      <View key={day} style={styles.weekdayCell}>
                        <Text
                          style={[styles.weekday, index === 0 && styles.sunday]}
                        >
                          {day}
                        </Text>
                      </View>
                    ))}
                  </View>
                  <View style={styles.grid}>
                    {Array.from(
                      { length: Math.ceil((firstDay + dayCount) / 7) * 7 },
                      (_, index) => {
                        const day = index - firstDay + 1;
                        if (day < 1 || day > dayCount)
                          return <View key={index} style={styles.cell} />;
                        const selected =
                          selectedDay === day &&
                          (hasSelection || value !== null);
                        return (
                          <Pressable
                            key={index}
                            accessibilityRole="button"
                            accessibilityLabel={t(
                              "datetime.dateAccessibility",
                              {
                                date: new Intl.DateTimeFormat(
                                  locale === "en" ? "en-US" : "ko-KR",
                                  {
                                    dateStyle: "full",
                                  },
                                ).format(
                                  new Date(
                                    month.getFullYear(),
                                    month.getMonth(),
                                    day,
                                  ),
                                ),
                              },
                            )}
                            accessibilityState={{ selected }}
                            onPress={() => chooseDay(day)}
                            style={styles.cell}
                          >
                            <View
                              style={[styles.day, selected && styles.selected]}
                            >
                              <Text
                                style={[
                                  styles.dayText,
                                  index % 7 === 0 && styles.sunday,
                                  selected && styles.selectedText,
                                ]}
                              >
                                {day}
                              </Text>
                            </View>
                          </Pressable>
                        );
                      },
                    )}
                  </View>
                </>
              ) : (
                <>
                  <View style={styles.timeColumns}>
                    {(["hour", "minute"] as const).map((unit) => (
                      <View key={unit} style={styles.timeColumn}>
                        <Text style={styles.caption}>
                          {unit === "hour"
                            ? t("datetime.hours")
                            : t("datetime.minutes")}
                        </Text>
                        <ScrollView
                          style={styles.timeList}
                          nestedScrollEnabled
                          contentContainerStyle={styles.timeOptions}
                        >
                          {Array.from(
                            { length: unit === "hour" ? 24 : 60 },
                            (_, number) => {
                              const selected =
                                number ===
                                (unit === "hour"
                                  ? draft.getHours()
                                  : draft.getMinutes());
                              return (
                                <Pressable
                                  key={number}
                                  accessibilityRole="button"
                                  accessibilityLabel={`${number} ${unit === "hour" ? t("datetime.hours") : t("datetime.minutes")}`}
                                  accessibilityState={{ selected }}
                                  onPress={() => chooseTime(unit, number)}
                                  style={[
                                    styles.timeOption,
                                    selected && styles.softSelected,
                                  ]}
                                >
                                  <Text
                                    style={[
                                      styles.timeText,
                                      selected && styles.greenText,
                                    ]}
                                  >
                                    {pad(number)}
                                  </Text>
                                </Pressable>
                              );
                            },
                          )}
                        </ScrollView>
                      </View>
                    ))}
                  </View>
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}
const styles = StyleSheet.create({
  compactField: { alignItems: "center", gap: 8 },
  compactLabel: {
    width: 36,
    flexShrink: 0,
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    color: "#79817D",
  },
  compactTrigger: {
    minHeight: 44,
    paddingHorizontal: 12,
    backgroundColor: "#F4F5F4",
    borderRadius: 12,
    gap: 4,
  },
  compactText: { fontSize: 13 },
  disabled: { opacity: 0.5 },
  field: { flexDirection: "row", gap: 10 },
  inputs: { flex: 1, minWidth: 0, flexDirection: "row", gap: 8 },
  trigger: {
    flex: 1,
    flexBasis: 0,
    width: 0,
    minWidth: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    minHeight: 48,
    paddingHorizontal: 14,
    backgroundColor: "#F4F5F4",
    borderRadius: 16,
  },
  triggerText: {
    flexShrink: 1,
    minWidth: 0,
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    color: "#222",
  },
  placeholder: { color: "#999" },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.42)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  dialog: {
    width: "100%",
    maxWidth: 380,
    maxHeight: "90%",
    backgroundColor: "white",
    borderRadius: 20,
    overflow: "hidden",
  },
  dialogContent: { padding: 20, gap: 10 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  closeAction: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    flexShrink: 0,
  },
  confirmAction: {
    minHeight: 44,
    paddingHorizontal: 8,
    justifyContent: "center",
  },
  confirmText: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 14,
    color: Colors.primary,
  },
  pressed: { opacity: 0.6 },
  month: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 18,
    color: "#171C19",
  },
  monthControls: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    flexShrink: 1,
  },
  monthControl: {
    width: 32,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
  },
  nextArrow: { transform: [{ rotate: "180deg" }] },
  weekdayCell: {
    width: "14.285714%",
    minHeight: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  cell: {
    width: "14.285714%",
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  weekday: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    color: "#929D96",
  },
  day: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  dayText: { fontSize: 15, color: "#333", fontFamily: Fonts.pretendardMedium },
  sunday: { color: "#C06A6A" },
  selected: { backgroundColor: Colors.primary },
  selectedText: { color: "white" },
  caption: {
    textAlign: "center",
    fontSize: 12,
    color: "#888",
    fontFamily: Fonts.pretendardRegular,
  },
  timeColumns: { flexDirection: "row", gap: 16 },
  timeColumn: { flex: 1, gap: 8 },
  timeList: { height: 180, borderRadius: 14, backgroundColor: "#F8F8F8" },
  timeOptions: { padding: 6, gap: 4 },
  timeOption: {
    height: 42,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  softSelected: { backgroundColor: Colors.softgreen },
  timeText: { fontFamily: Fonts.pretendardMedium, fontSize: 18, color: "#666" },
  greenText: { color: Colors.primary },
});
