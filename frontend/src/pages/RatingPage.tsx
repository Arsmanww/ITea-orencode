import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import GroupAddIcon from "@mui/icons-material/GroupAdd";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Collapse,
  IconButton,
  Link,
  MenuItem,
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
import { Fragment, useMemo, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { AgeGroup, RatingItem, RatingOut, Ref, Season, Squad } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Async, DownloadButton, EmptyState, FormDialog, PageTitle, Section, useGet, useInvalidate, useTabs } from "../components/common";
import { fmtDate, fmtNum } from "../utils/format";
import { TIER_LABEL } from "../utils/labels";

function Explainer({ data }: { data: RatingOut }) {
  const tiers = ["russia_championship", "russia_first", "interregional", "regional"] as const;
  const points = (tier: string, place: number) => data.settings.rules.find((r) => r.tier === tier && r.place === place)?.points ?? 0;
  return (
    <Section title="Как считается рейтинг">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Очки начисляются за 1–3 места в протоколе в зависимости от уровня соревнования; рейтинговый балл – сумма очков за сезон. Если спортсмен занял призовые места минимум на {data.settings.stability_min_prizes} соревнованиях, сумма умножается на коэффициент стабильности ×{fmtNum(data.settings.stability_coef)}. Спортсмены с действующей дисквалификацией или отстранением в рейтинг не попадают.
      </Typography>
      <TableContainer>
        <Table size="small">
          <TableHead><TableRow><TableCell>Уровень соревнования</TableCell><TableCell align="center">1 место</TableCell><TableCell align="center">2 место</TableCell><TableCell align="center">3 место</TableCell></TableRow></TableHead>
          <TableBody>
            {tiers.map((t) => (
              <TableRow key={t}>
                <TableCell>{TIER_LABEL[t]}</TableCell>
                {[1, 2, 3].map((p) => <TableCell key={p} align="center">{points(t, p)}</TableCell>)}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Section>
  );
}

function Row({ item, selectable, selected, onToggle, isFed }: { item: RatingItem; selectable: boolean; selected: boolean; onToggle: () => void; isFed: boolean }) {
  const [open, setOpen] = useState(false);
  const boosted = Number(item.coefficient) > 1;
  return (
    <Fragment>
      <TableRow hover sx={{ "& > td": { borderBottom: open ? "unset" : undefined }, bgcolor: selected ? "#EEF3FC" : undefined }}>
        {selectable && <TableCell padding="checkbox"><Checkbox checked={selected} onChange={onToggle} inputProps={{ "aria-label": `Выбрать ${item.athlete_name}` }} /></TableCell>}
        <TableCell><b>{item.place}</b></TableCell>
        <TableCell sx={{ fontWeight: 600 }}>{item.athlete_name}<Typography variant="caption" display="block" color="text.secondary">{item.age} лет · {item.organization ?? "без организации"}</Typography></TableCell>
        <TableCell>{item.rank ?? "–"}</TableCell>
        <TableCell align="center">{item.prizes}</TableCell>
        <TableCell align="right">{item.base_points}</TableCell>
        <TableCell align="center">{boosted ? <Chip size="small" color="success" label={`×${fmtNum(item.coefficient)}`} /> : "×1"}</TableCell>
        <TableCell align="right"><b>{fmtNum(item.total)}</b></TableCell>
        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
          {isFed && <DownloadButton size="small" path={`/athletes/${item.athlete_id}/report/export`} label="Справка" fallbackName="spravka.docx" sx={{ mr: 0.5 }} />}
          <IconButton size="small" onClick={() => setOpen((v) => !v)} aria-label="Расчёт очков">{open ? <ExpandLessIcon /> : <ExpandMoreIcon />}</IconButton>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={selectable ? 9 : 8} sx={{ py: 0, bgcolor: "#FAFBFE" }}>
          <Collapse in={open} unmountOnExit>
            <Box sx={{ py: 1.5 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Расчёт: {item.base_points} {boosted ? `× ${fmtNum(item.coefficient)} (призовых мест: ${item.prizes})` : ""} = {fmtNum(item.total)}
              </Typography>
              <Table size="small">
                <TableHead><TableRow><TableCell>Соревнование</TableCell><TableCell>Дата</TableCell><TableCell>Уровень</TableCell><TableCell align="center">Место</TableCell><TableCell align="right">Очки</TableCell></TableRow></TableHead>
                <TableBody>
                  {item.breakdown.map((b) => (
                    <TableRow key={b.competition_id}>
                      <TableCell><Link component={RouterLink} to={`/competitions/${b.competition_id}`}>{b.title}</Link></TableCell>
                      <TableCell>{fmtDate(b.date)}</TableCell>
                      <TableCell>{TIER_LABEL[b.tier]}</TableCell>
                      <TableCell align="center">{b.place ?? "–"}</TableCell>
                      <TableCell align="right">{b.points}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </Fragment>
  );
}

function SquadDialog({ open, onClose, data, members, onCreated }: { open: boolean; onClose: () => void; data: RatingOut; members: RatingItem[]; onCreated: () => void }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const table = data.tables[0];
  const defaultTitle = `Сборная Оренбургской области: ${table.discipline.name.replace("Программирование ", "")}${data.age_group ? `, ${data.age_group.name}` : ""}, ${data.season.name.toLowerCase()}`;
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () =>
      api<Squad>("/squads", {
        method: "POST",
        body: { season_id: data.season.id, discipline_id: table.discipline.id, age_group_id: data.age_group?.id ?? null, title: (title || defaultTitle).trim(), members: members.map((m) => ({ athlete_id: m.athlete_id })) },
      }),
    onSuccess: async () => {
      toast.success("Состав сборной сохранён. Проект приказа – на вкладке «Сборные»");
      await invalidate("/squads");
      onCreated();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  return (
    <FormDialog open={open} title="Сформировать сборную региона" onClose={onClose} onSubmit={() => { setError(null); create.mutate(); }} submitLabel="Сохранить состав" busy={create.isPending} submitDisabled={members.length === 0} error={error} maxWidth="md">
      <TextField label="Название состава" value={title} placeholder={defaultTitle} onChange={(e) => setTitle(e.target.value)} />
      <Typography variant="body2" color="text.secondary">Состав ({members.length}) в порядке рейтинга. Баллы фиксируются на момент формирования.</Typography>
      <TableContainer sx={{ maxHeight: 260 }}>
        <Table size="small" stickyHeader>
          <TableHead><TableRow><TableCell>№</TableCell><TableCell>Спортсмен</TableCell><TableCell>Разряд</TableCell><TableCell align="right">Баллы</TableCell></TableRow></TableHead>
          <TableBody>
            {members.map((m, i) => <TableRow key={m.athlete_id}><TableCell>{i + 1}</TableCell><TableCell>{m.athlete_name}</TableCell><TableCell>{m.rank ?? "–"}</TableCell><TableCell align="right">{fmtNum(m.total)}</TableCell></TableRow>)}
          </TableBody>
        </Table>
      </TableContainer>
    </FormDialog>
  );
}

function RatingTab({ onSquadCreated }: { onSquadCreated: () => void }) {
  const { me } = useAuth();
  const isFed = me?.active_role === "federation";
  const seasons = useGet<Season[]>("/rating/seasons");
  const disciplines = useGet<Ref[]>("/reference/disciplines");
  const groups = useGet<AgeGroup[]>("/reference/age-groups");
  const ranks = useGet<Ref[]>("/reference/ranks");
  const [params, setParams] = useSearchParams();
  const f = {
    season: params.get("season") ?? "", discipline: params.get("discipline") ?? "algorithmic",
    age: params.get("age") ?? "", rank: params.get("rank") ?? "",
  };
  const [selected, setSelected] = useState<number[]>([]);
  const [dialog, setDialog] = useState(false);
  const q = useGet<RatingOut>("/rating", { season_id: f.season, discipline: f.discipline, age_group_id: f.age, min_rank_id: f.rank, limit: 200 });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (e.target.value) next.set(k, e.target.value); else next.delete(k);
      return next;
    }, { replace: true });
    setSelected([]);
  };

  const chosen = useMemo(() => (q.data?.tables[0]?.items ?? []).filter((i) => selected.includes(i.athlete_id)), [q.data, selected]);

  return (
    <>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }, gap: 2, mb: 3 }}>
        <TextField select label="Сезон" value={f.season || (q.data ? String(q.data.season.id) : "")} onChange={set("season")}>
          {(seasons.data ?? []).map((s) => <MenuItem key={s.id} value={String(s.id)}>{s.name}</MenuItem>)}
        </TextField>
        <TextField select label="Дисциплина" value={f.discipline} onChange={set("discipline")}>
          {(disciplines.data ?? []).map((d) => <MenuItem key={d.id} value={d.code ?? ""}>{d.name.replace("Программирование ", "")}</MenuItem>)}
        </TextField>
        <TextField select label="Возрастная группа" value={f.age} onChange={set("age")}>
          <MenuItem value="">Все возрасты</MenuItem>
          {(groups.data ?? []).map((g) => <MenuItem key={g.id} value={String(g.id)}>{g.name}</MenuItem>)}
        </TextField>
        <TextField select label="Минимальный разряд" value={f.rank} onChange={set("rank")}>
          <MenuItem value="">Любой</MenuItem>
          {(ranks.data ?? []).map((r) => <MenuItem key={r.id} value={String(r.id)}>{r.name}</MenuItem>)}
        </TextField>
      </Box>

      <Async q={q}>
        {(data) => {
          const t = data.tables[0];
          return (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                {data.season.name}: {fmtDate(data.season.date_from)} – {fmtDate(data.season.date_to)}. Санкции, возраст и разряд проверены на {fmtDate(data.as_of)}. В рейтинге: {t.total_athletes}.
              </Typography>
              {t.excluded.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Исключены из рейтинга: {t.excluded.map((e) => `${e.athlete_name} – ${e.reason}`).join("; ")}.
                </Alert>
              )}
              {isFed && (
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mb: 2 }}>
                  <Button variant="contained" color="secondary" startIcon={<GroupAddIcon />} disabled={selected.length === 0} onClick={() => setDialog(true)}>
                    Сформировать сборную ({selected.length})
                  </Button>
                  <Button size="small" onClick={() => setSelected(t.items.slice(0, 5).map((i) => i.athlete_id))}>Выбрать топ-5</Button>
                  <Button size="small" disabled={selected.length === 0} onClick={() => setSelected([])}>Снять выбор</Button>
                </Stack>
              )}
              {t.items.length === 0 ? (
                <EmptyState title="В этом сезоне по выбранным условиям рейтинга нет" hint="Рейтинг строится по результатам опубликованных протоколов" />
              ) : (
                <Section>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          {isFed && <TableCell padding="checkbox" />}
                          <TableCell>Место</TableCell><TableCell>Спортсмен</TableCell><TableCell>Разряд</TableCell><TableCell align="center">Призовых</TableCell>
                          <TableCell align="right">Очки</TableCell><TableCell align="center">Коэфф.</TableCell><TableCell align="right">Итого</TableCell><TableCell />
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {t.items.map((i) => (
                          <Row key={i.athlete_id} item={i} isFed={isFed} selectable={isFed} selected={selected.includes(i.athlete_id)}
                            onToggle={() => setSelected((s) => (s.includes(i.athlete_id) ? s.filter((x) => x !== i.athlete_id) : [...s, i.athlete_id]))} />
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Section>
              )}
              <Explainer data={data} />
              <SquadDialog key={String(dialog)} open={dialog} onClose={() => setDialog(false)} data={data} members={chosen} onCreated={() => { setDialog(false); setSelected([]); onSquadCreated(); }} />
            </>
          );
        }}
      </Async>
    </>
  );
}

function SquadsTab() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<Squad[]>("/squads");
  const [approving, setApproving] = useState<Squad | null>(null);
  const [number, setNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const approve = useMutation({
    mutationFn: () => api(`/squads/${approving?.id}/approve`, { method: "POST", body: { order_number: number.trim() } }),
    onSuccess: async () => {
      toast.success("Состав утверждён приказом");
      setApproving(null);
      setNumber("");
      await invalidate("/squads");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  return (
    <Async q={q}>
      {(list) =>
        list.length === 0 ? (
          <EmptyState title="Составов сборной пока нет" hint="Выберите спортсменов в рейтинге и нажмите «Сформировать сборную»" />
        ) : (
          <>
            {list.map((s) => (
              <Section key={s.id} title={s.title}
                actions={
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip color={s.status === "approved" ? "success" : "warning"} label={s.status === "approved" ? `Утверждён, приказ № ${s.order_number}` : "Проект"} />
                    {s.status === "draft" && <Button size="small" onClick={() => { setError(null); setApproving(s); }}>Утвердить приказом</Button>}
                    <DownloadButton size="small" path={`/squads/${s.id}/order-project`} label="Проект приказа (.docx)" fallbackName="order.docx" />
                  </Stack>
                }>
                <TableContainer>
                  <Table size="small">
                    <TableHead><TableRow><TableCell>№</TableCell><TableCell>Спортсмен</TableCell><TableCell>Организация</TableCell><TableCell>Разряд</TableCell><TableCell>Тренер</TableCell><TableCell align="right">Баллы</TableCell></TableRow></TableHead>
                    <TableBody>
                      {s.members.map((m) => (
                        <TableRow key={m.athlete_id}>
                          <TableCell>{m.position}</TableCell><TableCell sx={{ fontWeight: 600 }}>{m.athlete_name}</TableCell><TableCell>{m.organization ?? "–"}</TableCell>
                          <TableCell>{m.rank ?? "–"}</TableCell><TableCell>{m.coach ?? "–"}</TableCell><TableCell align="right">{fmtNum(m.rating_points)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Section>
            ))}
            <FormDialog open={approving !== null} title="Утвердить состав приказом" onClose={() => setApproving(null)} onSubmit={() => approve.mutate()} submitDisabled={!number.trim()} busy={approve.isPending} error={error}>
              <TextField label="Номер приказа" value={number} onChange={(e) => setNumber(e.target.value)} />
            </FormDialog>
          </>
        )
      }
    </Async>
  );
}

export function RatingPage() {
  const { me } = useAuth();
  const { tab, select, onChange } = useTabs(0, "tab");
  const isFed = me?.active_role === "federation";
  return (
    <Box>
      <PageTitle title="Рейтинг спортсменов региона" subtitle="Очки по уровню соревнования, коэффициент стабильности и прозрачный расчёт по каждому спортсмену" />
      {isFed && (
        <Tabs value={tab} onChange={onChange} sx={{ mb: 2 }}>
          <Tab label="Рейтинг" />
          <Tab label="Сборные команды" />
        </Tabs>
      )}
      {tab === 0 && <RatingTab onSquadCreated={() => select(1)} />}
      {tab === 1 && isFed && <SquadsTab />}
    </Box>
  );
}
