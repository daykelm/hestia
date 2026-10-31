import { Image, StyleSheet, Text, View } from "react-native";
import { color } from "../lib/theme";

/** Same framing as the web: Esri World Imagery about 110 m across, the parcel in the middle. */
export function aerialUrl([lon, lat]: [number, number], width = 640, height = 400) {
  const halfLat = 0.0005;
  const halfLon = (halfLat * width) / height / Math.cos((lat * Math.PI) / 180);
  const box = [lon - halfLon, lat - halfLat, lon + halfLon, lat + halfLat].map((n) => n.toFixed(6)).join(",");
  return (
    "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export" +
    `?bbox=${box}&bboxSR=4326&imageSR=3857&size=${width},${height}&format=jpg&f=image`
  );
}

export function Aerial({ point, name }: { point: [number, number]; name: string }) {
  return (
    <View style={styles.frame}>
      <Image
        source={{ uri: aerialUrl(point) }}
        style={styles.image}
        resizeMode="cover"
        fadeDuration={200}
        accessibilityLabel={`Satellite view of ${name}`}
      />
      <View style={styles.pin} pointerEvents="none" />
      <Text style={styles.credit}>Satellite · Esri World Imagery</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { marginTop: 14, borderWidth: 1, borderColor: color.chart, borderRadius: 3, overflow: "hidden", backgroundColor: color.indigo },
  image: { width: "100%", aspectRatio: 16 / 10 },
  pin: {
    position: "absolute",
    left: "50%",
    top: "50%",
    width: 22,
    height: 22,
    marginLeft: -11,
    marginTop: -11,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: color.red,
  },
  credit: { position: "absolute", right: 0, bottom: 0, paddingHorizontal: 7, paddingVertical: 2, fontSize: 11, color: color.dust, backgroundColor: "rgba(10,16,33,0.7)" },
});
