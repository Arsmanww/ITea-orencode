import { Alert, Box, Button, Chip, Link, MenuItem, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api } from "../api/client";
import type { CoachAthlete, CompetitionList, Expiring, RankRequest, Ref, RegistryAthlete } from "../api/types";
import { AthleteHistoryDialog } from "../components/AthleteHistoryDialog";
import { AthletePicker } from "../components/AthletePicker";
import { LinkActions, LinkStatusChip } from "../components/LinkControls";
import { capitalize } from "../components/home/parts";
import { RankRequestDialog } from "../components/RankRequestDialog";
import { NotificationChannelsCard } from "../components/NotificationChannelsCard";
import { useToast } from "../components/Toast";
import { Async, DownloadButton, EmptyState, PageTitle, ReqStatusChip, Section, useGet, useInvalidate, useTabs } from "../components/common";
import { daysText, fmtDate, fmtPeriod } from "../utils/format";
import { KIND_LABEL } from "../utils/labels";

function LinkRequestForm() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const disciplines = useGet<Ref[]>("/reference/disciplines");
  const pending = useGet<CoachAthlete[]>("/coach/athletes", { status: "pending" });
  const [athlete, setAthlete] = useState<RegistryAthlete | null>(null);
  const [disciplineId, setDisciplineId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const send = useMutation({
    mutationFn: () => api("/coach/athletes/link-request", { method: "POST", body: { athlete_id: athlete?.id, discipline_id: Number(disciplineId) } }),
    onSuccess: async () => {
      toast.success("Запрос отправлен – спортсмен увидит его в своём кабинете");
      setAthlete(null);
      setError(null);
      await invalidate("/coach/athletes");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <Section title="Привязать спортсмена">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Выберите дисциплину и найдите спортсмена в реестре по фамилии. Связь начнёт действовать после подтверждения спортсменом; у спортсмена может быть несколько тренеров по разным дисциплинам.
      </Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
        <TextField select label="Дисциплина" value={disciplineId} onChange={(e) => { setDisciplineId(e.target.value); setAthlete(null); }} sx={{ minWidth: 240 }}>
          {(disciplines.data ?? []).map((d) => <MenuItem key={d.id} value={String(d.id)}>{d.name}</MenuItem>)}
        </TextField>
        <AthletePicker value={athlete} onChange={setAthlete} disciplineId={disciplineId} label={disciplineId ? "Спортсмен (занимается дисциплиной)" : "Спортсмен из реестра"} />
        <Button variant="contained" sx={{ minWidth: 180 }} disabled={!athlete || !disciplineId || send.isPending} onClick={() => { setError(null); send.mutate(); }}>Отправить запрос</Button>
      </Stack>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      <Async q={pending}>
        {(list) =>
          list.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Ожидают подтверждения спортсмена</Typography>
              <Stack spacing={1}>
                {list.map((l) => (
                  <Stack key={l.link_id} direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} justifyContent="space-between" sx={{ p: 1, borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="body2"><b>{l.athlete.full_name}</b> · {l.discipline.name.replace("Программирование ", "")}</Typography>
                    <LinkActions linkId={l.link_id} status={l.status} who={l.athlete.full_name} side="coach" />
                  </Stack>
                ))}
              </Stack>
            </Box>
          )
        }
      </Async>
    </Section>
  );
}

function WardsTab() {
  const wards = useGet<CoachAthlete[]>("/coach/athletes", { with_suspended: true });
  const [historyFor, setHistoryFor] = useState<CoachAthlete | null>(null);
  const open = useGet<CompetitionList>("/competitions", { status: "registration_open", limit: 20 });
  const [rankFor, setRankFor] = useState<CoachAthlete | null>(null);

  return (
    <>
      <Section title="Мои подопечные">
        <Async q={wards}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="Подопечных пока нет" hint="Отправьте запрос на привязку – после подтверждения спортсмен появится здесь" />
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Спортсмен</TableCell><TableCell>Возраст</TableCell><TableCell>Дисциплина</TableCell><TableCell>Разряд</TableCell><TableCell>Связь</TableCell><TableCell align="right">Действия</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {list.map((w) => (
                      <TableRow key={w.link_id}>
                        <TableCell sx={{ fontWeight: 600 }}>{w.athlete.full_name}</TableCell>
                        <TableCell>{w.age}</TableCell>
                        <TableCell>{capitalize(w.discipline.name.replace("Программирование ", ""))}</TableCell>
                        <TableCell>
                          {w.rank ? (
                            <>
                              {w.rank.name}
                              <Typography variant="caption" display="block" color={w.rank.warning ? "error.main" : "text.secondary"} fontWeight={w.rank.warning ? 700 : 400}>
                                {w.rank.valid_until ? `до ${fmtDate(w.rank.valid_until)} · ${daysText(w.rank.days_left)}` : "бессрочно"}
                              </Typography>
                            </>
                          ) : "–"}
                        </TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          <Stack direction="row" spacing={0.5} alignItems="center">
                            <LinkStatusChip status={w.status} />
                            <LinkActions linkId={w.link_id} status={w.status} who={w.athlete.full_name} side="coach" menu />
                          </Stack>
                          {w.since && <Typography variant="caption" color="text.secondary">с {fmtDate(w.since)}</Typography>}
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <Button size="small" onClick={() => setHistoryFor(w)}>Выступления</Button>
                            {w.status === "active" && <Button size="small" variant={w.rank?.warning ? "contained" : "outlined"} color={w.rank?.warning ? "warning" : "primary"} onClick={() => setRankFor(w)}>Заявка на разряд</Button>}
                            <DownloadButton size="small" path={`/athletes/${w.athlete.id}/report/export`} label="Справка" fallbackName="spravka.docx" />
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )
          }
        </Async>
      </Section>

      <Section title="Соревнования с открытым приёмом заявок" actions={<Button component={RouterLink} to="/calendar">Весь календарь</Button>}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>Заявка за подопечного подаётся на странице соревнования; сервер проверит возраст и дисциплину.</Typography>
        <Async q={open}>
          {(data) =>
            data.items.length === 0 ? (
              <EmptyState title="Сейчас нет соревнований с открытым приёмом заявок" />
            ) : (
              <Stack spacing={1}>
                {data.items.map((c) => (
                  <Stack key={c.id} direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between" sx={{ p: 1.25, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                    <Link component={RouterLink} to={`/competitions/${c.id}`} underline="hover" fontWeight={600}>{c.title}</Link>
                    <Typography variant="body2" color="text.secondary">{fmtPeriod(c.start_date, c.end_date)}</Typography>
                  </Stack>
                ))}
              </Stack>
            )
          }
        </Async>
      </Section>

      <AthleteHistoryDialog athlete={historyFor?.athlete ?? null} onClose={() => setHistoryFor(null)} />
      <RankRequestDialog
        open={rankFor !== null}
        onClose={() => setRankFor(null)}
        athleteId={rankFor?.athlete.id ?? null}
        athleteName={rankFor?.athlete.full_name}
        disciplines={rankFor ? [rankFor.discipline] : []}
        currentRanks={rankFor ? { [rankFor.discipline.id]: rankFor.rank ? { id: rankFor.rank.id, name: rankFor.rank.name } : null } : {}}
      />
    </>
  );
}

function RankRequestsTab() {
  const q = useGet<RankRequest[]>("/ranks/requests");
  return (
    <Section title="Заявки на разряды подопечных">
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Заявок нет" />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow><TableCell>Спортсмен</TableCell><TableCell>Разряд</TableCell><TableCell>Основание</TableCell><TableCell>Статус</TableCell><TableCell>Решение</TableCell></TableRow>
                </TableHead>
                <TableBody>
                  {list.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.athlete.full_name}</TableCell>
                      <TableCell>{KIND_LABEL[r.kind]}: {r.rank.name}</TableCell>
                      <TableCell sx={{ maxWidth: 260 }}>{r.competition.name}, место {r.result.place}{r.evsk_match === true && <Chip size="small" color="success" label="ЕВСК" sx={{ ml: 1 }} />}</TableCell>
                      <TableCell><ReqStatusChip status={r.status} /></TableCell>
                      <TableCell>{r.status === "approved" ? `Приказ № ${r.order_number}, до ${fmtDate(r.valid_until)}` : r.decision_comment ?? "–"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )
        }
      </Async>
    </Section>
  );
}

function ExpiringTab() {
  const [days, setDays] = useState(60);
  const q = useGet<Expiring>("/ranks/expiring", { days, include_expired: true });
  return (
    <Section
      title="Сроки действия разрядов подопечных"
      actions={
        <TextField select size="small" value={days} onChange={(e) => setDays(Number(e.target.value))} sx={{ width: 160 }}>
          <MenuItem value={30}>30 дней</MenuItem>
          <MenuItem value={60}>60 дней</MenuItem>
          <MenuItem value={180}>180 дней</MenuItem>
        </TextField>
      }
    >
      <Async q={q}>
        {(d) =>
          d.items.length === 0 ? (
            <EmptyState title={`В ближайшие ${days} дней разряды подопечных не истекают`} />
          ) : (
            <Stack spacing={1}>
              {d.items.map((i) => (
                <Alert key={i.assignment_id} severity={i.expired ? "error" : i.days_left <= 30 ? "warning" : "info"}>
                  <b>{i.subject_name}</b>: {i.title} ({i.discipline?.replace("Программирование ", "")}) – до {fmtDate(i.valid_until)}, {daysText(i.days_left)}
                </Alert>
              ))}
            </Stack>
          )
        }
      </Async>
    </Section>
  );
}

export function CoachCabinet() {
  const { tab, select, onChange } = useTabs();
  const expiring = useGet<Expiring>("/ranks/expiring", { days: 60 });
  return (
    <Box>
      <PageTitle title="Кабинет тренера" subtitle="Подопечные, заявки на соревнования и разряды" />
      {(expiring.data?.total ?? 0) > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={() => select(2)}>Показать</Button>}>
          У подопечных истекают разряды в ближайшие 60 дней: {expiring.data?.total}. Подайте заявки на подтверждение заранее.
        </Alert>
      )}
      <Tabs value={tab} onChange={onChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
        <Tab label="Подопечные" />
        <Tab label="Заявки на разряды" />
        <Tab label="Сроки" />
        <Tab label="Привязка и уведомления" />
      </Tabs>
      {tab === 0 && <WardsTab />}
      {tab === 1 && <RankRequestsTab />}
      {tab === 2 && <ExpiringTab />}
      {tab === 3 && (
        <>
          <LinkRequestForm />
          <NotificationChannelsCard />
        </>
      )}
    </Box>
  );
}
