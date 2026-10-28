import AddIcon from "@mui/icons-material/Add";
import { Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Link, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api } from "../api/client";
import type { CategoryRequest, Dashboard, Expiring, QueueItem, RankRequest } from "../api/types";
import { NotificationChannelsCard } from "../components/NotificationChannelsCard";
import { AuditLogSection, CompetitionTypesSection, SanctionsSection, StaffSection } from "../components/federation/FederationTools";
import { useToast } from "../components/Toast";
import { Async, CompStatusChip, DateField, EmptyState, FormDialog, PageTitle, Section, useGet, useInvalidate, useTabs } from "../components/common";
import { BRAND } from "../theme";
import { daysText, fmtDate, fmtDateTime, todayIso } from "../utils/format";
import { KIND_LABEL } from "../utils/labels";

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <Card>
      <CardContent>
        <Typography sx={{ fontSize: 34, fontWeight: 800, color: BRAND.blue, lineHeight: 1 }}>{value}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{label}</Typography>
      </CardContent>
    </Card>
  );
}

function Attention({ value, label, onClick, hot }: { value: number; label: string; onClick: () => void; hot?: boolean }) {
  return (
    <Card sx={{ height: "100%", borderColor: value && hot ? BRAND.red : undefined, bgcolor: value && hot ? "#FFF3F3" : undefined }}>
      {/* height: 100% – карточки в гриде растягиваются по самой высокой (двустрочный текст), а зона
          подсветки CardActionArea по умолчанию подстраивается под свой контент, а не под растянутую
          карточку: без этого внизу у однострочных карточек остаётся неподсвеченная полоска. */}
      <CardActionArea onClick={onClick} sx={{ height: "100%" }}>
        <CardContent>
          <Typography sx={{ fontSize: 30, fontWeight: 800, color: value && hot ? BRAND.red : BRAND.blueDark, lineHeight: 1 }}>{value}</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>{label}</Typography>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function DashboardBlock({ go }: { go: (tab: number) => void }) {
  const q = useGet<Dashboard>("/federation/dashboard");
  return (
    <Async q={q}>
      {(d) => (
        <>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, 1fr)", md: "repeat(6, 1fr)" }, gap: 2, mb: 3 }}>
            <Metric value={d.metrics.athletes} label="занимающихся" />
            <Metric value={d.metrics.coaches} label="тренеров" />
            <Metric value={d.metrics.judges} label="судей с категорией" />
            <Metric value={d.metrics.competitions_this_year} label="соревнований в году" />
            <Metric value={d.metrics.participants_this_year} label="участников в году" />
            <Metric value={d.metrics.ranks_assigned_this_year} label="разрядов присвоено" />
          </Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>Требует внимания</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }, gap: 2, mb: 3 }}>
            <Attention value={d.attention.applications_pending} label="заявок на соревнования" hot onClick={() => go(0)} />
            <Attention value={d.attention.rank_requests_pending} label="заявок на разряд" hot onClick={() => go(1)} />
            <Attention value={d.attention.judge_requests_pending} label="заявок судей" hot onClick={() => go(2)} />
            <Attention value={d.attention.expiring_30} label="сроков истекает за 30 дней" hot onClick={() => go(3)} />
            <Attention value={d.attention.expiring_60} label="сроков истекает за 60 дней" onClick={() => go(3)} />
          </Box>
          <Section title="Ближайшие соревнования и дедлайны" actions={<Button startIcon={<AddIcon />} variant="contained" component={RouterLink} to="/competitions/new">Создать соревнование</Button>}>
            {d.upcoming.length === 0 ? (
              <EmptyState title="Ближайших соревнований нет" />
            ) : (
              <Stack spacing={1}>
                {d.upcoming.map((c) => (
                  <Stack key={c.id} direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ p: 1.25, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                    <Link component={RouterLink} to={`/competitions/${c.id}`} underline="hover" fontWeight={600} sx={{ flexGrow: 1 }}>{c.title}</Link>
                    <CompStatusChip status={c.status} />
                    <Typography variant="body2" color="text.secondary">старт {fmtDate(c.start_date)}{c.registration_deadline ? ` · заявки до ${fmtDateTime(c.registration_deadline)}` : ""}</Typography>
                    {c.pending_applications > 0 && <Chip size="small" color="warning" label={`на модерации: ${c.pending_applications}`} />}
                  </Stack>
                ))}
              </Stack>
            )}
          </Section>
        </>
      )}
    </Async>
  );
}

function ApplicationsQueue() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<QueueItem[]>("/federation/applications", { status: "pending" });
  const [rejecting, setRejecting] = useState<QueueItem | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const moderate = useMutation({
    mutationFn: (v: { a: QueueItem; status: "approved" | "rejected"; comment?: string }) =>
      api(`/competitions/${v.a.competition_id}/applications/${v.a.id}`, { method: "PATCH", body: { status: v.status, comment: v.comment } }),
    onSuccess: async (_, v) => {
      toast.success(v.status === "approved" ? "Заявка одобрена" : "Заявка отклонена");
      setRejecting(null);
      setComment("");
      await invalidate("/federation", "/competitions");
    },
    onError: (e) => (rejecting ? setError(e instanceof Error ? e.message : "Ошибка") : toast.error(e)),
  });
  return (
    <Section title="Заявки на соревнования, ожидающие модерации">
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Очередь пуста" hint="Все заявки рассмотрены" />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Спортсмен</TableCell><TableCell>Соревнование</TableCell><TableCell>Возраст</TableCell><TableCell>Подал</TableCell><TableCell align="right">Решение</TableCell></TableRow></TableHead>
                <TableBody>
                  {list.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell sx={{ fontWeight: 600 }}>{a.athlete.full_name}</TableCell>
                      <TableCell sx={{ minWidth: 220 }}><Link component={RouterLink} to={`/competitions/${a.competition_id}`}>{a.competition_title}</Link></TableCell>
                      <TableCell>{a.age_on_start}</TableCell>
                      <TableCell>{a.submitted_by_role === "coach" ? "тренер" : "спортсмен"}</TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          <Button size="small" variant="contained" color="success" disabled={moderate.isPending} onClick={() => moderate.mutate({ a, status: "approved" })}>Одобрить</Button>
                          <Button size="small" color="error" onClick={() => { setError(null); setRejecting(a); }}>Отклонить</Button>
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
      <FormDialog open={rejecting !== null} title={`Отклонить заявку: ${rejecting?.athlete.full_name ?? ""}`} onClose={() => setRejecting(null)}
        onSubmit={() => rejecting && moderate.mutate({ a: rejecting, status: "rejected", comment })} submitLabel="Отклонить" submitDisabled={!comment.trim()} busy={moderate.isPending} error={error}>
        <TextField label="Причина отказа" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} required />
      </FormDialog>
    </Section>
  );
}

interface DecisionTarget { id: number; kind: "rank" | "judge"; title: string; defaultMonths: string }

function DecisionDialog({ target, onClose }: { target: DecisionTarget | null; onClose: () => void }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [decision, setDecision] = useState<"approved" | "rejected">("approved");
  const [orderNumber, setOrderNumber] = useState("");
  const [orderDate, setOrderDate] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const send = useMutation({
    mutationFn: () => {
      if (!target) throw new Error("Нет заявки");
      const path = target.kind === "rank" ? `/federation/rank-requests/${target.id}` : `/federation/judge-requests/${target.id}`;
      return api(path, {
        method: "PATCH",
        body: decision === "approved"
          ? { status: "approved", order_number: orderNumber.trim(), order_date: orderDate || null, valid_until: validUntil || null, comment: comment.trim() || null }
          : { status: "rejected", comment: comment.trim() },
      });
    },
    onSuccess: async () => {
      toast.success(decision === "approved" ? "Приказ зафиксирован, заявитель уведомлён" : "Заявка отклонена, заявитель уведомлён");
      onClose();
      setOrderNumber(""); setOrderDate(""); setValidUntil(""); setComment("");
      await invalidate("/federation", "/ranks", "/judges", "/athletes", "/notifications");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <FormDialog open={target !== null} title={target?.title ?? ""} onClose={onClose} onSubmit={() => { setError(null); send.mutate(); }}
      submitLabel={decision === "approved" ? "Утвердить" : "Отклонить"} busy={send.isPending} error={error}
      submitDisabled={decision === "approved" ? !orderNumber.trim() : !comment.trim()}>
      <ToggleButtonGroup exclusive fullWidth value={decision} onChange={(_, v) => { if (v) { setDecision(v); setComment(""); } }}>
        <ToggleButton value="approved" color="success">Утвердить</ToggleButton>
        <ToggleButton value="rejected" color="error">Отклонить</ToggleButton>
      </ToggleButtonGroup>
      {decision === "approved" ? (
        <>
          <TextField label="Номер приказа" value={orderNumber} onChange={(e) => setOrderNumber(e.target.value)} required />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
            <DateField label="Дата приказа" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} helperText="По умолчанию – сегодня" slotProps={{ htmlInput: { max: todayIso() } }} />
            <DateField label="Действует до" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} helperText={`По умолчанию: ${target?.defaultMonths}`} />
          </Box>
          <TextField label="Комментарий (необязательно)" value={comment} onChange={(e) => setComment(e.target.value)} />
        </>
      ) : (
        <TextField label="Причина отказа" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} required />
      )}
    </FormDialog>
  );
}

function RankQueue({ onDecide }: { onDecide: (t: DecisionTarget) => void }) {
  const q = useGet<RankRequest[]>("/federation/rank-requests", { status: "submitted" });
  return (
    <Section title="Заявки на присвоение и подтверждение разрядов">
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Заявок на рассмотрении нет" />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Спортсмен</TableCell><TableCell>Заявка</TableCell><TableCell>Основание</TableCell><TableCell>Подал</TableCell><TableCell align="right" /></TableRow></TableHead>
                <TableBody>
                  {list.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell sx={{ fontWeight: 600 }}>{r.athlete.full_name}<Typography variant="caption" display="block" color="text.secondary">{r.discipline.name.replace("Программирование ", "")}</Typography></TableCell>
                      <TableCell>{KIND_LABEL[r.kind]}: <b>{r.rank.name}</b></TableCell>
                      <TableCell sx={{ maxWidth: 280 }}>
                        <Link component={RouterLink} to={`/competitions/${r.competition.id}`}>{r.competition.name}</Link>, место {r.result.place}
                        {r.evsk_match === true && <Chip size="small" color="success" label="соответствует ЕВСК" sx={{ ml: 1 }} />}
                        {r.evsk_match === false && <Chip size="small" variant="outlined" label="ЕВСК: не подтверждено" sx={{ ml: 1 }} />}
                      </TableCell>
                      <TableCell>{r.submitted_by_role === "coach" ? "тренер" : "спортсмен"}</TableCell>
                      <TableCell align="right"><Button size="small" variant="contained" onClick={() => onDecide({ id: r.id, kind: "rank", title: `${r.athlete.full_name}: ${r.rank.name}`, defaultMonths: "дата приказа + 24 месяца" })}>Рассмотреть</Button></TableCell>
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

function JudgeQueue({ onDecide }: { onDecide: (t: DecisionTarget) => void }) {
  const q = useGet<CategoryRequest[]>("/federation/judge-requests", { status: "submitted" });
  return (
    <Section title="Заявки судей на категорию">
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Заявок на рассмотрении нет" />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Судья</TableCell><TableCell>Заявка</TableCell><TableCell>Комментарий</TableCell><TableCell>Дата</TableCell><TableCell align="right" /></TableRow></TableHead>
                <TableBody>
                  {list.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell sx={{ fontWeight: 600 }}>{r.judge.full_name}</TableCell>
                      <TableCell>{KIND_LABEL[r.kind]}: <b>{r.category.name}</b></TableCell>
                      <TableCell>{r.comment ?? "–"}</TableCell>
                      <TableCell>{fmtDate(r.created_at)}</TableCell>
                      <TableCell align="right"><Button size="small" variant="contained" onClick={() => onDecide({ id: r.id, kind: "judge", title: `${r.judge.full_name}: ${r.category.name}`, defaultMonths: "дата приказа + 48 месяцев" })}>Рассмотреть</Button></TableCell>
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

function ExpiringQueue() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [days, setDays] = useState(60);
  const q = useGet<Expiring>("/ranks/expiring", { days, include_expired: true });
  const run = useMutation({
    mutationFn: () => api<{ created: number }>("/federation/expiry-check", { method: "POST" }),
    onSuccess: async (r) => {
      toast.success(`Проверка выполнена, новых уведомлений: ${r.created}`);
      await invalidate("/notifications");
    },
    onError: toast.error,
  });
  return (
    <Section
      title="Истекающие разряды и судейские категории"
      actions={
        <Stack direction="row" spacing={1}>
          <ToggleButtonGroup size="small" exclusive value={days} onChange={(_, v) => v && setDays(v)}>
            <ToggleButton value={30}>30 дней</ToggleButton>
            <ToggleButton value={60}>60 дней</ToggleButton>
          </ToggleButtonGroup>
          <Button size="small" onClick={() => run.mutate()} disabled={run.isPending}>Разослать напоминания</Button>
        </Stack>
      }
    >
      <Async q={q}>
        {(d) =>
          d.items.length === 0 ? (
            <EmptyState title={`В ближайшие ${days} дней сроки не истекают`} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Кто</TableCell><TableCell>Разряд / категория</TableCell><TableCell>Действует до</TableCell><TableCell>Осталось</TableCell></TableRow></TableHead>
                <TableBody>
                  {d.items.map((i) => (
                    <TableRow key={`${i.kind}-${i.assignment_id}`}>
                      <TableCell sx={{ fontWeight: 600 }}>{i.subject_name}</TableCell>
                      <TableCell>{i.title}<Typography variant="caption" display="block" color="text.secondary">{i.kind === "rank" ? i.discipline?.replace("Программирование ", "") : "судейская категория"}</Typography></TableCell>
                      <TableCell>{fmtDate(i.valid_until)}</TableCell>
                      <TableCell><Chip size="small" color={i.expired ? "error" : i.days_left <= 30 ? "warning" : "default"} label={daysText(i.days_left)} /></TableCell>
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

export function FederationCabinet() {
  const { tab, select, onChange } = useTabs();
  const [target, setTarget] = useState<DecisionTarget | null>(null);
  return (
    <Box>
      <PageTitle title="Кабинет федерации" subtitle="Показатели, заявки и контроль сроков" />
      <DashboardBlock go={select} />
      <Tabs value={tab} onChange={onChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
        <Tab label="Заявки на соревнования" />
        <Tab label="Заявки на разряды" />
        <Tab label="Заявки судей" />
        <Tab label="Контроль сроков" />
        <Tab label="Дисквалификации" />
        <Tab label="Журнал действий" />
        <Tab label="Справочники" />
        <Tab label="Тренеры и судьи" />
      </Tabs>
      {tab === 0 && <ApplicationsQueue />}
      {tab === 1 && <RankQueue onDecide={setTarget} />}
      {tab === 2 && <JudgeQueue onDecide={setTarget} />}
      {tab === 3 && <ExpiringQueue />}
      {tab === 4 && <SanctionsSection />}
      {tab === 5 && <AuditLogSection />}
      {tab === 6 && <CompetitionTypesSection />}
      {tab === 7 && <StaffSection />}
      <DecisionDialog key={target ? `${target.kind}-${target.id}` : "none"} target={target} onClose={() => setTarget(null)} />
      <Alert severity="info" sx={{ mb: 3 }} action={<Button color="inherit" size="small" component={RouterLink} to="/registry">Открыть реестр</Button>}>
        Спортсмены, тренеры, судьи и организации – в «Реестре», рейтинг и сборная – в «Рейтинге», выгрузки – в «Отчётах».
      </Alert>
      <NotificationChannelsCard />
    </Box>
  );
}
