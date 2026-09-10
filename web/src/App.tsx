import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/store/auth";
import Shell from "@/layouts/Shell";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import CasesPage from "@/pages/CasesPage";
import CaseDetailPage from "@/pages/CaseDetailPage";
import NewCasePage from "@/pages/NewCasePage";
import NoticesPage from "@/pages/NoticesPage";
import PlansPage from "@/pages/PlansPage";
import GovtLandPage from "@/pages/GovtLandPage";
import ReportsPage from "@/pages/ReportsPage";
import LegalPage from "@/pages/LegalPage";
import OfficersPage from "@/pages/OfficersPage";
import CaseMapPage from "@/pages/CaseMapPage";
import VerifyPage from "@/pages/VerifyPage";
import { Spinner } from "@/components/ui";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="min-h-screen flex items-center justify-center"><Spinner /></div>;
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />;
  return children;
}

export default function App() {
  const load = useAuth((s) => s.load);
  useEffect(() => { load(); }, [load]);
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify/:code" element={<VerifyPage />} />
      <Route path="/" element={<RequireAuth><Shell /></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="inbox" element={<CasesPage inbox />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="cases/new" element={<NewCasePage />} />
        <Route path="cases/:id" element={<CaseDetailPage />} />
        <Route path="cases/:id/edit" element={<NewCasePage />} />
        <Route path="notices" element={<NoticesPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="govt-land" element={<GovtLandPage />} />
        <Route path="map" element={<CaseMapPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="legal" element={<LegalPage />} />
        <Route path="officers" element={<OfficersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
