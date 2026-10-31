import { EBGaramond_500Medium, useFonts } from "@expo-google-fonts/eb-garamond";
import { Stack, router, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as Updates from "expo-updates";
import { useEffect } from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { StoreProvider, useStore } from "../lib/store";
import { color } from "../lib/theme";

SplashScreen.preventAutoHideAsync();

function UpdateBanner() {
  const { isUpdatePending } = Updates.useUpdates();
  if (!isUpdatePending) return null;
  return (
    <Pressable style={styles.update} onPress={() => Updates.reloadAsync()} accessibilityRole="button">
      <Text style={styles.updateText}>A new version of Hestia is ready. Tap to restart.</Text>
    </Pressable>
  );
}

function Gate() {
  const { signedOut } = useStore();
  const segments = useSegments();
  useEffect(() => {
    if (signedOut && segments[0] !== "login") router.replace("/login");
  }, [signedOut, segments]);
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: color.sky },
        animation: "slide_from_right",
      }}
    />
  );
}

export default function Root() {
  const [loaded] = useFonts({ EBGaramond_500Medium });
  useEffect(() => {
    if (loaded) SplashScreen.hideAsync();
  }, [loaded]);
  if (!loaded) return null;
  return (
    <SafeAreaProvider>
      <StoreProvider>
        <SafeAreaView style={styles.root} edges={["top", "left", "right"]}>
          <StatusBar style="light" />
          <UpdateBanner />
          <Gate />
        </SafeAreaView>
      </StoreProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.sky },
  update: { backgroundColor: color.plate, borderBottomColor: color.chart, borderBottomWidth: 1, paddingVertical: 12, paddingHorizontal: 16 },
  updateText: { color: color.amber, fontSize: 14 },
});
