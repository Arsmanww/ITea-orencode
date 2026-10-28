import type {
  ApplicationStatus,
  CalendarPlan,
  CompetitionLevel,
  CompetitionStatus,
  LinkStatus,
  RatingTier,
  RequestKind,
  RequestStatus,
  Role,
} from "../api/types";

export const ROLE_LABEL: Record<Role, string> = {
  federation: "Федерация",
  athlete: "Спортсмен",
  coach: "Тренер",
  judge: "Судья",
  ministry: "Министерство",
};
export const ROLE_HOME: Record<Role, string> = {
  federation: "/federation",
  athlete: "/athlete",
  coach: "/coach",
  judge: "/judge",
  ministry: "/calendar",
};
export const LEVEL_LABEL: Record<CompetitionLevel, string> = {
  regional: "Региональное",
  interregional: "Межрегиональное",
  all_russian: "Всероссийское",
};
export const TIER_LABEL: Record<RatingTier, string> = {
  russia_championship: "Чемпионат России",
  russia_first: "Первенство России",
  interregional: "Межрегиональные",
  regional: "Региональные",
};
export const PLAN_LABEL: Record<CalendarPlan, string> = {
  none: "Вне плана",
  ekp_minsport: "ЕКП Минспорта России",
  oren_regional: "План Оренбургской области",
};
export const FORMAT_LABEL = { online: "Онлайн", offline: "Очно", mixed: "Онлайн + очно" } as const;
export const STAGE_FORMAT_LABEL = { online: "Онлайн", offline: "Очно" } as const;

export const COMP_STATUS_LABEL: Record<CompetitionStatus, string> = {
  draft: "Черновик",
  published: "Опубликовано",
  registration_open: "Приём заявок",
  registration_closed: "Приём закрыт",
  in_progress: "Проходит",
  finished: "Завершено",
  cancelled: "Отменено",
};
export const COMP_STATUS_COLOR: Record<CompetitionStatus, "default" | "primary" | "success" | "warning" | "error" | "info" | "secondary"> = {
  draft: "default",
  published: "info",
  registration_open: "success",
  registration_closed: "warning",
  in_progress: "primary",
  finished: "default",
  cancelled: "error",
};
export const APP_STATUS_LABEL: Record<ApplicationStatus, string> = {
  pending: "На модерации",
  approved: "Одобрена",
  rejected: "Отклонена",
  withdrawn: "Отозвана",
};
export const APP_STATUS_COLOR: Record<ApplicationStatus, "warning" | "success" | "error" | "default"> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
  withdrawn: "default",
};
export const REQ_STATUS_LABEL: Record<RequestStatus, string> = { submitted: "На рассмотрении", approved: "Утверждено", rejected: "Отклонено" };
export const REQ_STATUS_COLOR: Record<RequestStatus, "warning" | "success" | "error"> = { submitted: "warning", approved: "success", rejected: "error" };
export const KIND_LABEL: Record<RequestKind, string> = { assign: "Присвоение", confirm: "Подтверждение" };
export const LINK_STATUS_LABEL: Record<LinkStatus, string> = { pending: "Ожидает подтверждения", active: "Активна", suspended: "Приостановлена", ended: "Завершена" };
export const RESULT_STATUS_LABEL = { ranked: "В зачёте", did_not_start: "Неявка", disqualified: "Дисквалификация" } as const;
export const ORG_TYPE_LABEL: Record<string, string> = {
  school: "Школа",
  university: "Вуз",
  sports_school: "Спортивная школа",
  club: "Клуб",
  other: "Колледж / иное",
};
export const STAGE_LABEL: Record<string, string> = {
  initial: "Начальная подготовка",
  training: "Учебно-тренировочный этап",
  improvement: "Совершенствование мастерства",
  higher_mastery: "Высшее мастерство",
};

/** Допустимые переходы статуса соревнования (зеркало серверных правил). */
export const STATUS_TRANSITIONS: Record<CompetitionStatus, CompetitionStatus[]> = {
  draft: ["published", "registration_open", "cancelled"],
  published: ["draft", "registration_open", "cancelled"],
  registration_open: ["registration_closed", "cancelled"],
  registration_closed: ["registration_open", "in_progress", "cancelled"],
  in_progress: ["cancelled"],
  finished: [],
  cancelled: [],
};

export const SANCTION_LABEL = { disqualification: "Дисквалификация", suspension: "Отстранение" } as const;

/** Человекочитаемые названия действий журнала (код действия → текст). */
export const AUDIT_ACTION_LABEL: Record<string, string> = {
  "auth.login": "Вход",
  "auth.login_failed": "Неудачная попытка входа",
  "auth.switch_role": "Смена активной роли",
  "auth.register": "Регистрация с согласием на ПДн",
  "auth.password_reset_requested": "Запрос на восстановление пароля",
  "auth.password_reset": "Восстановление пароля",
  "competition.create": "Создание соревнования",
  "competition.update": "Изменение соревнования",
  "competition.regulation_upload": "Загрузка положения",
  "application.create": "Подача заявки",
  "application.moderate": "Модерация заявки",
  "results.submit": "Ввод результатов",
  "protocol.publish": "Публикация протокола",
  "judge.assign": "Назначение судьи",
  "judge.unassign": "Снятие судьи",
  "judge_request.create": "Заявка на судейскую категорию",
  "judge_request.decide": "Решение по судейской категории",
  "rank_request.create": "Заявка на разряд",
  "rank_request.decide": "Решение по разряду",
  "coach_link.request": "Запрос на привязку тренера",
  "coach_link.answer": "Ответ на запрос тренера",
  "coach_link.status": "Смена статуса связи тренер–спортсмен",
  "sanction.create": "Дисквалификация / отстранение",
  "sanction.end": "Завершение санкции",
  "reference.competition_type_create": "Новый тип соревнования",
  "reference.competition_type_update": "Изменение типа соревнования",
  "rating.settings_update": "Изменение таблицы баллов рейтинга",
  "squad.create": "Формирование сборной",
  "squad.approve": "Утверждение сборной",
  "report.headcount_export": "Выгрузка отчёта о численности",
  "report.athlete_export": "Выгрузка справки о выступлениях",
  "report.protocol_export": "Выгрузка протокола",
  "report.squad_order": "Выгрузка проекта приказа о сборной",
  "certificate.issue": "Выпуск справки с QR",
  "athlete.antidoping_update": "Отметка об антидопинговом курсе",
  "consent.scan_upload": "Загрузка скана согласия",
  "profile.email_notifications_toggle": "Уведомления на почту вкл/выкл",
};

/** Типы объектов журнала действий. */
export const ENTITY_LABEL: Record<string, string> = {
  user: "пользователь",
  athlete: "спортсмен",
  competition: "соревнование",
  competition_application: "заявка",
  protocol: "протокол",
  competition_judge: "судейская коллегия",
  judge_category_request: "заявка судьи",
  rank_request: "заявка на разряд",
  coach_athlete_link: "связь тренер–спортсмен",
  sanction: "санкция",
  competition_type: "тип соревнования",
  athlete_profile: "профиль спортсмена",
  consent: "согласие на ПДн",
  certificate: "справка с QR",
  squad: "сборная",
  rating_settings: "настройки рейтинга",
  report: "отчёт",
};
