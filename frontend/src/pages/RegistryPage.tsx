import SearchIcon from "@mui/icons-material/Search";
import {
  Box,
  Button,
  Chip,
  InputAdornment,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import type { AgeGroup, Organization, Paged, Ref, RegistryAthlete, RegistryCoach, RegistryJudge, RegistryOrganization } from "../api/types";
import { AthleteHistoryDialog } from "../components/AthleteHistoryDialog";
import { Async, EmptyState, PageTitle, useGet, useTabs } from "../components/common";
import { capitalize } from "../components/home/parts";
import { fmtDate } from "../utils/format";
import { ORG_TYPE_LABEL, STAGE_LABEL } from "../utils/labels";

const PAGE = 25;
type Filters = Record<string, string>;

/** Строка поиска с задержкой: запрос уходит, когда пользователь перестал печатать. */
function useDebounced(value: string, ms = 350) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: ReactNode }) {
  return (
    <TextField select size="small" label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <MenuItem value="">Все</MenuItem>
      {children}
    </TextField>
  );
}

function shortDiscipline(name: string) {
  return capitalize(name.replace("Программирование ", ""));
}

/** Общая оболочка вкладки: поиск, фильтры, таблица, пагинация и пустое состояние.
 * Поиск, фильтры и страница живут в адресной строке (с префиксом на вкладку) – кнопка «Назад»
 * браузера возвращает ровно то, что было отфильтровано, а не пустую форму. */
function RegistryTab<T>({
  prefix,
  path,
  filters,
  search,
  hint,
  head,
  row,
}: {
  prefix: string;
  path: string;
  filters: (f: Filters, set: (k: string) => (v: string) => void) => ReactNode;
  search: string;
  hint: string;
  head: ReactNode;
  row: (item: T) => ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const pk = (k: string) => `${prefix}_${k}`;
  const f: Filters = {};
  for (const [key, value] of params) {
    if (key.startsWith(`${prefix}_`) && key !== pk("q") && key !== pk("page")) f[key.slice(prefix.length + 1)] = value;
  }
  const page = Math.max(1, Number(params.get(pk("page"))) || 1);

  const [q, setQ] = useState(params.get(pk("q")) ?? "");
  const dq = useDebounced(q);
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return; }
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (dq.trim()) next.set(pk("q"), dq.trim()); else next.delete(pk("q"));
      next.set(pk("page"), "1");
      return next;
    }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq]);

  const set = (k: string) => (v: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v) next.set(pk(k), v); else next.delete(pk(k));
      next.set(pk("page"), "1");
      return next;
    }, { replace: true });
  };
  const setPage = (p: number) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set(pk("page"), String(p));
      return next;
    }, { replace: true });
  };
  const reset = () => {
    setQ("");
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of [...next.keys()]) if (key.startsWith(`${prefix}_`)) next.delete(key);
      return next;
    }, { replace: true });
  };

  const data = useGet<Paged<T>>(path, { ...f, q: dq.trim(), limit: PAGE, offset: (page - 1) * PAGE });
  const active = Object.values(f).some(Boolean) || dq.trim();
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)", lg: "minmax(240px, 2fr) repeat(auto-fit, minmax(150px, 1fr))" }, gap: 1.5, mb: 2, alignItems: "center" }}>
        <TextField
          size="small"
          placeholder={search}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          sx={{ gridColumn: { sm: "span 2", md: "span 3", lg: "auto" } }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }}
        />
        {filters(f, set)}
        {active && <Button onClick={reset} sx={{ justifySelf: "start" }}>Сбросить</Button>}
      </Box>
      <Async q={data}>
        {(d) =>
          d.items.length === 0 ? (
            <EmptyState title="Никого не нашли" hint={active ? "Измените условия поиска или сбросьте фильтры" : hint} />
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Найдено: {d.total}</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead><TableRow>{head}</TableRow></TableHead>
                  <TableBody>{d.items.map(row)}</TableBody>
                </Table>
              </TableContainer>
              {d.total > PAGE && (
                <Stack alignItems="center" sx={{ mt: 2 }}>
                  <Pagination count={Math.ceil(d.total / PAGE)} page={page} onChange={(_, p) => setPage(p)} color="primary" />
                </Stack>
              )}
            </>
          )
        }
      </Async>
    </Paper>
  );
}

function useRefs() {
  return {
    disciplines: useGet<Ref[]>("/reference/disciplines").data ?? [],
    organizations: useGet<Organization[]>("/reference/organizations").data ?? [],
    municipalities: useGet<Ref[]>("/reference/municipalities").data ?? [],
    ranks: useGet<Ref[]>("/reference/ranks").data ?? [],
    ageGroups: useGet<AgeGroup[]>("/reference/age-groups").data ?? [],
    categories: useGet<Ref[]>("/reference/judge-categories").data ?? [],
  };
}

function AthletesTab() {
  const r = useRefs();
  const [open, setOpen] = useState<RegistryAthlete | null>(null);
  return (
    <>
      <RegistryTab<RegistryAthlete>
        prefix="a"
        path="/registry/athletes"
        search="ФИО или email спортсмена"
        hint="В реестре пока нет спортсменов"
        filters={(f, set) => (
          <>
            <Select label="Дисциплина" value={f.discipline_id ?? ""} onChange={set("discipline_id")}>
              {r.disciplines.map((d) => <MenuItem key={d.id} value={String(d.id)}>{shortDiscipline(d.name)}</MenuItem>)}
            </Select>
            <Select label="Организация" value={f.organization_id ?? ""} onChange={set("organization_id")}>
              <MenuItem value="0">Без организации</MenuItem>
              {r.organizations.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.name}</MenuItem>)}
            </Select>
            <Select label="Разряд" value={f.rank_id ?? ""} onChange={set("rank_id")}>
              {r.ranks.map((x) => <MenuItem key={x.id} value={String(x.id)}>{x.name}</MenuItem>)}
            </Select>
            <Select label="Возраст" value={f.age_group_id ?? ""} onChange={set("age_group_id")}>
              {r.ageGroups.map((g) => <MenuItem key={g.id} value={String(g.id)}>{g.name}</MenuItem>)}
            </Select>
            <Select label="Муниципалитет" value={f.municipality_id ?? ""} onChange={set("municipality_id")}>
              {r.municipalities.map((m) => <MenuItem key={m.id} value={String(m.id)}>{m.name}</MenuItem>)}
            </Select>
          </>
        )}
        head={<><TableCell>Спортсмен</TableCell><TableCell>Возраст</TableCell><TableCell>Муниципалитет</TableCell><TableCell>Дисциплины, организация, разряд, тренер</TableCell><TableCell align="right" /></>}
        row={(a) => (
          <TableRow key={a.id} hover>
            <TableCell sx={{ minWidth: 200 }}>
              <Typography fontWeight={600}>{a.full_name}</Typography>
              <Typography variant="caption" color="text.secondary">{fmtDate(a.birth_date)}{a.email ? ` · ${a.email}` : ""}</Typography>
            </TableCell>
            <TableCell>{a.age}</TableCell>
            <TableCell>{a.municipality ?? "–"}</TableCell>
            <TableCell sx={{ minWidth: 320 }}>
              <Stack spacing={0.75}>
                {a.disciplines.map((d) => (
                  <Box key={d.discipline.id}>
                    <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                      <Typography variant="body2" fontWeight={600}>{shortDiscipline(d.discipline.name)}</Typography>
                      {d.rank && <Chip size="small" color="primary" variant="outlined" label={d.rank} />}
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      {d.organization ?? "без организации"} · с {new Date(d.since).getFullYear()} г.{d.training_stage ? ` · ${STAGE_LABEL[d.training_stage] ?? d.training_stage}` : ""}{d.coach ? ` · тренер ${d.coach}` : ""}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </TableCell>
            <TableCell align="right"><Button size="small" onClick={() => setOpen(a)}>Выступления</Button></TableCell>
          </TableRow>
        )}
      />
      <AthleteHistoryDialog athlete={open} onClose={() => setOpen(null)} />
    </>
  );
}

function CoachesTab() {
  const r = useRefs();
  return (
    <RegistryTab<RegistryCoach>
      prefix="c"
      path="/registry/coaches"
      search="ФИО или email тренера"
      hint="Тренеров пока нет"
      filters={(f, set) => (
        <>
          <Select label="Дисциплина" value={f.discipline_id ?? ""} onChange={set("discipline_id")}>
            {r.disciplines.map((d) => <MenuItem key={d.id} value={String(d.id)}>{shortDiscipline(d.name)}</MenuItem>)}
          </Select>
          <Select label="Организация" value={f.organization_id ?? ""} onChange={set("organization_id")}>
            {r.organizations.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.name}</MenuItem>)}
          </Select>
          <Select label="Муниципалитет" value={f.municipality_id ?? ""} onChange={set("municipality_id")}>
            {r.municipalities.map((m) => <MenuItem key={m.id} value={String(m.id)}>{m.name}</MenuItem>)}
          </Select>
        </>
      )}
      head={<><TableCell>Тренер</TableCell><TableCell>Организация</TableCell><TableCell>Муниципалитет</TableCell><TableCell>Дисциплины</TableCell><TableCell align="right">Подопечных</TableCell></>}
      row={(c) => (
        <TableRow key={c.id} hover>
          <TableCell sx={{ fontWeight: 600 }}>{c.full_name}{c.is_judge && <Chip size="small" variant="outlined" label="также судья" sx={{ ml: 1 }} />}</TableCell>
          <TableCell>{c.organization ?? "–"}</TableCell>
          <TableCell>{c.municipality ?? "–"}</TableCell>
          <TableCell>{c.disciplines.map(shortDiscipline).join(", ") || "–"}</TableCell>
          <TableCell align="right">{c.athletes}</TableCell>
        </TableRow>
      )}
    />
  );
}

function JudgesTab() {
  const r = useRefs();
  return (
    <RegistryTab<RegistryJudge>
      prefix="j"
      path="/registry/judges"
      search="ФИО или email судьи"
      hint="Судей пока нет"
      filters={(f, set) => (
        <>
          <Select label="Категория" value={f.category_id ?? ""} onChange={set("category_id")}>
            {r.categories.map((c) => <MenuItem key={c.id} value={String(c.id)}>{c.name}</MenuItem>)}
          </Select>
          <Select label="Организация" value={f.organization_id ?? ""} onChange={set("organization_id")}>
            {r.organizations.map((o) => <MenuItem key={o.id} value={String(o.id)}>{o.name}</MenuItem>)}
          </Select>
          <Select label="Муниципалитет" value={f.municipality_id ?? ""} onChange={set("municipality_id")}>
            {r.municipalities.map((m) => <MenuItem key={m.id} value={String(m.id)}>{m.name}</MenuItem>)}
          </Select>
        </>
      )}
      head={<><TableCell>Судья</TableCell><TableCell>Категория</TableCell><TableCell>Действует до</TableCell><TableCell>Организация</TableCell><TableCell align="right">Назначений</TableCell></>}
      row={(j) => (
        <TableRow key={j.id} hover>
          <TableCell sx={{ fontWeight: 600 }}>{j.full_name}<Typography variant="caption" display="block" color="text.secondary">{j.municipality ?? ""}</Typography></TableCell>
          <TableCell>{j.category ?? "не присвоена"}</TableCell>
          <TableCell>{j.valid_until ? <Chip size="small" color={j.expired ? "error" : "default"} label={j.expired ? `истекла ${fmtDate(j.valid_until)}` : fmtDate(j.valid_until)} /> : "–"}</TableCell>
          <TableCell>{j.organization ?? "–"}</TableCell>
          <TableCell align="right">{j.assignments}</TableCell>
        </TableRow>
      )}
    />
  );
}

function OrganizationsTab() {
  const r = useRefs();
  return (
    <RegistryTab<RegistryOrganization>
      prefix="o"
      path="/registry/organizations"
      search="Название организации"
      hint="Организаций пока нет"
      filters={(f, set) => (
        <>
          <Select label="Тип" value={f.type ?? ""} onChange={set("type")}>
            {Object.entries(ORG_TYPE_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </Select>
          <Select label="Дисциплина" value={f.discipline_id ?? ""} onChange={set("discipline_id")}>
            {r.disciplines.map((d) => <MenuItem key={d.id} value={String(d.id)}>{shortDiscipline(d.name)}</MenuItem>)}
          </Select>
          <Select label="Муниципалитет" value={f.municipality_id ?? ""} onChange={set("municipality_id")}>
            {r.municipalities.map((m) => <MenuItem key={m.id} value={String(m.id)}>{m.name}</MenuItem>)}
          </Select>
        </>
      )}
      head={<><TableCell>Организация</TableCell><TableCell>Тип</TableCell><TableCell>Муниципалитет</TableCell><TableCell>Дисциплины</TableCell><TableCell align="right">Занимающихся</TableCell><TableCell align="right">Тренеров</TableCell></>}
      row={(o) => (
        <TableRow key={o.id} hover>
          <TableCell sx={{ fontWeight: 600, minWidth: 220 }}>{o.name}<Typography variant="caption" display="block" color="text.secondary">{o.address ?? ""}</Typography></TableCell>
          <TableCell>{ORG_TYPE_LABEL[o.type] ?? o.type}</TableCell>
          <TableCell>{o.municipality}</TableCell>
          <TableCell sx={{ minWidth: 200 }}>{o.disciplines.map(shortDiscipline).join(", ") || "–"}</TableCell>
          <TableCell align="right">{o.athletes}</TableCell>
          <TableCell align="right">{o.coaches}</TableCell>
        </TableRow>
      )}
    />
  );
}

export function RegistryPage() {
  const { tab, onChange } = useTabs(0, "tab");
  return (
    <Box>
      <PageTitle title="Реестр" subtitle="Спортсмены, тренеры, судьи и организации: поиск и фильтры по дисциплине, организации, разряду, возрасту и муниципалитету" />
      <Tabs value={tab} onChange={onChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
        <Tab label="Спортсмены" />
        <Tab label="Тренеры" />
        <Tab label="Судьи" />
        <Tab label="Организации" />
      </Tabs>
      {tab === 0 && <AthletesTab />}
      {tab === 1 && <CoachesTab />}
      {tab === 2 && <JudgesTab />}
      {tab === 3 && <OrganizationsTab />}
    </Box>
  );
}
