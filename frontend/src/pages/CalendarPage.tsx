import AddIcon from "@mui/icons-material/Add";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import EventIcon from "@mui/icons-material/Event";
import PlaceIcon from "@mui/icons-material/Place";
import { Box, Button, Card, CardActionArea, CardActions, CardContent, Chip, FormControlLabel, MenuItem, Pagination, Stack, Switch, TextField, Typography } from "@mui/material";
import { Link as RouterLink, useSearchParams } from "react-router-dom";

import type { AgeGroup, AthleteProfile, CompetitionList, Ref } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Async, CompStatusChip, EmptyState, FormatChip, PageTitle, useGet } from "../components/common";
import { eligibility } from "../utils/eligibility";
import { fmtDateTime, fmtPeriod } from "../utils/format";
import { COMP_STATUS_LABEL, LEVEL_LABEL, PLAN_LABEL } from "../utils/labels";

const PAGE_SIZE = 12;

export function CalendarPage() {
  const { me } = useAuth();
  // Фильтры живут в адресной строке: плашка «приём заявок» в шапке ведёт на уже отфильтрованный
  // календарь, а «Назад» браузера возвращает к тем же фильтрам, а не к пустой форме.
  const [params, setParams] = useSearchParams();
  const f = {
    discipline: params.get("discipline") ?? "", status: params.get("status") ?? "", year: params.get("year") ?? "",
    level: params.get("level") ?? "", age_group_id: params.get("age_group_id") ?? "",
  };
  const forMe = params.get("for_me") === "1";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const disciplines = useGet<Ref[]>("/reference/disciplines");
  const ageGroups = useGet<AgeGroup[]>("/reference/age-groups");
  const list = useGet<CompetitionList>("/competitions", {
    ...f, for_me: me?.active_role === "athlete" && forMe ? true : undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE,
  });
  const isAthlete = me?.active_role === "athlete";
  const isCoach = me?.active_role === "coach";
  const profile = useGet<AthleteProfile>("/athletes/me/profile", undefined, { enabled: isAthlete });
  const setPage = (p: number) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    next.set("page", String(p));
    return next;
  }, { replace: true });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (e.target.value) next.set(k, e.target.value); else next.delete(k);
      next.set("page", "1");
      return next;
    }, { replace: true });
  };
  const setStatus = (v: string) => set("status")({ target: { value: v } });
  const setForMe = (v: boolean) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (v) next.set("for_me", "1"); else next.delete("for_me");
    next.set("page", "1");
    return next;
  }, { replace: true });
  const resetFilters = () => setParams((prev) => {
    const next = new URLSearchParams(prev);
    for (const key of ["discipline", "status", "year", "level", "age_group_id", "for_me", "page"]) next.delete(key);
    return next;
  }, { replace: true });

  return (
    <Box>
      <PageTitle
        title="Календарь соревнований"
        subtitle="Региональные, межрегиональные и всероссийские соревнования по 6 дисциплинам"
        actions={
          me?.active_role === "federation" && (
            <Button variant="contained" startIcon={<AddIcon />} component={RouterLink} to="/competitions/new">
              Создать соревнование
            </Button>
          )
        }
      />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }, gap: 2, mb: isAthlete ? 1.5 : 3 }}>
        <TextField select label="Дисциплина" value={f.discipline} onChange={set("discipline")}>
          <MenuItem value="">Все дисциплины</MenuItem>
          {(disciplines.data ?? []).map((d) => (
            <MenuItem key={d.id} value={d.code ?? ""}>{d.name.replace("Программирование ", "")}</MenuItem>
          ))}
        </TextField>
        <TextField select label="Статус" value={f.status} onChange={set("status")}>
          <MenuItem value="">Любой статус</MenuItem>
          {Object.entries(COMP_STATUS_LABEL)
            .filter(([k]) => me?.active_role === "federation" || k !== "draft")
            .map(([k, v]) => (
              <MenuItem key={k} value={k}>{v}</MenuItem>
            ))}
        </TextField>
        <TextField select label="Год" value={f.year} onChange={set("year")}>
          <MenuItem value="">Все годы</MenuItem>
          {[2027, 2026, 2025, 2024, 2023].map((y) => (
            <MenuItem key={y} value={y}>{y}</MenuItem>
          ))}
        </TextField>
        <TextField select label="Уровень" value={f.level} onChange={set("level")}>
          <MenuItem value="">Любой уровень</MenuItem>
          {Object.entries(LEVEL_LABEL).map(([k, v]) => (
            <MenuItem key={k} value={k}>{v}</MenuItem>
          ))}
        </TextField>
        <TextField select label="Возрастная группа" value={f.age_group_id} onChange={set("age_group_id")}>
          <MenuItem value="">Любая</MenuItem>
          {(ageGroups.data ?? []).map((g) => (
            <MenuItem key={g.id} value={String(g.id)}>{g.name}</MenuItem>
          ))}
        </TextField>
      </Box>
      {(isAthlete || isCoach) && (
        <Stack direction="row" spacing={1} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
          <Chip
            color={f.status === "registration_open" ? "primary" : "default"}
            variant={f.status === "registration_open" ? "filled" : "outlined"}
            label={isCoach ? "Сейчас можно подать за подопечного" : "Сейчас принимают заявки"}
            onClick={() => setStatus(f.status === "registration_open" ? "" : "registration_open")}
          />
        </Stack>
      )}
      {isAthlete && (
        <FormControlLabel
          sx={{ mb: 2 }}
          control={<Switch checked={forMe} onChange={(e) => setForMe(e.target.checked)} />}
          label="Только подходящие мне по дисциплине и возрасту на дату старта"
        />
      )}

      <Async q={list}>
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="Соревнований по этим условиям нет" hint="Измените фильтры или сбросьте их" action={<Button onClick={resetFilters}>Сбросить фильтры</Button>} />
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Найдено: {data.total}
              </Typography>
              <Stack spacing={1.5}>
                {data.items.map((c) => {
                  const el = profile.data ? eligibility(c, profile.data) : null;
                  return (
                    <Card key={c.id}>
                      <CardActionArea component={RouterLink} to={`/competitions/${c.id}`}>
                        <CardContent>
                          <Stack direction="row" spacing={1} sx={{ mb: 1 }} flexWrap="wrap" useFlexGap>
                            <CompStatusChip status={c.status} />
                            <FormatChip format={c.format} />
                            <Chip size="small" variant="outlined" label={LEVEL_LABEL[c.level]} />
                            <Chip size="small" variant="outlined" label={c.calendar_plan === "none" ? PLAN_LABEL.none : `${PLAN_LABEL[c.calendar_plan]} № ${c.plan_number}`} />
                            {c.is_team && <Chip size="small" label="Командный зачёт" color="info" variant="outlined" />}
                            {el && c.status === "registration_open" && (
                              <Chip size="small" color={el.ok ? "success" : "default"} icon={el.ok ? <CheckCircleIcon /> : undefined} label={el.ok ? "Вам подходит" : "Вам не подходит"} />
                            )}
                          </Stack>
                          <Typography variant="h6" sx={{ fontSize: "1.05rem", mb: 0.75 }}>
                            {c.title}
                          </Typography>
                          <Stack direction={{ xs: "column", sm: "row" }} spacing={{ xs: 0.5, sm: 3 }} color="text.secondary">
                            <Typography variant="body2" sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                              <EventIcon sx={{ fontSize: 17 }} /> {fmtPeriod(c.start_date, c.end_date)}
                            </Typography>
                            <Typography variant="body2" sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                              <PlaceIcon sx={{ fontSize: 17 }} /> {c.location ?? "место уточняется"}
                            </Typography>
                            {c.status === "registration_open" && c.registration_deadline && (
                              <Typography variant="body2" color="secondary.main" fontWeight={600}>
                                Заявки до {fmtDateTime(c.registration_deadline)}
                              </Typography>
                            )}
                          </Stack>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {c.discipline.name} · {c.age_groups.map((g) => g.name).join(", ")}
                          </Typography>
                        </CardContent>
                      </CardActionArea>
                      {c.status === "registration_open" && (isAthlete || isCoach) && (
                        <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
                          <Button
                            variant={isCoach || el?.ok ? "contained" : "outlined"}
                            component={RouterLink}
                            to={`/competitions/${c.id}`}
                            endIcon={<ArrowForwardIcon />}
                          >
                            {isCoach ? "Подать заявку за подопечного" : "Подать заявку"}
                          </Button>
                        </CardActions>
                      )}
                    </Card>
                  );
                })}
              </Stack>
              {data.total > PAGE_SIZE && (
                <Box sx={{ display: "flex", justifyContent: "center", mt: 3 }}>
                  <Pagination count={Math.ceil(data.total / PAGE_SIZE)} page={page} onChange={(_, p) => setPage(p)} color="primary" />
                </Box>
              )}
            </>
          )
        }
      </Async>
    </Box>
  );
}
