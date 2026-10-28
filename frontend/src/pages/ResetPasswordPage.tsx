import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { PasswordStrength } from "../components/PasswordStrength";
import { isPasswordStrong } from "../utils/password";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const submit = useMutation({
    mutationFn: () => api<{ detail: string }>("/auth/reset-password", { method: "POST", body: { token, new_password: password } }),
    onSuccess: () => {
      navigate("/login", { replace: true, state: { passwordReset: true } });
    },
  });

  const mismatch = confirm.length > 0 && password !== confirm;
  const ready = Boolean(token) && isPasswordStrong(password) && !mismatch;

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    if (ready) submit.mutate();
  };

  return (
    <Box sx={{ maxWidth: 480, mx: "auto" }}>
      <Card>
        <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
          <Typography variant="h5" sx={{ mb: 0.5 }}>Новый пароль</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>Придумайте новый пароль для входа в платформу.</Typography>

          {!token ? (
            <Alert severity="error">
              Ссылка повреждена: в ней нет кода восстановления. Запросите письмо заново.
            </Alert>
          ) : (
            <form onSubmit={onSubmit}>
              <Stack spacing={2}>
                <TextField label="Новый пароль" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
                <PasswordStrength password={password} />
                <TextField label="Повторите пароль" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                           required error={mismatch} helperText={mismatch ? "Пароли не совпадают" : " "} />
                {submit.isError && (
                  <Alert severity="error">{submit.error instanceof Error ? submit.error.message : "Не удалось сохранить пароль"}</Alert>
                )}
                <Button type="submit" variant="contained" size="large" disabled={!ready || submit.isPending}>
                  {submit.isPending ? "Сохраняем…" : "Сохранить пароль"}
                </Button>
              </Stack>
            </form>
          )}

          <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
            <Button component={RouterLink} to="/login" size="small">Вернуться ко входу</Button>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
