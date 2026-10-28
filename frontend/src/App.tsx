import { Box, Button, CircularProgress, Typography } from "@mui/material";
import { Suspense, lazy } from "react";
import { Link as RouterLink, Route, Routes } from "react-router-dom";

import { RequireAuth, RequireRole } from "./auth/guards";
import { Layout } from "./components/Layout";

const AthleteCabinet = lazy(() => import("./pages/AthleteCabinet").then((m) => ({ default: m.AthleteCabinet })));
const CalendarPage = lazy(() => import("./pages/CalendarPage").then((m) => ({ default: m.CalendarPage })));
const CoachCabinet = lazy(() => import("./pages/CoachCabinet").then((m) => ({ default: m.CoachCabinet })));
const CompetitionFormPage = lazy(() => import("./pages/CompetitionFormPage").then((m) => ({ default: m.CompetitionFormPage })));
const CompetitionPage = lazy(() => import("./pages/CompetitionPage").then((m) => ({ default: m.CompetitionPage })));
const FederationCabinet = lazy(() => import("./pages/FederationCabinet").then((m) => ({ default: m.FederationCabinet })));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })));
const JudgeCabinet = lazy(() => import("./pages/JudgeCabinet").then((m) => ({ default: m.JudgeCabinet })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const ProfilePage = lazy(() => import("./pages/ProfilePage").then((m) => ({ default: m.ProfilePage })));
const PublicHome = lazy(() => import("./pages/PublicHome").then((m) => ({ default: m.PublicHome })));
const RatingPage = lazy(() => import("./pages/RatingPage").then((m) => ({ default: m.RatingPage })));
const RegisterPage = lazy(() => import("./pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })));
const VerifyPage = lazy(() => import("./pages/VerifyPage").then((m) => ({ default: m.VerifyPage })));
const RegistryPage = lazy(() => import("./pages/RegistryPage").then((m) => ({ default: m.RegistryPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((m) => ({ default: m.ReportsPage })));

function NotFound() {
  return (
    <div style={{ textAlign: "center", padding: "64px 0" }}>
      <Typography variant="h3" color="primary">
        404
      </Typography>
      <Typography sx={{ my: 2 }}>Такой страницы нет</Typography>
      <Button variant="contained" component={RouterLink} to="/">
        На главную
      </Button>
    </div>
  );
}

function Fallback() {
  return (
    <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
      <CircularProgress />
    </Box>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PublicHome />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="verify/:token" element={<VerifyPage />} />

        <Route path="calendar" element={<RequireAuth><CalendarPage /></RequireAuth>} />
        <Route path="competitions/new" element={<RequireAuth><RequireRole roles={["federation"]}><CompetitionFormPage /></RequireRole></RequireAuth>} />
        <Route path="competitions/:id" element={<RequireAuth><CompetitionPage /></RequireAuth>} />
        <Route path="rating" element={<RequireAuth><RatingPage /></RequireAuth>} />

        <Route path="athlete" element={<RequireAuth><RequireRole roles={["athlete"]}><AthleteCabinet /></RequireRole></RequireAuth>} />
        <Route path="coach" element={<RequireAuth><RequireRole roles={["coach"]}><CoachCabinet /></RequireRole></RequireAuth>} />
        <Route path="judge" element={<RequireAuth><RequireRole roles={["judge"]}><JudgeCabinet /></RequireRole></RequireAuth>} />
        <Route path="federation" element={<RequireAuth><RequireRole roles={["federation"]}><FederationCabinet /></RequireRole></RequireAuth>} />
        <Route path="profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="registry" element={<RequireAuth><RequireRole roles={["federation"]}><RegistryPage /></RequireRole></RequireAuth>} />
        <Route path="reports" element={<RequireAuth><RequireRole roles={["federation"]}><ReportsPage /></RequireRole></RequireAuth>} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </Suspense>
  );
}
