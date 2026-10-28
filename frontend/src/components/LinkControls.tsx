import HistoryIcon from "@mui/icons-material/History";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import { Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, ListItemText, Menu, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { LinkHistory, LinkStatus } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { LINK_STATUS_LABEL } from "../utils/labels";
import { Async, EmptyState, FormDialog, useGet, useInvalidate } from "./common";
import { useToast } from "./Toast";

const STATUS_COLOR: Record<LinkStatus, "warning" | "success" | "default" | "error"> = { pending: "warning", active: "success", suspended: "default", ended: "error" };

const ACTIONS: Record<LinkStatus, { to: LinkStatus; label: string; color: "warning" | "error" | "success" }[]> = {
  pending: [{ to: "ended", label: "Отозвать", color: "error" }],
  active: [{ to: "suspended", label: "Приостановить", color: "warning" }, { to: "ended", label: "Завершить", color: "error" }],
  suspended: [{ to: "active", label: "Возобновить", color: "success" }, { to: "ended", label: "Завершить", color: "error" }],
  ended: [],
};

export function LinkStatusChip({ status }: { status: LinkStatus }) {
  return <Chip size="small" color={STATUS_COLOR[status]} variant={status === "suspended" ? "outlined" : "filled"} label={LINK_STATUS_LABEL[status]} />;
}

/** Смена статуса связи тренер–спортсмен и история изменений. side – кто нажимает; menu – компактно, в меню «⋯». */
export function LinkActions({ linkId, status, who, side, menu = false }: { linkId: number; status: LinkStatus; who: string; side: "coach" | "athlete"; menu?: boolean }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const toast = useToast();
  const invalidate = useInvalidate();
  const [target, setTarget] = useState<{ to: LinkStatus; label: string } | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState(false);
  const change = useMutation({
    mutationFn: () => api(`/links/${linkId}`, { method: "PATCH", body: { status: target?.to, comment: comment.trim() || null } }),
    onSuccess: async () => {
      toast.success(`Связь: ${LINK_STATUS_LABEL[target!.to].toLowerCase()}. Вторая сторона уведомлена`);
      setTarget(null);
      setComment("");
      await invalidate("/coach", "/athlete", "/athletes", "/links");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Ошибка"),
  });
  const actions = ACTIONS[status].filter((a) => side === "coach" || status !== "pending");
  return (
    <>
      {menu ? (
        <>
          <IconButton size="small" aria-label={`Связь: ${who}`} onClick={(e) => setAnchor(e.currentTarget)}><MoreVertIcon fontSize="small" /></IconButton>
          <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
            {actions.map((a) => (
              <MenuItem key={a.to} onClick={() => { setAnchor(null); setError(null); setTarget(a); }}>
                <ListItemText slotProps={{ primary: { color: `${a.color}.main` } }}>{a.label} связь</ListItemText>
              </MenuItem>
            ))}
            <MenuItem onClick={() => { setAnchor(null); setHistory(true); }}><HistoryIcon fontSize="small" sx={{ mr: 1 }} />История изменений</MenuItem>
          </Menu>
        </>
      ) : (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap justifyContent="flex-end">
          {actions.map((a) => (
            <Button key={a.to} size="small" color={a.color} onClick={() => { setError(null); setTarget(a); }}>{a.label}</Button>
          ))}
          <Button size="small" startIcon={<HistoryIcon />} onClick={() => setHistory(true)}>История</Button>
        </Stack>
      )}
      <FormDialog open={target !== null} title={`${target?.label ?? ""} связь: ${who}`} onClose={() => setTarget(null)} onSubmit={() => change.mutate()}
        submitLabel={target?.label} busy={change.isPending} error={error}>
        <Typography variant="body2" color="text.secondary">
          {target?.to === "suspended" && "Пока связь приостановлена, тренер не подаёт заявки за спортсмена; возобновить можно в любой момент."}
          {target?.to === "ended" && "Завершённую связь вернуть нельзя – понадобится новый запрос на привязку."}
          {target?.to === "active" && "Связь снова станет активной: тренер сможет подавать заявки за спортсмена."}
        </Typography>
        <TextField label="Комментарий (попадёт в историю)" value={comment} onChange={(e) => setComment(e.target.value)} multiline minRows={2} />
      </FormDialog>
      <LinkHistoryDialog linkId={history ? linkId : null} onClose={() => setHistory(false)} />
    </>
  );
}

function LinkHistoryDialog({ linkId, onClose }: { linkId: number | null; onClose: () => void }) {
  // последний открытый id держим, пока диалог доигрывает анимацию закрытия
  const [shown, setShown] = useState(linkId);
  useEffect(() => {
    if (linkId !== null) setShown(linkId);
  }, [linkId]);
  const q = useGet<LinkHistory[]>(`/links/${shown}/history`, undefined, { enabled: shown !== null });
  return (
    <Dialog open={linkId !== null} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>История связи тренер–спортсмен</DialogTitle>
      <DialogContent>
        <Async q={q}>
          {(items) =>
            items.length === 0 ? (
              <EmptyState title="Изменений нет" />
            ) : (
              <Stack spacing={1.5}>
                {items.map((h, i) => (
                  <Stack key={i} spacing={0.5} sx={{ pl: 1.5, borderLeft: "3px solid", borderColor: "primary.light" }}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                      {h.old_status && <><LinkStatusChip status={h.old_status} /><Typography>→</Typography></>}
                      <LinkStatusChip status={h.new_status} />
                    </Stack>
                    <Typography variant="body2">{h.changed_by.full_name} · {fmtDateTime(h.changed_at)}</Typography>
                    {h.comment && <Typography variant="body2" color="text.secondary">«{h.comment}»</Typography>}
                  </Stack>
                ))}
              </Stack>
            )
          }
        </Async>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Закрыть</Button></DialogActions>
    </Dialog>
  );
}
