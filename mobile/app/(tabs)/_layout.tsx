import { Tabs } from "expo-router";
import { FolderKanban, Home, Map as MapIcon, User } from "lucide-react-native";
import { colors } from "@/theme";

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: colors.primary, tabBarInactiveTintColor: colors.muted, tabBarStyle: { height: 62, paddingBottom: 8, paddingTop: 6 }, tabBarLabelStyle: { fontSize: 12, fontWeight: "600" } }}>
      <Tabs.Screen name="home" options={{ title: "Home", tabBarIcon: ({ color }) => <Home color={color} size={24} /> }} />
      <Tabs.Screen name="cases" options={{ title: "Cases", tabBarIcon: ({ color }) => <FolderKanban color={color} size={24} /> }} />
      <Tabs.Screen name="map" options={{ title: "Map", tabBarIcon: ({ color }) => <MapIcon color={color} size={24} /> }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarIcon: ({ color }) => <User color={color} size={24} /> }} />
    </Tabs>
  );
}
