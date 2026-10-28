import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import QrCode2Icon from "@mui/icons-material/QrCode2";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  Alert,
  Badge,
  Box,
  Button,
  Chip,
  Link,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api, download } from "../api/client";
import type { AthleteProfile, Certificate, History, HistoryItem, Link as CoachLink, MyRank, RankRequest } from "../api/types";
import { LinkActions, LinkStatusChip } from "../components/LinkControls";
import { RankRequestDialog } from "../components/RankRequestDialog";
import { useToast } from "../components/Toast";
import { NotificationChannelsCard } from "../components/NotificationChannelsCard";
import { Async, DateField, DownloadButton, EmptyState, KeyValue, PageTitle, ReqStatusChip, Section, ValidityAlert, useGet, useInvalidate, useTabs } from "../components/common";
import { daysText, fmtDate, fmtNum, fmtTime, todayIso } from "../utils/format";
import { KIND_LABEL, LEVEL_LABEL, RESULT_STATUS_LABEL, STAGE_LABEL } from "../utils/labels";

function CoachRequests() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<CoachLink[]>("/athlete/coach-requests");
  const answer = useMutation({
    mutationFn: (v: { id: number; status: "accepted" | "rejected" }) => api(`/athlete/coach-requests/${v.id}`, { method: "PATCH", body: { status: v.status } }),
    onSuccess: async (_, v) => {
      toast.success(v.status === "accepted" ? "Тренер привязан" : "Запрос отклонён");
      await invalidate("/athlete", "/athletes");
    },
    onError: toast.error,
  });
  return (
    <Section title="Мои тренеры и запросы на привязку">
      <Async q={q}>
        {(all) => {
          const list = all.filter((l) => l.status === "pending");
          const links = all.filter((l) => l.status === "active" || l.status === "suspended");
          return (
          <Stack spacing={1.5}>
            {links.map((l) => (
              <Stack key={l.id} direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                <Box sx={{ flexGrow: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center"><Typography fontWeight={700}>{l.coach.full_name}</Typography><LinkStatusChip status={l.status} /></Stack>
                  <Typography variant="body2" color="text.secondary">Дисциплина: {l.discipline.name}{l.confirmed_at ? ` · с ${fmtDate(l.confirmed_at)}` : ""}</Typography>
                </Box>
                <LinkActions linkId={l.id} status={l.status} who={l.coach.full_name} side="athlete" />
              </Stack>
            ))}
            {list.length === 0 && links.length === 0 && (
              <EmptyState title="Тренеров и входящих запросов нет" hint="Когда тренер отправит запрос, вы подтвердите или отклоните его здесь" />
            )}
              {list.map((l) => (
                <Stack key={l.id} direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#FFF8E5", border: "1px solid #F2DDA4" }}>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography fontWeight={700}>{l.coach.full_name}</Typography>
                    <Typography variant="body2" color="text.secondary">Дисциплина: {l.discipline.name} · запрос от {fmtDate(l.requested_at)}</Typography>
                  </Box>
                  <Button variant="contained" color="success" disabled={answer.isPending} onClick={() => answer.mutate({ id: l.id, status: "accepted" })}>Подтвердить</Button>
                  <Button color="error" disabled={answer.isPending} onClick={() => answer.mutate({ id: l.id, status: "rejected" })}>Отклонить</Button>
                </Stack>
              ))}
          </Stack>
          );
        }}
      </Async>
    </Section>
  );
}

function AntidopingAndConsent({ p }: { p: AthleteProfile }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [date, setDate] = useState(p.antidoping_course_date ?? "");
  const [url, setUrl] = useState(p.antidoping_cert_url ?? "");
  const file = useRef<HTMLInputElement>(null);
  const save = useMutation({
    mutationFn: () => api("/athletes/me/antidoping", { method: "PUT", body: { course_date: date, cert_url: url.trim() || null } }),
    onSuccess: async () => {
      toast.success("Отметка об антидопинговом курсе сохранена");
      await invalidate("/athletes/me/profile");
    },
    onError: toast.error,
  });
  const upload = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api("/me/consent", { method: "POST", form });
    },
    onSuccess: async () => {
      toast.success("Скан согласия загружен");
      await invalidate("/athletes/me/profile", "/me/consent");
    },
    onError: toast.error,
  });
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
      <Section title="Антидопинг (РУСАДА)">
        <Stack spacing={2}>
          {p.antidoping_course_date ? <Alert severity="success">Курс пройден {fmtDate(p.antidoping_course_date)}</Alert> : <Alert severity="warning">Отметка о прохождении онлайн-курса РУСАДА не указана</Alert>}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <DateField label="Дата прохождения" value={date} onChange={(e) => setDate(e.target.value)} slotProps={{ htmlInput: { max: todayIso() } }} />
            <TextField label="Ссылка на сертификат" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} />
          </Stack>
          <Stack direction="row" spacing={2} alignItems="center">
            <Button variant="contained" disabled={!date || save.isPending} onClick={() => save.mutate()}>Сохранить</Button>
            <Link href="https://rusada.ru" target="_blank" rel="noreferrer">Официальные материалы РУСАДА</Link>
          </Stack>
        </Stack>
      </Section>
      <Section title="Согласие на обработку персональных данных">
        <Stack spacing={2}>
          {p.consent.accepted ? (
            <Alert severity={p.consent.has_scan ? "success" : "info"}>
              Согласие принято{p.consent.signed_by ? ` (${p.consent.is_guardian ? "законный представитель: " : ""}${p.consent.signed_by})` : ""}.{" "}
              {p.consent.has_scan ? "Скан подписанного документа загружен." : "Загрузите скан подписанного согласия – федерация хранит его в бумажном виде."}
            </Alert>
          ) : (
            <Alert severity="warning">Согласие не найдено. Загрузите скан подписанного документа.</Alert>
          )}
          <input ref={file} type="file" hidden accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
          <Box>
            <Button variant="outlined" startIcon={<UploadFileIcon />} disabled={upload.isPending} onClick={() => file.current?.click()}>
              {p.consent.has_scan ? "Заменить скан" : "Загрузить скан"}
            </Button>
          </Box>
        </Stack>
      </Section>
    </Box>
  );
}

function ProfileTab() {
  const q = useGet<AthleteProfile>("/athletes/me/profile");
  return (
    <Async q={q}>
      {(p) => (
        <>
          <Section title="Профиль">
            <KeyValue
              items={[
                ["ФИО", `${p.user.last_name} ${p.user.first_name} ${p.user.patronymic ?? ""}`],
                ["Дата рождения", `${fmtDate(p.user.birth_date)} (${p.age} лет)`],
                ["Муниципалитет", p.municipality],
                ["Email", p.user.email],
                ...(p.guardian_name ? ([["Законный представитель", `${p.guardian_name}${p.guardian_phone ? `, ${p.guardian_phone}` : ""}`]] as [string, string][]) : []),
              ]}
            />
          </Section>
          <Section title="Занятия и тренеры">
            <Stack spacing={1.5}>
              {p.enrollments.map((e) => {
                const coach = p.coaches.find((c) => c.discipline.id === e.discipline.id);
                return (
                  <Stack key={e.discipline.id} direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography fontWeight={700}>{e.discipline.name}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {e.organization ?? "Без организации"} · с {fmtDate(e.start_date)}{e.training_stage ? ` · ${STAGE_LABEL[e.training_stage] ?? e.training_stage}` : ""}
                      </Typography>
                    </Box>
                    {coach ? <Chip color="primary" variant="outlined" label={`Тренер: ${coach.coach.full_name}`} /> : <Chip variant="outlined" label="Без тренера – заявки подаёте сами" />}
                  </Stack>
                );
              })}
            </Stack>
          </Section>
          <CoachRequests />
          <AntidopingAndConsent p={p} />
          <NotificationChannelsCard />
        </>
      )}
    </Async>
  );
}

function RanksTab({ profile }: { profile: AthleteProfile }) {
  const ranks = useGet<MyRank[]>("/athletes/me/ranks");
  const requests = useGet<RankRequest[]>("/ranks/requests");
  const [open, setOpen] = useState(false);
  const coached = Object.fromEntries(profile.coaches.map((c) => [c.discipline.id, c.coach.full_name]));
  const current = Object.fromEntries((ranks.data ?? []).map((r) => [r.discipline.id, { id: r.rank.id, name: r.rank.name }]));
  const allCoached = profile.enrollments.length > 0 && profile.enrollments.every((e) => coached[e.discipline.id]);

  return (
    <>
      <Section
        title="Мои разряды"
        actions={<Button variant="contained" onClick={() => setOpen(true)} disabled={allCoached}>Подать на разряд</Button>}
      >
        {allCoached && <Alert severity="info" sx={{ mb: 2 }}>У вас есть тренеры по всем дисциплинам – заявки на разряд подают они.</Alert>}
        <Async q={ranks}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="Разрядов пока нет" hint="Выступайте на соревнованиях: по результатам протокола можно подать заявку на разряд" />
            ) : (
              <Stack spacing={1.5}>
                {list.map((r) => (
                  <Box key={r.discipline.id}>
                    <ValidityAlert info={r.rank} what="Разряд" />
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                      <EmojiEventsIcon color={r.rank.warning ? "warning" : "primary"} />
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography fontWeight={700}>{r.rank.name}</Typography>
                        <Typography variant="body2" color="text.secondary">{r.discipline.name}</Typography>
                      </Box>
                      <Typography variant="body2">{r.rank.valid_until ? `до ${fmtDate(r.rank.valid_until)} · ${daysText(r.rank.days_left)}` : "бессрочно"}</Typography>
                      {r.pending_request && <Chip size="small" color="warning" label="Заявка на рассмотрении" />}
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )
          }
        </Async>
      </Section>
      <Section title="Мои заявки на разряд">
        <Async q={requests}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="Заявок не было" />
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Разряд</TableCell><TableCell>Тип</TableCell><TableCell>Основание</TableCell><TableCell>Подал</TableCell><TableCell>Статус</TableCell><TableCell>Решение</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {list.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>{r.rank.name}<Typography variant="caption" display="block" color="text.secondary">{r.discipline.name}</Typography></TableCell>
                        <TableCell>{KIND_LABEL[r.kind]}</TableCell>
                        <TableCell sx={{ maxWidth: 260 }}>{r.competition.name}, место {r.result.place}{r.evsk_match === true && <Chip size="small" color="success" label="ЕВСК" sx={{ ml: 1 }} />}</TableCell>
                        <TableCell>{r.submitted_by_role === "coach" ? "тренер" : "я"}</TableCell>
                        <TableCell><ReqStatusChip status={r.status} /></TableCell>
                        <TableCell>{r.status === "approved" ? `Приказ № ${r.order_number} от ${fmtDate(r.order_date)}, до ${fmtDate(r.valid_until)}` : r.decision_comment ?? "–"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )
          }
        </Async>
      </Section>
      <RankRequestDialog open={open} onClose={() => setOpen(false)} athleteId={null} disciplines={profile.enrollments.map((e) => e.discipline)} currentRanks={current} coachedDisciplines={coached} />
    </>
  );
}

function CertificateButton({ item }: { item: HistoryItem }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const issue = useMutation({
    mutationFn: async () => {
      const cert = await api<Certificate>("/athletes/me/certificates", { method: "POST", body: { result_id: item.result_id } });
      await download(`/athletes/me/certificates/${cert.id}/export`, undefined, "spravka.docx");
      return cert;
    },
    onSuccess: async (c) => {
      toast.success(`Справка № ${c.number} сформирована`);
      await invalidate("/athletes/me/certificates");
    },
    onError: toast.error,
  });
  const disabled = item.status !== "ranked" || item.place === null;
  return (
    <Button size="small" startIcon={<QrCode2Icon />} disabled={disabled || issue.isPending} onClick={() => issue.mutate()}>
      {issue.isPending ? "…" : "Справка"}
    </Button>
  );
}

function CertificatesSection() {
  const q = useGet<Certificate[]>("/athletes/me/certificates");
  return (
    <Section title="Мои справки об участии (с QR-кодом)">
      <Async q={q}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="Справок пока нет" hint="Нажмите «Справка» в строке выступления: документ получит номер и QR-код для проверки подлинности" />
          ) : (
            <Stack spacing={1.5}>
              {list.map((c) => (
                <Stack key={c.id} direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                  <Box component="img" src={`/api/v1/public/certificates/${c.verify_token}/qr.png`} alt={`QR справки ${c.number}`} sx={{ width: 84, height: 84, bgcolor: "#fff", borderRadius: 1 }} />
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography fontWeight={700}>№ {c.number}</Typography>
                    <Typography variant="body2" color="text.secondary">{c.competition_title} · {c.place} место из {c.participants} · выдана {fmtDate(c.issued_at)}</Typography>
                    <Link component={RouterLink} to={`/verify/${c.verify_token}`} variant="body2">Открыть страницу проверки подлинности</Link>
                  </Box>
                  <DownloadButton size="small" path={`/athletes/me/certificates/${c.id}/export`} label="Скачать (.docx)" fallbackName="spravka.docx" />
                </Stack>
              ))}
            </Stack>
          )
        }
      </Async>
    </Section>
  );
}

function HistoryTab() {
  const q = useGet<History>("/athletes/me/history", { limit: 200 });
  return (
    <Async q={q}>
      {(h) => (
        <Section
          title="История выступлений"
          actions={<DownloadButton path="/athletes/me/report/export" label="Справка (.docx)" fallbackName="spravka.docx" />}
        >
          <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
            <Chip label={`Участий: ${h.total}`} />
            <Chip color="warning" icon={<EmojiEventsIcon />} label={`Призовых мест: ${h.prizes}`} />
          </Stack>
          {h.items.length === 0 ? (
            <EmptyState title="Выступлений пока нет" hint="После публикации протокола результат появится здесь автоматически" action={<Button component={RouterLink} to="/calendar" variant="contained">Календарь соревнований</Button>} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Дата</TableCell><TableCell>Соревнование</TableCell><TableCell>Статус</TableCell><TableCell>Дисциплина</TableCell><TableCell align="center">Место</TableCell><TableCell align="right">Баллы</TableCell><TableCell align="right">Время</TableCell><TableCell>Протокол</TableCell><TableCell align="right">Справка</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {h.items.map((i) => (
                    <TableRow key={i.result_id} sx={i.place && i.place <= 3 ? { bgcolor: "#FFF8E5" } : undefined}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(i.end_date)}</TableCell>
                      <TableCell sx={{ minWidth: 220 }}><Link component={RouterLink} to={`/competitions/${i.competition_id}`}>{i.competition_title}</Link></TableCell>
                      <TableCell>{LEVEL_LABEL[i.level]}</TableCell>
                      <TableCell>{i.discipline.replace("Программирование ", "")}</TableCell>
                      <TableCell align="center"><b>{i.place ? `${i.place} / ${i.participants}` : RESULT_STATUS_LABEL[i.status]}</b></TableCell>
                      <TableCell align="right">{fmtNum(i.score)}</TableCell>
                      <TableCell align="right">{fmtTime(i.time_seconds)}</TableCell>
                      <TableCell>{i.protocol_number}</TableCell>
                      <TableCell align="right"><CertificateButton item={i} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Section>
      )}
    </Async>
  );
}

export function AthleteCabinet() {
  const { tab, onChange } = useTabs();
  const profile = useGet<AthleteProfile>("/athletes/me/profile");
  const ranks = useGet<MyRank[]>("/athletes/me/ranks");
  const incoming = useGet<CoachLink[]>("/athlete/coach-requests", { status: "pending" });
  const warnings = (ranks.data ?? []).filter((r) => r.rank.warning);

  return (
    <Box>
      <PageTitle title="Кабинет спортсмена" subtitle={profile.data ? `${profile.data.user.last_name} ${profile.data.user.first_name}, ${profile.data.age} лет` : undefined} />
      {warnings.map((r) => <ValidityAlert key={r.discipline.id} info={r.rank} what={`Разряд (${r.discipline.name.replace("Программирование ", "")})`} />)}
      <Tabs value={tab} onChange={onChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
        <Tab label={<Badge color="secondary" badgeContent={incoming.data?.length ?? 0} sx={{ "& .MuiBadge-badge": { right: -14 } }}>Профиль</Badge>} />
        <Tab label="Разряды" />
        <Tab label="История выступлений" />
      </Tabs>
      {tab === 0 && <ProfileTab />}
      {tab === 1 && <Async q={profile}>{(p) => <RanksTab profile={p} />}</Async>}
      {tab === 2 && (
        <>
          <HistoryTab />
          <CertificatesSection />
        </>
      )}
    </Box>
  );
}
