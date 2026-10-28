import { Alert, MenuItem, TextField } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import type { DisciplineRef, History, RankRequest, Ref } from "../api/types";
import { fmtDate } from "../utils/format";
import { KIND_LABEL } from "../utils/labels";
import { FormDialog, useGet, useInvalidate } from "./common";
import { useToast } from "./Toast";

interface Props {
  open: boolean;
  onClose: () => void;
  /** null – спортсмен подаёт за себя; число – тренер подаёт за подопечного */
  athleteId: number | null;
  athleteName?: string;
  disciplines: DisciplineRef[];
  /** действующий разряд по дисциплинам (id дисциплины → разряд) */
  currentRanks: Record<number, { id: number; name: string } | null | undefined>;
  /** дисциплины, где у спортсмена есть тренер (подаёт тренер) – только для режима «сам за себя» */
  coachedDisciplines?: Record<number, string>;
}

/** Заявка на присвоение/подтверждение разряда: основание – соревнование и результат из протокола. */
export function RankRequestDialog({ open, onClose, athleteId, athleteName, disciplines, currentRanks, coachedDisciplines = {} }: Props) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [disciplineId, setDisciplineId] = useState("");
  const [kind, setKind] = useState<"assign" | "confirm">("assign");
  const [rankId, setRankId] = useState("");
  const [resultId, setResultId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const ranks = useGet<Ref[]>("/reference/ranks");
  const history = useGet<History>(athleteId === null ? "/athletes/me/history" : `/athletes/${athleteId}/history`, { limit: 200 }, { enabled: open });

  useEffect(() => {
    if (open) {
      setDisciplineId(disciplines.length === 1 ? String(disciplines[0].id) : "");
      setKind("assign");
      setRankId("");
      setResultId("");
      setError(null);
    }
  }, [open, disciplines]);

  const discipline = disciplines.find((d) => String(d.id) === disciplineId);
  const current = discipline ? currentRanks[discipline.id] : null;
  const currentOrder = ranks.data?.find((r) => r.id === current?.id)?.order_no ?? 0;
  const coach = discipline ? coachedDisciplines[discipline.id] : undefined;

  const rankOptions = useMemo(() => {
    const all = ranks.data ?? [];
    return kind === "confirm" ? all.filter((r) => r.id === current?.id) : all.filter((r) => (r.order_no ?? 0) > currentOrder);
  }, [ranks.data, kind, current, currentOrder]);

  const results = useMemo(
    () => (history.data?.items ?? []).filter((h) => h.status === "ranked" && h.place !== null && discipline && h.discipline === discipline.name),
    [history.data, discipline],
  );

  const submit = useMutation({
    mutationFn: () => {
      const result = results.find((r) => String(r.result_id) === resultId);
      return api<RankRequest>("/ranks/requests", {
        method: "POST",
        body: { athlete_id: athleteId, rank_id: Number(rankId), kind, competition_id: result?.competition_id, result_id: Number(resultId) },
      });
    },
    onSuccess: async (r) => {
      toast.success(r.evsk_match === true ? "Заявка подана. Результат может соответствовать требованиям ЕВСК" : "Заявка на разряд подана в федерацию");
      onClose();
      await invalidate("/ranks", "/athletes", "/federation");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });

  return (
    <FormDialog
      open={open}
      title={athleteName ? `Заявка на разряд: ${athleteName}` : "Заявка на разряд"}
      onClose={onClose}
      onSubmit={() => submit.mutate()}
      submitDisabled={!discipline || !rankId || !resultId || Boolean(coach)}
      busy={submit.isPending}
      error={error}
      maxWidth="md"
    >
      {disciplines.length > 1 && (
        <TextField select label="Дисциплина" value={disciplineId} onChange={(e) => { setDisciplineId(e.target.value); setRankId(""); setResultId(""); }}>
          {disciplines.map((d) => <MenuItem key={d.id} value={String(d.id)}>{d.name}</MenuItem>)}
        </TextField>
      )}
      {coach && <Alert severity="warning">По этой дисциплине вас ведёт тренер {coach}: заявку на разряд подаёт тренер. Спортсмен с тренером подать её самостоятельно не может.</Alert>}
      {discipline && !coach && (
        <>
          <Alert severity="info">
            Действующий разряд по дисциплине: <b>{current?.name ?? "нет"}</b>. Заявка рассматривается федерацией; в ней указывается соревнование и результат, на основании которых запрошен разряд.
          </Alert>
          <TextField select label="Тип заявки" value={kind} onChange={(e) => { setKind(e.target.value as "assign" | "confirm"); setRankId(""); }}>
            {(["assign", "confirm"] as const).map((k) => <MenuItem key={k} value={k} disabled={k === "confirm" && !current}>{KIND_LABEL[k]} разряда</MenuItem>)}
          </TextField>
          <TextField select label="Разряд" value={rankId} onChange={(e) => setRankId(e.target.value)} helperText={rankOptions.length === 0 ? "Нет доступных разрядов для этого типа заявки" : undefined}>
            {rankOptions.map((r) => <MenuItem key={r.id} value={String(r.id)}>{r.name}</MenuItem>)}
          </TextField>
          <TextField select label="Основание: соревнование и результат" value={resultId} onChange={(e) => setResultId(e.target.value)}
            helperText={history.isLoading ? "Загрузка результатов…" : results.length === 0 ? "Нет результатов в зачёте по этой дисциплине" : "Протокол соревнования должен быть опубликован"}>
            {results.map((r) => (
              <MenuItem key={r.result_id} value={String(r.result_id)} sx={{ whiteSpace: "normal" }}>
                {r.competition_title} – {r.place} место из {r.participants} ({fmtDate(r.end_date)})
              </MenuItem>
            ))}
          </TextField>
        </>
      )}
    </FormDialog>
  );
}
