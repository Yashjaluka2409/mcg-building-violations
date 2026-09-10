import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { api } from "@/api/client";
import { property } from "@/api/endpoints";
import { Card, CardTitle, Header, Muted } from "@/components/ui";
import LeafletMap from "@/components/LeafletMap";
import { colors } from "@/theme";

/** Field map: government-land layer + open cases, rendered with Leaflet in a WebView (as in the MCG app). */
export default function MapScreen() {
  const r = useRouter();
  const land = useQuery({ queryKey: ["govt-land"], queryFn: () => property.govtLand() });
  const pts = useQuery({ queryKey: ["map-points"], queryFn: () => api.get("/dashboards/map/", { params: { open: 1 } }).then((x) => x.data) });
  const [sel, setSel] = useState<any>(null);
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title="Field Map" subtitle="Government land & violation cases" />
      <Card style={{ flex: 1, padding: 8 }}>
        <CardTitle>Government land layer</CardTitle>
        <Muted>Tap a case marker to open it. Coloured polygons are MCG / HSVP / GMDA / State land.</Muted>
        <View style={{ flex: 1, marginTop: 8, borderRadius: 12, overflow: "hidden" }}><LeafletMap govtLand={land.data} points={pts.data} onPointPress={(p) => { setSel(p); r.push(`/case/${p.id}`); }} /></View>
        {sel && <Text style={{ marginTop: 6, color: colors.muted }}>{sel.case_no} · {sel.address}</Text>}
      </Card>
    </View>
  );
}
