import { ArrowLeft, Menu } from "lucide-react-native";
import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, ViewStyle } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, radius, shadow, spacing, STATUS_COLORS } from "@/theme";

/** Purple header exactly like the MCG HARYANA app (title + subtitle, back or menu). */
export function Header({ title, subtitle, back, right }: { title: string; subtitle?: string; back?: boolean; right?: React.ReactNode }) {
  const r = useRouter();
  const ins = useSafeAreaInsets();
  return (
    <View style={[s.header, { paddingTop: ins.top + 8 }]}>
      <Pressable onPress={() => (back ? r.back() : r.push("/(tabs)/profile"))} style={s.hbtn}>{back ? <ArrowLeft color="#fff" size={26} /> : <View style={{ width: 26 }} />}</Pressable>
      <View style={{ flex: 1, alignItems: "center" }}><Text style={s.htitle}>{title}</Text>{subtitle ? <Text style={s.hsub}>{subtitle}</Text> : null}</View>
      <View style={s.hbtn}>{right ?? <Pressable onPress={() => r.push("/(tabs)/profile")}><Menu color="#fff" size={26} /></Pressable>}</View>
    </View>
  );
}
export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) { return <View style={[s.card, style]}>{children}</View>; }
export function CardTitle({ children }: { children: React.ReactNode }) { return <Text style={s.cardTitle}>{children}</Text>; }
export function Pill({ text, bg = colors.success100, fg = colors.success }: { text: string; bg?: string; fg?: string }) { return <View style={[s.pill, { backgroundColor: bg }]}><Text style={{ color: fg, fontWeight: "600", fontSize: 12 }}>{text}</Text></View>; }
export function StatusPill({ status }: { status: string }) { const c = STATUS_COLORS[status] || { bg: "#f3f4f6", fg: "#374151" }; return <Pill text={status.replace(/_/g, " ")} bg={c.bg} fg={c.fg} />; }
export function Button({ title, onPress, variant = "primary", disabled, loading, icon }: { title: string; onPress: () => void; variant?: "primary" | "outline" | "danger" | "accent"; disabled?: boolean; loading?: boolean; icon?: React.ReactNode }) {
  const bg = variant === "primary" ? colors.primary : variant === "danger" ? colors.danger : variant === "accent" ? colors.accent : colors.surface;
  const fg = variant === "outline" ? colors.text : "#fff";
  return <Pressable onPress={onPress} disabled={disabled || loading} style={[s.btn, { backgroundColor: disabled ? "#c4c4cc" : bg, borderWidth: variant === "outline" ? 1 : 0, borderColor: colors.border }]}>{loading ? <ActivityIndicator color={fg} /> : <>{icon}<Text style={{ color: fg, fontWeight: "700", fontSize: 16 }}>{title}</Text></>}</Pressable>;
}
export function Input(props: React.ComponentProps<typeof TextInput> & { label?: string }) { return <View style={{ marginBottom: spacing.md }}>{props.label ? <Text style={s.label}>{props.label}</Text> : null}<TextInput placeholderTextColor={colors.muted} {...props} style={[s.input, props.style]} /></View>; }
export function Row({ children, style }: { children: React.ReactNode; style?: ViewStyle }) { return <View style={[{ flexDirection: "row", alignItems: "center", gap: spacing.sm }, style]}>{children}</View>; }
export function Muted({ children }: { children: React.ReactNode }) { return <Text style={{ color: colors.muted, fontSize: 13 }}>{children}</Text>; }
export function Tile({ icon, label, onPress, badge }: { icon: React.ReactNode; label: string; onPress: () => void; badge?: number }) {
  return <Pressable onPress={onPress} style={s.tile}>{icon}<Text style={s.tileText}>{label}</Text>{!!badge && <View style={s.badge}><Text style={{ color: "#fff", fontSize: 11, fontWeight: "700" }}>{badge}</Text></View>}</Pressable>;
}
export function Stat({ value, label, color = colors.primary }: { value: string | number; label: string; color?: string }) { return <View style={{ alignItems: "center", flex: 1 }}><Text style={{ fontSize: 26, fontWeight: "800", color }}>{value}</Text><Text style={{ color: colors.muted, fontSize: 13 }}>{label}</Text></View>; }

const s = StyleSheet.create({
  header: { backgroundColor: colors.primary, flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingBottom: 14, borderBottomLeftRadius: 0 },
  hbtn: { width: 44, alignItems: "center", justifyContent: "center" },
  htitle: { color: "#fff", fontSize: 20, fontWeight: "700" }, hsub: { color: "#f2e7ed", fontSize: 13 },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.lg, marginHorizontal: spacing.lg, marginTop: spacing.md, ...shadow },
  cardTitle: { fontSize: 17, fontWeight: "700", color: colors.text, marginBottom: spacing.sm },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, alignSelf: "flex-start" },
  btn: { flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", paddingVertical: 14, borderRadius: radius.md, marginTop: spacing.sm },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, backgroundColor: "#fff", color: colors.text },
  label: { fontSize: 13, fontWeight: "600", color: colors.text, marginBottom: 6 },
  tile: { width: "48%", backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingVertical: 20, alignItems: "center", gap: 8 },
  tileText: { fontWeight: "600", color: colors.text, textAlign: "center" },
  badge: { position: "absolute", top: 8, right: 8, backgroundColor: colors.danger, borderRadius: 10, minWidth: 20, height: 20, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 },
});
