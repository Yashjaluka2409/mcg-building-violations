import { useInfiniteQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AlertTriangle, Lock, OctagonPause, Search } from "lucide-react-native";
import { useState } from "react";
import { FlatList, Image, Pressable, Text, TextInput, View } from "react-native";
import { cases } from "@/api/endpoints";
import { Header, Pill, StatusPill } from "@/components/ui";
import { colors, radius, shadow } from "@/theme";

export default function CasesScreen() {
  const p = useLocalSearchParams<{ inbox?: string; status?: string; mine?: string }>();
  const r = useRouter();
  const [q, setQ] = useState("");
  const params: any = { page_size: 20, ordering: "-updated_at", search: q || undefined, inbox: p.inbox, mine: p.mine };
  if (p.status) params.status__in = p.status;
  const list = useInfiniteQuery({ queryKey: ["cases", params], queryFn: ({ pageParam = 1 }) => cases.list({ ...params, page: pageParam }), initialPageParam: 1, getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined) });
  const items = list.data?.pages.flatMap((pg: any) => pg.results) || [];
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title={p.inbox ? "Inbox" : p.mine ? "My Cases" : "Cases"} subtitle={p.status ? p.status.replace(/_/g, " ") : "Violation cases in your area"} />
      <View style={{ margin: 16, marginBottom: 4, flexDirection: "row", alignItems: "center", backgroundColor: "#fff", borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12 }}><Search color={colors.muted} size={18} /><TextInput style={{ flex: 1, paddingVertical: 10, paddingHorizontal: 8, fontSize: 15 }} placeholder="Case no, PID, address, owner" value={q} onChangeText={setQ} returnKeyType="search" /></View>
      <FlatList data={items} keyExtractor={(x: any) => x.id} onEndReached={() => list.hasNextPage && list.fetchNextPage()} refreshing={list.isRefetching} onRefresh={() => list.refetch()} contentContainerStyle={{ padding: 16, paddingTop: 8, gap: 12 }}
        ListEmptyComponent={<Text style={{ textAlign: "center", color: colors.muted, marginTop: 40 }}>{list.isLoading ? "Loading…" : "No cases"}</Text>}
        renderItem={({ item: c }: any) => (
          <Pressable onPress={() => r.push(`/case/${c.id}`)} style={{ backgroundColor: "#fff", borderRadius: radius.lg, padding: 14, ...shadow, flexDirection: "row", gap: 12 }}>
            {c.thumbnail ? <Image source={{ uri: c.thumbnail }} style={{ width: 64, height: 64, borderRadius: 10, backgroundColor: "#eee" }} /> : <View style={{ width: 64, height: 64, borderRadius: 10, backgroundColor: colors.primary100 }} />}
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Text style={{ fontWeight: "700", color: colors.primary, fontSize: 12 }}>{c.case_no}</Text>{c.stop_work_issued && <OctagonPause color={colors.danger} size={14} />}{c.sealed && <Lock color="#b45309" size={14} />}{c.sla_breached && <AlertTriangle color={colors.danger} size={14} />}</View>
              <Text style={{ fontWeight: "600", color: colors.text }} numberOfLines={1}>{c.address_line}</Text>
              <Text style={{ color: colors.muted, fontSize: 12 }} numberOfLines={1}>{c.primary_violation?.code} {c.primary_violation?.title_en}</Text>
              <View style={{ flexDirection: "row", gap: 6, marginTop: 6, flexWrap: "wrap" }}><StatusPill status={c.status} /><Pill text={c.land_type === "PRIVATE" ? "Private" : c.land_type === "UNKNOWN" ? "?" : "Govt land"} bg={c.land_type.startsWith("GOVT") ? colors.danger100 : "#f3f4f6"} fg={c.land_type.startsWith("GOVT") ? colors.danger : colors.muted} /><Pill text={`W${c.ward_number ?? "-"} · ${c.days_in_stage}d`} bg="#f3f4f6" fg={colors.muted} /></View>
            </View>
          </Pressable>)} />
    </View>
  );
}
