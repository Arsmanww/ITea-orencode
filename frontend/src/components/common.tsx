import DownloadIcon from "@mui/icons-material/Download";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
  type ButtonProps,
  type TextFieldProps,
} from "@mui/material";
import { useQuery, useQueryClient, type QueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useCallback, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, api, download } from "../api/client";
import type { ApplicationStatus, CompetitionStatus, RequestStatus, ValidityInfo } from "../api/types";
import { daysText, fmtDate } from "../utils/format";
import {
  APP_STATUS_COLOR,
  APP_STATUS_LABEL,
  COMP_STATUS_COLOR,
  COMP_STATUS_LABEL,
  FORMAT_LABEL,
  REQ_STATUS_COLOR,
  REQ_STATUS_LABEL,
} from "../utils/labels";
import { useToast } from "./Toast";

type Query = Record<string, string | number | boolean | null | undefined>;

/** GET-запрос с кэшем. Ключ = [путь, параметры], поэтому invalidate(qc, "/путь") сбрасывает все варианты. */
export function useGet<T>(path: string, query?: Query, options: { enabled?: boolean; refetchInterval?: number; retry?: boolean } = {}) {
  return useQuery<T, ApiError>({
    queryKey: [path, query ?? {}],
    queryFn: () => api<T>(path, { query }),
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval,
    retry: options.retry ?? false,
  });
}

export function invalidate(qc: QueryClient, ...paths: string[]) {
  return Promise.all(paths.map((p) => qc.invalidateQueries({ predicate: (q) => typeof q.queryKey[0] === "string" && (q.queryKey[0] as string).startsWith(p) })));
}

export function useInvalidate() {
  const qc = useQueryClient();
  return (...paths: string[]) => invalidate(qc, ...paths);
}

/** Возвращает пользователя к началу страницы: контент сменился, старая позиция прокрутки бессмысленна. */
export function scrollToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
}

/** Состояние вкладок: при переключении страница всегда показывается с начала.
 * С urlKey активная вкладка хранится в адресной строке – кнопка «Назад» браузера её восстанавливает. */
export function useTabs(initial = 0, urlKey?: string) {
  const [params, setParams] = useSearchParams();
  const [localTab, setLocalTab] = useState(initial);
  const urlTab = urlKey ? Number(params.get(urlKey)) : NaN;
  const tab = urlKey && Number.isInteger(urlTab) ? urlTab : localTab;
  const select = useCallback((value: number) => {
    scrollToTop();
    if (urlKey) {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set(urlKey, String(value));
        return next;
      }, { replace: true });
    } else {
      setLocalTab(value);
    }
  }, [urlKey, setParams]);
  return { tab, select, onChange: useCallback((_: unknown, value: number) => select(value), [select]) };
}

export function Loading({ label = "Загрузка…" }: { label?: string }) {
  return (
    <Stack alignItems="center" spacing={1.5} sx={{ py: 6 }}>
      <CircularProgress size={32} />
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <Alert severity="error" sx={{ my: 2 }}>
      {error instanceof Error ? error.message : "Не удалось загрузить данные"}
    </Alert>
  );
}

/** Показывает загрузку/ошибку, а при успехе отдаёт данные в render-функцию. */
export function Async<T>({ q, children }: { q: UseQueryResult<T, ApiError>; children: (data: T) => ReactNode }) {
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  // запрос выключен (например, диалог закрывается) – данных нет, рисовать нечего
  if (q.data === undefined) return null;
  return <>{children(q.data)}</>;
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 4, textAlign: "center", borderStyle: "dashed" }}>
      <Typography fontWeight={700}>{title}</Typography>
      {hint && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {hint}
        </Typography>
      )}
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Paper>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} spacing={1.5} sx={{ mb: 3 }}>
      <Box>
        <Typography variant="h4" component="h1" sx={{ fontSize: { xs: "1.5rem", sm: "2rem" } }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>{actions}</Stack>}
    </Stack>
  );
}

export function Section({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, mb: 3 }}>
      {(title || actions) && (
        <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
          {title && <Typography variant="h6">{title}</Typography>}
          {actions}
        </Stack>
      )}
      {children}
    </Paper>
  );
}

export function CompStatusChip({ status }: { status: CompetitionStatus }) {
  return <Chip size="small" label={COMP_STATUS_LABEL[status]} color={COMP_STATUS_COLOR[status]} variant={status === "finished" ? "outlined" : "filled"} />;
}
export function FormatChip({ format }: { format: "online" | "offline" | "mixed" }) {
  return <Chip size="small" label={FORMAT_LABEL[format]} variant="outlined" color={format === "offline" ? "secondary" : "primary"} />;
}
export function AppStatusChip({ status }: { status: ApplicationStatus }) {
  return <Chip size="small" label={APP_STATUS_LABEL[status]} color={APP_STATUS_COLOR[status]} />;
}
export function ReqStatusChip({ status }: { status: RequestStatus }) {
  return <Chip size="small" label={REQ_STATUS_LABEL[status]} color={REQ_STATUS_COLOR[status]} />;
}

/** Плашка о сроке действия разряда или категории; молчит, если срок не поджимает. */
export function ValidityAlert({ info, what }: { info: ValidityInfo | null | undefined; what: string }) {
  if (!info || !info.warning) return null;
  return (
    <Alert severity={info.expired ? "error" : "warning"} sx={{ mb: 2 }}>
      {what} «{info.name}»: {daysText(info.days_left)} (действует до {fmtDate(info.valid_until)}).
      {info.expired ? " Подайте заявку на подтверждение." : " Подайте заявку на подтверждение заранее."}
    </Alert>
  );
}

export function DownloadButton({
  path,
  query,
  label,
  fallbackName,
  ...rest
}: { path: string; query?: Query; label: string; fallbackName?: string } & Omit<ButtonProps, "onClick" | "children">) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <DownloadIcon />}
      disabled={busy || rest.disabled}
      variant="outlined"
      {...rest}
      onClick={async () => {
        setBusy(true);
        try {
          await download(path, query, fallbackName);
        } catch (e) {
          toast.error(e);
        } finally {
          setBusy(false);
        }
      }}
    >
      {label}
    </Button>
  );
}

export function DateField(props: TextFieldProps) {
  return <TextField type="date" {...props} slotProps={{ ...props.slotProps, inputLabel: { shrink: true } }} />;
}
export function DateTimeField(props: TextFieldProps) {
  return <TextField type="datetime-local" {...props} slotProps={{ ...props.slotProps, inputLabel: { shrink: true } }} />;
}

/** Диалог с формой: сам показывает ошибку сервера и блокирует кнопку на время запроса. */
export function FormDialog({
  open,
  title,
  onClose,
  onSubmit,
  submitLabel = "Отправить",
  submitDisabled,
  busy,
  error,
  children,
  maxWidth = "sm",
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onSubmit: () => void;
  submitLabel?: string;
  submitDisabled?: boolean;
  busy?: boolean;
  error?: string | null;
  children: ReactNode;
  maxWidth?: "xs" | "sm" | "md";
}) {
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth={maxWidth}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          {children}
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>
          Отмена
        </Button>
        <Button variant="contained" onClick={onSubmit} disabled={busy || submitDisabled}>
          {busy ? "Отправка…" : submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Минимальный вывод текста с абзацами и нумерованными пунктами. */
export function MiniText({ text, color }: { text: string; color?: string }) {
  return (
    <>
      {text.split(/\n\s*\n/).map((p, i) => (
        <Typography key={i} sx={{ mb: 1.5, whiteSpace: "pre-line", color }}>
          {p}
        </Typography>
      ))}
    </>
  );
}

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "200px 1fr" }, columnGap: 2, rowGap: { xs: 0.5, sm: 1 } }}>
      {items.map(([k, v]) => (
        <Box key={k} sx={{ display: "contents" }}>
          <Typography variant="body2" color="text.secondary" sx={{ mt: { xs: 1, sm: 0 } }}>
            {k}
          </Typography>
          <Typography component="div">{v ?? "–"}</Typography>
        </Box>
      ))}
    </Box>
  );
}
