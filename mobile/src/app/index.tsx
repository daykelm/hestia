import { router } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, SectionList, StyleSheet, Text, View } from "react-native";
import { Help } from "../components/Help";
import { displayName, displayPlace, postForm, type Deal } from "../lib/api";
import { useStore } from "../lib/store";
import { color, serif } from "../lib/theme";

// Same order as the server. The first three start open, because those are the deals to act on.
const VERDICTS: [string, boolean][] = [
  ["Worth a title check", true],
  ["Numbers fit, danger open", true],
  ["Only if the title clears", true],
  ["Can't say yet", false],
  ["Not scored yet", false],
  ["Pass at this price", false],
  ["No price on the list", false],
];

const verdictOf = (d: Deal) => d.costs?.verdict || "No price on the list";
const compact = (n: number) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}K` : `$${Math.round(n)}`);

function saleDay(d: Deal) {
  const [month, day, year] = (d.metadata.sale_date || "").split("/").map(Number);
  return year ? new Date(year, month - 1, day).getTime() : 0;
}

function today() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

function groups(rows: Deal[], prefix: string) {
  const room = (d: Deal) => (d.costs?.value ? (d.costs.worst || 0) / d.costs.value : 99);
  return VERDICTS.map(([title, startOpen]) => ({
    key: `${prefix}${title}`,
    title,
    startOpen,
    rows: rows.filter((d) => verdictOf(d) === title).sort((a, b) => room(a) - room(b)),
  })).filter((group) => group.rows.length);
}

export default function Desk() {
  const { deals, guide, loading, error, refresh } = useStore();
  const [step, setStep] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const steps = guide?.steps || [];

  const lane = useMemo(() => deals.filter((d) => (step ? [step] : ["Found", "Researched"]).includes(d.status)), [deals, step]);

  const { title, sections } = useMemo(() => {
    const upcoming = lane.map(saleDay).filter((day) => day >= today());
    if (step || !upcoming.length) return { title: step || "From the auctions", sections: groups(lane, "") };
    const next = Math.min(...upcoming);
    const now = groups(lane.filter((d) => saleDay(d) === next), "");
    const rest = groups(lane.filter((d) => saleDay(d) !== next), "other:");
    const label = new Date(next).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
    return { title: `Next sale · ${label}`, sections: [...now, ...rest] };
  }, [lane, step]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const d of deals) c[d.status] = (c[d.status] || 0) + 1;
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
      <Pressable onPress={() => setMore((open) => !open)} accessibilityRole="button" accessibilityState={{ expanded: more }} style={styles.moreToggle}>
        <Text style={styles.moreText}>{more ? "Hide steps and collect" : "Steps and collect"}</Text>
      </Pressable>
      {more ? (
        <>
      <View style={styles.actions}>
        <Pressable style={[styles.button, busy && styles.disabled]} disabled={busy} onPress={scoreAll} accessibilityRole="button">
          <Text style={styles.buttonText}>Score unchecked</Text>
        </Pressable>
        <Pressable style={[styles.button, styles.primary, busy && styles.disabled]} disabled={busy} onPress={collect} accessibilityRole="button">
          <Text style={[styles.buttonText, styles.primaryText]}>Collect sales</Text>
        </Pressable>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.process}>
        <Chip label="From the auctions" on={!step} onPress={() => setStep("")} count={(counts.Found || 0) + (counts.Researched || 0)} />
        {steps.map((name, n) => (
          <Chip key={name} label={`${n + 1} ${name}`} on={step === name} onPress={() => setStep(name)} count={counts[name] || 0} />
        ))}
        <Chip label="Passed" on={step === "Passed"} onPress={() => setStep("Passed")} count={counts.Passed || 0} />
        <Help topic="steps" />
      </ScrollView>
        </>
      ) : null}
      {note ? <Text style={styles.note}>{note}</Text> : null}
      <Text style={styles.title}>{title}</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );

  const isOpen = (group: { key: string; startOpen: boolean }) => toggled[group.key] ?? (group.startOpen && !group.key.startsWith("other:"));

  return (
    <SectionList
      sections={sections.map((group) => ({ ...group, data: isOpen(group) ? group.rows : [] }))}
      keyExtractor={(d) => String(d.id)}
      stickySectionHeadersEnabled={false}
      ListHeaderComponent={header}
      ListEmptyComponent={loading ? undefined : <Text style={styles.empty}>Nothing in this step.</Text>}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={color.dust} colors={[color.red]} progressBackgroundColor={color.plate} />}
      contentContainerStyle={styles.list}
      renderSectionHeader={({ section }) => (
        <Pressable
          style={styles.group}
          onPress={() => setToggled((open) => ({ ...open, [section.key]: !isOpen(section) }))}
          accessibilityRole="button"
          accessibilityState={{ expanded: isOpen(section) }}
        >
          <Text style={styles.groupTitle}>{section.key.startsWith("other:") ? "Other sales: " : ""}{section.title}</Text>
          <Text style={styles.groupCount}>{section.rows.length}</Text>
          <Text style={styles.groupToggle}>{isOpen(section) ? "Hide" : "Show"}</Text>
        </Pressable>
      )}
      renderItem={({ item, section }) => <Row deal={item} dated={section.key.startsWith("other:") || Boolean(step)} />}
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

function Row({ deal, dated }: { deal: Deal; dated: boolean }) {
  const danger = deal.card?.find((line) => line.label === "Danger")?.text;
  const costs = deal.costs;
  const range = !costs?.rows ? "—" : compact(costs.best!) === compact(costs.worst!) ? compact(costs.best!) : `${compact(costs.best!)}–${compact(costs.worst!)}`;
  const where = [displayPlace(deal.location), dated ? deal.metadata.sale_date : ""].filter(Boolean).join(" · ");
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={() => router.push(`/deal/${deal.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`${displayName(deal.address)}, ${verdictOf(deal)}, all in ${range}`}
    >
      <View style={styles.prop}>
        <Text style={styles.name} numberOfLines={1}>
          {displayName(deal.address)}
        </Text>
        <Text style={styles.where} numberOfLines={1}>{where}</Text>
        {danger && danger !== "None on record" ? <Text style={styles.danger} numberOfLines={2}>{danger}</Text> : null}
      </View>
      <Text style={styles.bid}>{range}</Text>
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
  moreToggle: { minHeight: 44, justifyContent: "center", paddingHorizontal: 16 },
  moreText: { color: color.quiet, fontSize: 14, textDecorationLine: "underline" },
  title: { color: color.dust, fontFamily: serif, fontSize: 24, paddingHorizontal: 16, paddingTop: 12 },
  group: { flexDirection: "row", alignItems: "baseline", gap: 8, minHeight: 44, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  groupTitle: { color: color.dust, fontFamily: serif, fontSize: 18, flexShrink: 1 },
  groupCount: { color: color.quiet, fontSize: 14, fontVariant: ["tabular-nums"] },
  groupToggle: { color: color.quiet, fontSize: 13, marginLeft: "auto" },
  danger: { color: color.amber, fontSize: 13, marginTop: 2 },
  error: { color: color.red, paddingHorizontal: 16, paddingVertical: 8 },
  empty: { color: color.quiet, padding: 16 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: color.indigo },
  rowPressed: { backgroundColor: color.indigo },
  prop: { flex: 1, minWidth: 0 },
  name: { color: color.dust, fontSize: 16, fontWeight: "500" },
  where: { color: color.quiet, fontSize: 13, marginTop: 2 },
  bid: { color: color.dust, fontSize: 15, fontVariant: ["tabular-nums"] },
});
