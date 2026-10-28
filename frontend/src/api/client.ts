const BASE = "/api/v1";
const TOKEN_KEY = "fsp_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let token: string | null = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export const getToken = () => token;

export function setToken(value: string | null) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* хранилище недоступно – работаем только в памяти */
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query) {
  const params = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

/** Превращает ответ об ошибке FastAPI в понятный текст. */
function errorMessage(status: number, data: unknown): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { msg?: string; loc?: (string | number)[] }) => {
        const field = d.loc && d.loc.length > 1 ? `${d.loc.slice(1).join(".")}: ` : "";
        return field + (d.msg ?? "").replace(/^Value error, /, "");
      })
      .join("; ");
  }
  if (status === 401) return "Требуется вход в систему";
  if (status === 403) return "Недостаточно прав для этого действия";
  if (status >= 500) return "Ошибка сервера, попробуйте позже";
  return `Ошибка запроса (${status})`;
}

async function parse(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

function handleUnauthorized(path: string, status: number) {
  if (status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/register")) {
    setToken(null);
    window.dispatchEvent(new Event("fsp-auth-expired"));
  }
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; query?: Query; form?: FormData } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, options.query), { method: options.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (!res.ok) {
    handleUnauthorized(path, res.status);
    throw new ApiError(res.status, errorMessage(res.status, await parse(res)));
  }
  if (res.status === 204) return undefined as T;
  return (await parse(res)) as T;
}

/** Скачивание файла (.docx, .xlsx) с авторизацией. Имя берётся из Content-Disposition. */
export async function download(path: string, query?: Query, fallbackName = "document"): Promise<void> {
  const res = await fetch(buildUrl(path, query), { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    handleUnauthorized(path, res.status);
    throw new ApiError(res.status, errorMessage(res.status, await parse(res)));
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  const plain = /filename="([^"]+)"/i.exec(disposition);
  const name = utf8 ? decodeURIComponent(utf8[1]) : plain ? plain[1] : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
