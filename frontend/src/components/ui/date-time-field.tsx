import { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Colors, Fonts } from "@/constants/theme";

type Props = {
  value: Date | null;
  onChange: (value: Date) => void;
  label?: string;
};
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
const pad = (value: number) => String(value).padStart(2, "0");

/** A local date/time field. Changes are committed only when the user confirms. */
export default function DateTimeField({
  value,
  onChange,
  label = "발생 시각",
}: Props) {
  const [mode, setMode] = useState<"date" | "time" | null>(null);
  const [draft, setDraft] = useState(() => new Date());
  const [month, setMonth] = useState(() => new Date());
  const open = (nextMode: "date" | "time") => {
    const initial = new Date(value ?? new Date());
    initial.setSeconds(0, 0);
    setDraft(initial);
    setMonth(new Date(initial.getFullYear(), initial.getMonth(), 1));
    setMode(nextMode);
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
  const chooseDay = (day: number) =>
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
  const chooseTime = (unit: "hour" | "minute", number: number) =>
    setDraft((current) => {
      const next = new Date(current);
      if (unit === "hour") next.setHours(number);
      else next.setMinutes(number);
      return next;
    });
  return (
    <View style={styles.field}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label} 날짜 선택`}
        onPress={() => open("date")}
        style={styles.trigger}
      >
        <Text style={[styles.triggerText, !value && styles.placeholder]}>
          {value
            ? `${value.getFullYear()}.${pad(value.getMonth() + 1)}.${pad(value.getDate())}`
            : "날짜 선택"}
        </Text>
        <Text style={styles.arrow}>⌄</Text>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label} 시간 선택`}
        onPress={() => open("time")}
        style={styles.trigger}
      >
        <Text style={[styles.triggerText, !value && styles.placeholder]}>
          {value
            ? `${pad(value.getHours())}:${pad(value.getMinutes())}`
            : "시간 선택"}
        </Text>
        <Text style={styles.arrow}>⌄</Text>
      </Pressable>
      <Modal
        visible={mode !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setMode(null)}
        statusBarTranslucent
      >
        <View style={styles.overlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityLabel="선택 취소"
            onPress={() => setMode(null)}
          />
          <View style={styles.dialog} accessibilityViewIsModal>
            <ScrollView
              showsVerticalScrollIndicator={false}
              contentContainerStyle={styles.dialogContent}
            >
              <View style={styles.header}>
                <View>
                  <Text style={styles.eyebrow}>{label}</Text>
                  <Text style={styles.title}>
                    {mode === "date" ? "날짜 선택" : "시간 선택"}
                  </Text>
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="닫기"
                  onPress={() => setMode(null)}
                  style={styles.close}
                >
                  <Text style={styles.closeText}>×</Text>
                </Pressable>
              </View>
              {mode === "date" ? (
                <>
                  <View style={styles.monthHeader}>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="이전 달"
                      onPress={() => changeMonth(-1)}
                      style={styles.close}
                    >
                      <Text style={styles.nav}>‹</Text>
                    </Pressable>
                    <Text style={styles.month}>
                      {month.getFullYear()}년 {month.getMonth() + 1}월
                    </Text>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="다음 달"
                      onPress={() => changeMonth(1)}
                      style={styles.close}
                    >
                      <Text style={styles.nav}>›</Text>
                    </Pressable>
                  </View>
                  <View style={styles.grid}>
                    {weekdays.map((day, index) => (
                      <View key={day} style={styles.cell}>
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
                        const selected = selectedDay === day;
                        return (
                          <Pressable
                            key={index}
                            accessibilityRole="button"
                            accessibilityLabel={`${month.getFullYear()}년 ${month.getMonth() + 1}월 ${day}일`}
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
                  <View style={styles.preview}>
                    <Text style={styles.previewText}>
                      {pad(draft.getHours())}
                      <Text style={styles.colon}> : </Text>
                      {pad(draft.getMinutes())}
                    </Text>
                    <Text style={styles.caption}>24시간 기준</Text>
                  </View>
                  <View style={styles.timeColumns}>
                    {(["hour", "minute"] as const).map((unit) => (
                      <View key={unit} style={styles.timeColumn}>
                        <Text style={styles.caption}>
                          {unit === "hour" ? "시" : "분"}
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
                                  accessibilityLabel={`${number}${unit === "hour" ? "시" : "분"}`}
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
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => setMode(null)}
                  style={styles.cancel}
                >
                  <Text style={styles.cancelText}>취소</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    onChange(new Date(draft));
                    setMode(null);
                  }}
                  style={styles.confirm}
                >
                  <Text style={styles.confirmText}>선택 완료</Text>
                </Pressable>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}
const styles = StyleSheet.create({
  field: { flexDirection: "row", gap: 10 },
  trigger: {
    flex: 1,
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
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    color: "#222",
  },
  placeholder: { color: "#999" },
  arrow: { color: "#888", fontSize: 18 },
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
    borderRadius: 26,
    overflow: "hidden",
  },
  dialogContent: { padding: 22, gap: 16 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  eyebrow: {
    fontSize: 12,
    color: "#888",
    fontFamily: Fonts.pretendardRegular,
    marginBottom: 6,
  },
  title: { fontFamily: Fonts.pretendardSemiBold, fontSize: 22, color: "#111" },
  close: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  closeText: { fontSize: 28, color: "#777" },
  monthHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  month: { fontFamily: Fonts.pretendardSemiBold, fontSize: 16, color: "#222" },
  nav: { fontSize: 28, color: "#555" },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  cell: {
    width: "14.285714%",
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  weekday: { fontFamily: Fonts.pretendardRegular, fontSize: 12, color: "#999" },
  day: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
  },
  dayText: { fontSize: 14, color: "#333", fontFamily: Fonts.pretendardMedium },
  sunday: { color: "#C06A6A" },
  selected: { backgroundColor: Colors.primary },
  selectedText: { color: "white" },
  preview: {
    padding: 16,
    backgroundColor: "#F4F8F6",
    borderRadius: 18,
    alignItems: "center",
    gap: 6,
  },
  previewText: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 36,
    color: Colors.primary,
  },
  colon: { color: "#A0B9B0" },
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
  actions: { flexDirection: "row", gap: 10, marginTop: 8 },
  cancel: {
    flex: 1,
    height: 48,
    borderRadius: 14,
    backgroundColor: "#F2F3F2",
    alignItems: "center",
    justifyContent: "center",
  },
  cancelText: {
    color: "#777",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
  },
  confirm: {
    flex: 2,
    height: 48,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  confirmText: {
    color: "white",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
  },
});
