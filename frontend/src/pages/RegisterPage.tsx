import { Alert, Box, Button, Card, CardContent, Checkbox, FormControlLabel, FormGroup, FormHelperText, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useMemo, useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import type { RegistrationOptions } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Async, DateField, useGet } from "../components/common";
import { PasswordStrength } from "../components/PasswordStrength";
import { ageOn, todayIso } from "../utils/format";
import { ROLE_HOME } from "../utils/labels";
import { isEmailLike, isPasswordStrong } from "../utils/password";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const options = useGet<RegistrationOptions>("/public/options");
  const [f, setF] = useState({
    last_name: "", first_name: "", patronymic: "", birth_date: "", gender: "male", email: "", password: "",
    municipality_id: "", organization_id: "", guardian_name: "", guardian_phone: "", guardian_email: "",
  });
  const [confirmPassword, setConfirmPassword] = useState("");
  const [disciplines, setDisciplines] = useState<number[]>([]);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((p) => ({ ...p, [k]: e.target.value }));
  const age = f.birth_date ? ageOn(f.birth_date, todayIso()) : null;
  const minor = age !== null && age < 18;
  const emailOk = f.email.length === 0 || isEmailLike(f.email);
  const passwordMismatch = confirmPassword.length > 0 && f.password !== confirmPassword;
  const credentialsOk = isEmailLike(f.email) && isPasswordStrong(f.password) && f.password === confirmPassword;

  const orgs = useMemo(
    () => (options.data?.organizations ?? []).filter((o) => !f.municipality_id || o.municipality_id === Number(f.municipality_id)),
    [options.data, f.municipality_id],
  );

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setError(null);
    if (!isEmailLike(f.email)) return setError("Укажите корректный email");
    if (!isPasswordStrong(f.password)) return setError("Пароль не соответствует требованиям к сложности");
    if (f.password !== confirmPassword) return setError("Пароли не совпадают");
    if (disciplines.length === 0) return setError("Выберите хотя бы одну дисциплину");
    if (!consent) return setError("Нужно согласие на обработку персональных данных");
    setBusy(true);
    try {
      const me = await register({
        email: f.email.trim(), password: f.password, last_name: f.last_name.trim(), first_name: f.first_name.trim(),
        patronymic: f.patronymic.trim() || null, birth_date: f.birth_date, gender: f.gender,
        municipality_id: f.municipality_id ? Number(f.municipality_id) : null,
        organization_id: f.organization_id ? Number(f.organization_id) : null,
        discipline_ids: disciplines, consent,
        guardian_name: minor ? f.guardian_name.trim() : null, guardian_phone: minor ? f.guardian_phone.trim() : null,
        guardian_email: minor && f.guardian_email.trim() ? f.guardian_email.trim() : null,
      });
      navigate(ROLE_HOME[me.active_role], { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось зарегистрироваться");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 760, mx: "auto" }}>
      <Card>
        <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
          <Typography variant="h5" sx={{ mb: 0.5 }}>
            Быстрая регистрация спортсмена
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            После регистрации можно сразу смотреть календарь и подавать заявки. Скан подписанного согласия загружается в кабинете.
          </Typography>
          <Async q={options}>
            {(opt) => (
              <form onSubmit={submit}>
                <Stack spacing={2}>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
                    <TextField label="Фамилия" value={f.last_name} onChange={set("last_name")} required />
                    <TextField label="Имя" value={f.first_name} onChange={set("first_name")} required />
                    <TextField label="Отчество" value={f.patronymic} onChange={set("patronymic")} />
                  </Box>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
                    <DateField label="Дата рождения" value={f.birth_date} onChange={set("birth_date")} required slotProps={{ htmlInput: { max: todayIso() } }} />
                    <TextField select label="Пол" value={f.gender} onChange={set("gender")}>
                      <MenuItem value="male">Мужской</MenuItem>
                      <MenuItem value="female">Женский</MenuItem>
                    </TextField>
                    <TextField select label="Муниципальное образование" value={f.municipality_id} onChange={(e) => setF((p) => ({ ...p, municipality_id: e.target.value, organization_id: "" }))}>
                      <MenuItem value="">Не указано</MenuItem>
                      {opt.municipalities.map((m) => (
                        <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>
                      ))}
                    </TextField>
                    <TextField select label="Организация" value={f.organization_id} onChange={set("organization_id")} helperText="Школа, вуз, спортшкола, клуб">
                      <MenuItem value="">Без организации</MenuItem>
                      {orgs.map((o) => (
                        <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
                      ))}
                    </TextField>
                  </Box>

                  <Box>
                    <Typography fontWeight={600} sx={{ mb: 0.5 }}>Дисциплины</Typography>
                    <FormGroup sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                      {opt.disciplines.map((d) => (
                        <FormControlLabel
                          key={d.id}
                          label={d.name.replace("Программирование ", "")}
                          control={<Checkbox checked={disciplines.includes(d.id)} onChange={(e) => setDisciplines((p) => (e.target.checked ? [...p, d.id] : p.filter((x) => x !== d.id)))} />}
                        />
                      ))}
                    </FormGroup>
                  </Box>

                  {minor && (
                    <Alert severity="info">
                      Вам {age} лет: нужны данные законного представителя, он же даёт согласие на обработку персональных данных.
                      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2, mt: 2 }}>
                        <TextField label="ФИО представителя" value={f.guardian_name} onChange={set("guardian_name")} required sx={{ bgcolor: "#fff" }} />
                        <TextField label="Телефон" value={f.guardian_phone} onChange={set("guardian_phone")} required sx={{ bgcolor: "#fff" }} />
                        <TextField label="Email (необязательно)" value={f.guardian_email} onChange={set("guardian_email")} sx={{ bgcolor: "#fff" }} />
                      </Box>
                    </Alert>
                  )}

                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
                    <TextField label="Email (логин)" type="email" value={f.email} onChange={set("email")} required autoComplete="username"
                               error={!emailOk} helperText={!emailOk ? "Некорректный формат email" : " "} />
                    <Box />
                    <TextField label="Пароль" type="password" value={f.password} onChange={set("password")} required autoComplete="new-password" />
                    <TextField label="Повторите пароль" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                               required autoComplete="new-password" error={passwordMismatch} helperText={passwordMismatch ? "Пароли не совпадают" : " "} />
                  </Box>
                  <PasswordStrength password={f.password} />

                  <Box>
                    <FormControlLabel
                      control={<Checkbox checked={consent} onChange={(e) => setConsent(e.target.checked)} />}
                      label={`Даю согласие на обработку персональных данных (152-ФЗ)${minor ? " — от имени законного представителя" : ""}`}
                    />
                    <FormHelperText sx={{ ml: 4 }}>Обязательное условие регистрации. Согласие сохраняется в системе.</FormHelperText>
                  </Box>

                  {error && <Alert severity="error">{error}</Alert>}
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                    <Button type="submit" variant="contained" size="large" disabled={busy || !credentialsOk}>
                      {busy ? "Регистрируем…" : "Зарегистрироваться"}
                    </Button>
                    <Typography variant="body2" color="text.secondary">
                      Уже есть аккаунт?{" "}
                      <Button component={RouterLink} to="/login" size="small">Войти</Button>
                    </Typography>
                  </Stack>
                </Stack>
              </form>
            )}
          </Async>
        </CardContent>
      </Card>
    </Box>
  );
}
