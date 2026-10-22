import { useEffect, useState } from "react";

import { Toaster } from "./components/Toaster";
import { Sidebar } from "./components/layout/Sidebar";
import { Topbar } from "./components/layout/Topbar";
import { ConvertHome } from "./features/convert/ConvertHome";
import { Workbench } from "./features/convert/Workbench";
import { HistoryView } from "./features/history/HistoryView";
import { SettingsView } from "./features/settings/SettingsView";
import { useProviders } from "./hooks/useProviders";
import { useTheme } from "./hooks/useTheme";
import { api } from "./lib/api";
import { useRoute } from "./lib/router";
import type { AppInfo } from "./types/convert";

const TITLES = { convert: "Convertir", history: "Historique", settings: "Réglages" } as const;

export default function App() {
  const route = useRoute();
  const { theme, toggle } = useTheme();
  const providers = useProviders();
  const [info, setInfo] = useState<AppInfo | null>(null);

  useEffect(() => {
    api.settings.info().then(setInfo, () => undefined);
  }, []);

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar route={route} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          title={TITLES[route.name]}
          theme={theme}
          onToggleTheme={toggle}
          providers={providers.providers}
          providersLoading={providers.loading}
          providersError={providers.error}
          onRefreshProviders={() => providers.refresh(true)}
        />
        <main className="min-h-0 flex-1 overflow-y-auto">
          {route.name === "convert" && (route.id ? <Workbench key={route.id} id={route.id} info={info} /> : <ConvertHome />)}
          {route.name === "history" && <HistoryView />}
          {route.name === "settings" && <SettingsView info={info} />}
        </main>
      </div>
      <Toaster />
    </div>
  );
}
