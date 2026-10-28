import DeleteIcon from "@mui/icons-material/Delete";
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Stack,
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
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { Application, ApplicationStatus, Competition, CompetitionStatus, JudgeAssignment, JudgeItem, Protocol, Ref, ResultRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { fmtDateTime, fmtNum, fmtTime, plural } from "../../utils/format";
import { APP_STATUS_LABEL, RESULT_STATUS_LABEL, STATUS_TRANSITIONS } from "../../utils/labels";
import { AppStatusChip, Async, DownloadButton, EmptyState, FormDialog, Section, useGet, useInvalidate } from "../common";
import { useToast } from "../Toast";

const TRANSITION_LABEL: Record<CompetitionStatus, string> = {
  draft: "Вернуть в черновик",
  published: "Опубликовать в календаре",
  registration_open: "Открыть приём заявок",
  registration_closed: "Закрыть приём заявок",
  in_progress: "Начать соревнование",
  finished: "Завершить",
  cancelled: "Отменить соревнование",
};

export function StatusActions({ comp }: { comp: Competition }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const change = useMutation({
    mutationFn: (status: CompetitionStatus) => api(`/competitions/${comp.id}`, { method: "PATCH", body: { status } }),
    onSuccess: async () => {
      toast.success("Статус изменён");
      await invalidate(`/competitions`);
    },
    onError: toast.error,
  });
  const next = STATUS_TRANSITIONS[comp.status];
  if (next.length === 0) return null;
  return (
    <Section title="Управление статусом">
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {next.map((s) => (
          <Button key={s} variant={s === "cancelled" ? "outlined" : "contained"} color={s === "cancelled" ? "error" : "primary"} disabled={change.isPending} onClick={() => change.mutate(s)}>
            {TRANSITION_LABEL[s]}
          </Button>
        ))}
      </Stack>
    </Section>
  );
}

export function ModerationPanel({ comp }: { comp: Competition }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [filter, setFilter] = useState<ApplicationStatus | "">("pending");
  const apps = useGet<Application[]>(`/competitions/${comp.id}/applications`, { status: filter || undefined });
  const [rejecting, setRejecting] = useState<Application | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const moderate = useMutation({
    mutationFn: (v: { id: number; status: "approved" | "rejected"; comment?: string }) =>
      api(`/competitions/${comp.id}/applications/${v.id}`, { method: "PATCH", body: { status: v.status, comment: v.comment } }),
    onSuccess: async (_, v) => {
      toast.success(v.status === "approved" ? "Заявка одобрена" : "Заявка отклонена");
      setRejecting(null);
      setComment("");
      await invalidate(`/competitions/${comp.id}/applications`, "/federation");
    },
    onError: (e) => (rejecting ? setError(e instanceof Error ? e.message : "Ошибка") : toast.error(e)),
  });

  return (
    <Section
      title="Заявки на участие"
      actions={
        <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v !== null && setFilter(v)}>
          <ToggleButton value="pending">На модерации</ToggleButton>
          <ToggleButton value="approved">Одобренные</ToggleButton>
          <ToggleButton value="rejected">Отклонённые</ToggleButton>
          <ToggleButton value="">Все</ToggleButton>
        </ToggleButtonGroup>
      }
    >
      <Async q={apps}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title={filter ? `Нет заявок со статусом «${APP_STATUS_LABEL[filter]}»` : "Заявок нет"} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Спортсмен</TableCell>
                    <TableCell>Возраст</TableCell>
                    <TableCell>Команда</TableCell>
                    <TableCell>Подал</TableCell>
                    <TableCell>Статус</TableCell>
                    <TableCell align="right">Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {list.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell>{a.athlete.full_name}</TableCell>
                      <TableCell>{a.age_on_start}</TableCell>
                      <TableCell>{a.team?.name ?? "–"}</TableCell>
                      <TableCell>{a.submitted_by_role === "coach" ? "тренер" : "спортсмен"}</TableCell>
                      <TableCell><AppStatusChip status={a.status} /></TableCell>
                      <TableCell align="right">
                        {a.status === "pending" ? (
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <Button size="small" variant="contained" color="success" disabled={moderate.isPending} onClick={() => moderate.mutate({ id: a.id, status: "approved" })}>Одобрить</Button>
                            <Button size="small" color="error" onClick={() => { setError(null); setRejecting(a); }}>Отклонить</Button>
                          </Stack>
                        ) : (
                          <Typography variant="caption" color="text.secondary">{a.moderation_comment ?? ""}</Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )
        }
      </Async>
      <FormDialog
        open={rejecting !== null}
        title={`Отклонить заявку: ${rejecting?.athlete.full_name ?? ""}`}
        onClose={() => setRejecting(null)}
        onSubmit={() => rejecting && moderate.mutate({ id: rejecting.id, status: "rejected", comment })}
        submitLabel="Отклонить"
        submitDisabled={!comment.trim()}
        busy={moderate.isPending}
        error={error}
      >
        <TextField label="Причина отказа" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} required />
      </FormDialog>
    </Section>
  );
}

export function JudgesPanel({ comp }: { comp: Competition }) {
  const { me } = useAuth();
  const isFed = me?.active_role === "federation";
  const toast = useToast();
  const invalidate = useInvalidate();
  const list = useGet<JudgeAssignment[]>(`/competitions/${comp.id}/judges`);
  const positions = useGet<Ref[]>("/reference/judge-positions");
  const judges = useGet<JudgeItem[]>("/reference/judges", undefined, { enabled: isFed });
  const [open, setOpen] = useState(false);
  const [judgeId, setJudgeId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const editable = isFed && comp.status !== "finished" && comp.status !== "cancelled";

  const assign = useMutation({
    mutationFn: () => api(`/competitions/${comp.id}/judges`, { method: "POST", body: { judge_id: Number(judgeId), position_id: Number(positionId) } }),
    onSuccess: async () => {
      toast.success("Судья назначен");
      setOpen(false);
      setJudgeId("");
      await invalidate(`/competitions/${comp.id}/judges`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/competitions/${comp.id}/judges/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      toast.success("Судья снят с соревнования");
      await invalidate(`/competitions/${comp.id}/judges`);
    },
    onError: toast.error,
  });

  return (
    <Section title="Судейская коллегия" actions={editable && <Button variant="outlined" onClick={() => { setError(null); setOpen(true); }}>Назначить судью</Button>}>
      <Async q={list}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title="Судейская коллегия не назначена" />
          ) : (
            <Stack spacing={1}>
              {rows.map((r) => (
                <Stack key={r.id} direction="row" alignItems="center" spacing={1.5} sx={{ py: 0.5 }}>
                  <Chip size="small" color="primary" variant="outlined" label={r.position.name} sx={{ minWidth: 190 }} />
                  <Typography sx={{ flexGrow: 1 }}>{r.judge.full_name}</Typography>
                  {editable && (
                    <IconButton size="small" aria-label="Снять судью" onClick={() => remove.mutate(r.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Stack>
              ))}
            </Stack>
          )
        }
      </Async>
      <FormDialog open={open} title="Назначить судью" onClose={() => setOpen(false)} onSubmit={() => assign.mutate()} submitDisabled={!judgeId || !positionId} busy={assign.isPending} error={error}>
        <TextField select label="Судья" value={judgeId} onChange={(e) => setJudgeId(e.target.value)}>
          {(judges.data ?? []).map((j) => (
            <MenuItem key={j.id} value={String(j.id)}>{j.name} – {j.category ?? "без категории"}{j.valid_until ? ` (до ${j.valid_until})` : ""}</MenuItem>
          ))}
        </TextField>
        <TextField select label="Судейская должность" value={positionId} onChange={(e) => setPositionId(e.target.value)}>
          {(positions.data ?? []).map((p) => (
            <MenuItem key={p.id} value={String(p.id)}>{p.name}</MenuItem>
          ))}
        </TextField>
        <Alert severity="info">Сервер проверит, что категория судьи действует на дату окончания соревнования и что он не участвует как спортсмен.</Alert>
      </FormDialog>
    </Section>
  );
}

interface Draft { status: ResultRow["status"]; score: string; tasks: string; time: string }

export function ResultsPanel({ comp }: { comp: Competition }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const apps = useGet<Application[]>(`/competitions/${comp.id}/applications`, { status: "approved" });
  const results = useGet<ResultRow[]>(`/competitions/${comp.id}/results`);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [publishError, setPublishError] = useState<string | null>(null);
  const open = comp.status === "registration_closed" || comp.status === "in_progress";

  useEffect(() => {
    if (!results.data) return;
    const next: Record<number, Draft> = {};
    results.data.forEach((r) => {
      next[r.application_id] = { status: r.status, score: r.score ? String(Number(r.score)) : "", tasks: r.tasks_solved?.toString() ?? "", time: r.time_seconds ? String(Number(r.time_seconds)) : "" };
    });
    setDrafts(next);
  }, [results.data]);

  const get = (id: number): Draft => drafts[id] ?? { status: "ranked", score: "", tasks: "", time: "" };
  const patch = (id: number, p: Partial<Draft>) => setDrafts((d) => ({ ...d, [id]: { ...get(id), ...p } }));

  const save = useMutation({
    mutationFn: async () => {
      const payload = (apps.data ?? [])
        .map((a) => ({ a, d: drafts[a.id] }))
        .filter(({ d }) => d && (d.status !== "ranked" || d.score || d.tasks || d.time))
        .map(({ a, d }) => ({
          application_id: a.id, status: d.status,
          score: d.score ? Number(d.score) : null, tasks_solved: d.tasks ? Number(d.tasks) : null, time_seconds: d.time ? Number(d.time) : null,
        }));
      if (payload.length === 0) throw new Error("Введите результат хотя бы для одного участника");
      return api("/competitions/" + comp.id + "/results", { method: "POST", body: { results: payload } });
    },
    onSuccess: async () => {
      toast.success("Результаты сохранены");
      setPublishError(null);
      await invalidate(`/competitions/${comp.id}/results`);
    },
    onError: toast.error,
  });
  const publish = useMutation({
    mutationFn: () => api(`/competitions/${comp.id}/publish-protocol`, { method: "POST" }),
    onSuccess: async () => {
      toast.success("Протокол опубликован, результаты попали в историю спортсменов");
      await invalidate("/competitions", "/athletes", "/rating");
    },
    onError: (e) => setPublishError(e instanceof Error ? e.message : "Ошибка"),
  });

  if (!open) {
    return (
      <Section title="Ввод результатов">
        <Alert severity="info">
          {comp.status === "finished" ? "Соревнование завершено, протокол опубликован." : "Результаты вносятся после закрытия приёма заявок: закройте приём в блоке «Управление статусом»."}
        </Alert>
      </Section>
    );
  }
  return (
    <Section title="Ввод результатов и публикация протокола">
      <Async q={apps}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Нет участников с одобренными заявками" hint="Одобрите заявки на вкладке «Заявки»" />
          ) : (
            <Stack spacing={2}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Участник</TableCell>
                      <TableCell sx={{ minWidth: 150 }}>Статус</TableCell>
                      <TableCell sx={{ minWidth: 100 }}>Баллы</TableCell>
                      <TableCell sx={{ minWidth: 100 }}>Решено задач</TableCell>
                      <TableCell sx={{ minWidth: 120 }}>Время, сек</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {list.map((a) => {
                      const d = get(a.id);
                      const off = d.status !== "ranked";
                      return (
                        <TableRow key={a.id}>
                          <TableCell>{a.athlete.full_name}{a.team ? <Typography variant="caption" display="block" color="text.secondary">{a.team.name}</Typography> : null}</TableCell>
                          <TableCell>
                            <TextField select value={d.status} onChange={(e) => patch(a.id, { status: e.target.value as Draft["status"] })}>
                              {Object.entries(RESULT_STATUS_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
                            </TextField>
                          </TableCell>
                          <TableCell><TextField type="number" value={d.score} disabled={off} onChange={(e) => patch(a.id, { score: e.target.value })} slotProps={{ htmlInput: { min: 0, step: "0.01" } }} /></TableCell>
                          <TableCell><TextField type="number" value={d.tasks} disabled={off} onChange={(e) => patch(a.id, { tasks: e.target.value })} slotProps={{ htmlInput: { min: 0 } }} /></TableCell>
                          <TableCell><TextField type="number" value={d.time} disabled={off} onChange={(e) => patch(a.id, { time: e.target.value })} slotProps={{ htmlInput: { min: 0, step: "0.001" } }} /></TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
              <Typography variant="body2" color="text.secondary">
                Места проставляются автоматически при публикации: больше баллов – выше, при равенстве – больше решённых задач и меньше времени. Для неявившихся укажите «Неявка».
              </Typography>
              {publishError && <Alert severity="error">{publishError}</Alert>}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <Button variant="outlined" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Сохранение…" : "Сохранить результаты"}</Button>
                <Button variant="contained" color="secondary" onClick={() => publish.mutate()} disabled={publish.isPending || !results.data?.length}>
                  {publish.isPending ? "Публикация…" : "Опубликовать протокол"}
                </Button>
              </Stack>
            </Stack>
          )
        }
      </Async>
    </Section>
  );
}

export function ProtocolPanel({ comp }: { comp: Competition }) {
  const q = useGet<Protocol>(`/competitions/${comp.id}/protocol`, undefined, { enabled: comp.status === "finished" });
  if (comp.status !== "finished") return null;
  if (q.isLoading) return null;
  if (q.error || !q.data) return <Section title="Протокол"><Alert severity="info">Протокол ещё не опубликован.</Alert></Section>;
  const p = q.data;
  const hasTeam = p.snapshot.rows.some((r) => r.team);
  const evsk = new Map(p.evsk.map((e) => [e.athlete_id, e]));
  return (
    <Section
      title={`Протокол № ${p.number}`}
      actions={<DownloadButton path={`/competitions/${comp.id}/protocol/export`} label="Протокол (.docx)" fallbackName={`protocol-${comp.id}.docx`} />}
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Опубликован {fmtDateTime(p.published_at)} · участников: {p.snapshot.participants ?? p.snapshot.rows.length}
      </Typography>
      {p.evsk.length > 0 && (
        <Alert severity="success" sx={{ mb: 1.5 }}>
          Результаты {p.evsk.length} {plural(p.evsk.length, ["участника", "участников", "участников"])} могут соответствовать разрядным требованиям ЕВСК –
          отмечены в колонке «ЕВСК». Заявку на разряд подаёт тренер (или спортсмен без тренера); заявление в Госуслугах федерация формирует вне платформы.
        </Alert>
      )}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Место</TableCell>
              <TableCell>Участник</TableCell>
              {hasTeam && <TableCell>Команда</TableCell>}
              <TableCell align="right">Баллы</TableCell>
              <TableCell align="right">Задач</TableCell>
              <TableCell align="right">Время</TableCell>
              <TableCell>Примечание</TableCell>
              {p.evsk.length > 0 && <TableCell>ЕВСК</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {p.snapshot.rows.map((r) => (
              <TableRow key={r.athlete_id} sx={r.place && r.place <= 3 ? { bgcolor: "#FFF8E5" } : undefined}>
                <TableCell><Box component="b">{r.place ?? "–"}</Box></TableCell>
                <TableCell>{r.full_name}</TableCell>
                {hasTeam && <TableCell>{r.team ?? "–"}</TableCell>}
                <TableCell align="right">{fmtNum(r.score)}</TableCell>
                <TableCell align="right">{r.tasks_solved ?? "–"}</TableCell>
                <TableCell align="right">{fmtTime(r.time_seconds)}</TableCell>
                <TableCell>{r.status === "ranked" ? "" : RESULT_STATUS_LABEL[r.status as keyof typeof RESULT_STATUS_LABEL] ?? r.status}</TableCell>
                {p.evsk.length > 0 && (
                  <TableCell sx={{ minWidth: 200 }}>
                    {evsk.has(r.athlete_id) && (() => {
                      const e = evsk.get(r.athlete_id)!;
                      return (
                        <Tooltip title={`${e.kind === "confirm" ? "Подтверждение" : "Присвоение"}: ${e.rank}. Сейчас: ${e.current_rank ?? "разряда нет"}${e.request_pending ? ". Заявка уже подана" : ""}`}>
                          <Chip size="small" color={e.request_pending ? "default" : "success"} label={`${e.kind === "confirm" ? "подтв." : "→"} ${e.rank}${e.request_pending ? " · заявка подана" : ""}`} />
                        </Tooltip>
                      );
                    })()}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Section>
  );
}
