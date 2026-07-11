import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { AuthProvider } from "./lib/authProvider";
import { ThemeProvider } from "@/components/theme-provider";
import { CallbackHandler } from "@/components/callback-handler";
import { ProtectedRoute } from "@/components/protected-route";
import Home from "./pages/landing";
import DashboardShell from "./pages/dashboard";
import DashboardHome from "./pages/home";
import NewProject from "./pages/newProject";
import OnboardingPage from "./pages/onboarding";
import DashboardProfile from "./pages/profile";
import DashboardTrends from "./pages/trends";
import DashboardAssets from "./pages/assets";
import DashboardCompliance from "./pages/compliance";
import Generate from "./pages/generate";
import ProjectOverviewPage from "./pages/projectOverview";
import TaskDetailPage from "./pages/taskDetail";
import GenerateInitiator from "./pages/generateInitiator";
import GuidedGenerate from "./pages/guidedGenerate";
import NotFoundPage from "./pages/notFound";
import CapcutDraftPage from "./pages/capcut-draft";
import StatisticsPage from "./pages/statistics";
import EasyGenerationPage from "./pages/easy-generation";

function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Landing Page */}
            <Route path="/" element={<Home />} />

            {/* Cognito OAuth callback — must match redirect_uri in cognito.ts */}
            <Route path="/callback" element={<CallbackHandler />} />

            {/* CapCut Draft Test Page (unprotected for easy testing) */}
            <Route path="/capcut-draft" element={<CapcutDraftPage />} />

            {/* Dashboard (Protected under ProtectedRoute) */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute redirectTo="/">
                  <DashboardShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardHome />} />
              <Route path="onboarding" element={<OnboardingPage />} />
              <Route path="new" element={<NewProject />} />
              <Route path="profile" element={<DashboardProfile />} />
              <Route path="assets" element={<DashboardAssets />} />
              <Route path="trends" element={<DashboardTrends />} />
              <Route path="statistics" element={<StatisticsPage />} />
              <Route path="compliance" element={<DashboardCompliance />} />
              <Route path="generate" element={<Generate />} />

              {/* Project-scoped routes — static segments before dynamic :taskId */}
              <Route path="project/:projectId" element={<ProjectOverviewPage />} />
              <Route path="project/:projectId/compliance" element={<DashboardCompliance />} />
              <Route path="project/:projectId/compliance/:taskId" element={<DashboardCompliance />} />
              <Route path="project/:projectId/generate" element={<GenerateInitiator />} />
              <Route path="project/:projectId/guided-generate" element={<GuidedGenerate />} />
              <Route path="project/:projectId/easy" element={<EasyGenerationPage />} />
              <Route path="project/:projectId/:taskId" element={<TaskDetailPage />} />

              {/* Redirect any other dashboard path to home */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>

            {/* Catch-all — unknown routes */}
            <Route path="not-found" element={<NotFoundPage />} />
            {/* Catch-all Redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
