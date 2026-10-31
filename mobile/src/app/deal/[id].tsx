import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { Aerial } from "../../components/Aerial";
import { Help } from "../../components/Help";
import { ScoreDot } from "../../components/ScoreDot";
import { band, displayName, displayPlace, money, postForm, SignedOut, type Deal } from "../../lib/api";
import { useStore } from "../../lib/store";
import { bandColor, color, serif } from "../../lib/theme";

const STEPS = ["Found", "Researched", "Title checked", "Bid set", "Won", "Buyer assigned", "Closed"];

/** Same rule as the server: forward one, back one (never back to Found), or pass before you win. */
function moves(status: string, researched: boolean) {
  if (status === "Passed") return { back: [] as string[], reopen: researched ? "Researched" : "Found", pass: false };
  const at = STEPS.indexOf(status);
  const back = at > 1 ? [STEPS[at - 1]] : [];
  return { back, reopen: "", pass: !["Won", "Buyer assigned", "Closed"].includes(status) };
}

export default function DealScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { deals, guide, replace, refresh } = useStore();
  const deal = deals.find((d) => String(d.id) === id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string | boolean>>({});

  if (!deal) {
    return (
      <View style={styles.root}>
        <Back />
        <Text style={styles.quiet}>That deal is no longer on the list.</Text>
      </View>
    );
  }

  const meta = deal.metadata;
  const d = meta.diligence;
  const b = band(deal);
  const set = (key: string, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  async function send(path: string, fields: Record<string, string | boolean | number | undefined>) {
    setBusy(true);
    setError("");
    try {
      const result = await postForm<{ deal: Deal }>(path, { id: deal!.id, ...fields });
      replace(result.deal);
      setForm({});
    } catch (err) {
      if (err instanceof SignedOut) refresh();
      setError(err instanceof Error ? err.message : "That did not go through.");
    } finally {
      setBusy(false);
    }
  }

  const go = (to: string, fields: Record<string, string | boolean | undefined> = {}) => send("/api/step", { to, ...fields });
  const { back, reopen, pass } = moves(deal.status, Boolean(d));
  const at = STEPS.indexOf(deal.status);

  const coords: [string, string, string][] = [
    ["Sale day", meta.sale_date || "—", "sale"],
    [meta.price_basis === "final judgment" ? "Final judgment" : "Opening bid", money(deal.price), meta.price_basis === "final judgment" ? "judgment" : "bid"],
    ["Tax roll value", money(meta.roll_value), "roll"],
    ["Roll ÷ bid", meta.roll_value && deal.price ? `${(meta.roll_value / deal.price).toFixed(1)}×` : "—", "ratio"],
  ];
  if (meta.parcel) coords.push(["Parcel", meta.parcel, "parcel"]);
  if (meta.case) coords.push(["Case", meta.case, "case"]);

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Back />
        <Text style={styles.name}>{displayName(deal.address)}</Text>
        <Text style={styles.where}>{[displayPlace(deal.location), deal.source].filter(Boolean).join(" · ")}</Text>
        {d?.point ? <Aerial point={d.point} name={displayName(deal.address)} /> : null}
        {d?.house ? <Text style={styles.house}>{d.house}</Text> : null}
        {deal.card?.length ? (
          <View style={styles.brief}>
            {deal.card.map((line) => (
              <View key={line.label} style={styles.briefItem}>
                <Text style={styles.dt}>{line.label}</Text>
                <Text style={[styles.briefText, (line.label === "Danger" && line.text !== "None on record" || line.label === "Tax" && line.text.startsWith("Delinquent") || line.label === "Cause" && (line.text.includes("HOA") || line.text.includes(" and ")) || line.label === "Also" && (line.text.startsWith("Not this door") || line.text.startsWith("Parcel record") || line.text.includes("Disagrees"))) && { color: color.amber }]}>{line.text}</Text>
              </View>
            ))}
          </View>
        ) : null}

        <View style={styles.panel}>
          <View style={styles.rowCenter}>
            <Text style={styles.stepHead}>
              {at >= 0 ? `Step ${at + 1} of ${STEPS.length}: ` : ""}
              <Text style={styles.stepName}>{deal.status}</Text>
            </Text>
            <Help topic="steps" />
          </View>
          <View style={styles.stepper} accessibilityLabel={`Step ${at + 1} of 7, ${deal.status}`}>
            {STEPS.map((step, n) => (
              <View key={step} style={styles.stepCell}>
                {n > 0 ? <View style={[styles.line, n <= at && styles.lineOn]} /> : null}
                <View style={[styles.dot, n < at && styles.dotDone, n === at && styles.dotNow]} />
              </View>
            ))}
          </View>
          <Text style={styles.guide}>{guide?.step_guide[deal.status] || ""}</Text>

          {deal.status === "Found" ? <Action label="Score this deal" busy={busy} onPress={() => send("/api/research", {})} /> : null}

          {deal.status === "Researched" ? (
            <View style={styles.gap}>
              <View style={styles.links}>
                {(guide?.check_links[meta.county || ""] || []).map((link) => (
                  <Pressable key={link.url} onPress={() => Linking.openURL(link.url)} accessibilityRole="link" hitSlop={8}>
                    <Text style={styles.link}>{link.name}</Text>
                  </Pressable>
                ))}
              </View>
              <Tick value={Boolean(form.title)} onChange={(v) => set("title", v)} label="I read the docket. The sale clears the mortgage." />
              <Tick value={Boolean(form.liens)} onChange={(v) => set("liens", v)} label="I searched liens and taxes owed. Nothing survives the sale." />
              <Action label="Mark title checked" busy={busy} disabled={!form.title || !form.liens} onPress={() => go("Title checked", { title: true, liens: true })} />
            </View>
          ) : null}

          {deal.status === "Title checked" ? (
            <View style={styles.gap}>
              <Field label="Most I will bid" value={String(form.max_bid ?? "")} onChange={(v) => set("max_bid", v)} />
              <Action label="Set my ceiling" busy={busy} disabled={!form.max_bid} onPress={() => go("Bid set", { max_bid: String(form.max_bid) })} />
            </View>
          ) : null}

          {deal.status === "Bid set" ? (
            <View style={styles.gap}>
              <Text style={styles.quiet}>
                Sale day {meta.sale_date || "not set"}. Your ceiling is {money(meta.max_bid)}. The county bids $100 at a time and stops there. Your deposit has to clear before the sale.
              </Text>
              {meta.bid_url ? (
                <Pressable onPress={() => Linking.openURL(meta.bid_url!)} accessibilityRole="link" style={styles.action}>
                  <Text style={styles.actionText}>Place this bid</Text>
                </Pressable>
              ) : null}
              <Field label="Winning price" value={String(form.won_price ?? "")} onChange={(v) => set("won_price", v)} />
              <Action label="We won it" busy={busy} disabled={!form.won_price} onPress={() => go("Won", { won_price: String(form.won_price) })} />
            </View>
          ) : null}

          {deal.status === "Won" ? (
            <View style={styles.gap}>
              <Field label="Buyer" value={String(form.buyer ?? "")} onChange={(v) => set("buyer", v)} numeric={false} />
              <Field label="Assignment fee" value={String(form.fee ?? "")} onChange={(v) => set("fee", v)} />
              <Action label="Assign the buyer" busy={busy} disabled={!form.buyer} onPress={() => go("Buyer assigned", { buyer: String(form.buyer), fee: form.fee ? String(form.fee) : undefined })} />
            </View>
          ) : null}

          {deal.status === "Buyer assigned" ? <Action label="Mark closed" busy={busy} onPress={() => go("Closed")} /> : null}
          {reopen ? <Action label="Reopen" busy={busy} onPress={() => go(reopen)} /> : null}

          <View style={styles.more}>
            {back.map((to) => (
              <Small key={to} label={`Back to ${to}`} onPress={() => go(to)} disabled={busy} />
            ))}
            {pass ? <Small label={deal.status === "Bid set" ? "Lost or skipped" : "Pass"} onPress={() => go("Passed")} disabled={busy} /> : null}
          </View>
          {error ? <Text style={styles.error}>{error}</Text> : null}
        </View>

        <View style={styles.coords}>
          {coords.map(([label, value, topic]) => (
            <View key={label} style={styles.coord}>
              <View style={styles.rowCenter}>
                <Text style={styles.dt}>{label}</Text>
                <Help topic={topic} />
              </View>
              <Text style={styles.dd}>{value}</Text>
            </View>
          ))}
        </View>

        <View style={styles.scoreHead}>
          <ScoreDot score={d?.score || 0} band={b} />
          <Text style={styles.scoreLabel}>Score</Text>
          <Help topic="score" />
          <Text style={[styles.scoreValue, { color: bandColor[b] }]}>{d?.score ? `${d.score} of 10` : "Unscored"}</Text>
        </View>

        {d?.score ? (
          <>
            <View style={[styles.verdict, { borderLeftColor: bandColor[b] }]}>
              <View style={styles.rowCenter}>
                <Text style={[styles.verdictLabel, { color: bandColor[b] }]}>{guide?.bands[b as keyof typeof guide.bands] || ""}</Text>
                <Help topic="band" />
              </View>
              <Text style={styles.quiet}>
                {(d.version || 1) < (guide?.rules_version || 0) ? "Scored under the old rules. Score it again to recheck every source." : d.reason}
              </Text>
            </View>
            {(d.flags || []).map((flag) => (
              <Text key={flag} style={styles.flag}>
                • {flag}
              </Text>
            ))}
            {d.factors.map((f) => (
              <View key={f.name} style={styles.factor}>
                <View style={styles.factorHead}>
                  <View style={styles.rowCenter}>
                    <Text style={[styles.factorName, f.checked === false && styles.off]}>{f.name}</Text>
                    {guide?.factor_help[f.name] ? <Help topic={guide.factor_help[f.name]} /> : null}
                  </View>
                  {f.checked === false ? (
                    <Text style={styles.unchecked}>Not checked</Text>
                  ) : (
                    <View style={styles.pips} accessibilityLabel={`${f.points} of ${f.of}`}>
                      {Array.from({ length: f.of }, (_, n) => (
                        <View key={n} style={[styles.pip, n < f.points && styles.pipOn]} />
                      ))}
                    </View>
                  )}
                </View>
                <Text style={styles.note}>{f.note}</Text>
                {f.sources?.length ? <Text style={styles.sources}>{f.sources.join(" + ")}</Text> : null}
              </View>
            ))}
            {d.identity?.note ? <Text style={styles.sources}>{d.identity.note}</Text> : null}
          </>
        ) : (
          <Text style={styles.quiet}>Not scored yet. Scoring reads the tax rolls, code cases, the flood map, and nearby sales.</Text>
        )}

        {deal.link ? (
          <Pressable onPress={() => Linking.openURL(deal.link)} accessibilityRole="link" style={{ marginTop: 20 }}>
            <Text style={styles.link}>Open the auction listing</Text>
          </Pressable>
        ) : null}
        {deal.street?.length ? (
          <View style={styles.street}>
            <Text style={styles.quiet}>Look up</Text>
            {deal.street.map((item) => (
              <Pressable key={item.name} onPress={() => Linking.openURL(item.url)} accessibilityRole="link" hitSlop={8}>
                <Text style={styles.link}>{item.name}</Text>
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Back() {
  return (
    <Pressable onPress={() => router.back()} accessibilityRole="button" hitSlop={10} style={styles.back}>
      <Text style={styles.backText}>‹ Desk</Text>
    </Pressable>
  );
}

function Action({ label, onPress, busy, disabled }: { label: string; onPress: () => void; busy: boolean; disabled?: boolean }) {
  const off = busy || disabled;
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      accessibilityState={{ disabled: off }}
      style={({ pressed }) => [styles.action, off && styles.disabled, pressed && { transform: [{ scale: 0.97 }] }]}
    >
      <Text style={styles.actionText}>{busy ? "Working…" : label}</Text>
    </Pressable>
  );
}

function Small({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={styles.small} accessibilityRole="button">
      <Text style={styles.smallText}>{label}</Text>
    </Pressable>
  );
}

function Tick({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <Pressable style={styles.tick} onPress={() => onChange(!value)} accessibilityRole="checkbox" accessibilityState={{ checked: value }}>
      <Switch value={value} onValueChange={onChange} trackColor={{ false: color.chart, true: color.red }} thumbColor={color.dust} />
      <Text style={styles.tickText}>{label}</Text>
    </Pressable>
  );
}

function Field({ label, value, onChange, numeric = true }: { label: string; value: string; onChange: (v: string) => void; numeric?: boolean }) {
  return (
    <View>
      <Text style={styles.dt}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        keyboardType={numeric ? "decimal-pad" : "default"}
        style={styles.input}
        placeholderTextColor={color.fog}
        selectionColor={color.amber}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.sky },
  content: { padding: 16, paddingBottom: 56 },
  back: { minHeight: 44, justifyContent: "center", alignSelf: "flex-start" },
  backText: { color: color.quiet, fontSize: 15 },
  name: { color: color.dust, fontFamily: serif, fontSize: 32, lineHeight: 36 },
  where: { color: color.amber, fontSize: 13, marginTop: 4 },
  panel: { marginTop: 16, padding: 14, borderWidth: 1, borderColor: color.chart, borderRadius: 3, backgroundColor: color.indigo },
  rowCenter: { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  stepHead: { color: color.quiet, fontSize: 13 },
  stepName: { color: color.dust, fontWeight: "600" },
  stepper: { flexDirection: "row", marginTop: 14, marginBottom: 10 },
  stepCell: { flex: 1, alignItems: "center", justifyContent: "center", height: 14 },
  line: { position: "absolute", left: "-50%", right: "50%", top: 6.5, height: 1, backgroundColor: color.chart },
  lineOn: { backgroundColor: color.dust },
  dot: { width: 11, height: 11, borderRadius: 6, borderWidth: 1, borderColor: color.quiet, backgroundColor: color.indigo },
  dotDone: { backgroundColor: color.dust, borderColor: color.dust },
  dotNow: { width: 14, height: 14, borderRadius: 7, borderWidth: 3, borderColor: color.dust, backgroundColor: color.sky },
  guide: { color: color.dust, fontSize: 15, lineHeight: 21, marginBottom: 12 },
  gap: { gap: 12 },
  links: { flexDirection: "row", flexWrap: "wrap", gap: 16 },
  link: { color: color.dust, fontSize: 15, textDecorationLine: "underline", textDecorationColor: color.fog },
  tick: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44 },
  tickText: { flex: 1, color: color.dust, fontSize: 14, lineHeight: 19 },
  action: { minHeight: 48, borderRadius: 6, backgroundColor: color.red, alignItems: "center", justifyContent: "center", marginTop: 4 },
  actionText: { color: color.sky, fontSize: 16, fontWeight: "600" },
  disabled: { opacity: 0.45 },
  more: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  small: { minHeight: 36, paddingHorizontal: 12, borderRadius: 6, borderWidth: 1, borderColor: color.chart, justifyContent: "center" },
  smallText: { color: color.quiet, fontSize: 13 },
  error: { color: color.red, marginTop: 10, fontSize: 14 },
  input: { minHeight: 44, marginTop: 4, borderWidth: 1, borderColor: color.chart, borderRadius: 6, paddingHorizontal: 10, color: color.dust, fontSize: 16, backgroundColor: color.sky },
  coords: { flexDirection: "row", flexWrap: "wrap", marginTop: 18, paddingVertical: 12, borderTopWidth: 1, borderBottomWidth: 1, borderColor: color.chart, rowGap: 12 },
  coord: { width: "50%", paddingRight: 12 },
  dt: { color: color.quiet, fontSize: 12 },
  dd: { color: color.dust, fontSize: 15, marginTop: 2, fontVariant: ["tabular-nums"] },
  scoreHead: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 18 },
  scoreLabel: { color: color.quiet, fontSize: 14 },
  scoreValue: { marginLeft: "auto", fontSize: 15, fontVariant: ["tabular-nums"] },
  verdict: { marginTop: 10, padding: 12, borderLeftWidth: 3, backgroundColor: color.indigo, gap: 4 },
  verdictLabel: { fontSize: 15, fontWeight: "600" },
  flag: { color: bandColor.risky, fontSize: 13, marginTop: 8 },
  factor: { paddingVertical: 10, borderTopWidth: 1, borderTopColor: color.chart, marginTop: 8 },
  factorHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  factorName: { color: color.dust, fontSize: 15, fontWeight: "500" },
  off: { color: color.quiet },
  unchecked: { color: bandColor.thin, fontSize: 12 },
  pips: { flexDirection: "row", gap: 5 },
  pip: { width: 9, height: 9, borderRadius: 5, borderWidth: 1, borderColor: color.quiet },
  pipOn: { backgroundColor: color.dust, borderColor: color.dust },
  note: { color: color.quiet, fontSize: 13, lineHeight: 19, marginTop: 4 },
  sources: { color: color.quiet, opacity: 0.8, fontSize: 12, marginTop: 4 },
  quiet: { color: color.quiet, fontSize: 14, lineHeight: 20 },
  house: { color: color.dust, fontSize: 15, marginTop: 12, fontVariant: ["tabular-nums"] },
  brief: { flexDirection: "row", flexWrap: "wrap", rowGap: 14, marginTop: 16 },
  briefItem: { width: "50%", paddingRight: 12 },
  briefText: { color: color.dust, fontSize: 15, lineHeight: 20, marginTop: 2 },
  street: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 14, marginTop: 16 },
});
