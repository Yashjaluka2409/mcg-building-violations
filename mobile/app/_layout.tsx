import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import "@/i18n";
import { useAuth } from "@/store/auth";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

export default function RootLayout() {
  const load = useAuth((s) => s.load);
  useEffect(() => { load(); }, [load]);
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={qc}>
        <StatusBar style="light" />
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="inspection/new" />
          <Stack.Screen name="case/[id]" />
          <Stack.Screen name="tasks/index" />
        </Stack>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
