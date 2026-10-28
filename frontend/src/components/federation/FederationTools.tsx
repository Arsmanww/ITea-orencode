import AddIcon from "@mui/icons-material/Add";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  Link,
  MenuItem,
  Pagination,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api } from "../../api/client";
import type { AuditItem, AuditPage, Ref, RegistrationOptions, RegistryAthlete, Sanction, SanctionKind } from "../../api/types";
import { fmtDate, fmtDateTime, todayIso } from "../../utils/format";
import { AUDIT_ACTION_LABEL, ENTITY_LABEL, ROLE_LABEL, SANCTION_LABEL } from "../../utils/labels";
import { isEmailLike } from "../../utils/password";
import { AthletePicker } from "../AthletePicker";
import { Async, DateField, EmptyState, FormDialog, Section, useGet, useInvalidate } from "../common";
import { useToast } from "../Toast";

const AUDIT_PAGE = 30;

/** Короткое описание изменений из diff журнала: «поле: было → стало» или «поле: значение». */
function diffText(diff: AuditItem["diff"]): string {
  if (!diff) return "";
  const show = (v: unknown) => (v === null || v === undefined || v === "None" ? "–" : typeof v === "object" ? JSON.stringify(v) : String(v));
  if (diff.before && diff.after && typeof diff.before === "object" && typeof diff.after === "object") {
    const before = diff.before as Record<string, unknown>;
    const after = diff.after as Record<string, unknown>;
    return Object.keys(after).map((k) => `${k}: ${show(before[k])} → ${show(after[k])}`).join("; ");
  }
  return Object.entries(diff).map(([k, v]) => `${k}: ${show(v)}`).join("; ");
}

export function AuditLogSection() {
  const [f, setF] = useState({ action: "", q: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const q = useGet<AuditPage>("/federation/audit-log", { ...f, limit: AUDIT_PAGE, offset: (page - 1) * AUDIT_PAGE });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => {
    setF((p) => ({ ...p, [k]: e.target.value }));
    setPage(1);
  };
  return (
    <Section title="Журнал действий: кто, когда и что сделал">
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "2fr 2fr 1fr 1fr" }, gap: 1.5, mb: 2 }}>
        <TextField select size="small" label="Действие" value={f.action} onChange={set("action")}>
          <MenuItem value="">Все действия</MenuItem>
          {(q.data?.actions ?? []).map((a) => <MenuItem key={a} value={a}>{AUDIT_ACTION_LABEL[a] ?? a}</MenuItem>)}
        </TextField>
        <TextField size="small" label="Автор: фамилия или email" value={f.q} onChange={set("q")} />
        <DateField size="small" label="С" value={f.date_from} onChange={set("date_from")} />
        <DateField size="small" label="По" value={f.date_to} onChange={set("date_to")} />
      </Box>
      <Async q={q}>
        {(d) =>
          d.items.length === 0 ? (
            <EmptyState title="Записей нет" hint="Измените фильтры: в журнал попадают вход, заявки, модерация, результаты, протоколы, решения и изменения справочников" />
          ) : (
            <>
              <TableContainer>
                <Table size="small">
                  <TableHead><TableRow><TableCell>Когда</TableCell><TableCell>Кто</TableCell><TableCell>Действие</TableCell><TableCell>Объект</TableCell><TableCell>Изменения</TableCell></TableRow></TableHead>
                  <TableBody>
                    {d.items.map((a) => {
                      const text = diffText(a.diff);
                      return (
                        <TableRow key={a.id}>
                          <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDateTime(a.created_at)}</TableCell>
                          <TableCell sx={{ minWidth: 160 }}>
                            {a.user?.full_name ?? "–"}
                            {a.active_role && <Typography variant="caption" display="block" color="text.secondary">{ROLE_LABEL[a.active_role]}{a.ip ? ` · ${a.ip}` : ""}</Typography>}
                          </TableCell>
                          <TableCell sx={{ minWidth: 180 }}>{AUDIT_ACTION_LABEL[a.action] ?? a.action}</TableCell>
                          <TableCell sx={{ whiteSpace: "nowrap" }}>
                            {a.entity_type === "competition" && a.entity_id ? <Link component={RouterLink} to={`/competitions/${a.entity_id}`}>соревнование #{a.entity_id}</Link> : `${ENTITY_LABEL[a.entity_type] ?? a.entity_type}${a.entity_id ? ` #${a.entity_id}` : ""}`}
                          </TableCell>
                          <TableCell sx={{ maxWidth: 360 }}>
                            <Tooltip title={text} placement="top-start">
                              <Typography variant="body2" color="text.secondary" noWrap>{text || "–"}</Typography>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">Всего записей: {d.total}</Typography>
                {d.total > AUDIT_PAGE && <Pagination count={Math.ceil(d.total / AUDIT_PAGE)} page={page} onChange={(_, p) => setPage(p)} color="primary" />}
              </Stack>
            </>
          )
        }
      </Async>
    </Section>
  );
}

export function SanctionsSection() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [activeOnly, setActiveOnly] = useState(true);
  const q = useGet<Sanction[]>("/federation/sanctions", { active_only: activeOnly });
  const [open, setOpen] = useState(false);
  const [athlete, setAthlete] = useState<RegistryAthlete | null>(null);
  const [form, setForm] = useState({ kind: "disqualification" as SanctionKind, date_from: todayIso(), date_to: "", reason: "" });
  const [error, setError] = useState<string | null>(null);
  const [ending, setEnding] = useState<Sanction | null>(null);
  const [endDate, setEndDate] = useState(todayIso());

  const create = useMutation({
    mutationFn: () => api("/federation/sanctions", { method: "POST", body: { athlete_id: athlete?.id, ...form, date_to: form.date_to || null, reason: form.reason.trim() } }),
    onSuccess: async () => {
      toast.success("Санкция зафиксирована: спортсмен и его тренеры уведомлены, рейтинг пересчитан");
      setOpen(false);
      setAthlete(null);
      setForm({ kind: "disqualification", date_from: todayIso(), date_to: "", reason: "" });
      await invalidate("/federation", "/rating");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  const end = useMutation({
    mutationFn: () => api(`/federation/sanctions/${ending?.id}`, { method: "PATCH", body: { date_to: endDate } }),
    onSuccess: async () => {
      toast.success("Срок санкции сокращён");
      setEnding(null);
      await invalidate("/federation", "/rating");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <Section
      title="Дисквалификации и отстранения"
      actions={
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="body2">только действующие</Typography>
          <Switch checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setError(null); setOpen(true); }}>Зафиксировать</Button>
        </Stack>
      }
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Пока санкция действует, спортсмен не попадает в рейтинг и не допускается к заявкам на соревнования в этот период.
      </Typography>
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title={activeOnly ? "Действующих санкций нет" : "Санкций не было"} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Спортсмен</TableCell><TableCell>Вид</TableCell><TableCell>Период</TableCell><TableCell>Основание</TableCell><TableCell align="right" /></TableRow></TableHead>
                <TableBody>
                  {list.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell sx={{ fontWeight: 600 }}>{s.athlete.full_name}</TableCell>
                      <TableCell><Chip size="small" color={s.active ? "error" : "default"} label={SANCTION_LABEL[s.kind]} /></TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(s.date_from)} – {s.date_to ? fmtDate(s.date_to) : "бессрочно"}</TableCell>
                      <TableCell sx={{ maxWidth: 320 }}>
                        {s.reason}
                        {s.competition && <Typography variant="caption" display="block"><Link component={RouterLink} to={`/competitions/${s.competition.id}`}>{s.competition.name}</Link></Typography>}
                      </TableCell>
                      <TableCell align="right">{s.active && <Button size="small" onClick={() => { setError(null); setEndDate(todayIso()); setEnding(s); }}>Завершить досрочно</Button>}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )
        }
      </Async>
      <FormDialog open={open} title="Дисквалификация или отстранение" onClose={() => setOpen(false)} onSubmit={() => { setError(null); create.mutate(); }}
        submitLabel="Зафиксировать" busy={create.isPending} error={error} submitDisabled={!athlete || form.reason.trim().length < 3}>
        <AthletePicker value={athlete} onChange={setAthlete} />
        <TextField select label="Вид" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as SanctionKind })}>
          {Object.entries(SANCTION_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
        </TextField>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
          <DateField label="С" value={form.date_from} onChange={(e) => setForm({ ...form, date_from: e.target.value })} required />
          <DateField label="По (пусто – бессрочно)" value={form.date_to} onChange={(e) => setForm({ ...form, date_to: e.target.value })} />
        </Box>
        <TextField label="Основание (рапорт, решение)" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} multiline minRows={2} required />
      </FormDialog>
      <FormDialog open={ending !== null} title={`Завершить: ${ending?.athlete.full_name ?? ""}`} onClose={() => setEnding(null)} onSubmit={() => { setError(null); end.mutate(); }}
        submitLabel="Сохранить" busy={end.isPending} error={error}>
        <DateField label="Последний день действия" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      </FormDialog>
    </Section>
  );
}

export function CompetitionTypesSection() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<Ref[]>("/reference/competition-types", { include_inactive: true });
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => api("/reference/competition-types", { method: "POST", body: { name: name.trim() } }),
    onSuccess: async () => {
      toast.success("Тип добавлен – он уже доступен в форме создания соревнования");
      setName("");
      setError(null);
      await invalidate("/reference/competition-types");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  const toggle = useMutation({
    mutationFn: (t: Ref) => api(`/reference/competition-types/${t.id}`, { method: "PATCH", body: { is_active: !t.is_active } }),
    onSuccess: () => invalidate("/reference/competition-types"),
    onError: toast.error,
  });
  return (
    <Section title="Справочник типов соревнований">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Тип выбирается при создании соревнования. Отключённый тип скрывается из формы, но остаётся у уже созданных соревнований.
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField size="small" label="Новый тип, например «Олимпиада»" value={name} onChange={(e) => setName(e.target.value)} sx={{ flexGrow: 1 }} error={!!error} helperText={error} />
        <Button variant="contained" startIcon={<AddIcon />} disabled={name.trim().length < 2 || add.isPending} onClick={() => add.mutate()}>Добавить</Button>
      </Stack>
      <Async q={q}>
        {(list) => (
          <Stack spacing={1}>
            {list.map((t) => (
              <Stack key={t.id} direction="row" alignItems="center" justifyContent="space-between" sx={{ p: 1.25, borderRadius: 2, border: "1px solid", borderColor: "divider", opacity: t.is_active ? 1 : 0.6 }}>
                <Typography fontWeight={600}>{t.name}</Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" color="text.secondary">{t.is_active ? "используется" : "отключён"}</Typography>
                  <Switch checked={!!t.is_active} disabled={toggle.isPending} onChange={() => toggle.mutate(t)} />
                </Stack>
              </Stack>
            ))}
          </Stack>
        )}
      </Async>
    </Section>
  );
}

interface StaffOut { user_id: number; email: string; role: string; created_new_user: boolean }

const EMPTY_STAFF_FORM = {
  role: "coach" as "coach" | "judge", email: "", last_name: "", first_name: "", patronymic: "",
  birth_date: "", gender: "male", phone: "", municipality_id: "", organization_id: "", bio: "",
};

/** Тренер и судья не регистрируются сами – федерация заводит аккаунт, человек задаёт пароль по ссылке из письма. */
export function StaffSection() {
  const toast = useToast();
  const options = useGet<RegistrationOptions>("/public/options");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(EMPTY_STAFF_FORM);
  const [consent, setConsent] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((p) => ({ ...p, [k]: e.target.value }));
  const orgs = useMemo(
    () => (options.data?.organizations ?? []).filter((o) => !f.municipality_id || o.municipality_id === Number(f.municipality_id)),
    [options.data, f.municipality_id],
  );
  const ready = isEmailLike(f.email) && !!f.last_name.trim() && !!f.first_name.trim() && !!f.birth_date;

  const create = useMutation({
    mutationFn: () => api<StaffOut>("/federation/staff", {
      method: "POST",
      body: {
        email: f.email.trim(), last_name: f.last_name.trim(), first_name: f.first_name.trim(),
        patronymic: f.patronymic.trim() || null, birth_date: f.birth_date, gender: f.gender,
        phone: f.phone.trim() || null, municipality_id: f.municipality_id ? Number(f.municipality_id) : null,
        organization_id: f.organization_id ? Number(f.organization_id) : null,
        role: f.role, bio: f.role === "coach" ? (f.bio.trim() || null) : null, consent,
      },
    }),
    onSuccess: (r) => {
      toast.success(r.created_new_user
        ? `Аккаунт создан, письмо со ссылкой для входа отправлено на ${r.email}`
        : `Роль «${ROLE_LABEL[f.role]}» добавлена существующему аккаунту ${r.email}`);
      setOpen(false);
      setF(EMPTY_STAFF_FORM);
      setConsent(true);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <Section title="Тренеры и судьи" actions={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>Завести аккаунт</Button>}>
      <Typography variant="body2" color="text.secondary">
        Тренер или судья не регистрируется сам: федерация заводит аккаунт, человек получает письмо со ссылкой и задаёт
        пароль. Если email уже есть на платформе – роль добавится к существующему аккаунту (мульти-роль), письмо не отправляется.
        Полный список – в «Реестре».
      </Typography>
      <FormDialog open={open} title="Завести аккаунт тренера или судьи" onClose={() => setOpen(false)}
        onSubmit={() => { setError(null); create.mutate(); }} submitLabel="Создать" busy={create.isPending}
        error={error} submitDisabled={!ready}>
        <ToggleButtonGroup exclusive fullWidth value={f.role} onChange={(_, v) => v && setF((p) => ({ ...p, role: v }))}>
          <ToggleButton value="coach">Тренер</ToggleButton>
          <ToggleButton value="judge">Судья</ToggleButton>
        </ToggleButtonGroup>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
          <TextField label="Фамилия" value={f.last_name} onChange={set("last_name")} required />
          <TextField label="Имя" value={f.first_name} onChange={set("first_name")} required />
          <TextField label="Отчество" value={f.patronymic} onChange={set("patronymic")} />
          <TextField select label="Пол" value={f.gender} onChange={set("gender")}>
            <MenuItem value="male">Мужской</MenuItem>
            <MenuItem value="female">Женский</MenuItem>
          </TextField>
          <DateField label="Дата рождения" value={f.birth_date} onChange={set("birth_date")} required slotProps={{ htmlInput: { max: todayIso() } }} />
          <TextField label="Телефон (необязательно)" value={f.phone} onChange={set("phone")} />
          <TextField label="Email" type="email" value={f.email} onChange={set("email")} required sx={{ gridColumn: { sm: "1 / -1" } }} />
          <TextField select label="Муниципалитет" value={f.municipality_id}
                     onChange={(e) => setF((p) => ({ ...p, municipality_id: e.target.value, organization_id: "" }))}>
            <MenuItem value="">Не указано</MenuItem>
            {(options.data?.municipalities ?? []).map((m) => <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>)}
          </TextField>
          <TextField select label="Организация" value={f.organization_id} onChange={set("organization_id")}>
            <MenuItem value="">Без организации</MenuItem>
            {orgs.map((o) => <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>)}
          </TextField>
        </Box>
        {f.role === "coach" && <TextField label="О тренере (необязательно)" value={f.bio} onChange={set("bio")} multiline minRows={2} />}
        <FormControlLabel
          control={<Checkbox checked={consent} onChange={(e) => setConsent(e.target.checked)} />}
          label="Согласие на обработку персональных данных уже получено офлайн"
        />
      </FormDialog>
    </Section>
  );
}
