import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import * as Location from "expo-location";
import { SafeAreaView } from "react-native-safe-area-context";
import { Alert, View, Pressable, StyleSheet, Text } from "react-native";
import { router } from "expo-router";
import { Colors, Fonts } from "@/constants/theme";
import { pickLocation } from "@/lib/location-picker";
const googleMapsApiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;
// 대략 좌표이므로 실제 위치로 교체
const CAMPUSES = {
  humanities: { latitude: 37.5882, longitude: 126.9933 },
  science: { latitude: 37.2939, longitude: 126.9751 },
};
type LatLng = { latitude: number; longitude: number };

export default function CreatePostMap() {
  const mapRef = useRef<MapView>(null);
  const [pin, setPin] = useState<LatLng>();
  const [placeName, setPlaceName] = useState<string>();

  const moveTo = (target: LatLng) =>
    mapRef.current?.animateToRegion(
      { ...target, latitudeDelta: 0.01, longitudeDelta: 0.01 },
      400,
    );

  const goToMyLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        Alert.alert("위치 권한이 필요합니다.");
        return;
      }
      const { coords } = await Location.getCurrentPositionAsync({});
      const here = { latitude: coords.latitude, longitude: coords.longitude };
      setPin(here);
      moveTo(here);
    } catch {
      Alert.alert("현재 위치를 가져오지 못했습니다.");
    }
  };

  useEffect(() => {
    if (!pin) return;
    let active = true;
    axios
      .get<{ results: { formatted_address: string }[]; status: string }>(
        `https://maps.googleapis.com/maps/api/geocode/json?latlng=${pin.latitude},${pin.longitude}&language=ko&key=${googleMapsApiKey}`,
      )
      .then((res) => {
        if (!active) return;
        setPlaceName(
          res.data.results[0]?.formatted_address ?? "주소를 찾을 수 없는 위치",
        );
      })
      .catch(() => {
        if (active) setPlaceName("주소를 불러오지 못했습니다");
      });
    return () => {
      active = false;
    };
  }, [pin]);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#FFF" }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingHorizontal: 20,
          height: 64,
        }}
      >
        <Pressable onPress={() => router.back()} accessibilityLabel="뒤로가기">
          <Text style={{ fontSize: 36, color: "#111" }}>‹</Text>
        </Pressable>
        <Text
          style={{
            fontSize: 18,
            color: "#111",
            fontFamily: Fonts.pretendardSemiBold,
          }}
        >
          지도에서 선택
        </Text>
        <View style={{ width: 44, height: 44, justifyContent: "center" }} />
      </View>
      <View style={{ flex: 1 }}>
        <MapView
          ref={mapRef}
          provider={PROVIDER_GOOGLE}
          style={StyleSheet.absoluteFill}
          initialRegion={{
            ...CAMPUSES.science,
            latitudeDelta: 0.01,
            longitudeDelta: 0.01,
          }}
          zoomEnabled
          scrollEnabled
          showsMyLocationButton={false}
          onPress={(e) => setPin(e.nativeEvent.coordinate)}
        >
          {pin ? <Marker coordinate={pin} pinColor={Colors.primary} /> : null}
        </MapView>

        <View
          pointerEvents="box-none"
          style={{
            position: "absolute",
            top: 12,
            left: 16,
            right: 16,
            flexDirection: "row",
            gap: 8,
          }}
        >
          <Chip label="현재 위치" primary onPress={goToMyLocation} />
          <Chip
            label="인문사회캠퍼스"
            onPress={() => moveTo(CAMPUSES.humanities)}
          />
          <Chip
            label="자연과학캠퍼스"
            onPress={() => moveTo(CAMPUSES.science)}
          />
        </View>

        <View
          style={{
            position: "absolute",
            left: 16,
            right: 16,
            bottom: 16,
            padding: 18,
            borderRadius: 20,
            backgroundColor: "#FFF",
            shadowColor: "#000",
            shadowOpacity: 0.15,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 4 },
            elevation: 8,
          }}
        >
          <Text
            numberOfLines={2}
            style={{
              fontSize: 16,
              color: pin ? "#111" : "#888",
              fontFamily: Fonts.pretendardSemiBold,
            }}
          >
            {!pin
              ? "지도를 탭해서 위치를 선택해주세요"
              : (placeName ?? "위치를 확인하는 중...")}
          </Text>
          <Pressable
            disabled={!pin || !placeName}
            onPress={() => {
              if (!pin || !placeName) return;
              pickLocation({ address: placeName, ...pin });
              router.back();
            }}
            style={{
              marginTop: 12,
              height: 46,
              borderRadius: 12,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: Colors.primary,
              opacity: pin && placeName ? 1 : 0.4,
            }}
          >
            <Text
              style={{
                fontSize: 15,
                color: "#FFF",
                fontFamily: Fonts.pretendardMedium,
              }}
            >
              이 위치로 선택
            </Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

function Chip({
  label,
  onPress,
  primary,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 8,
        borderRadius: 999,
        backgroundColor: primary ? Colors.primary : "#FFF",
        shadowColor: "#000",
        shadowOpacity: 0.15,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
        elevation: 4,
      }}
    >
      <Text
        style={{
          fontSize: 13,
          color: primary ? "#FFF" : "#111",
          fontFamily: Fonts.pretendardMedium,
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}
