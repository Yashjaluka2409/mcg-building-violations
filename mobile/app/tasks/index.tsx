import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import * as Location from "expo-location";
import { Camera, MapPin, Navigation, Play } from "lucide-react-native";
import { useEffect, useState } from "react";
import { Alert, FlatList, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { api, errorMessage } from "@/api/client";
import { Button, Card, Header, Input, Muted, Pill } from "@/components/ui";
import { captureWithCamera, Fix, uploadMedia } from "@/services/capture";
import { colors, radius, shadow } from "@/theme";

const TSTAT: Record<string, { bg: string; fg: string }> = { ASSIGNED: { bg: "#fef3c7", fg: "#b45309" }, UNASSIGNED: { bg: "#f3f4f6", fg: "#6b7280" }, IN_PROGRESS: { bg: "#d1faf8", fg: "#0f766e" }, VIOLATION_RECORDED: { bg: "#fee2e2", fg: "#b91c1c" }, NO_VIOLATION: { bg: "#dcfce7", fg: "#166534" }, NOT_FOUND: { bg: "#f3f4f6", fg: "#374151" }, CANCELLED: { bg: "#f3f4f6", fg: "#9ca3af" } };
const dist = (a: [number, number], b: [number, number]) => { const R = 6371000, p1 = (a[0] * Math.PI) / 180, p2 = (b[0] * Math.PI) / 180, dp = ((b[0] - a[0]) * Math.PI) / 180, dl = ((b[1] - a[1]) * Math.PI) / 180; const x = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(x)); };

/** Planned inspections pushed by the JC. "Start" works only within the geofence (default 100 m):
 *  the phone's GPS fix is sent to the server, which refuses the start if the officer is not on site. */
export default function TasksScreen() {
  const r = useRouter();
  const qc = useQueryClient();
  const [me, setMe] = useState<[number, number] | null>(null);
  const [closing, setClosing] = useState<any>(null);
  const [remarks, setRemarks] = useState("");
  const [caps, setCaps] = useState<{ id: string; uri: string; fix: Fix }[]>([]);
  const [busy, setBusy] = useState(false);
  const q = useQuery({ queryKey: ["tasks-mine"], queryFn: () => api.get("/inspections/tasks/", { params: { mine: 1, open: 1, page_size: 100, ordering: "due_at" } }).then((x) => x.data) });
  useEffect(() => { (async () => { const p = await Location.requestForegroundPermissionsAsync(); if (p.granted) { const l = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }); setMe([l.coords.latitude, l.coords.longitude]); } })(); }, []);
  const start = async (t: any) => {
    try {
      const l = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Highest });
      const res = await api.post(`/inspections/tasks/${t.id}/start/`, { latitude: l.coords.latitude.toFixed(7), longitude: l.coords.longitude.toFixed(7), accuracy_m: Math.round(l.coords.accuracy ?? 0) });
      qc.invalidateQueries({ queryKey: ["tasks-mine"] });
      r.push({ pathname: "/inspection/new", params: { task: String(res.data.id), pid: res.data.pid || "", address: res.data.address || "", lat: String(res.data.latitude ?? ""), lng: String(res.data.longitude ?? ""), owner: res.data.owner_name || "", mobile: res.data.owner_mobile || "", instructions: res.data.instructions || "" } });
    } catch (e) { Alert.alert("Cannot start", errorMessage(e)); }
  };
  const capture = async () => { try { const c = await captureWithCamera(false); if (!c) return; const up = await uploadMedia({ uri: c.uri, name: c.name, type: c.type }, "TASK_EVIDENCE", { fix: c.fix }); setCaps((s) => [...s, { id: up.id, uri: c.uri, fix: c.fix }]); } catch (e) { Alert.alert("Camera", errorMessage(e)); } };
  const submitClose = async (outcome: string) => {
    setBusy(true);
    try { const l = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Highest }); await api.post(`/inspections/tasks/${closing.id}/close/`, { outcome, remarks, media_ids: caps.map((c) => c.id), latitude: l.coords.latitude.toFixed(7), longitude: l.coords.longitude.toFixed(7) }); setClosing(null); setCaps([]); setRemarks(""); qc.invalidateQueries({ queryKey: ["tasks-mine"] }); Alert.alert("Filed", "Inspection report filed."); } catch (e) { Alert.alert("Error", errorMessage(e)); }
    setBusy(false);
  };
  const items = q.data?.results || [];
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title="Planned Inspections" subtitle={`${items.length} assigned · start within 100 m of the property`} back />
      <FlatList data={items} keyExtractor={(x: any) => String(x.id)} refreshing={q.isFetching} onRefresh={() => q.refetch()} contentContainerStyle={{ padding: 16, gap: 12 }}
        ListEmptyComponent={<Text style={{ textAlign: "center", color: colors.muted, marginTop: 40 }}>{q.isLoading ? "Loading…" : "No planned inspections assigned to you"}</Text>}
        renderItem={({ item: t }: any) => { const d = me && t.latitude ? dist(me, [Number(t.latitude), Number(t.longitude)]) : null; const near = d != null && d <= (t.geofence_m || 100); const c = TSTAT[t.status] || TSTAT.ASSIGNED; return (
          <View style={{ backgroundColor: "#fff", borderRadius: radius.lg, padding: 14, ...shadow }}>
            <View style={{ flexDirection: "row", gap: 6, alignItems: "center", flexWrap: "wrap" }}><Pill text={t.category_display} bg={colors.primary100} fg={colors.primary} /><Pill text={t.status_display} bg={c.bg} fg={c.fg} />{t.is_overdue && <Pill text="OVERDUE" bg={colors.danger100} fg={colors.danger} />}</View>
            <Text style={{ fontWeight: "700", fontSize: 16, marginTop: 6 }}>{t.address || "(map point)"}</Text>
            <Muted>{t.pid ? `PID ${t.pid} · ` : ""}{t.owner_name}{t.owner_mobile ? ` · ${t.owner_mobile}` : ""}{t.ward_number ? ` · Ward ${t.ward_number}` : ""}</Muted>
            <Text style={{ marginTop: 6 }}>{t.instructions}</Text>
            <Muted>Pushed by {t.created_by?.name} · due {String(t.due_at || "").slice(0, 10)}</Muted>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8 }}><MapPin color={near ? colors.success : colors.muted} size={16} /><Text style={{ color: near ? colors.success : colors.muted, fontWeight: "600" }}>{d == null ? (t.latitude ? "Locating…" : "No coordinates - your start location will be recorded") : `${Math.round(d)} m away${near ? " · within geofence" : " · move closer to start"}`}</Text></View>
            <View style={{ flexDirection: "row", gap: 8 }}><View style={{ flex: 1 }}><Button title={t.status === "IN_PROGRESS" ? "Continue inspection" : "Start inspection"} variant={near || !t.latitude ? "primary" : "outline"} icon={<Play color={near || !t.latitude ? "#fff" : colors.text} size={18} />} onPress={() => start(t)} /></View>{t.status === "IN_PROGRESS" && <View style={{ flex: 1 }}><Button title="No violation" variant="outline" onPress={() => setClosing(t)} /></View>}</View>
          </View>); }} />
      <Modal visible={!!closing} animationType="slide" transparent onRequestClose={() => setClosing(null)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,.4)", justifyContent: "flex-end" }}><View style={{ backgroundColor: "#fff", borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: 20, maxHeight: "85%" }}><ScrollView>
          <Text style={{ fontSize: 20, fontWeight: "800" }}>Report from site</Text><Muted>{closing?.address}</Muted>
          <Input label="What was found" multiline numberOfLines={4} value={remarks} onChangeText={setRemarks} placeholder="e.g. Residential use by owner's family; no PG activity; no construction." style={{ marginTop: 10 }} />
          <Button title="Photograph the property (mandatory)" variant="accent" icon={<Camera color="#fff" size={18} />} onPress={capture} /><Muted>{caps.length} photo(s) attached{caps[0] ? ` · ${caps[0].fix.latitude.toFixed(4)}, ${caps[0].fix.longitude.toFixed(4)}` : ""}</Muted>
          <Button title="File: no violation found" onPress={() => submitClose("NO_VIOLATION")} loading={busy} disabled={!remarks || !caps.length} /><Button title="File: property not traceable" variant="outline" onPress={() => submitClose("NOT_FOUND")} disabled={!remarks || !caps.length} /><Button title="Cancel" variant="outline" onPress={() => setClosing(null)} />
        </ScrollView></View></View>
      </Modal>
    </View>
  );
}
