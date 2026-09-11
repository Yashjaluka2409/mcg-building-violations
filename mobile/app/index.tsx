import { Redirect, useRouter } from "expo-router";
import { Phone } from "lucide-react-native";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Image, KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from "react-native";
import { auth } from "@/api/endpoints";
import { API_BASE, deviceId, errorMessage, setServer } from "@/api/client";
import { Button } from "@/components/ui";
import { useAuth } from "@/store/auth";
import { colors, radius } from "@/theme";

/** OTP login screen - same composition as the MCG HARYANA app login (logo, purple ground, white card). */
export default function Login() {
  const { t } = useTranslation();
  const { user, loading, login } = useAuth();
  const r = useRouter();
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [stage, setStage] = useState<"mobile" | "otp">("mobile");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [editServer, setEditServer] = useState(false);
  const [server, setServerText] = useState(API_BASE.replace(/\/building-violations\/api$/, ""));
  if (loading) return <View style={s.root}><ActivityIndicator color="#fff" /></View>;
  if (user) return <Redirect href="/(tabs)/home" />;
  const send = async () => { setBusy(true); setErr(""); try { await auth.requestOtp(mobile); setStage("otp"); } catch (e) { setErr(errorMessage(e)); } setBusy(false); };
  const verify = async () => { setBusy(true); setErr(""); try { const d = await auth.verifyOtp(mobile, otp, deviceId()); await login(d.access_token, d.refresh_token, d.user); r.replace("/(tabs)/home"); } catch (e) { setErr(errorMessage(e)); } setBusy(false); };
  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.root}>
      <View style={{ alignItems: "center", marginBottom: 28 }}>
        <View style={s.logoBox}><Image source={require("../assets/brand/mcg-logo.png")} style={{ width: 200, height: 86, resizeMode: "contain" }} /></View>
        <Text style={s.title}>Building Violations</Text>
        <Text style={s.sub}>Municipal Corporation of Gurugram</Text>
      </View>
      <View style={s.card}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 14 }}><Phone color={colors.primary} size={22} /><Text style={{ fontSize: 22, fontWeight: "700", color: colors.text }}>{t("login")}</Text></View>
        {stage === "mobile" ? (
          <>
            <Text style={s.label}>{t("phone")}</Text>
            <View style={{ flexDirection: "row", gap: 10 }}><View style={s.cc}><Text style={{ fontSize: 18, color: colors.muted }}>+91</Text></View><TextInput style={[s.input, { flex: 1 }]} keyboardType="number-pad" maxLength={10} placeholder="Enter Number" placeholderTextColor={colors.muted} value={mobile} onChangeText={(v) => setMobile(v.replace(/\D/g, ""))} /></View>
            <Button title={t("sendOtp")} onPress={send} disabled={mobile.length !== 10} loading={busy} />
          </>
        ) : (
          <>
            <Text style={s.label}>{t("otp")} · +91 {mobile}</Text>
            <TextInput style={[s.input, { textAlign: "center", letterSpacing: 8, fontSize: 22 }]} keyboardType="number-pad" maxLength={6} value={otp} onChangeText={(v) => setOtp(v.replace(/\D/g, ""))} autoFocus />
            <Button title={t("verify")} onPress={verify} disabled={otp.length < 4} loading={busy} />
            <Button title="Change number" variant="outline" onPress={() => setStage("mobile")} />
          </>
        )}
        {!!err && <Text style={{ color: colors.danger, marginTop: 10, textAlign: "center" }}>{err}</Text>}
        {editServer ? (
          <View style={{ marginTop: 14 }}>
            <Text style={s.label}>Server (portal address)</Text>
            <TextInput style={s.input} autoCapitalize="none" autoCorrect={false} keyboardType="url" value={server} onChangeText={setServerText} placeholder="https://sandbox.example.gov.in" />
            <Button title="Save server" variant="outline" onPress={async () => { const b = await setServer(server); setServerText(b.replace(/\/building-violations\/api$/, "")); setEditServer(false); setErr(""); }} />
          </View>
        ) : (
          <Text onPress={() => setEditServer(true)} style={{ color: colors.muted, fontSize: 12, textAlign: "center", marginTop: 14 }}>Server: {server.replace(/^https?:\/\//, "")}  ·  change</Text>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.primary, justifyContent: "center", padding: 22 },
  logoBox: { backgroundColor: "#fff", borderRadius: 6, padding: 6, marginBottom: 18 },
  title: { color: "#fff", fontSize: 30, fontWeight: "800" }, sub: { color: "#f2e7ed", fontSize: 17, marginTop: 4 },
  card: { backgroundColor: "#fff", borderRadius: radius.xl, padding: 22 },
  label: { fontSize: 16, fontWeight: "700", color: colors.text, marginBottom: 10 },
  cc: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 16, justifyContent: "center", backgroundColor: "#f9fafb" },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 14, fontSize: 18, color: colors.text },
});
