import NotificationsIcon from "@mui/icons-material/Notifications";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";
import { Badge, Box, Button, Divider, IconButton, Popover, Stack, Tooltip, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { NotificationItem, NotificationList } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { useGet, useInvalidate } from "./common";
import { useToast } from "./Toast";

const KIND_TARGET: Record<string, string> = {
  competition_application: "/calendar",
  protocol: "/calendar",
  rank_request: "/athlete",
  coach_athlete_link: "/athlete",
};

export function NotificationsBell() {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const navigate = useNavigate();
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<NotificationList>("/notifications", { limit: 20 }, { refetchInterval: 30_000 });
  const unread = q.data?.unread ?? 0;

  const markRead = useMutation({
    mutationFn: (id: number) => api(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => invalidate("/notifications"),
    onError: toast.error,
  });
  const markAll = useMutation({
    mutationFn: () => api("/notifications/read-all", { method: "POST" }),
    onSuccess: () => invalidate("/notifications"),
    onError: toast.error,
  });

  const open = (n: NotificationItem) => {
    if (!n.read_at) markRead.mutate(n.id);
    setAnchor(null);
    if (n.entity_type === "competition" && n.entity_id) navigate(`/competitions/${n.entity_id}`);
    else if (n.entity_type && KIND_TARGET[n.entity_type]) navigate(KIND_TARGET[n.entity_type]);
  };

  return (
    <>
      <Tooltip title="Уведомления">
        <IconButton color="inherit" onClick={(e) => setAnchor(e.currentTarget)} aria-label="Уведомления">
          <Badge badgeContent={unread} color="secondary" max={99}>
            {unread ? <NotificationsIcon /> : <NotificationsNoneIcon />}
          </Badge>
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: { width: { xs: "calc(100vw - 24px)", sm: 400 }, maxHeight: 520 } } }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1.5 }}>
          <Typography fontWeight={700}>Уведомления{unread ? ` (${unread})` : ""}</Typography>
          <Button size="small" disabled={!unread} onClick={() => markAll.mutate()}>
            Прочитать все
          </Button>
        </Stack>
        <Divider />
        {q.data && q.data.items.length === 0 && (
          <Typography color="text.secondary" sx={{ p: 3, textAlign: "center" }}>
            Новых событий нет
          </Typography>
        )}
        {q.data?.items.map((n) => (
          <Box
            key={n.id}
            onClick={() => open(n)}
            sx={{ px: 2, py: 1.25, cursor: "pointer", bgcolor: n.read_at ? "transparent" : "#EEF3FC", borderBottom: "1px solid", borderColor: "divider", "&:hover": { bgcolor: "#E4ECFA" } }}
          >
            <Typography variant="body2" fontWeight={n.read_at ? 500 : 700}>
              {n.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {n.body}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {fmtDateTime(n.created_at)}
            </Typography>
          </Box>
        ))}
      </Popover>
    </>
  );
}
