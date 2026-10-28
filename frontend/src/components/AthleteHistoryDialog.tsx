import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Link, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import type { History } from "../api/types";
import { fmtDate, fmtNum } from "../utils/format";
import { LEVEL_LABEL, RESULT_STATUS_LABEL } from "../utils/labels";
import { Async, DownloadButton, EmptyState, useGet } from "./common";

/** Сводка выступлений спортсмена: для тренера (подопечные) и федерации (реестр). */
export function AthleteHistoryDialog({ athlete: open, onClose }: { athlete: { id: number; full_name: string } | null; onClose: () => void }) {
  // последнего спортсмена держим, пока диалог доигрывает анимацию закрытия
  const [athlete, setAthlete] = useState(open);
  useEffect(() => {
    if (open !== null) setAthlete(open);
  }, [open]);
  const q = useGet<History>(`/athletes/${athlete?.id}/history`, undefined, { enabled: athlete !== null });
  return (
    <Dialog open={open !== null} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Выступления: {athlete?.full_name}</DialogTitle>
      <DialogContent>
        <Async q={q}>
          {(h) =>
            h.items.length === 0 ? (
              <EmptyState title="Выступлений пока нет" hint="Результаты появляются здесь после публикации протокола" />
            ) : (
              <>
                <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
                  <Chip label={`Стартов: ${h.total}`} />
                  <Chip color="warning" label={`Призовых мест: ${h.prizes}`} />
                  <Chip variant="outlined" label={`Побед: ${h.items.filter((i) => i.place === 1).length}`} />
                </Stack>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow><TableCell>Дата</TableCell><TableCell>Соревнование</TableCell><TableCell>Уровень</TableCell><TableCell align="right">Место</TableCell><TableCell align="right">Баллы</TableCell><TableCell>Протокол</TableCell></TableRow>
                    </TableHead>
                    <TableBody>
                      {h.items.map((i) => (
                        <TableRow key={i.result_id} sx={i.place && i.place <= 3 ? { bgcolor: "#FFF8E5" } : undefined}>
                          <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(i.start_date)}</TableCell>
                          <TableCell sx={{ minWidth: 220 }}>
                            <Link component={RouterLink} to={`/competitions/${i.competition_id}`} onClick={onClose}>{i.competition_title}</Link>
                            <Typography variant="caption" display="block" color="text.secondary">{i.discipline}</Typography>
                          </TableCell>
                          <TableCell>{LEVEL_LABEL[i.level]}</TableCell>
                          <TableCell align="right">
                            <Box component="b">{i.place ?? (RESULT_STATUS_LABEL[i.status as keyof typeof RESULT_STATUS_LABEL] ?? "–")}</Box>
                            {i.place && <Typography variant="caption" color="text.secondary"> из {i.participants}</Typography>}
                          </TableCell>
                          <TableCell align="right">{fmtNum(i.score)}</TableCell>
                          <TableCell>{i.protocol_number}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            )
          }
        </Async>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {athlete && <DownloadButton path={`/athletes/${athlete.id}/report/export`} label="Справка о выступлениях (.docx)" fallbackName="spravka.docx" />}
        <Button onClick={onClose}>Закрыть</Button>
      </DialogActions>
    </Dialog>
  );
}
