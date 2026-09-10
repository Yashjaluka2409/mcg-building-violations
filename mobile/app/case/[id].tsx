import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import { Camera, Download, FileSignature, Hammer, Lock, MessageSquareReply, OctagonPause, Send, Video } from "lucide-react-native";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, Image, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { API_BASE, getToken } from "@/api/client";
import { cases, notices } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button, Card, CardTitle, Header, Input, Muted, Pill, StatusPill } from "@/components/ui";
import { captureWithCamera, Fix, pickDocument, uploadMedia } from "@/services/capture";
import { enqueue } from "@/services/offline";
import { colors, radius } from "@/theme";

type Sheet = null | "service" | "response" | "execution";

export default function CaseScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["case", id], queryFn: () => cases.get(id!) });
  const [sheet, setSheet] = useState<Sheet>(null);
  const [f, setF] = useState<any>({});
  const [caps, setCaps] = useState<{ file: any; fix: Fix | null; id?: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const act = useMutation({ mutationFn: ({ action, data }: any) => cases.action(id!, action, data), onSuccess: () => { qc.invalidateQueries({ queryKey: ["case", id] }); qc.invalidateQueries({ queryKey: ["counts"] }); setSheet(null); setCaps([]); setF({}); }, onError: (e) => Alert.alert("Error", errorMessage(e)) });
  if (!q.data) return <View style={{ flex: 1, backgroundColor: colors.bg }}><Header title="Case" back /></View>;
  const c = q.data;
  const can = (a: string) => c.available_actions.includes(a);
  const pendingNotice = c.notices.find((n: any) => (c.status === "ORDER_ISSUED" ? n.is_final_order : n.kind === "NOTICE") && !n.served_at) || c.notices[0];
  const capture = async (video: boolean, kind: string) => { try { const x = await captureWithCamera(video); if (!x) return; const up = await uploadMedia({ uri: x.uri, name: x.name, type: x.type }, kind, { caseId: c.id, noticeId: kind.includes("DELIVERY") ? pendingNotice?.id : undefined, fix: x.fix }); setCaps((s) => [...s, { file: { uri: x.uri, type: x.type }, fix: x.fix, id: up.id }]); } catch (e: any) { if (e?.message === "Network Error") { Alert.alert("Offline", "Photo queued; sync from Home when online."); } else Alert.alert("Camera", errorMessage(e)); } };
  const pickDoc = async () => { const d = await pickDocument(); if (!d) return; const up = await uploadMedia(d, "RESPONSE", { caseId: c.id, fix: null }); setCaps((s) => [...s, { file: { uri: d.uri, type: d.type }, fix: null, id: up.id }]); };
  const openPdf = async (nid: string) => { const tok = await getToken("accessToken"); Linking.openURL(`${API_BASE}${notices.pdfPath(nid)}?token=${tok}`); };
  const ids = caps.map((x) => x.id).filter(Boolean);
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title={c.case_no} subtitle={`Ward ${c.ward_number ?? "-"} · ${c.current_owner_role}`} back />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <Card>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 8 }}><StatusPill status={c.status} /><Pill text={c.land_type.startsWith("GOVT") ? t("governmentLand") : t("private")} bg={c.land_type.startsWith("GOVT") ? colors.danger100 : "#f3f4f6"} fg={c.land_type.startsWith("GOVT") ? colors.danger : colors.muted} />{c.stop_work_issued && <Pill text={t("stopWork")} bg={colors.danger100} fg={colors.danger} />}{c.sealed && <Pill text={t("sealedPremises")} bg={colors.secondary100} fg="#b45309" />}</View>
          <Text style={{ fontSize: 17, fontWeight: "700" }}>{c.address_line}</Text>
          <Muted>{c.pid ? `PID ${c.pid} · ` : ""}{c.owner_name || "-"} · {c.pid_linked_mobile || c.alternate_mobile || "no mobile"}</Muted>
          {c.response_due_at && c.status === "SCN_SERVED" && <Text style={{ color: colors.danger, marginTop: 6, fontWeight: "600" }}>Reply due {String(c.response_due_at).slice(0, 10)}</Text>}
          {c.compliance_due_at && ["ORDER_SERVED", "EXECUTION_DUE"].includes(c.status) && <Text style={{ color: colors.danger, marginTop: 6, fontWeight: "600" }}>Comply by {String(c.compliance_due_at).slice(0, 10)}{c.status === "EXECUTION_DUE" ? " - period over, execution due" : ""}</Text>}
        </Card>
        <Card><CardTitle>{t("violations")}</CardTitle>{c.violations.map((v: any) => <View key={v.id} style={{ marginBottom: 8 }}><Text style={{ fontWeight: "600" }}><Text style={{ color: colors.primary }}>{v.code}</Text> {v.violation_type.title_en}</Text><Muted>{v.violation_type.contravention_of}</Muted>{!!v.remarks && <Muted>{v.remarks}</Muted>}</View>)}<Text style={{ marginTop: 6 }}>{c.description}</Text></Card>
        {c.notices.length > 0 && <Card><CardTitle>Notices & orders</CardTitle>{c.notices.map((n: any) => <View key={n.id} style={{ borderTopWidth: 1, borderColor: colors.border, paddingVertical: 8 }}><Text style={{ fontWeight: "700", color: colors.primary }}>{n.notice_no}</Text><Text>{n.order_type.title_en}</Text><Muted>{String(n.issued_at).slice(0, 10)} · {n.signature_status === "SIGNED" ? "digitally signed" : n.signature_status} · {n.served_at ? `served ${n.served_mode} ${String(n.served_at).slice(0, 10)}` : "NOT SERVED"}</Muted><Pressable onPress={() => openPdf(n.id)} style={{ flexDirection: "row", gap: 6, alignItems: "center", marginTop: 6 }}><Download color={colors.accent} size={18} /><Text style={{ color: colors.accent, fontWeight: "600" }}>Open / print PDF</Text></Pressable></View>)}</Card>}
        <Card><CardTitle>Actions</CardTitle>
          {can("submit_to_ae") && <Button title={t("submit")} icon={<Send color="#fff" size={18} />} onPress={() => act.mutate({ action: "submit", data: {} })} />}
          {can("record_service") && <Button title={t("recordDelivery")} variant="accent" icon={<FileSignature color="#fff" size={18} />} onPress={() => setSheet("service")} />}
          {can("record_response") && <Button title={t("uploadReply")} variant="outline" icon={<MessageSquareReply color={colors.text} size={18} />} onPress={() => setSheet("response")} />}
          {can("record_execution") && <Button title={t("recordExecution")} variant="danger" icon={<Hammer color="#fff" size={18} />} onPress={() => setSheet("execution")} />}
          {!can("submit_to_ae") && !can("record_service") && !can("record_response") && !can("record_execution") && <Muted>No field action pending on this case for your role.</Muted>}
        </Card>
        <Card><CardTitle>{t("evidence")} ({c.media.length})</CardTitle><View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>{c.media.map((m: any) => <View key={m.id} style={{ width: "31%" }}>{m.media_type === "IMAGE" && m.url ? <Image source={{ uri: m.url }} style={{ width: "100%", aspectRatio: 1, borderRadius: 8 }} /> : <View style={{ width: "100%", aspectRatio: 1, borderRadius: 8, backgroundColor: "#eee", alignItems: "center", justifyContent: "center" }}><Video color={colors.muted} /></View>}<Muted>{m.kind.replace(/_/g, " ").toLowerCase()}{m.latitude ? (m.geotag_verified ? " ✓" : " ✗") : ""}</Muted></View>)}</View></Card>
        <Card><CardTitle>Timeline</CardTitle>{c.events.slice().reverse().slice(0, 12).map((e: any) => <View key={e.id} style={{ borderLeftWidth: 2, borderColor: colors.primary, paddingLeft: 10, marginBottom: 8 }}><Text style={{ fontWeight: "600" }}>{e.action.replace(/_/g, " ")}</Text><Muted>{String(e.at).replace("T", " ").slice(0, 16)} · {e.actor?.name || "system"}{e.remarks ? ` · ${e.remarks}` : ""}</Muted></View>)}</Card>
      </ScrollView>
      <Modal visible={!!sheet} animationType="slide" transparent onRequestClose={() => setSheet(null)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,.4)", justifyContent: "flex-end" }}>
          <View style={{ backgroundColor: "#fff", borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: 20, maxHeight: "88%" }}>
            <ScrollView>
              {sheet === "service" && <>
                <Text style={{ fontSize: 20, fontWeight: "800", marginBottom: 6 }}>{t("recordDelivery")}</Text><Muted>{pendingNotice?.notice_no} · {pendingNotice?.order_type?.title_en}</Muted>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 12 }}>{["AFFIXATION", "IN_PERSON", "POST", "BEAT_OF_DRUM"].map((m) => <Pressable key={m} onPress={() => setF({ ...f, mode: m })}><Pill text={m.replace(/_/g, " ")} bg={(f.mode || "AFFIXATION") === m ? colors.primary : "#f3f4f6"} fg={(f.mode || "AFFIXATION") === m ? "#fff" : colors.muted} /></Pressable>)}</View>
                <Input label="Remarks (received by / refused / witnesses)" value={f.remarks || ""} onChangeText={(v) => setF({ ...f, remarks: v })} />
                <Button title="Photograph the affixed / delivered notice" variant="accent" icon={<Camera color="#fff" size={18} />} onPress={() => capture(false, c.status === "ORDER_ISSUED" ? "ORDER_DELIVERY" : "NOTICE_DELIVERY")} />
                <Thumbs caps={caps} />
                <Button title="Confirm delivery" onPress={() => act.mutate({ action: "record_service", data: { notice: pendingNotice?.id, mode: f.mode || "AFFIXATION", remarks: f.remarks || "", media_ids: ids } })} loading={act.isPending} disabled={!ids.length} />
              </>}
              {sheet === "response" && <>
                <Text style={{ fontSize: 20, fontWeight: "800", marginBottom: 6 }}>{t("uploadReply")}</Text>
                <Input label="Received on (YYYY-MM-DD)" value={f.received_on || new Date().toISOString().slice(0, 10)} onChangeText={(v) => setF({ ...f, received_on: v })} />
                <Input label="Submitted by" value={f.submitted_by_name || ""} onChangeText={(v) => setF({ ...f, submitted_by_name: v })} />
                <Input label="Summary of reply" multiline numberOfLines={4} value={f.summary || ""} onChangeText={(v) => setF({ ...f, summary: v })} />
                <View style={{ flexDirection: "row", gap: 8 }}><View style={{ flex: 1 }}><Button title="Photograph reply" variant="accent" icon={<Camera color="#fff" size={18} />} onPress={() => capture(false, "RESPONSE")} /></View><View style={{ flex: 1 }}><Button title="Pick from gallery" variant="outline" onPress={pickDoc} /></View></View>
                <Thumbs caps={caps} />
                <Button title="Submit reply" onPress={() => act.mutate({ action: "record_response", data: { received_on: f.received_on || new Date().toISOString().slice(0, 10), submitted_by_name: f.submitted_by_name || "", summary: f.summary, requests_hearing: false, media_ids: ids } })} loading={act.isPending} disabled={!f.summary} />
              </>}
              {sheet === "execution" && <>
                <Text style={{ fontSize: 20, fontWeight: "800", marginBottom: 6 }}>{t("recordExecution")}</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 8 }}>{["DEMOLITION", "PARTIAL_DEMOLITION", "SEALING", "EVICTION", "REMOVAL"].map((m) => <Pressable key={m} onPress={() => setF({ ...f, action: m })}><Pill text={m.replace(/_/g, " ")} bg={(f.action || "DEMOLITION") === m ? colors.danger : "#f3f4f6"} fg={(f.action || "DEMOLITION") === m ? "#fff" : colors.muted} /></Pressable>)}</View>
                <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>{[["CORPORATION", "By MCG squad"], ["OWNER_SELF", "By owner"]].map(([m, l]) => <Pressable key={m} onPress={() => setF({ ...f, mode: m })}><Pill text={l} bg={(f.mode || "CORPORATION") === m ? colors.primary : "#f3f4f6"} fg={(f.mode || "CORPORATION") === m ? "#fff" : colors.muted} /></Pressable>)}</View>
                <Input label="Squad in-charge" value={f.squad_incharge || ""} onChangeText={(v) => setF({ ...f, squad_incharge: v })} /><Input label="Police station (if assistance)" value={f.police_station || ""} onChangeText={(v) => setF({ ...f, police_station: v })} /><Input label="Seal memo no. (sealing)" value={f.seal_memo_no || ""} onChangeText={(v) => setF({ ...f, seal_memo_no: v })} /><Input label="Cost incurred (INR)" keyboardType="numeric" value={f.cost || ""} onChangeText={(v) => setF({ ...f, cost: v })} /><Input label="Remarks" value={f.remarks || ""} onChangeText={(v) => setF({ ...f, remarks: v })} />
                <View style={{ flexDirection: "row", gap: 8 }}><View style={{ flex: 1 }}><Button title={t("takePhoto")} variant="accent" icon={<Camera color="#fff" size={18} />} onPress={() => capture(false, (f.mode || "CORPORATION") === "OWNER_SELF" ? "COMPLIANCE" : "EXECUTION")} /></View><View style={{ flex: 1 }}><Button title={t("recordVideo")} variant="outline" icon={<Video color={colors.text} size={18} />} onPress={() => capture(true, (f.mode || "CORPORATION") === "OWNER_SELF" ? "COMPLIANCE" : "EXECUTION")} /></View></View>
                <Thumbs caps={caps} />
                <Button title="Confirm" variant="danger" icon={<Lock color="#fff" size={18} />} onPress={() => act.mutate({ action: "record_execution", data: { action: f.action || "DEMOLITION", mode: f.mode || "CORPORATION", executed_on: new Date().toISOString(), media_ids: ids, squad_incharge: f.squad_incharge || "", police_assistance: !!f.police_station, police_station: f.police_station || "", seal_memo_no: f.seal_memo_no || "", cost_incurred_inr: f.cost || null, remarks: f.remarks || "" } })} loading={act.isPending} disabled={!ids.length} />
              </>}
              <Button title="Cancel" variant="outline" onPress={() => { setSheet(null); setCaps([]); }} />
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}
function Thumbs({ caps }: { caps: { file: any; fix: Fix | null }[] }) {
  return <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 8 }}>{caps.map((c, i) => <View key={i} style={{ width: "23%" }}>{c.file.type?.startsWith("image") ? <Image source={{ uri: c.file.uri }} style={{ width: "100%", aspectRatio: 1, borderRadius: 8 }} /> : <View style={{ width: "100%", aspectRatio: 1, borderRadius: 8, backgroundColor: "#eee" }} />}{c.fix && <Text style={{ fontSize: 9, color: colors.muted }}>{c.fix.latitude.toFixed(4)},{c.fix.longitude.toFixed(4)}</Text>}</View>)}</View>;
}
