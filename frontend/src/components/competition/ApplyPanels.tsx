import CancelIcon from "@mui/icons-material/Cancel";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Alert, Box, Button, MenuItem, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";
import type { Application, AthleteProfile, CoachAthlete, Competition } from "../../api/types";
import { ageFits, eligibility } from "../../utils/eligibility";
import { fmtDateTime } from "../../utils/format";
import { AppStatusChip, Async, EmptyState, FormDialog, Section, useGet, useInvalidate } from "../common";
import { useToast } from "../Toast";

function Check({ ok, children }: { ok: boolean; children: string }) {
  return (
    <Stack direction="row" spacing={1} alignItems="flex-start">
      {ok ? <CheckCircleIcon color="success" fontSize="small" /> : <CancelIcon color="error" fontSize="small" />}
      <Typography variant="body2">{children}</Typography>
    </Stack>
  );
}

function ApplicationsTable({ apps, showAthlete }: { apps: Application[]; showAthlete: boolean }) {
  if (apps.length === 0) return <EmptyState title="Заявок пока нет" />;
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            {showAthlete && <TableCell>Спортсмен</TableCell>}
            <TableCell>Возраст на старте</TableCell>
            <TableCell>Подана</TableCell>
            <TableCell>Статус</TableCell>
            <TableCell>Комментарий федерации</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {apps.map((a) => (
            <TableRow key={a.id}>
              {showAthlete && <TableCell>{a.athlete.full_name}</TableCell>}
              <TableCell>{a.age_on_start}</TableCell>
              <TableCell>{fmtDateTime(a.created_at)}</TableCell>
              <TableCell><AppStatusChip status={a.status} /></TableCell>
              <TableCell>{a.moderation_comment ?? "–"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function AthleteApplyPanel({ comp }: { comp: Competition }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const profile = useGet<AthleteProfile>("/athletes/me/profile");
  const apps = useGet<Application[]>(`/competitions/${comp.id}/applications`);
  const [open, setOpen] = useState(false);
  const [team, setTeam] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => api(`/competitions/${comp.id}/applications`, { method: "POST", body: { team_name: team.trim() || null } }),
    onSuccess: async () => {
      toast.success("Заявка подана и ожидает модерации федерацией");
      setOpen(false);
      await invalidate(`/competitions/${comp.id}/applications`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <Section title="Моя заявка">
      <Async q={profile}>
        {(p) => (
          <Async q={apps}>
            {(list) => {
              const active = list.find((a) => a.status === "pending" || a.status === "approved");
              const el = eligibility(comp, p);
              const coach = p.coaches.find((c) => c.discipline.id === comp.discipline.id);
              const canApply = comp.status === "registration_open" && !active && !coach;
              return (
                <Stack spacing={2}>
                  {list.length > 0 && <ApplicationsTable apps={list} showAthlete={false} />}
                  {active?.status === "approved" && <Alert severity="success">Заявка одобрена – вы допущены к участию.</Alert>}
                  {active?.status === "pending" && <Alert severity="info">Заявка на модерации. Решение придёт в уведомлении.</Alert>}
                  {!active && coach && comp.status === "registration_open" && (
                    <Alert severity="info">По этой дисциплине вас ведёт тренер {coach.coach.full_name} – заявку подаёт он. Обратитесь к тренеру.</Alert>
                  )}
                  {!active && comp.status !== "registration_open" && <Alert severity="info">Приём заявок сейчас не ведётся.</Alert>}
                  {canApply && (
                    <Box>
                      {!el.ok && <Alert severity="warning" sx={{ mb: 2 }}>{el.reasons.join(". ")}</Alert>}
                      <Button variant="contained" size="large" onClick={() => { setError(null); setOpen(true); }}>
                        Подать заявку
                      </Button>
                    </Box>
                  )}
                  <FormDialog
                    open={open}
                    title="Заявка на соревнование"
                    onClose={() => setOpen(false)}
                    onSubmit={() => submit.mutate()}
                    submitLabel="Подать заявку"
                    submitDisabled={!el.ok || (comp.is_team && !team.trim())}
                    busy={submit.isPending}
                    error={error}
                  >
                    <Typography fontWeight={700}>{comp.title}</Typography>
                    <Stack spacing={1}>
                      <Typography variant="body2" color="text.secondary">Проверка перед отправкой:</Typography>
                      <Check ok={!el.reasons.some((r) => r.startsWith("Возраст"))}>
                        {`Возраст на дату старта: ${el.age} лет; группы соревнования: ${comp.age_groups.map((g) => `${g.min_age}–${g.max_age}`).join(", ")}`}
                      </Check>
                      <Check ok={!el.reasons.some((r) => r.startsWith("Вы не занимаетесь"))}>{`Дисциплина: ${comp.discipline.name}`}</Check>
                    </Stack>
                    {comp.is_team && <TextField label="Название команды" value={team} onChange={(e) => setTeam(e.target.value)} required helperText="Командный зачёт: участники одной команды указывают одно название" />}
                  </FormDialog>
                </Stack>
              );
            }}
          </Async>
        )}
      </Async>
    </Section>
  );
}

export function CoachApplyPanel({ comp }: { comp: Competition }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const wards = useGet<CoachAthlete[]>("/coach/athletes");
  const apps = useGet<Application[]>(`/competitions/${comp.id}/applications`);
  const [open, setOpen] = useState(false);
  const [athleteId, setAthleteId] = useState("");
  const [team, setTeam] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => api(`/competitions/${comp.id}/applications`, { method: "POST", body: { athlete_id: Number(athleteId), team_name: team.trim() || null } }),
    onSuccess: async () => {
      toast.success("Заявка за подопечного подана");
      setOpen(false);
      setAthleteId("");
      await invalidate(`/competitions/${comp.id}/applications`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <Section
      title="Заявки моих подопечных"
      actions={
        comp.status === "registration_open" && (
          <Button variant="contained" onClick={() => { setError(null); setOpen(true); }}>Подать заявку за подопечного</Button>
        )
      }
    >
      <Async q={wards}>
        {(all) => {
          const mine = all.filter((w) => w.discipline.id === comp.discipline.id);
          const closed = comp.status !== "registration_open";
          const chosen = mine.find((w) => String(w.athlete.id) === athleteId);
          const fit = chosen ? ageFits(comp.age_groups, chosen.birth_date, comp.start_date) : null;
          return (
            <Stack spacing={2}>
              {closed && (
                <Alert severity="info">
                  Приём заявок сейчас не ведётся{comp.status === "finished" ? ": соревнование завершено" : ""}. Кнопка подачи появится, когда федерация откроет регистрацию.
                </Alert>
              )}
              {!closed && mine.length === 0 && (
                <Alert severity="warning">
                  У вас нет подтверждённых подопечных по дисциплине «{comp.discipline.name}» – привяжите спортсмена в кабинете, тогда сможете подать за него заявку.
                </Alert>
              )}
              <Async q={apps}>{(list) => <ApplicationsTable apps={list} showAthlete />}</Async>
              <FormDialog
                open={open}
                title="Заявка за подопечного"
                onClose={() => setOpen(false)}
                onSubmit={() => submit.mutate()}
                submitDisabled={!chosen || (fit !== null && !fit.ok) || (comp.is_team && !team.trim())}
                busy={submit.isPending}
                error={error}
              >
                {mine.length === 0 ? (
                  <Alert severity="warning">У вас нет подтверждённых подопечных по дисциплине «{comp.discipline.name}».</Alert>
                ) : (
                  <TextField select label="Спортсмен" value={athleteId} onChange={(e) => setAthleteId(e.target.value)}>
                    {mine.map((w) => (
                      <MenuItem key={w.link_id} value={String(w.athlete.id)}>{w.athlete.full_name} · {w.age} лет</MenuItem>
                    ))}
                  </TextField>
                )}
                {fit && <Check ok={fit.ok}>{`Возраст на дату старта: ${fit.age} лет; группы: ${comp.age_groups.map((g) => `${g.min_age}–${g.max_age}`).join(", ")}`}</Check>}
                {comp.is_team && <TextField label="Название команды" value={team} onChange={(e) => setTeam(e.target.value)} required />}
              </FormDialog>
            </Stack>
          );
        }}
      </Async>
    </Section>
  );
}
