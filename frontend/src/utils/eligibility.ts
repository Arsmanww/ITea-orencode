import type { AgeGroup, AthleteProfile, Competition } from "../api/types";
import { ageOn } from "./format";

export interface Eligibility { ok: boolean; reasons: string[]; age: number }

/** Подсказка в интерфейсе. Окончательную проверку делает сервер при подаче заявки. */
export function ageFits(groups: AgeGroup[], birthDate: string, on: string): { ok: boolean; age: number } {
  const age = ageOn(birthDate, on);
  return { ok: groups.some((g) => g.min_age <= age && age <= g.max_age), age };
}

export function eligibility(comp: Competition, profile: AthleteProfile): Eligibility {
  const reasons: string[] = [];
  const { ok: ageOk, age } = ageFits(comp.age_groups, profile.user.birth_date, comp.start_date);
  if (!ageOk) {
    reasons.push(`Возраст на дату старта – ${age} лет, не входит в группы: ${comp.age_groups.map((g) => `${g.name} (${g.min_age}–${g.max_age})`).join(", ")}`);
  }
  if (!profile.enrollments.some((e) => e.discipline.id === comp.discipline.id)) {
    reasons.push(`Вы не занимаетесь дисциплиной «${comp.discipline.name}»`);
  }
  return { ok: reasons.length === 0, reasons, age };
}
