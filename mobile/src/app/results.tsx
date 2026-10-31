import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { getJSON } from "../lib/api";
import { color, serif } from "../lib/theme";

type Entry = { kind: string; total: number; unsold: number; kept: number; outside: number; buyers: number; median?: number };
type Market = { county: string; kind: string; sales: number; median: number; at_70: number };
type Results = { from?: string; through?: string; counties: { county: string; kinds: Entry[] }[]; market?: Market[] };

const SEGMENTS = { unsold: "#7f7bd0", kept: "#cf7722", outside: "#2f95dd" };
const percent = (part: number, whole: number) => `${whole ? Math.round((100 * part) / whole) : 0}%`;

export default function PastResults() {
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON<Results>("/api/results")
      .then(setResults)
      .catch(() => setError("Past results did not load. Go back and try again."));
  }, []);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <Pressable onPress={() => router.back()} accessibilityRole="button" style={styles.back}>
        <Text style={styles.quiet}>‹ Desk</Text>
      </Pressable>
      <Text style={styles.title}>Past results</Text>
      <Text style={styles.quiet}>
        {results?.from ? `${results.from} to ${results.through}. ` : ""}Kept means it went back to the plaintiff or the certificate holder. Prices are what was bid, not what a resale brought.
      </Text>
      <View style={styles.legend}>
        {(["Did not sell", "Kept", "Outside buyer"] as const).map((label, n) => (
          <View key={label} style={styles.legendItem}>
            <View style={[styles.swatch, { backgroundColor: Object.values(SEGMENTS)[n] }]} />
            <Text style={styles.small}>{label}</Text>
          </View>
        ))}
      </View>
      {error ? <Text style={styles.quiet}>{error}</Text> : null}
      {results ? (["Foreclosure", "Tax deed"] as const).map((kind) => <Kind key={kind} kind={kind} results={results} />) : null}
      {results?.market?.length ? (
        <View>
          <Text style={styles.kind}>Price against the tax roll</Text>
          <Text style={styles.caption}>What outside buyers paid, as a share of the tax roll. Typical sale. It shows what it took to win, not what a resale brought.</Text>
          {results.market.map((row) => (
            <View key={`${row.county}${row.kind}`} style={styles.row}>
              <View style={styles.rowHead}>
                <Text style={styles.county}>{row.county} · {row.kind.toLowerCase()}</Text>
                <Text style={styles.small}>{row.sales} buyers</Text>
              </View>
              <View style={styles.paid}>
                <View style={[styles.paidBar, { width: `${80 * row.median}%` }]} />
                <Text style={styles.county}>{Math.round(row.median * 100)}%</Text>
              </View>
              <Text style={styles.small}>About {Math.round(row.at_70 * 100)}% paid 70% of the roll or less.</Text>
            </View>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function Kind({ kind, results }: { kind: string; results: Results }) {
  const members = results.counties.flatMap((c) => c.kinds.filter((e) => e.kind === kind).map((e) => ({ county: c.county, ...e })));
  if (!members.length) return null;
  const top = Math.max(1, ...members.map((e) => e.median || 0));
  return (
    <View>
      <Text style={styles.kind}>{kind}s</Text>
      <Text style={styles.caption}>How the auctions ended</Text>
      {members.map((e) => (
        <View key={e.county} style={styles.row}>
          <View style={styles.rowHead}>
            <Text style={styles.county}>{e.county}</Text>
            <Text style={styles.small}>{e.total.toLocaleString("en-US")} auctions</Text>
          </View>
          <View style={styles.bar}>
            {(["unsold", "kept", "outside"] as const).filter((key) => e[key]).map((key) => (
              <View key={key} style={{ flex: e[key], backgroundColor: SEGMENTS[key] }} />
            ))}
          </View>
          <Text style={styles.small}>
            {percent(e.unsold, e.total)} did not sell · {percent(e.kept, e.total)} kept · {percent(e.outside, e.total)} outside buyer
          </Text>
        </View>
      ))}
      <Text style={styles.caption}>What outside buyers paid, as a multiple of {kind === "Tax deed" ? "the opening bid" : "the final judgment"}. Typical sale.</Text>
      {members.map((e) => (
        <View key={e.county} style={styles.row}>
          <View style={styles.rowHead}>
            <Text style={styles.county}>{e.county}</Text>
            <Text style={styles.small}>{e.buyers.toLocaleString("en-US")} buyers</Text>
          </View>
          {e.median ? (
            <View style={styles.paid}>
              <View style={[styles.paidBar, { width: `${(80 * e.median) / top}%` }]} />
              <Text style={styles.county}>{e.median}×</Text>
            </View>
          ) : (
            <Text style={styles.small}>Too few outside sales to say.</Text>
          )}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.sky },
  content: { padding: 16, paddingBottom: 48 },
  back: { minHeight: 44, justifyContent: "center" },
  title: { color: color.dust, fontFamily: serif, fontSize: 32, marginBottom: 6 },
  quiet: { color: color.quiet, fontSize: 14, lineHeight: 20 },
  small: { color: color.quiet, fontSize: 13, fontVariant: ["tabular-nums"] },
  legend: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 14 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  kind: { color: color.dust, fontFamily: serif, fontSize: 24, marginTop: 24 },
  caption: { color: color.dust, fontSize: 15, marginTop: 14, marginBottom: 4 },
  row: { paddingVertical: 10, borderTopWidth: 1, borderTopColor: color.chart },
  rowHead: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  county: { color: color.dust, fontSize: 15, fontVariant: ["tabular-nums"] },
  bar: { flexDirection: "row", gap: 2, height: 12, borderRadius: 4, overflow: "hidden", marginBottom: 6 },
  paid: { flexDirection: "row", alignItems: "center", gap: 8 },
  paidBar: { height: 12, backgroundColor: SEGMENTS.outside, borderTopRightRadius: 4, borderBottomRightRadius: 4 },
});
