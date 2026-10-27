import { Autocomplete, Box, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";

import type { Paged, RegistryAthlete } from "../api/types";
import { useGet } from "./common";
import { capitalize } from "./home/parts";

/** Поиск спортсмена в реестре по ФИО (федерация и тренер). Запрос уходит после паузы в наборе. */
export function AthletePicker({
  value,
  onChange,
  disciplineId,
  label = "Спортсмен из реестра",
}: {
  value: RegistryAthlete | null;
  onChange: (a: RegistryAthlete | null) => void;
  disciplineId?: string;
  label?: string;
}) {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(input.trim()), 300);
    return () => clearTimeout(t);
  }, [input]);
  const res = useGet<Paged<RegistryAthlete>>("/registry/athletes", { q, discipline_id: disciplineId || undefined, limit: 15 }, { enabled: q.length >= 2 });
  return (
    <Autocomplete
      sx={{ minWidth: 280, flexGrow: 1 }}
      value={value}
      onChange={(_, v) => onChange(v)}
      inputValue={input}
      onInputChange={(_, v) => setInput(v)}
      options={q.length >= 2 ? res.data?.items ?? [] : []}
      filterOptions={(x) => x}
      getOptionLabel={(a) => a.full_name}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      loading={res.isFetching}
      noOptionsText={input.trim().length < 2 ? "Введите хотя бы 2 буквы фамилии или имени" : q !== input.trim() || res.isFetching ? "Ищем в реестре…" : "Никого не нашли"}
      loadingText="Ищем в реестре…"
      renderOption={({ key, ...props }, a) => (
        <Box component="li" key={key} {...props}>
          <Box>
            <Typography fontWeight={600}>{a.full_name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {a.age} лет{a.municipality ? ` · ${a.municipality}` : ""} · {a.disciplines.map((d) => capitalize(d.discipline.name.replace("Программирование ", ""))).join(", ")}
            </Typography>
          </Box>
        </Box>
      )}
      renderInput={(params) => <TextField {...params} label={label} />}
    />
  );
}
