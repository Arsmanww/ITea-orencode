import { Box, Button, Card, CardContent, LinearProgress, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { useState } from "react";

import type { Headcount, HeadcountRow } from "../api/types";
import { Async, DownloadButton, PageTitle, Section, useGet } from "../components/common";
import { BRAND } from "../theme";

function Dynamics({ title, rows, years }: { title: string; rows: HeadcountRow[]; years: number[] }) {
  return (
    <Section title={title}>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Показатель</TableCell>
              {years.map((y) => <TableCell key={y} align="right">{y}</TableCell>)}
              <TableCell align="right">Δ</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => {
              const first = r.counts[years[0]] ?? 0;
              const last = r.counts[years[years.length - 1]] ?? 0;
              return (
                <TableRow key={r.label}>
                  <TableCell>{r.label.replace("Программирование ", "")}{r.extra && r.extra !== "–" ? <Typography variant="caption" display="block" color="text.secondary">{r.extra}</Typography> : null}</TableCell>
                  {years.map((y) => <TableCell key={y} align="right">{r.counts[y] ?? 0}</TableCell>)}
                  <TableCell align="right" sx={{ color: last >= first ? "success.main" : "error.main", fontWeight: 700 }}>{last - first > 0 ? "+" : ""}{last - first}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Section>
  );
}

export function ReportsPage() {
  const [from, setFrom] = useState("2024");
  const [to, setTo] = useState(String(Math.max(new Date().getFullYear(), 2026)));
  const valid = Number(to) - Number(from) >= 1 && Number(to) - Number(from) <= 10;
  const q = useGet<Headcount>("/analytics/headcount", { year_from: from, year_to: to }, { enabled: valid });

  return (
    <Box>
      <PageTitle title="Отчёты и документы" subtitle="Выгрузки по заданным формам из данных платформы" />

      <Section title="Численность занимающихся спортивным программированием">
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Динамика по годам в разрезах муниципалитетов, организаций, дисциплин и возрастных групп. В .xlsx – отдельные листы с итогами, диаграммой и приростом.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField label="С года" type="number" value={from} onChange={(e) => setFrom(e.target.value)} sx={{ maxWidth: 160 }} slotProps={{ htmlInput: { min: 2000, max: 2100 } }} />
          <TextField label="По год" type="number" value={to} onChange={(e) => setTo(e.target.value)} sx={{ maxWidth: 160 }} slotProps={{ htmlInput: { min: 2000, max: 2100 } }} />
          <DownloadButton variant="contained" disabled={!valid} path="/analytics/headcount/export" query={{ year_from: from, year_to: to }} label="Выгрузить отчёт о численности (.xlsx)" fallbackName="headcount.xlsx" />
        </Stack>
        {!valid && <Typography color="error" variant="body2" sx={{ mt: 1 }}>Динамика строится минимум за два года (не более 11 лет).</Typography>}
      </Section>

      {valid && (
        <Async q={q}>
          {(d) => {
            const max = Math.max(...d.years.map((y) => d.total[y] ?? 0), 1);
            return (
              <>
                <Section title="Динамика численности">
                  <Stack spacing={1.5}>
                    {d.years.map((y) => (
                      <Box key={y}>
                        <Stack direction="row" justifyContent="space-between">
                          <Typography fontWeight={700}>{y}</Typography>
                          <Typography>{d.total[y]} занимающихся · новых {d.new[y]} · тренеров {d.coaches[y]} · судей {d.judges[y]}</Typography>
                        </Stack>
                        <LinearProgress variant="determinate" value={((d.total[y] ?? 0) / max) * 100} sx={{ height: 12, borderRadius: 6, bgcolor: "#E4EAF5", "& .MuiLinearProgress-bar": { bgcolor: BRAND.blue } }} />
                      </Box>
                    ))}
                  </Stack>
                </Section>
                <Dynamics title="По дисциплинам" rows={d.disciplines} years={d.years} />
                <Dynamics title="По возрастным группам" rows={d.age_groups} years={d.years} />
                <Dynamics title="По муниципалитетам" rows={d.municipalities} years={d.years} />
                <Dynamics title="По организациям" rows={d.organizations} years={d.years} />
              </>
            );
          }}
        </Async>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" }, gap: 2 }}>
        {[
          { t: "Протокол соревнования (.docx)", d: "Формируется автоматически после публикации протокола: титульный лист, все участники, судейская коллегия, подписи.", to: "/calendar", b: "Открыть календарь" },
          { t: "Проект приказа о сборной (.docx)", d: "Состав сборной формируется из рейтинга; проект приказа скачивается на вкладке «Сборные команды».", to: "/rating", b: "Открыть рейтинг" },
          { t: "Справка спортсмена (.docx)", d: "Список турниров, места и присвоенные разряды. Доступна в кабинете спортсмена, тренера и в рейтинге.", to: "/rating", b: "Рейтинг → «Справка»" },
        ].map((c) => (
          <Card key={c.t}>
            <CardContent>
              <Typography fontWeight={700} sx={{ mb: 0.5 }}>{c.t}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, minHeight: 60 }}>{c.d}</Typography>
              <Button component={RouterLink} to={c.to}>{c.b}</Button>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  );
}
