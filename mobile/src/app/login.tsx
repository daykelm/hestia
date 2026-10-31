import { router } from "expo-router";
import { useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { WebView, type WebViewNavigation } from "react-native-webview";
import { BASE } from "../lib/api";
import { useStore } from "../lib/store";
import { color, serif } from "../lib/theme";

/**
 * Cloudflare Access login runs in a web view. Its cookie lands in Android's shared cookie store,
 * which the app's own requests to hestia.trading also use.
 */
export default function Login() {
  const { signedIn } = useStore();
  const done = useRef(false);
  const [loading, setLoading] = useState(true);

  function onChange(state: WebViewNavigation) {
    const url = state.url || "";
    const home = url.startsWith(`${BASE}/`) && !url.includes("/cdn-cgi/");
    if (home && !state.loading && !done.current) {
      done.current = true;
      signedIn();
      router.replace("/");
    }
  }

  return (
    <View style={styles.root}>
      <Text style={styles.title}>Sign in to Hestia</Text>
      <Text style={styles.note}>Use the same Cloudflare login as hestia.trading. You stay signed in on this phone.</Text>
      <View style={styles.frame}>
        <WebView
          source={{ uri: `${BASE}/` }}
          onNavigationStateChange={onChange}
          onLoadEnd={() => setLoading(false)}
          sharedCookiesEnabled
          thirdPartyCookiesEnabled
          style={styles.web}
        />
        {loading ? <ActivityIndicator style={styles.spinner} color={color.dust} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.sky, padding: 16 },
  title: { color: color.dust, fontFamily: serif, fontSize: 30, marginTop: 8 },
  note: { color: color.quiet, fontSize: 14, marginTop: 6, marginBottom: 14 },
  frame: { flex: 1, borderRadius: 3, overflow: "hidden", borderColor: color.chart, borderWidth: 1 },
  web: { flex: 1, backgroundColor: color.sky },
  spinner: { position: "absolute", top: 24, alignSelf: "center" },
});
