import { useState } from "react";
import {
  Alert,
  Keyboard,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ThemedText } from "@/components/themed-text";
import {
  BottomTabInset,
  Colors,
  Fonts,
  MaxContentWidth,
} from "@/constants/theme";
import SettingIcon from "@/assets/icons/setting.svg";

type BoardTab = "lost" | "found";
type SortOrder = "recommended" | "latest";

export default function HomeScreen() {
  const [activeTab, setActiveTab] = useState<BoardTab>("lost");
  const [sortOrder, setSortOrder] = useState<SortOrder>("recommended");
  const [search, setSearch] = useState("");

  const changeTab = (tab: BoardTab) => {
    Keyboard.dismiss();
    setActiveTab(tab);
  };

  const toggleSort = () => {
    setSortOrder((current) =>
      current === "recommended" ? "latest" : "recommended",
    );
  };

  const handleWrite = () => {
    Alert.alert(
      "글쓰기",
      activeTab === "lost"
        ? "분실물 등록 화면을 연결해주세요."
        : "습득물 등록 화면을 연결해주세요.",
    );
  };

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
        <View style={styles.content}>
          {/* 헤더 */}
          <View style={styles.header}>
            <ThemedText type="title" style={styles.logo}>
              Lost & Found
            </ThemedText>

            <Pressable
              onPress={() => Alert.alert("설정", "설정 화면을 연결해주세요.")}
              accessibilityRole="button"
              accessibilityLabel="설정"
              hitSlop={8}
              style={({ pressed }) => [
                styles.settingsButton,
                pressed && styles.pressed,
              ]}
            >
              <SettingIcon />
            </Pressable>
          </View>

          {/* 게시판 탭 */}
          <View style={styles.tabs}>
            <Pressable
              onPress={() => changeTab("lost")}
              accessibilityRole="tab"
              accessibilityState={{
                selected: activeTab === "lost",
              }}
              style={[styles.tab, activeTab === "lost" && styles.activeTab]}
            >
              <ThemedText
                style={[
                  styles.tabText,
                  activeTab === "lost" && styles.activeTabText,
                ]}
              >
                분실했어요
              </ThemedText>
            </Pressable>

            <Pressable
              onPress={() => changeTab("found")}
              accessibilityRole="tab"
              accessibilityState={{
                selected: activeTab === "found",
              }}
              style={[styles.tab, activeTab === "found" && styles.activeTab]}
            >
              <ThemedText
                style={[
                  styles.tabText,
                  activeTab === "found" && styles.activeTabText,
                ]}
              >
                습득했어요
              </ThemedText>
            </Pressable>
          </View>

          {/* 정렬 · 필터 · 검색 */}
          <View style={styles.toolbar}>
            <Pressable
              onPress={toggleSort}
              accessibilityRole="button"
              accessibilityLabel="정렬 방식 변경"
              style={({ pressed }) => [
                styles.toolButton,
                pressed && styles.pressed,
              ]}
            >
              <ThemedText style={styles.sortIcon}>↕</ThemedText>

              <ThemedText type="small" style={styles.toolText}>
                {sortOrder === "recommended" ? "추천순" : "최신순"}
              </ThemedText>
            </Pressable>

            <Pressable
              onPress={() => Alert.alert("필터", "필터 기능을 연결해주세요.")}
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.toolButton,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.filterIcon}>
                <View style={styles.filterLine}>
                  <View style={styles.filterKnobLeft} />
                </View>
                <View style={styles.filterLine}>
                  <View style={styles.filterKnobRight} />
                </View>
              </View>

              <ThemedText type="small" style={styles.toolText}>
                필터
              </ThemedText>
            </Pressable>

            <View style={styles.searchBox}>
              <View style={styles.searchIcon}>
                <View style={styles.searchCircle} />
                <View style={styles.searchHandle} />
              </View>

              <TextInput
                style={styles.searchInput}
                placeholder="검색해보세요"
                placeholderTextColor="#9A9DA3"
                value={search}
                onChangeText={setSearch}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="search"
                onSubmitEditing={() => Keyboard.dismiss()}
                accessibilityLabel="게시글 검색"
              />
            </View>
          </View>

          {/* 게시글 리스트 영역 */}
          <View
            style={styles.boardArea}
            accessibilityLabel={
              activeTab === "lost" ? "분실물 게시판" : "습득물 게시판"
            }
          />

          {/* 글쓰기 버튼 */}
          <Pressable
            onPress={handleWrite}
            accessibilityRole="button"
            accessibilityLabel={
              activeTab === "lost" ? "분실물 등록" : "습득물 등록"
            }
            style={({ pressed }) => [
              styles.floatingButton,
              pressed && styles.floatingPressed,
            ]}
          >
            <View style={styles.plusHorizontal} />
            <View style={styles.plusVertical} />
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  safeArea: {
    flex: 1,
    width: "100%",
    maxWidth: MaxContentWidth,
    alignSelf: "center",
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingTop: 16,
    paddingBottom: 30,
  },
  logo: {
    color: "#111111",
    fontSize: 23,
    lineHeight: 32,
    letterSpacing: -0.7,
  },
  settingsButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  settingsIcon: {
    color: "#30353A",
    fontSize: 29,
    lineHeight: 36,
  },

  tabs: {
    flexDirection: "row",
    gap: 18,
    borderBottomWidth: 1,
    borderBottomColor: "#EEEEEF",
  },
  tab: {
    paddingTop: 4,
    paddingBottom: 12,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
    marginBottom: -1,
  },
  activeTab: {
    borderBottomColor: "#111111",
  },
  tabText: {
    color: "#9A9DA3",
    fontSize: 17,
    lineHeight: 26,
  },
  activeTabText: {
    color: "#111111",
  },

  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 16,
  },
  toolButton: {
    height: 42,
    paddingHorizontal: 12,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  toolText: {
    color: "#222222",
  },
  sortIcon: {
    color: "#30353A",
    fontSize: 19,
    lineHeight: 24,
  },

  filterIcon: {
    width: 15,
    height: 16,
    justifyContent: "space-evenly",
  },
  filterLine: {
    height: 1.5,
    backgroundColor: "#30353A",
    justifyContent: "center",
  },
  filterKnobLeft: {
    position: "absolute",
    left: 3,
    width: 5,
    height: 5,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: "#30353A",
    backgroundColor: "#FFFFFF",
  },
  filterKnobRight: {
    position: "absolute",
    right: 2,
    width: 5,
    height: 5,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: "#30353A",
    backgroundColor: "#FFFFFF",
  },

  searchBox: {
    flex: 1,
    minWidth: 0,
    height: 42,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    gap: 8,
  },
  searchIcon: {
    width: 18,
    height: 20,
  },
  searchCircle: {
    position: "absolute",
    top: 1,
    left: 0,
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 1.7,
    borderColor: "#30353A",
  },
  searchHandle: {
    position: "absolute",
    top: 13,
    left: 12,
    width: 7,
    height: 1.7,
    borderRadius: 1,
    backgroundColor: "#30353A",
    transform: [{ rotate: "45deg" }],
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    height: "100%",
    paddingVertical: 0,
    color: "#222222",
    fontSize: 13,
    fontFamily: Fonts.pretendardMedium,
  },

  boardArea: {
    flex: 1,
    marginTop: 20,
  },

  floatingButton: {
    position: "absolute",
    right: 24,
    bottom: BottomTabInset + 20,
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 5,
  },
  plusHorizontal: {
    position: "absolute",
    width: 26,
    height: 1.5,
    borderRadius: 1,
    backgroundColor: "#FFFFFF",
  },
  plusVertical: {
    position: "absolute",
    width: 1.5,
    height: 26,
    borderRadius: 1,
    backgroundColor: "#FFFFFF",
  },
  floatingPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.96 }],
  },
  pressed: {
    opacity: 0.6,
  },
});
