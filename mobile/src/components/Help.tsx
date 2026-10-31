import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text } from "react-native";
import { useStore } from "../lib/store";
import { color, serif } from "../lib/theme";

/** The same explanations as the (!) buttons on the web desk, served by Hestia. */
export function Help({ topic }: { topic: string }) {
  const { guide } = useStore();
  const [open, setOpen] = useState(false);
  const entry = guide?.help[topic];
  if (!entry) return null;
  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={`What is ${entry.title}?`}
        style={styles.icon}
      >
        <Text style={styles.mark}>!</Text>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.scrim} onPress={() => setOpen(false)}>
          <Pressable style={styles.card} onPress={() => {}}>
            <Text style={styles.title}>{entry.title}</Text>
            <Text style={styles.text}>{entry.text}</Text>
            <Pressable style={styles.ok} onPress={() => setOpen(false)} accessibilityRole="button">
              <Text style={styles.okText}>Got it</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  icon: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.25,
    borderColor: color.quiet,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 6,
  },
  mark: { color: color.quiet, fontSize: 11, fontWeight: "700", lineHeight: 13 },
  scrim: { flex: 1, backgroundColor: "rgba(5,8,18,0.6)", justifyContent: "center", padding: 24 },
  card: { backgroundColor: color.plate, borderColor: color.chart, borderWidth: 1, borderRadius: 3, padding: 20 },
  title: { color: color.dust, fontFamily: serif, fontSize: 22, marginBottom: 8 },
  text: { color: color.quiet, fontSize: 15, lineHeight: 22 },
  ok: { marginTop: 16, minHeight: 44, borderRadius: 6, borderWidth: 1, borderColor: color.chart, backgroundColor: color.indigo, alignItems: "center", justifyContent: "center" },
  okText: { color: color.dust, fontSize: 15 },
});
