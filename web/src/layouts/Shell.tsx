import { clsx } from "clsx";
import { Bell, BookOpenText, ClipboardList, FileSignature, FolderKanban, Globe, Inbox, LayoutDashboard, LogOut, Map as MapIcon, MapPinned, Menu, Moon, PlusCircle, ScrollText, Sun, UserCog } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { cases, notificationsApi } from "@/api/endpoints";
import { useAuth } from "@/store/auth";
import { ago } from "@/utils/format";

/** Portal shell replicating the MCG platform layout: purple brand header, collapsible sidebar with
 *  role-based menu (like /cd-waste-admin/je/..., /challan/... modules), notification bell, dark mode. */
export default function Shell() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(true);
  const [dark, setDark] = useState(localStorage.getItem("bvmsDark") === "1");
  const [bell, setBell] = useState(false);
  const counts = useQuery({ queryKey: ["counts"], queryFn: cases.counts, refetchInterval: 60_000 });
  const notes = useQuery({ queryKey: ["notifications"], queryFn: notificationsApi.list, refetchInterval: 60_000 });
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.setItem("bvmsDark", dark ? "1" : "0"); }, [dark]);
  const role = user?.role || "VIEWER";
  const can = (...roles: string[]) => roles.includes(role) || ["ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER"].includes(role);
  const items = [
    { to: "/dashboard", icon: LayoutDashboard, label: t("nav.dashboard") },
    { to: "/inbox", icon: Inbox, label: t("nav.inbox"), badge: counts.data?.inbox },
    { to: "/cases/new", icon: PlusCircle, label: t("nav.new_case"), show: can("JE", "AE", "FIELD_STAFF") },
    { to: "/cases", icon: FolderKanban, label: t("nav.cases") },
    { to: "/map", icon: MapPinned, label: t("nav.map") },
    { to: "/notices", icon: FileSignature, label: t("nav.notices") },
    { to: "/plans", icon: ClipboardList, label: t("nav.plans") },
    { to: "/govt-land", icon: MapIcon, label: t("nav.govt_land") },
    { to: "/reports", icon: ScrollText, label: t("nav.reports") },
    { to: "/legal", icon: BookOpenText, label: t("nav.legal") },
    { to: "/officers", icon: UserCog, label: t("nav.officers"), show: can("JC") },
  ].filter((i) => i.show !== false);
  const unread = notes.data?.results.filter((n) => !n.read_at).length || 0;
  return (
    <div className="min-h-screen flex bg-light-background dark:bg-dark-background">
      <aside className={clsx("bg-white dark:bg-dark-surface border-r border-light-border dark:border-dark-border flex flex-col transition-all duration-200 sticky top-0 h-screen", open ? "w-64" : "w-16")}>
        <div className="flex items-center gap-3 px-3 h-16 border-b border-light-border dark:border-dark-border">
          <img src="/brand/mcg-logo.png" alt="MCG" className={clsx("object-contain", open ? "h-10" : "h-8")} />
          {open && <div className="leading-tight"><div className="font-bold text-primary-600 text-sm">{t("app.title")}</div><div className="text-[11px] text-light-text-muted">{t("app.subtitle")}</div></div>}
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.to === "/cases"} className={({ isActive }) => clsx("flex items-center gap-3 mx-2 my-0.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors", isActive ? "bg-primary-50 text-primary-700 dark:bg-primary-900/40" : "text-light-text dark:text-dark-text hover:bg-gray-50 dark:hover:bg-dark-border")}>
              <it.icon className="h-5 w-5 shrink-0" />
              {open && <span className="flex-1 truncate">{it.label}</span>}
              {open && !!it.badge && <span className="badge bg-primary-500 text-white">{it.badge}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-light-border dark:border-dark-border text-xs text-light-text-muted">{open && <div>{t("app.module")} v1.0</div>}</div>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-16 bg-gradient-to-r from-primary-600 to-primary-500 text-white flex items-center px-4 gap-3 sticky top-0 z-40 shadow-panel">
          <button className="p-2 rounded hover:bg-white/10" onClick={() => setOpen(!open)}><Menu className="h-5 w-5" /></button>
          <div className="font-semibold text-lg flex-1 truncate">{t("app.module")}</div>
          <button className="p-2 rounded hover:bg-white/10 text-sm flex items-center gap-1" onClick={() => { const l = i18n.language === "hi" ? "en" : "hi"; i18n.changeLanguage(l); localStorage.setItem("bvmsLang", l); }}><Globe className="h-4 w-4" />{i18n.language === "hi" ? "EN" : "हिं"}</button>
          <button className="p-2 rounded hover:bg-white/10" onClick={() => setDark(!dark)}>{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
          <div className="relative">
            <button className="p-2 rounded hover:bg-white/10 relative" onClick={() => setBell(!bell)}><Bell className="h-5 w-5" />{unread > 0 && <span className="absolute -top-0.5 -right-0.5 bg-secondary-500 text-[10px] rounded-full h-4 min-w-4 px-1 flex items-center justify-center">{unread}</span>}</button>
            {bell && (
              <div className="absolute right-0 mt-2 w-96 card text-light-text dark:text-dark-text max-h-96 overflow-y-auto z-50">
                <div className="flex items-center justify-between px-3 py-2 border-b border-light-border"><span className="font-semibold text-sm">Notifications</span><button className="text-xs text-primary-600" onClick={() => notificationsApi.markRead().then(() => notes.refetch())}>Mark all read</button></div>
                {notes.data?.results.length ? notes.data.results.map((n) => (
                  <button key={n.id} className={clsx("block w-full text-left px-3 py-2 border-b border-light-border hover:bg-gray-50 text-sm", !n.read_at && "bg-primary-50/50")} onClick={() => { setBell(false); if (n.case) nav(`/cases/${n.case}`); }}>
                    <div className="font-medium">{n.title}</div><div className="text-xs text-light-text-muted truncate">{n.body}</div><div className="text-[11px] text-light-text-muted">{ago(n.created_at)}</div>
                  </button>)) : <div className="p-4 text-sm text-light-text-muted">No notifications</div>}
              </div>
            )}
          </div>
          <div className="hidden sm:block text-right leading-tight"><div className="text-sm font-semibold">{user?.name}</div><div className="text-[11px] opacity-80">{user?.designation || user?.role}</div></div>
          <div className="h-9 w-9 rounded-full bg-white/20 flex items-center justify-center font-bold">{(user?.name || "?").slice(0, 1)}</div>
          <button className="p-2 rounded hover:bg-white/10" title={t("nav.logout")} onClick={() => { logout(); nav("/login"); }}><LogOut className="h-5 w-5" /></button>
        </header>
        <main className="flex-1 p-4 lg:p-6 max-w-[1600px] w-full mx-auto"><Outlet /></main>
      </div>
    </div>
  );
}
