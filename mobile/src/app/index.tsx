import { router } from "expo-router";
import { useMemo, useState } from "react";
import { Image, Linking, Pressable, RefreshControl, ScrollView, SectionList, StyleSheet, Text, View } from "react-native";
import { aerialUrl } from "../components/Aerial";
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

const REGIONS = ["Palm Beach", "Broward", "Miami-Dade", "Monroe", "Lee"];

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
  const [region, setRegion] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const steps = guide?.steps || [];

  const lane = useMemo(
    () => deals.filter((d) => (step ? [step] : ["Found", "Researched"]).includes(d.status) && (!region || d.metadata.county === region)),
    [deals, step, region],
  );

  const regionCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const d of deals) if (["Found", "Researched"].includes(d.status)) c[d.metadata.county || ""] = (c[d.metadata.county || ""] || 0) + 1;
    return c;
  }, [deals]);

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
    setNote("Collecting every county. This takes a few minutes…");
    try {
      type Step = { running: boolean; note?: string; added: number; updated: number; notes: string[] };
      let result = await postForm<Step>("/api/collect");
      while (result.running) {
        setNote(result.note || "Collecting…");
        await new Promise((done) => setTimeout(done, 4000));
        result = await postForm<Step>("/api/collect");
      }
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
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.process}>
        <Chip label="All" on={!region} onPress={() => setRegion("")} count={Object.values(regionCounts).reduce((a, b) => a + b, 0)} />
        {REGIONS.map((name) => (
          <Chip key={name} label={name} on={region === name} onPress={() => setRegion(name)} count={regionCounts[name] || 0} />
        ))}
      </ScrollView>
      <Pressable onPress={() => router.push("/results")} accessibilityRole="link" style={styles.moreToggle}>
        <Text style={styles.moreText}>Past results by county</Text>
      </Pressable>
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
  const [photoFailed, setPhotoFailed] = useState(false);
  const danger = deal.card?.find((line) => line.label === "Danger")?.text;
  const costs = deal.costs;
  const range = !costs?.rows ? "—" : compact(costs.best!) === compact(costs.worst!) ? compact(costs.best!) : `${compact(costs.best!)}–${compact(costs.worst!)}`;
  const where = [displayPlace(deal.location), dated ? deal.metadata.sale_date : ""].filter(Boolean).join(" · ");
  const point = deal.metadata.diligence?.point;
  const uri = deal.photo && !photoFailed ? deal.photo : point ? aerialUrl(point, 640, 400) : "";
  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={() => router.push(`/deal/${deal.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`${displayName(deal.address)}, ${verdictOf(deal)}, all in ${range}`}
    >
      <View>
        {uri ? <Image source={{ uri }} style={styles.photo} resizeMode="cover" fadeDuration={200} onError={() => setPhotoFailed(true)} /> : <View style={styles.photo} />}
        {deal.street_view ? (
          <Pressable style={styles.streetView} onPress={() => Linking.openURL(deal.street_view!)} accessibilityRole="link" accessibilityLabel={`Street View of ${displayName(deal.address)}`}>
            <Text style={styles.streetViewText}>Street View</Text>
          </Pressable>
        ) : null}
      </View>
      <View style={styles.cardBody}>
        <Text style={styles.bid}>{range} <Text style={styles.allIn}>all in</Text></Text>
        {deal.metadata.diligence?.house ? <Text style={styles.facts} numberOfLines={1}>{deal.metadata.diligence.house}</Text> : null}
        <Text style={styles.name} numberOfLines={1}>
          {displayName(deal.address)}
        </Text>
        <Text style={styles.where} numberOfLines={1}>{where}</Text>
        {danger && danger !== "None on record" ? <Text style={styles.danger} numberOfLines={2}>{danger}</Text> : null}
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
  card: { marginHorizontal: 16, marginBottom: 12, borderWidth: 1, borderColor: color.chart, borderRadius: 6, overflow: "hidden", backgroundColor: color.indigo },
  cardPressed: { borderColor: color.quiet },
  photo: { width: "100%", aspectRatio: 16 / 10, backgroundColor: color.plate },
  streetView: { position: "absolute", right: 8, bottom: 8, minHeight: 44, paddingHorizontal: 12, borderRadius: 6, justifyContent: "center", backgroundColor: "rgba(10,16,33,0.85)" },
  streetViewText: { color: color.dust, fontSize: 14 },
  cardBody: { padding: 12 },
  facts: { color: color.dust, fontSize: 14, marginTop: 2, fontVariant: ["tabular-nums"] },
  name: { color: color.dust, fontSize: 15, marginTop: 6 },
  where: { color: color.quiet, fontSize: 13, marginTop: 2 },
  bid: { color: color.dust, fontSize: 22, fontWeight: "600", fontVariant: ["tabular-nums"] },
  allIn: { color: color.quiet, fontSize: 12 },
});
