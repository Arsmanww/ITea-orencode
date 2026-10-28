import GavelIcon from "@mui/icons-material/Gavel";
import { Alert, Box, Button, Chip, Link, MenuItem, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { api } from "../api/client";
import type { CategoryRequest, JudgeAssignment, MyAssignments, Ref } from "../api/types";
import { NotificationChannelsCard } from "../components/NotificationChannelsCard";
import { useToast } from "../components/Toast";
import { Async, CompStatusChip, EmptyState, FormDialog, PageTitle, ReqStatusChip, Section, ValidityAlert, useGet, useInvalidate } from "../components/common";
import { daysText, fmtDate, fmtPeriod } from "../utils/format";
import { KIND_LABEL } from "../utils/labels";

function AssignmentsTable({ rows }: { rows: JudgeAssignment[] }) {
  if (rows.length === 0) return <EmptyState title="Назначений нет" />;
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Соревнование</TableCell><TableCell>Даты</TableCell><TableCell>Должность</TableCell><TableCell>Статус</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {rows.map((a) => (
            <TableRow key={a.id}>
              <TableCell sx={{ minWidth: 240 }}><Link component={RouterLink} to={`/competitions/${a.competition.id}`}>{a.competition.title}</Link></TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtPeriod(a.competition.start_date, a.competition.end_date)}</TableCell>
              <TableCell><Chip size="small" variant="outlined" color="primary" label={a.position.name} /></TableCell>
              <TableCell><CompStatusChip status={a.competition.status} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function RequestDialog({ open, onClose, currentId }: { open: boolean; onClose: () => void; currentId: number | null }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const categories = useGet<Ref[]>("/reference/judge-categories");
  const [categoryId, setCategoryId] = useState("");
  const [kind, setKind] = useState<"assign" | "confirm">(currentId ? "confirm" : "assign");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const currentOrder = categories.data?.find((c) => c.id === currentId)?.order_no ?? 0;
  const options = (categories.data ?? []).filter((c) => (kind === "confirm" ? c.id === currentId : (c.order_no ?? 0) > currentOrder));

  const send = useMutation({
    mutationFn: () => api("/judges/me/category-requests", { method: "POST", body: { category_id: Number(categoryId), kind, comment: comment.trim() || null } }),
    onSuccess: async () => {
      toast.success("Заявка отправлена в федерацию");
      setCategoryId("");
      setComment("");
      onClose();
      await invalidate("/judges");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <FormDialog open={open} title="Заявка на судейскую категорию" onClose={onClose} onSubmit={() => { setError(null); send.mutate(); }} submitDisabled={!categoryId} busy={send.isPending} error={error}>
      <TextField select label="Тип заявки" value={kind} onChange={(e) => { setKind(e.target.value as "assign" | "confirm"); setCategoryId(""); }}>
        <MenuItem value="assign">Присвоение более высокой категории</MenuItem>
        <MenuItem value="confirm" disabled={!currentId}>Подтверждение текущей категории</MenuItem>
      </TextField>
      <TextField select label="Категория" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} helperText={options.length === 0 ? "Для этого типа заявки нет доступных категорий" : undefined}>
        {options.map((c) => <MenuItem key={c.id} value={String(c.id)}>{c.name}</MenuItem>)}
      </TextField>
      <TextField label="Комментарий" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} placeholder="Например: отработано 6 соревнований" />
    </FormDialog>
  );
}

export function JudgeCabinet() {
  const data = useGet<MyAssignments>("/judges/me/assignments");
  const requests = useGet<CategoryRequest[]>("/judges/me/category-requests");
  const [open, setOpen] = useState(false);

  return (
    <Box>
      <PageTitle title="Кабинет судьи" actions={<Button variant="contained" onClick={() => setOpen(true)}>Заявка на категорию</Button>} />
      <Async q={data}>
        {(d) => (
          <>
            <ValidityAlert info={d.category} what="Судейская категория" />
            <Section title="Судейская категория">
              {d.category ? (
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                  <GavelIcon color={d.category.warning ? "warning" : "primary"} sx={{ fontSize: 40 }} />
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="h6">{d.category.name}</Typography>
                    <Typography color="text.secondary">
                      Присвоена {fmtDate(d.category.assigned_at)} · {d.category.valid_until ? `действует до ${fmtDate(d.category.valid_until)} (${daysText(d.category.days_left)})` : "бессрочно"}
                    </Typography>
                  </Box>
                  <Chip color={d.category.expired ? "error" : d.category.warning ? "warning" : "success"} label={d.category.expired ? "Истекла" : d.category.warning ? "Скоро истекает" : "Действует"} />
                </Stack>
              ) : (
                <EmptyState title="Судейская категория не присвоена" hint="Подайте заявку на присвоение категории" />
              )}
            </Section>
            <Section title="Предстоящие назначения"><AssignmentsTable rows={d.upcoming} /></Section>
            <Section title="Мои соревнования (история работы)"><AssignmentsTable rows={d.past} /></Section>
            <RequestDialog key={String(open)} open={open} onClose={() => setOpen(false)} currentId={d.category?.id ?? null} />
          </>
        )}
      </Async>
      <Section title="Мои заявки на категорию">
        <Async q={requests}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="Заявок не было" />
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead><TableRow><TableCell>Дата</TableCell><TableCell>Заявка</TableCell><TableCell>Статус</TableCell><TableCell>Решение</TableCell></TableRow></TableHead>
                  <TableBody>
                    {list.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>{fmtDate(r.created_at)}</TableCell>
                        <TableCell>{KIND_LABEL[r.kind]}: {r.category.name}</TableCell>
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
      <NotificationChannelsCard />
      {requests.error && <Alert severity="error">{requests.error.message}</Alert>}
    </Box>
  );
}
