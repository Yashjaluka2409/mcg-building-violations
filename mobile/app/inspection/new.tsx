import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { Camera, CheckCircle2, LocateFixed, Search, Video } from "lucide-react-native";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, Image, Pressable, ScrollView, Text, View } from "react-native";
import { cases, masters, plans, property } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button, Card, CardTitle, Header, Input, Muted, Pill } from "@/components/ui";
import LeafletMap from "@/components/LeafletMap";
import { captureWithCamera, currentFix, Fix, uploadMedia } from "@/services/capture";
import { enqueue } from "@/services/offline";
import { colors, radius } from "@/theme";

/** JE field inspection: PID → property → GPS/land check → violations → geotagged evidence → submit. */
export default function NewInspection() {
  const { t } = useTranslation();
  const r = useRouter();
  const vtypes = useQuery({ queryKey: ["vtypes"], queryFn: masters.violationTypes });
  const [f, setF] = useState<any>({ construction_stage: "UNDER_CONSTRUCTION", priority: "NORMAL", land_type: "UNKNOWN", source: "FIELD_INSPECTION" });
  const [fix, setFix] = useState<Fix | null>(null);
  const [landCheck, setLandCheck] = useState<any>(null);
  const [pidInfo, setPidInfo] = useState<any>(null);
  const [planMatch, setPlanMatch] = useState<any[]>([]);
  const [sel, setSel] = useState<Record<string, string>>({});
  const [captures, setCaptures] = useState<{ file: any; fix: Fix; kind: string; uploadedId?: string }[]>([]);
  const [cat, setCat] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }));
  const locate = async () => { try { const fx = await currentFix(); setFix(fx); const chk = await property.checkPoint(fx.latitude, fx.longitude); setLandCheck(chk); setF((s: any) => ({ ...s, latitude: fx.latitude, longitude: fx.longitude, location_accuracy_m: fx.accuracy, land_type: chk.land_type, ward: chk.ward?.id ?? s.ward })); } catch (e) { Alert.alert("Location", errorMessage(e)); } };
  useEffect(() => { locate(); }, []);
  const lookup = useMutation({ mutationFn: () => property.lookupPid(f.pid), onSuccess: async (d) => { setPidInfo(d); setF((s: any) => ({ ...s, owner_name: d.owner_name, pid_linked_mobile: d.mobile, address_line: d.address, locality: d.colony, sector: d.sector, pid_snapshot: d.raw })); try { setPlanMatch(await plans.byPid(f.pid)); } catch { setPlanMatch([]); } }, onError: (e) => Alert.alert("PID", errorMessage(e)) });
  const capture = async (video: boolean) => { try { const c = await captureWithCamera(video); if (!c) return; setCaptures((s) => [...s, { file: { uri: c.uri, name: c.name, type: c.type }, fix: c.fix, kind: "INSPECTION" }]); } catch (e) { Alert.alert("Camera", errorMessage(e)); } };
  const cats = useMemo(() => Array.from(new Set((vtypes.data || []).map((v: any) => v.category))), [vtypes.data]);
  const list = (vtypes.data || []).filter((v: any) => !cat || v.category === cat);
  const submit = async (send: boolean) => {
    if (!f.address_line && !f.pid) return Alert.alert("Required", "Enter PID or address");
    if (!Object.keys(sel).length) return Alert.alert("Required", "Select at least one violation");
    if (!f.description) return Alert.alert("Required", "Enter observations");
    if (send && !captures.length) return Alert.alert("Required", "Capture at least one geotagged photo");
    setBusy(true);
    const data = { ...f, violations: Object.entries(sel).map(([code, remarks], i) => ({ code, remarks, is_primary: i === 0 })), submit: send };
    try {
      const ids: string[] = [];
      for (const c of captures) { const up = await uploadMedia(c.file, c.kind, { fix: c.fix }); ids.push(up.id); }
      const created = await cases.create({ ...data, media_ids: ids });
      r.replace(`/case/${created.id}`);
    } catch (e: any) {
      if (e?.message === "Network Error") { await enqueue("case", { data, media: captures }); Alert.alert("Saved offline", "No network. The inspection will be uploaded automatically when you are back online."); r.replace("/(tabs)/home"); }
      else Alert.alert("Error", errorMessage(e));
    }
    setBusy(false);
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title={t("newInspection")} subtitle="Building violation report" back />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <Card><CardTitle>1. Property</CardTitle>
          <Text style={{ fontWeight: "600", marginBottom: 6 }}>{t("pid")}</Text>
          <View style={{ flexDirection: "row", gap: 8 }}><View style={{ flex: 1 }}><Input placeholder="e.g. GGN012345" autoCapitalize="characters" value={f.pid || ""} onChangeText={(v) => set("pid", v.toUpperCase())} /></View><Pressable onPress={() => lookup.mutate()} disabled={!f.pid} style={{ backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: 16, height: 50, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 6 }}><Search color="#fff" size={18} /><Text style={{ color: "#fff", fontWeight: "700" }}>{t("fetch")}</Text></Pressable></View>
          {pidInfo && <View style={{ backgroundColor: colors.accent100, borderRadius: radius.md, padding: 10, marginBottom: 10 }}><Text style={{ fontWeight: "700" }}>✓ {pidInfo.owner_name} · {pidInfo.mobile}</Text><Muted>{pidInfo.address} · Ward {pidInfo.ward_no} · {pidInfo.property_type} · {pidInfo.floors}</Muted></View>}
          {planMatch.length > 0 && <View style={{ backgroundColor: colors.success100, borderRadius: radius.md, padding: 10, marginBottom: 10 }}><Text style={{ fontWeight: "700" }}>Sanctioned plan on record</Text>{planMatch.map((p: any) => <Muted key={p.id}>{p.plan_no} · {p.permitted_floors} · coverage {p.permitted_ground_coverage_pct}% · FAR {p.permitted_far} · height {p.permitted_height_m} m{p.licence_no ? ` · licence ${p.licence_no}` : ""}</Muted>)}</View>}
          <Input label={t("address")} multiline value={f.address_line || ""} onChangeText={(v) => set("address_line", v)} placeholder="House / plot no., street, colony" />
          <Input label="Owner name" value={f.owner_name || ""} onChangeText={(v) => set("owner_name", v)} />
          <Input label="Mobile linked to PID" keyboardType="phone-pad" value={f.pid_linked_mobile || ""} onChangeText={(v) => set("pid_linked_mobile", v)} />
          <Input label="Alternate mobile for notice" keyboardType="phone-pad" value={f.alternate_mobile || ""} onChangeText={(v) => set("alternate_mobile", v)} />
          <Input label="Person present on site" value={f.person_on_site || ""} onChangeText={(v) => set("person_on_site", v)} />
        </Card>
        <Card><View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}><CardTitle>2. Location & land</CardTitle><Pressable onPress={locate} style={{ flexDirection: "row", gap: 4, alignItems: "center" }}><LocateFixed color={colors.accent} size={18} /><Text style={{ color: colors.accent, fontWeight: "600" }}>Refresh GPS</Text></Pressable></View>
          <View style={{ height: 220, borderRadius: radius.md, overflow: "hidden" }}><LeafletMap marker={fix ? [fix.latitude, fix.longitude] : null} govtLand={landCheck?.parcels?.length ? { type: "FeatureCollection", features: landCheck.parcels.map((p: any) => ({ type: "Feature", geometry: p.geometry, properties: p })) } : undefined} onMapPress={async (lat, lng) => { const chk = await property.checkPoint(lat, lng); setLandCheck(chk); setFix({ latitude: lat, longitude: lng, accuracy: null, altitude: null, at: new Date().toISOString() }); setF((s: any) => ({ ...s, latitude: lat, longitude: lng, land_type: chk.land_type, ward: chk.ward?.id ?? s.ward })); }} /></View>
          <Muted>{fix ? `${fix.latitude.toFixed(6)}, ${fix.longitude.toFixed(6)} (±${Math.round(fix.accuracy ?? 0)} m)` : "Getting location…"}{landCheck?.ward ? ` · Ward ${landCheck.ward.number}` : ""}</Muted>
          {landCheck && <View style={{ marginTop: 8 }}>{landCheck.parcels?.length ? <Pill text={`⚠ ${landCheck.parcels[0].agency} land: ${landCheck.parcels[0].name || landCheck.parcels[0].khasra_no}`} bg={colors.danger100} fg={colors.danger} /> : <Pill text="Not inside mapped government land" bg="#f3f4f6" fg={colors.muted} />}</View>}
          <View style={{ flexDirection: "row", gap: 8, marginTop: 12, flexWrap: "wrap" }}>{["PLINTH", "UNDER_CONSTRUCTION", "COMPLETED", "OCCUPIED"].map((s) => <Pressable key={s} onPress={() => set("construction_stage", s)}><Pill text={s.replace(/_/g, " ")} bg={f.construction_stage === s ? colors.primary : "#f3f4f6"} fg={f.construction_stage === s ? "#fff" : colors.muted} /></Pressable>)}</View>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}><View style={{ flex: 1 }}><Input label="Storeys" placeholder="S+4" value={f.storeys || ""} onChangeText={(v) => set("storeys", v)} /></View><View style={{ flex: 1 }}><Input label="Covered area sq m" keyboardType="numeric" value={f.covered_area_sqm || ""} onChangeText={(v) => set("covered_area_sqm", v)} /></View></View>
        </Card>
        <Card><CardTitle>3. {t("violations")} ({Object.keys(sel).length})</CardTitle>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}><View style={{ flexDirection: "row", gap: 8 }}><Pressable onPress={() => setCat("")}><Pill text="All" bg={!cat ? colors.primary : "#f3f4f6"} fg={!cat ? "#fff" : colors.muted} /></Pressable>{cats.map((c: any) => <Pressable key={c} onPress={() => setCat(c)}><Pill text={c.replace(/_/g, " ")} bg={cat === c ? colors.primary : "#f3f4f6"} fg={cat === c ? "#fff" : colors.muted} /></Pressable>)}</View></ScrollView>
          {list.map((v: any) => { const on = sel[v.code] !== undefined; return <Pressable key={v.code} onPress={() => setSel((s) => { const n = { ...s }; if (on) delete n[v.code]; else n[v.code] = ""; return n; })} style={{ borderWidth: 1, borderColor: on ? colors.primary : colors.border, backgroundColor: on ? colors.primary50 : "#fff", borderRadius: radius.md, padding: 10, marginBottom: 8 }}><View style={{ flexDirection: "row", gap: 8 }}><CheckCircle2 color={on ? colors.primary : colors.border} size={20} /><View style={{ flex: 1 }}><Text style={{ fontWeight: "600" }}><Text style={{ color: colors.primary }}>{v.code}</Text> {v.title_en}</Text><Muted>{v.title_hi}</Muted><Muted>{v.contravention_of}</Muted></View></View>{on && <Input placeholder="Remarks / measurement (printed on notice)" value={sel[v.code]} onChangeText={(x) => setSel((s) => ({ ...s, [v.code]: x }))} style={{ marginTop: 8 }} />}</Pressable>; })}
        </Card>
        <Card><CardTitle>4. {t("evidence")}</CardTitle>
          <Input label={t("description")} multiline numberOfLines={4} value={f.description || ""} onChangeText={(v) => set("description", v)} placeholder="What was found: floors, setbacks, use, work in progress, persons met…" />
          <View style={{ flexDirection: "row", gap: 10 }}><View style={{ flex: 1 }}><Button title={t("takePhoto")} variant="accent" icon={<Camera color="#fff" size={20} />} onPress={() => capture(false)} /></View><View style={{ flex: 1 }}><Button title={t("recordVideo")} variant="outline" icon={<Video color={colors.text} size={20} />} onPress={() => capture(true)} /></View></View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 }}>{captures.map((c, i) => <View key={i} style={{ width: "31%" }}>{c.file.type.startsWith("image") ? <Image source={{ uri: c.file.uri }} style={{ width: "100%", aspectRatio: 1, borderRadius: 8 }} /> : <View style={{ width: "100%", aspectRatio: 1, borderRadius: 8, backgroundColor: "#eee", alignItems: "center", justifyContent: "center" }}><Video color={colors.muted} /></View>}<Muted>{c.fix.latitude.toFixed(4)}, {c.fix.longitude.toFixed(4)}</Muted></View>)}</View>
        </Card>
        <View style={{ margin: 16 }}><Button title={t("submit")} onPress={() => submit(true)} loading={busy} /><Button title={t("saveDraft")} variant="outline" onPress={() => submit(false)} disabled={busy} /></View>
      </ScrollView>
    </View>
  );
}
