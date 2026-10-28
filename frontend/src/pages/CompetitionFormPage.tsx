import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import { Alert, Box, Button, Checkbox, FormControlLabel, IconButton, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { AgeGroup, Competition, Ref } from "../api/types";
import { useToast } from "../components/Toast";
import { DateField, DateTimeField, PageTitle, Section, useGet, useInvalidate } from "../components/common";
import { localToIso } from "../utils/format";
import { LEVEL_LABEL, PLAN_LABEL, TIER_LABEL } from "../utils/labels";

interface StageDraft { name: string; format: "online" | "offline"; starts_at: string; ends_at: string; place_or_url: string }

const TIERS_BY_LEVEL: Record<string, string[]> = {
  regional: ["regional"],
  interregional: ["interregional"],
  all_russian: ["russia_championship", "russia_first"],
};

export function CompetitionFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const invalidate = useInvalidate();
  const disciplines = useGet<Ref[]>("/reference/disciplines");
  const types = useGet<Ref[]>("/reference/competition-types");
  const groups = useGet<AgeGroup[]>("/reference/age-groups");
  const file = useRef<HTMLInputElement>(null);
  const [regulation, setRegulation] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [f, setF] = useState({
    title: "", discipline_id: "", type_id: "", level: "regional", rating_tier: "regional", status: "published",
    plan_number: "", start_date: "", end_date: "", location: "", registration_opens_at: "", registration_deadline: "", description: "", is_team: false,
  });
  const [ageGroups, setAgeGroups] = useState<number[]>([]);
  const [stages, setStages] = useState<StageDraft[]>([{ name: "", format: "offline", starts_at: "", ends_at: "", place_or_url: "" }]);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((p) => ({ ...p, [k]: e.target.value }));
  const setLevel = (level: string) => setF((p) => ({ ...p, level, rating_tier: TIERS_BY_LEVEL[level][0] }));
  const plan = f.level === "regional" ? "oren_regional" : "ekp_minsport";
  const patchStage = (i: number, p: Partial<StageDraft>) => setStages((s) => s.map((x, j) => (j === i ? { ...x, ...p } : x)));

  const create = useMutation({
    mutationFn: async () => {
      const body = {
        title: f.title.trim(), discipline_id: Number(f.discipline_id), type_id: Number(f.type_id), level: f.level, rating_tier: f.rating_tier,
        status: f.status, calendar_plan: plan, plan_number: f.plan_number.trim() || null, start_date: f.start_date, end_date: f.end_date,
        location: f.location.trim() || null, registration_opens_at: localToIso(f.registration_opens_at), registration_deadline: localToIso(f.registration_deadline),
        is_team: f.is_team, description: f.description.trim() || null, age_group_ids: ageGroups,
        stages: stages.map((s) => ({ name: s.name.trim(), format: s.format, starts_at: localToIso(s.starts_at), ends_at: localToIso(s.ends_at), place_or_url: s.place_or_url.trim() || null })),
      };
      const created = await api<Competition>("/competitions", { method: "POST", body });
      if (regulation) {
        const form = new FormData();
        form.append("file", regulation);
        await api(`/competitions/${created.id}/regulation`, { method: "POST", form });
      }
      return created;
    },
    onSuccess: async (c) => {
      toast.success("Соревнование создано");
      await invalidate("/competitions");
      navigate(`/competitions/${c.id}`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  const ready = f.title.trim().length >= 5 && f.discipline_id && f.type_id && f.start_date && f.end_date && f.plan_number.trim() && ageGroups.length > 0 && stages.every((s) => s.name.trim() && s.starts_at && s.ends_at);

  return (
    <Box>
      <PageTitle title="Новое соревнование" subtitle="Региональные соревнования входят в план Оренбургской области, межрегиональные и всероссийские – в ЕКП Минспорта России" />
      <Section title="Основное">
        <Stack spacing={2}>
          <TextField label="Название" value={f.title} onChange={set("title")} required />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" }, gap: 2 }}>
            <TextField select label="Дисциплина" value={f.discipline_id} onChange={set("discipline_id")} required>
              {(disciplines.data ?? []).map((d) => <MenuItem key={d.id} value={String(d.id)}>{d.name}</MenuItem>)}
            </TextField>
            <TextField select label="Тип (справочник)" value={f.type_id} onChange={set("type_id")} required>
              {(types.data ?? []).map((t) => <MenuItem key={t.id} value={String(t.id)}>{t.name}</MenuItem>)}
            </TextField>
            <TextField select label="Статус публикации" value={f.status} onChange={set("status")}>
              <MenuItem value="draft">Черновик</MenuItem>
              <MenuItem value="published">Опубликовать в календаре</MenuItem>
              <MenuItem value="registration_open">Сразу открыть приём заявок</MenuItem>
            </TextField>
            <TextField select label="Уровень соревнования" value={f.level} onChange={(e) => setLevel(e.target.value)}>
              {Object.entries(LEVEL_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField select label="Очки в рейтинге" value={f.rating_tier} onChange={set("rating_tier")}>
              {TIERS_BY_LEVEL[f.level].map((t) => <MenuItem key={t} value={t}>{TIER_LABEL[t as keyof typeof TIER_LABEL]}</MenuItem>)}
            </TextField>
            <FormControlLabel control={<Switch checked={f.is_team} onChange={(e) => setF((p) => ({ ...p, is_team: e.target.checked }))} />} label="Командный зачёт" />
          </Box>
          <Alert severity="info" sx={{ alignItems: "center" }}>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2, alignItems: "center" }}>
              <Typography>Календарный план: <b>{PLAN_LABEL[plan]}</b></Typography>
              <TextField label="Номер в плане" value={f.plan_number} onChange={set("plan_number")} required sx={{ bgcolor: "#fff" }} />
            </Box>
          </Alert>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
            <DateField label="Дата начала" value={f.start_date} onChange={set("start_date")} required />
            <DateField label="Дата окончания" value={f.end_date} onChange={set("end_date")} required />
            <TextField label="Место проведения" value={f.location} onChange={set("location")} />
            <DateTimeField label="Приём заявок: открытие" value={f.registration_opens_at} onChange={set("registration_opens_at")} />
            <DateTimeField label="Приём заявок: дедлайн" value={f.registration_deadline} onChange={set("registration_deadline")} />
          </Box>
          <TextField label="Описание" value={f.description} onChange={set("description")} multiline minRows={2} />
        </Stack>
      </Section>

      <Section title="Возрастные группы">
        <Stack direction="row" flexWrap="wrap" useFlexGap>
          {(groups.data ?? []).map((g) => (
            <FormControlLabel key={g.id} label={`${g.name} (${g.min_age}–${g.max_age})`}
              control={<Checkbox checked={ageGroups.includes(g.id)} onChange={(e) => setAgeGroups((p) => (e.target.checked ? [...p, g.id] : p.filter((x) => x !== g.id)))} />} />
          ))}
        </Stack>
      </Section>

      <Section title="Этапы" actions={<Button startIcon={<AddIcon />} onClick={() => setStages((s) => [...s, { name: "", format: "offline", starts_at: "", ends_at: "", place_or_url: "" }])}>Добавить этап</Button>}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Формат задаётся для каждого этапа: например, разработка онлайн, защита очно.
        </Typography>
        <Stack spacing={2}>
          {stages.map((s, i) => (
            <Paper key={i} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography fontWeight={700}>Этап {i + 1}</Typography>
                {stages.length > 1 && <IconButton size="small" onClick={() => setStages((x) => x.filter((_, j) => j !== i))} aria-label="Удалить этап"><DeleteIcon /></IconButton>}
              </Stack>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "2fr 1fr 1fr 1fr" }, gap: 2 }}>
                <TextField label="Название этапа" value={s.name} onChange={(e) => patchStage(i, { name: e.target.value })} required />
                <TextField select label="Формат" value={s.format} onChange={(e) => patchStage(i, { format: e.target.value as StageDraft["format"] })}>
                  <MenuItem value="online">Онлайн</MenuItem>
                  <MenuItem value="offline">Очно</MenuItem>
                </TextField>
                <DateTimeField label="Начало" value={s.starts_at} onChange={(e) => patchStage(i, { starts_at: e.target.value })} required />
                <DateTimeField label="Окончание" value={s.ends_at} onChange={(e) => patchStage(i, { ends_at: e.target.value })} required />
              </Box>
              <TextField sx={{ mt: 2 }} label={s.format === "online" ? "Ссылка на платформу" : "Адрес проведения"} value={s.place_or_url} onChange={(e) => patchStage(i, { place_or_url: e.target.value })} />
            </Paper>
          ))}
        </Stack>
      </Section>

      <Section title="Положение (регламент)">
        <input ref={file} type="file" hidden accept=".pdf,.doc,.docx" onChange={(e) => setRegulation(e.target.files?.[0] ?? null)} />
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <Button variant="outlined" onClick={() => file.current?.click()}>Выбрать файл (PDF, DOC, DOCX)</Button>
          <Typography color="text.secondary">{regulation ? regulation.name : "Файл не выбран – положение можно добавить позже"}</Typography>
        </Stack>
      </Section>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Stack direction="row" spacing={2}>
        <Button variant="contained" size="large" disabled={!ready || create.isPending} onClick={() => { setError(null); create.mutate(); }}>
          {create.isPending ? "Создаём…" : "Создать соревнование"}
        </Button>
        <Button component={RouterLink} to="/calendar" size="large">Отмена</Button>
      </Stack>
    </Box>
  );
}
