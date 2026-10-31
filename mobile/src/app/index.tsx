import { router } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { Help } from "../components/Help";
import { ScoreDot } from "../components/ScoreDot";
import { band, displayName, displayPlace, money, postForm, type Deal } from "../lib/api";
import { useStore } from "../lib/store";
import { bandColor, color, serif } from "../lib/theme";

const RANK: Record<string, number> = { excellent: 0, good: 1, fair: 2, thin: 3, risky: 4, "": 5 };
const BAND_ORDER = ["excellent", "good", "fair", "risky", "thin"] as const;

export default function Desk() {
  const { deals, guide, loading, error, refresh } = useStore();
  const [step, setStep] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const steps = guide?.steps || [];

  const lane = useMemo(() => {
    const wanted = step ? [step] : ["Found", "Researched"];
    const ratio = (d: Deal) => (d.metadata.roll_value || 0) / (d.price || 1);
    return deals
      .filter((d) => wanted.includes(d.status))
      .sort(
        (a, b) =>
          RANK[band(a)] - RANK[band(b)] ||
          (b.metadata.diligence?.score || 0) - (a.metadata.diligence?.score || 0) ||
          ratio(b) - ratio(a),
      );
  }, [deals, step]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const d of deals) {
      c[d.status] = (c[d.status] || 0) + 1;
      const b = band(d);
      if (b) c[`band:${b}`] = (c[`band:${b}`] || 0) + 1;
    }
    return c;
  }, [deals]);

  const stale = deals.filter((d) => (d.metadata.diligence?.version || 0) < (guide?.rules_version || 0)).length;

  async function scoreAll() {
    setBusy(true);
    try {
      let left = 1;
      while (left > 0) {
        const result = await postForm<{ scored: number; left: number; note: string }>("/api/score");
        setNote(result.note);
        left = result.scored ? result.left : 0;
      }
      await refresh();
    } catch {
      setNote("Scoring stopped before it finished. Tap Score again to pick up where it left off.");
    } finally {
      setBusy(false);
    }
  }

  async function collect() {
    setBusy(true);
    setNote("Collecting Broward, Miami-Dade, and Lee. This takes about a minute…");
    try {
      const result = await postForm<{ added: number; updated: number; notes: string[] }>("/api/collect");
      setNote(`Added ${result.added}, updated ${result.updated}. ${result.notes.join(" ")}`);
      await refresh();
    } catch {
      setNote("The collect request did not finish. Check the connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const header = (
    <View>
      <View style={styles.bar}>
        <Text style={styles.mark}>✦ Hestia</Text>
        <Text style={styles.counts}>
          {deals.length} deals{stale ? ` · ${stale} to score` : ""}
        </Text>
      </View>
      <View style={styles.actions}>
        <Pressable style={[styles.button, busy && styles.disabled]} disabled={busy} onPress={scoreAll} accessibilityRole="button">
          <Text style={styles.buttonText}>Score unchecked</Text>
        </Pressable>
        <Pressable style={[styles.button, styles.primary, busy && styles.disabled]} disabled={busy} onPress={collect} accessibilityRole="button">
          <Text style={[styles.buttonText, styles.primaryText]}>Collect sales</Text>
        </Pressable>
      </View>
      {note ? <Text style={styles.note}>{note}</Text> : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.process}>
        <Chip label="From the auctions" on={!step} onPress={() => setStep("")} count={(counts.Found || 0) + (counts.Researched || 0)} />
        {steps.map((name, n) => (
          <Chip key={name} label={`${n + 1} ${name}`} on={step === name} onPress={() => setStep(name)} count={counts[name] || 0} />
        ))}
        <Chip label="Passed" on={step === "Passed"} onPress={() => setStep("Passed")} count={counts.Passed || 0} />
        <Help topic="steps" />
      </ScrollView>
      <View style={styles.bands}>
        {BAND_ORDER.filter((b) => counts[`band:${b}`]).map((b) => (
          <Text key={b} style={[styles.bandText, { color: bandColor[b] }]}>
            {counts[`band:${b}`]} {(guide?.bands[b] || b).toLowerCase()}
          </Text>
        ))}
        <Help topic="band" />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );

  return (
    <FlatList
      data={lane}
      keyExtractor={(d) => String(d.id)}
      ListHeaderComponent={header}
      ListEmptyComponent={loading ? undefined : <Text style={styles.empty}>Nothing in this step.</Text>}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={color.dust} colors={[color.red]} progressBackgroundColor={color.plate} />}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => <Row deal={item} />}
    />
  );
}

function Chip({ label, on, count, onPress }: { label: string; on: boolean; count: number; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, on && styles.chipOn]} accessibilityRole="button" accessibilityState={{ selected: on }}>
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
      <Text style={styles.chipCount}>{count}</Text>
    </Pressable>
  );
}

function Row({ deal }: { deal: Deal }) {
  const score = deal.metadata.diligence?.score || 0;
  const b = band(deal);
  const judgment = deal.metadata.price_basis === "final judgment";
  const ratio = deal.metadata.roll_value && deal.price ? `${(deal.metadata.roll_value / deal.price).toFixed(1)}×` : "—";
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={() => router.push(`/deal/${deal.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`${displayName(deal.address)}, ${b ? b : "unscored"}, score ${score || "none"}`}
    >
      <View style={styles.scoreCell}>
        <ScoreDot score={score} band={b} />
        <Text style={[styles.score, { color: bandColor[b] }]}>{score || "—"}</Text>
      </View>
      <View style={styles.prop}>
        <Text style={styles.name} numberOfLines={1}>
          {displayName(deal.address)}
        </Text>
        <Text style={styles.where} numberOfLines={1}>
          {displayPlace(deal.location)} · {deal.metadata.sale_date || "no sale day"}
        </Text>
      </View>
      <View style={styles.money}>
        <Text style={styles.bid}>{money(deal.price)}</Text>
        <Text style={styles.ratio}>{judgment ? "judgment · " : ""}{ratio}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { paddingBottom: 48, backgroundColor: color.sky },
  bar: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", paddingHorizontal: 16, paddingTop: 12 },
  mark: { color: color.dust, fontFamily: serif, fontSize: 30 },
  counts: { color: color.quiet, fontSize: 13 },
  actions: { flexDirection: "row", gap: 8, paddingHorizontal: 16, marginTop: 12 },
  button: { flex: 1, minHeight: 44, borderRadius: 6, borderWidth: 1, borderColor: color.chart, backgroundColor: color.indigo, alignItems: "center", justifyContent: "center" },
  primary: { backgroundColor: color.red, borderColor: color.red },
  disabled: { opacity: 0.55 },
  buttonText: { color: color.dust, fontSize: 15 },
  primaryText: { color: color.sky, fontWeight: "600" },
  note: { color: color.amber, fontSize: 13, paddingHorizontal: 16, marginTop: 8 },
  process: { paddingHorizontal: 16, paddingTop: 14, gap: 6, alignItems: "center" },
  chip: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 40, paddingHorizontal: 12, borderRadius: 3, borderWidth: 1, borderColor: color.chart },
  chipOn: { borderColor: color.dust, backgroundColor: color.plate },
  chipText: { color: color.quiet, fontSize: 13 },
  chipTextOn: { color: color.dust },
  chipCount: { color: color.dust, fontSize: 13, fontVariant: ["tabular-nums"] },
  bands: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 10, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 8 },
  bandText: { fontSize: 13, fontVariant: ["tabular-nums"] },
  error: { color: color.red, paddingHorizontal: 16, paddingVertical: 8 },
  empty: { color: color.quiet, padding: 16 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: color.indigo },
  rowPressed: { backgroundColor: color.indigo },
  scoreCell: { width: 48, flexDirection: "row", alignItems: "center", gap: 6 },
  score: { fontSize: 15, fontVariant: ["tabular-nums"] },
  prop: { flex: 1, minWidth: 0 },
  name: { color: color.dust, fontSize: 16, fontWeight: "500" },
  where: { color: color.quiet, fontSize: 13, marginTop: 2 },
  money: { alignItems: "flex-end" },
  bid: { color: color.dust, fontSize: 15, fontVariant: ["tabular-nums"] },
  ratio: { color: color.quiet, fontSize: 12, marginTop: 2, fontVariant: ["tabular-nums"] },
});
