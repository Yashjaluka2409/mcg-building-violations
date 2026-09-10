import { useRouter } from "expo-router";
import { Globe, LogOut, Phone, ShieldCheck, Smartphone, User } from "lucide-react-native";
import { useTranslation } from "react-i18next";
import { Pressable, Text, View } from "react-native";
import { deviceId } from "@/api/client";
import { Button, Card, CardTitle, Header, Pill } from "@/components/ui";
import { setLang } from "@/i18n";
import { useAuth } from "@/store/auth";
import { colors } from "@/theme";

export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const r = useRouter();
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header title={t("profile")} back />
      <Card>
        <View style={{ flexDirection: "row", gap: 14, alignItems: "center" }}><View style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }}><User color="#fff" size={40} /></View><View><Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>{user?.name}</Text><Pill text={user?.role || ""} bg={colors.primary100} fg={colors.primary} /></View></View>
        <View style={{ marginTop: 16, gap: 10 }}>
          <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}><Phone color={colors.muted} size={18} /><Text style={{ fontSize: 16 }}>{user?.mobile}</Text></View>
          <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}><ShieldCheck color={colors.muted} size={18} /><Text style={{ fontSize: 16 }}>{user?.designation} · Zones {user?.zones?.map((z: any) => z.code).join(", ") || "all"}</Text></View>
          {!!user?.delegation_order_no && <Text style={{ color: colors.muted }}>Delegation order: {user.delegation_order_no}</Text>}
          <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}><Smartphone color={colors.muted} size={18} /><Text style={{ fontSize: 14, color: colors.muted }}>Device ID: {deviceId()}</Text></View>
        </View>
      </Card>
      <Card><CardTitle>App Settings</CardTitle>
        <Pressable onPress={() => setLang(i18n.language === "hi" ? "en" : "hi")} style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10 }}><Globe color={colors.muted} size={20} /><Text style={{ flex: 1, fontSize: 17 }}>{t("language")}</Text><Text style={{ color: colors.muted, fontSize: 16 }}>{i18n.language === "hi" ? "हिंदी" : "English"}</Text></Pressable>
      </Card>
      <View style={{ flex: 1 }} />
      <View style={{ margin: 16 }}><Button title={t("logout")} variant="danger" icon={<LogOut color="#fff" size={20} />} onPress={async () => { await logout(); r.replace("/"); }} /></View>
    </View>
  );
}
