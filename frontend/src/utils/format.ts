export function fmtDate(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "–";
  return `${d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })} ${d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
}

export function fmtPeriod(from: string, to: string): string {
  return from === to ? fmtDate(from) : `${fmtDate(from)} – ${fmtDate(to)}`;
}

/** "700.00" → "700", "86.50" → "86,5" */
export function fmtNum(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

export function fmtTime(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const total = Number(value);
  if (Number.isNaN(total)) return "–";
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const frac = total - Math.floor(total);
  const tail = frac > 0.0005 ? `.${String(Math.round(frac * 1000)).padStart(3, "0")}` : "";
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}${tail}` : `${m}:${String(s).padStart(2, "0")}${tail}`;
}

export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

export function ageOn(birth: string, on: string): number {
  const b = new Date(`${birth}T00:00:00`);
  const d = new Date(`${on}T00:00:00`);
  let age = d.getFullYear() - b.getFullYear();
  if (d.getMonth() < b.getMonth() || (d.getMonth() === b.getMonth() && d.getDate() < b.getDate())) age -= 1;
  return age;
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Значение <input type="datetime-local"> → ISO со смещением Оренбурга (+05:00). */
export function localToIso(value: string): string | null {
  return value ? `${value.length === 16 ? `${value}:00` : value}+05:00` : null;
}

export function daysText(days: number | null): string {
  if (days === null) return "бессрочно";
  if (days < 0) return `истёк ${Math.abs(days)} ${plural(Math.abs(days), ["день", "дня", "дней"])} назад`;
  if (days === 0) return "истекает сегодня";
  return `осталось ${days} ${plural(days, ["день", "дня", "дней"])}`;
}
