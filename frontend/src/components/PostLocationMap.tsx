import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";

type Props = {
  latitude: number;
  longitude: number;
};

export default function PostLocationMap({ latitude, longitude }: Props) {
  return (
    <MapView
      provider={PROVIDER_GOOGLE}
      style={{ height: 200 }}
      scrollEnabled={false}
      initialRegion={{
        latitude,
        longitude,
        latitudeDelta: 0.005,
        longitudeDelta: 0.005,
      }}
    >
      <Marker coordinate={{ latitude, longitude }} />
    </MapView>
  );
}
