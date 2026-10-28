import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { Box, Button, Chip, Link, Stack, Tab, Tabs, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Competition } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AthleteApplyPanel, CoachApplyPanel } from "../components/competition/ApplyPanels";
import { JudgesPanel, ModerationPanel, ProtocolPanel, ResultsPanel, StatusActions } from "../components/competition/FederationPanels";
import { Async, CompStatusChip, DownloadButton, FormatChip, KeyValue, Section, useGet, useInvalidate, useTabs } from "../components/common";
import { useToast } from "../components/Toast";
import { fmtDateTime, fmtPeriod } from "../utils/format";
import { LEVEL_LABEL, PLAN_LABEL, STAGE_FORMAT_LABEL, TIER_LABEL } from "../utils/labels";

function RegulationBlock({ comp }: { comp: Competition }) {
  const { me } = useAuth();
  const toast = useToast();
  const invalidate = useInvalidate();
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api(`/competitions/${comp.id}/regulation`, { method: "POST", form });
    },
    onSuccess: async () => {
      toast.success("Положение загружено");
      await invalidate("/competitions");
    },
    onError: toast.error,
  });
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
      {comp.regulation_url ? (
        <DownloadButton path={`/competitions/${comp.id}/regulation`} label="Скачать положение" fallbackName="regulation.pdf" />
      ) : (
        <Typography variant="body2" color="text.secondary">Положение пока не опубликовано</Typography>
      )}
      {me?.active_role === "federation" && (
        <>
          <input ref={input} type="file" hidden accept=".pdf,.doc,.docx" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
          <Button startIcon={<UploadFileIcon />} onClick={() => input.current?.click()} disabled={upload.isPending}>
            {comp.regulation_url ? "Заменить положение" : "Загрузить положение"}
          </Button>
        </>
      )}
    </Stack>
  );
}

export function CompetitionPage() {
  const { id } = useParams();
  const { me } = useAuth();
  const q = useGet<Competition>(`/competitions/${id}`);
  const { tab, onChange } = useTabs();
  const role = me?.active_role;

  return (
    <Box>
      <Button component={RouterLink} to="/calendar" startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>
        К календарю
      </Button>
      <Async q={q}>
        {(c) => (
          <>
            <Stack direction="row" spacing={1} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
              <CompStatusChip status={c.status} />
              <FormatChip format={c.format} />
              <Chip size="small" variant="outlined" label={LEVEL_LABEL[c.level]} />
              {c.is_team && <Chip size="small" color="info" variant="outlined" label="Командный зачёт" />}
            </Stack>
            <Typography variant="h4" component="h1" sx={{ fontSize: { xs: "1.4rem", sm: "2rem" }, mb: 3 }}>
              {c.title}
            </Typography>

            <Section title="О соревновании" actions={<RegulationBlock comp={c} />}>
              <KeyValue
                items={[
                  ["Дисциплина", c.discipline.name],
                  ["Тип", c.type.name],
                  ["Даты проведения", fmtPeriod(c.start_date, c.end_date)],
                  ["Место", c.location ?? "уточняется"],
                  ["Календарный план", c.calendar_plan === "none" ? PLAN_LABEL.none : `${PLAN_LABEL[c.calendar_plan]}, № ${c.plan_number}`],
                  ["Очки в рейтинге", TIER_LABEL[c.rating_tier]],
                  ["Возрастные группы", <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap key="g">{c.age_groups.map((g) => <Chip key={g.id} size="small" label={`${g.name}`} />)}</Stack>],
                  ["Приём заявок", c.registration_opens_at || c.registration_deadline ? `${fmtDateTime(c.registration_opens_at)} – ${fmtDateTime(c.registration_deadline)}` : "–"],
                  ["Описание", c.description],
                ]}
              />
            </Section>

            <Section title="Этапы соревнования">
              <Stack spacing={1.5}>
                {c.stages.map((s) => (
                  <Stack key={s.id} direction={{ xs: "column", sm: "row" }} spacing={{ xs: 0.5, sm: 2 }} alignItems={{ sm: "center" }} sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                    <Chip size="small" label={`Этап ${s.order_no}`} />
                    <Typography fontWeight={700} sx={{ flexGrow: 1 }}>{s.name}</Typography>
                    <Chip size="small" color={s.format === "online" ? "primary" : "secondary"} label={STAGE_FORMAT_LABEL[s.format]} />
                    <Typography variant="body2" color="text.secondary">{fmtDateTime(s.starts_at)} – {fmtDateTime(s.ends_at)}</Typography>
                    {s.place_or_url && (
                      <Typography variant="body2">
                        {s.place_or_url.startsWith("http") ? <Link href={s.place_or_url} target="_blank" rel="noreferrer">ссылка</Link> : s.place_or_url}
                      </Typography>
                    )}
                  </Stack>
                ))}
              </Stack>
            </Section>

            {role === "athlete" && <AthleteApplyPanel comp={c} />}
            {role === "coach" && <CoachApplyPanel comp={c} />}

            {role === "federation" ? (
              <>
                <StatusActions comp={c} />
                {c.status !== "cancelled" && (
                  <>
                    <Tabs value={tab} onChange={onChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
                      <Tab label="Заявки" />
                      <Tab label="Судейская коллегия" />
                      <Tab label="Результаты и протокол" />
                    </Tabs>
                    {tab === 0 && <ModerationPanel comp={c} />}
                    {tab === 1 && <JudgesPanel comp={c} />}
                    {tab === 2 && <ResultsPanel comp={c} />}
                  </>
                )}
              </>
            ) : (
              <JudgesPanel comp={c} />
            )}
            <ProtocolPanel comp={c} />
          </>
        )}
      </Async>
    </Box>
  );
}
