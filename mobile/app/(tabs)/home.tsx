import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { CloudUpload, Crosshair, FileSignature, FolderKanban, Hammer, Inbox, MapPin, PlusCircle } from "lucide-react-native";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import * as Location from "expo-location";
import { cases, dashboards } from "@/api/endpoints";
import { Card, CardTitle, Header, Pill, Stat, Tile } from "@/components/ui";
import { pending, sync } from "@/services/offline";
import { useAuth } from "@/store/auth";
import { colors } from "@/theme";

export default function HomeScreen() {
  const { t } = useTranslation();
  const r = useRouter();
  const user = useAuth((s) => s.user);
  const counts = useQuery({ queryKey: ["counts"], queryFn: cases.counts });
  const taskCounts = useQuery({ queryKey: ["task-counts"], queryFn: () => import("@/api/client").then(({ api }) => api.get("/inspections/tasks/counts/").then((x) => x.data)) });
  const deadlines = useQuery({ queryKey: ["deadlines"], queryFn: dashboards.deadlines });
  const [acc, setAcc] = useState<number | null>(null);
  const [queued, setQueued] = useState(0);
  const [syncing, setSyncing] = useState(false);
  useEffect(() => { (async () => { const p = await Location.requestForegroundPermissionsAsync(); if (p.granted) { const l = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }); setAcc(l.coords.accuracy ?? null); } setQueued(await pending()); })(); }, []);
  const doSync = async () => { setSyncing(true); await sync(); setQueued(await pending()); counts.refetch(); setSyncing(false); };
  const greet = new Date().getHours() < 12 ? "Good Morning!" : new Date().getHours() < 17 ? "Good Afternoon!" : "Good Evening!";
  const role = user?.role;
  const c = counts.data || {};
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title={greet} subtitle={`${user?.name || ""} · ${user?.designation || role || ""}`} />
      <ScrollView refreshControl={<RefreshControl refreshing={counts.isFetching} onRefresh={() => { counts.refetch(); deadlines.refetch(); }} />} contentContainerStyle={{ paddingBottom: 30 }}>
        <Card><View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}><CardTitle>{t("locationStatus")}</CardTitle><Pill text={acc == null ? "NO FIX" : acc <= 25 ? t("good") : t("poor")} bg={acc != null && acc <= 25 ? colors.success100 : colors.secondary100} fg={acc != null && acc <= 25 ? colors.success : "#b45309"} /></View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><MapPin color={colors.primary} size={18} /><Text style={{ color: colors.muted }}>{t("gpsAccuracy")}: {acc == null ? "-" : `${Math.round(acc)} m`}</Text></View></Card>
        <Card><CardTitle>{t("todaysSummary")}</CardTitle><View style={{ flexDirection: "row" }}><Stat value={c.inbox ?? 0} label={t("inbox")} /><Stat value={c.to_serve ?? 0} label={t("toServe")} color={colors.accent} /><Stat value={c.execution_due ?? 0} label={t("executionDue")} color={colors.danger} /><Stat value={c.overdue ?? 0} label={t("overdue")} color={colors.secondary} /></View></Card>
        <Card><CardTitle>{t("quickActions")}</CardTitle>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
            {["JE", "AE", "FIELD_STAFF", "ADMIN"].includes(role) && <Tile icon={<PlusCircle color={colors.secondary} size={30} />} label={t("newInspection")} onPress={() => r.push("/inspection/new")} />}
            <Tile icon={<Crosshair color={colors.secondary} size={30} />} label="Planned inspections" badge={taskCounts.data?.assigned_to_me} onPress={() => r.push("/tasks")} />
            <Tile icon={<Inbox color={colors.secondary} size={30} />} label={t("inbox")} badge={c.inbox} onPress={() => r.push({ pathname: "/(tabs)/cases", params: { inbox: "1" } })} />
            <Tile icon={<FileSignature color={colors.secondary} size={30} />} label={t("toServe")} badge={c.to_serve} onPress={() => r.push({ pathname: "/(tabs)/cases", params: { status: "SCN_ISSUED,ORDER_ISSUED" } })} />
            <Tile icon={<Hammer color={colors.secondary} size={30} />} label={t("executionDue")} badge={c.execution_due} onPress={() => r.push({ pathname: "/(tabs)/cases", params: { status: "EXECUTION_DUE" } })} />
            <Tile icon={<FolderKanban color={colors.secondary} size={30} />} label={t("myCases")} onPress={() => r.push({ pathname: "/(tabs)/cases", params: { mine: "1" } })} />
            {c.drafts > 0 && <Tile icon={<FolderKanban color={colors.muted} size={30} />} label={t("drafts")} badge={c.drafts} onPress={() => r.push({ pathname: "/(tabs)/cases", params: { status: "DRAFT" } })} />}
          </View></Card>
        {queued > 0 && <Card><Pressable onPress={doSync} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}><CloudUpload color={colors.accent} size={26} /><View style={{ flex: 1 }}><Text style={{ fontWeight: "700" }}>{t("offlineQueue")}: {queued}</Text><Text style={{ color: colors.muted, fontSize: 13 }}>{syncing ? "Syncing…" : t("sync")}</Text></View></Pressable></Card>}
        {deadlines.data && (deadlines.data.compliance_due?.length || deadlines.data.responses_due?.length) ? <Card><CardTitle>Deadlines this week</CardTitle>{[...(deadlines.data.compliance_due || []).map((x: any) => ({ ...x, k: "Comply by" })), ...(deadlines.data.responses_due || []).map((x: any) => ({ ...x, k: "Reply due" }))].slice(0, 8).map((d: any) => <Pressable key={d.id + d.k} onPress={() => r.push(`/case/${d.id}`)} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: colors.border }}><Text style={{ fontWeight: "600" }}>{d.case_no} · Ward {d.ward ?? "-"}</Text><Text style={{ color: colors.muted, fontSize: 13 }}>{d.k} {String(d.due).slice(0, 10)} · {d.address}</Text></Pressable>)}</Card> : null}
      </ScrollView>
    </View>
  );
}
