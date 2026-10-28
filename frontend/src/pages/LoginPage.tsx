import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import GavelIcon from "@mui/icons-material/Gavel";
import GroupsIcon from "@mui/icons-material/Groups";
import PersonIcon from "@mui/icons-material/Person";
import SwapHorizIcon from "@mui/icons-material/SwapHoriz";
import { Alert, Box, Button, Card, CardContent, Divider, Stack, TextField, Typography } from "@mui/material";
import { useState, type FormEvent, type ReactElement } from "react";
import { Link as RouterLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { BRAND } from "../theme";
import { ROLE_HOME } from "../utils/labels";

const DOMAIN = "@fsp-demo.example.com";
const DEMO_PASSWORD = "Demo12345!";
const DEMO: { label: string; hint: string; email: string; icon: ReactElement }[] = [
  { label: "Федерация", hint: "календарь, модерация, протоколы", email: `admin${DOMAIN}`, icon: <AdminPanelSettingsIcon /> },
  { label: "Тренер", hint: "подопечные, заявки, разряды", email: `coach05${DOMAIN}`, icon: <GroupsIcon /> },
  { label: "Спортсмен", hint: "заявки, история, разряд", email: `athlete073${DOMAIN}`, icon: <PersonIcon /> },
  { label: "Судья", hint: "категория, назначения", email: `judge03${DOMAIN}`, icon: <GavelIcon /> },
  { label: "Мульти-аккаунт", hint: "спортсмен + тренер", email: `athlete.coach${DOMAIN}`, icon: <SwapHorizIcon /> },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: string; passwordReset?: boolean } | null;
  const from = state?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: string, p: string) => {
    setBusy(true);
    setError(null);
    try {
      const me = await login(e, p);
      navigate(from ?? ROLE_HOME[me.active_role], { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    submit(email.trim(), password);
  };

  return (
    <Box sx={{ maxWidth: 940, mx: "auto" }}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
        <Card>
          <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
            <Typography variant="h5" sx={{ mb: 0.5 }}>
              Вход в платформу
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              Один аккаунт — несколько кабинетов: роль можно сменить без повторного входа.
            </Typography>
            <form onSubmit={onSubmit}>
              <Stack spacing={2}>
                <TextField label="Email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
                <TextField label="Пароль" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                {state?.passwordReset && !error && <Alert severity="success">Пароль изменён, войдите с новым паролем.</Alert>}
                {error && <Alert severity="error">{error}</Alert>}
                <Button type="submit" variant="contained" size="large" disabled={busy}>
                  {busy ? "Входим…" : "Войти"}
                </Button>
                <Button component={RouterLink} to="/forgot-password" size="small" sx={{ alignSelf: "flex-start" }}>
                  Забыли пароль?
                </Button>
              </Stack>
            </form>
            <Divider sx={{ my: 3 }} />
            <Typography variant="body2" color="text.secondary">
              Нет аккаунта?{" "}
              <Button component={RouterLink} to="/register" size="small">
                Быстрая регистрация
              </Button>
            </Typography>
          </CardContent>
        </Card>

        <Card sx={{ bgcolor: "#EAF0FA", borderColor: "#C9D8F2" }}>
          <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
            <Typography variant="h5" sx={{ mb: 0.5 }}>
              Демо-доступ
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 2.5 }}>
              Войти одним нажатием. Все данные вымышленные, пароль у всех <b>{DEMO_PASSWORD}</b>.
            </Typography>
            <Stack spacing={1.25}>
              {DEMO.map((d) => (
                <Button
                  key={d.email}
                  variant="contained"
                  disabled={busy}
                  onClick={() => submit(d.email, DEMO_PASSWORD)}
                  startIcon={d.icon}
                  sx={{ justifyContent: "flex-start", textAlign: "left", py: 1.2, bgcolor: "#fff", color: BRAND.blueDark, "&:hover": { bgcolor: "#F5F8FE" } }}
                >
                  <Box>
                    <Typography fontWeight={700} sx={{ lineHeight: 1.2 }}>
                      {d.label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {d.hint}
                    </Typography>
                  </Box>
                </Button>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
