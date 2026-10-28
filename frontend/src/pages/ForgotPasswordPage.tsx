import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api } from "../api/client";
import { isEmailLike } from "../utils/password";

/**
 * Ответ сервера одинаков независимо от того, зарегистрирован ли такой email, — поэтому по
 * экрану нельзя проверить, есть ли аккаунт с данным адресом.
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => api<{ detail: string }>("/auth/forgot-password", { method: "POST", body: { email: email.trim() } }),
    onSuccess: (r) => setSent(r.detail),
  });

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault();
    submit.mutate();
  };

  return (
    <Box sx={{ maxWidth: 480, mx: "auto" }}>
      <Card>
        <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
          <Typography variant="h5" sx={{ mb: 0.5 }}>Восстановление пароля</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Укажите email, с которым вы регистрировались, — пришлём ссылку для сброса пароля.
          </Typography>

          {sent ? (
            <Alert severity="success">{sent}</Alert>
          ) : (
            <form onSubmit={onSubmit}>
              <Stack spacing={2}>
                <TextField label="Email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
                {submit.isError && <Alert severity="error">{submit.error instanceof Error ? submit.error.message : "Не удалось отправить запрос"}</Alert>}
                <Button type="submit" variant="contained" size="large" disabled={submit.isPending || !isEmailLike(email)}>
                  {submit.isPending ? "Отправляем…" : "Отправить ссылку"}
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
