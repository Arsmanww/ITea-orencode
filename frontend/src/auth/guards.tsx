import { Alert, Box, Button, CircularProgress } from "@mui/material";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import type { Role } from "../api/types";
import { ROLE_HOME, ROLE_LABEL } from "../utils/labels";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

/** Экран доступен только в указанных активных ролях. Сервер проверяет права независимо. */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { me, switchRole } = useAuth();
  if (!me) return null;
  if (roles.includes(me.active_role)) return <>{children}</>;
  const available = roles.find((r) => me.roles.includes(r));
  return (
    <Alert
      severity="warning"
      sx={{ my: 3 }}
      action={
        available ? (
          <Button color="inherit" size="small" onClick={() => switchRole(available)}>
            Переключиться: {ROLE_LABEL[available]}
          </Button>
        ) : (
          <Button color="inherit" size="small" href={ROLE_HOME[me.active_role]}>
            В мой кабинет
          </Button>
        )
      }
    >
      Этот раздел доступен только для роли «{roles.map((r) => ROLE_LABEL[r]).join("» или «")}». Сейчас активна роль «{ROLE_LABEL[me.active_role]}».
    </Alert>
  );
}
