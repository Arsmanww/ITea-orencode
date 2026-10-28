export type Role = "federation" | "athlete" | "coach" | "judge" | "ministry";
export type CompetitionLevel = "regional" | "interregional" | "all_russian";
export type RatingTier = "russia_championship" | "russia_first" | "interregional" | "regional";
export type CalendarPlan = "none" | "ekp_minsport" | "oren_regional";
export type CompetitionStatus = "draft" | "published" | "registration_open" | "registration_closed" | "in_progress" | "finished" | "cancelled";
export type StageFormat = "online" | "offline";
export type ApplicationStatus = "pending" | "approved" | "rejected" | "withdrawn";
export type RequestStatus = "submitted" | "approved" | "rejected";
export type RequestKind = "assign" | "confirm";
export type LinkStatus = "pending" | "active" | "suspended" | "ended";

export interface UserOut {
  id: number;
  email: string;
  last_name: string;
  first_name: string;
  patronymic: string | null;
  birth_date: string;
  gender: "male" | "female";
  phone: string | null;
  municipality_id: number | null;
}
export interface Me { user: UserOut; roles: Role[]; active_role: Role }
export interface TokenOut { access_token: string; token_type: string; expires_in: number; roles: Role[]; active_role: Role }

export interface Ref { id: number; name: string; code?: string | null; order_no?: number | null; validity_months?: number | null; is_active?: boolean | null }
export interface DisciplineRef { id: number; code: string; name: string }
export interface AgeGroup { id: number; name: string; min_age: number; max_age: number }
export interface UserRef { id: number; full_name: string }
export interface Organization { id: number; name: string; type: string; municipality_id: number }

export interface Stage { id: number; order_no: number; name: string; format: StageFormat; starts_at: string; ends_at: string; place_or_url: string | null }
export interface Competition {
  id: number;
  title: string;
  discipline: DisciplineRef;
  type: { id: number; name: string };
  level: CompetitionLevel;
  rating_tier: RatingTier;
  status: CompetitionStatus;
  calendar_plan: CalendarPlan;
  plan_number: string | null;
  start_date: string;
  end_date: string;
  location: string | null;
  registration_opens_at: string | null;
  registration_deadline: string | null;
  is_team: boolean;
  description: string | null;
  format: "online" | "offline" | "mixed";
  age_groups: AgeGroup[];
  stages: Stage[];
  regulation_url: string | null;
}
export interface CompetitionList { items: Competition[]; total: number; limit: number; offset: number }

export interface Application {
  id: number;
  competition_id: number;
  athlete: { id: number; full_name: string; birth_date: string };
  team: { id: number; name: string } | null;
  status: ApplicationStatus;
  age_on_start: number;
  submitted_by_user_id: number;
  submitted_by_role: Role;
  coach_id: number | null;
  moderated_by: number | null;
  moderated_at: string | null;
  moderation_comment: string | null;
  created_at: string;
}
export interface QueueItem extends Application { competition_title: string }

export interface ResultRow {
  id: number;
  application_id: number;
  athlete_id: number;
  athlete_name: string;
  place: number | null;
  status: "ranked" | "disqualified" | "did_not_start";
  score: string | null;
  time_seconds: string | null;
  tasks_solved: number | null;
  note: string | null;
}
export interface ProtocolRow {
  place: number | null;
  athlete_id: number;
  full_name: string;
  birth_date: string;
  team: string | null;
  score: string | null;
  time_seconds: string | null;
  tasks_solved: number | null;
  status: string;
  note: string | null;
}
export interface Protocol {
  id: number;
  competition_id: number;
  number: string;
  version: number;
  status: string;
  published_at: string | null;
  snapshot: { competition: string; start_date: string; end_date: string; location: string | null; participants?: number; rows: ProtocolRow[] };
  evsk: EvskCandidate[];
}

export interface HistoryItem {
  result_id: number;
  competition_id: number;
  competition_title: string;
  discipline: string;
  level: CompetitionLevel;
  rating_tier: RatingTier;
  start_date: string;
  end_date: string;
  place: number | null;
  status: "ranked" | "disqualified" | "did_not_start";
  score: string | null;
  time_seconds: string | null;
  tasks_solved: number | null;
  participants: number;
  protocol_id: number;
  protocol_number: string;
}
export interface History { athlete_id: number; athlete_name: string; total: number; prizes: number; items: HistoryItem[] }

export interface ValidityInfo {
  id: number;
  name: string;
  assigned_at: string | null;
  valid_until: string | null;
  days_left: number | null;
  expired: boolean;
  warning: boolean;
}
export interface MyRank { discipline: DisciplineRef; rank: ValidityInfo; pending_request: boolean }
export interface RankRequest {
  id: number;
  athlete: UserRef;
  rank: { id: number; name: string };
  discipline: DisciplineRef;
  kind: RequestKind;
  competition: { id: number; name: string };
  result: { id: number; place: number | null; score: string | null };
  submitted_by_role: Role;
  coach_id: number | null;
  status: RequestStatus;
  evsk_match: boolean | null;
  created_at: string;
  decision_comment: string | null;
  order_number: string | null;
  order_date: string | null;
  valid_until: string | null;
}

export interface Link {
  id: number;
  status: LinkStatus;
  coach: UserRef;
  athlete: UserRef;
  discipline: DisciplineRef;
  requested_at: string;
  confirmed_at: string | null;
  ended_at: string | null;
}
export interface CoachAthlete {
  link_id: number;
  athlete: UserRef;
  birth_date: string;
  age: number;
  discipline: DisciplineRef;
  status: LinkStatus;
  since: string | null;
  rank: ValidityInfo | null;
}

export interface AthleteProfile {
  user: UserOut;
  age: number;
  municipality: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  guardian_email: string | null;
  antidoping_course_date: string | null;
  antidoping_cert_url: string | null;
  enrollments: { discipline: DisciplineRef; organization: string | null; training_stage: string | null; start_date: string }[];
  coaches: { coach: UserRef; discipline: DisciplineRef }[];
  consent: { accepted: boolean; has_scan: boolean; signed_by: string | null; is_guardian: boolean };
}

export interface JudgeAssignment {
  id: number;
  competition: { id: number; title: string; start_date: string; end_date: string; status: CompetitionStatus };
  judge: UserRef;
  position: { id: number; name: string };
  assigned_at: string;
}
export interface MyAssignments { category: ValidityInfo | null; upcoming: JudgeAssignment[]; past: JudgeAssignment[] }
export interface CategoryRequest {
  id: number;
  judge: UserRef;
  category: { id: number; name: string };
  kind: RequestKind;
  status: RequestStatus;
  comment: string | null;
  created_at: string;
  decision_comment: string | null;
  order_number: string | null;
  valid_until: string | null;
}
export interface JudgeItem { id: number; name: string; category: string | null; valid_until: string | null }

export interface ExpiringItem {
  kind: "rank" | "judge_category";
  assignment_id: number;
  subject_id: number;
  subject_name: string;
  title: string;
  discipline: string | null;
  valid_until: string;
  days_left: number;
  expired: boolean;
}
export interface Expiring { days: number; total: number; items: ExpiringItem[] }

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: number | null;
  created_at: string;
  read_at: string | null;
}
export interface NotificationList { unread: number; items: NotificationItem[] }

export interface Dashboard {
  metrics: { athletes: number; coaches: number; judges: number; competitions_this_year: number; participants_this_year: number; ranks_assigned_this_year: number };
  attention: { applications_pending: number; rank_requests_pending: number; judge_requests_pending: number; expiring_30: number; expiring_60: number; registration_open: number };
  upcoming: { id: number; title: string; start_date: string; status: CompetitionStatus; registration_deadline: string | null; pending_applications: number }[];
}

export interface BreakdownItem { competition_id: number; title: string; date: string; tier: RatingTier; place: number | null; points: number }
export interface RatingItem {
  place: number;
  athlete_id: number;
  athlete_name: string;
  birth_date: string;
  age: number;
  organization: string | null;
  rank: string | null;
  base_points: number;
  prizes: number;
  coefficient: string;
  total: string;
  breakdown: BreakdownItem[];
}
export interface RatingTable {
  discipline: DisciplineRef;
  total_athletes: number;
  items: RatingItem[];
  excluded: { athlete_id: number; athlete_name: string; reason: string }[];
}
export interface Season { id: number; name: string; date_from: string; date_to: string }
export interface RatingSettings { stability_coef: string; stability_min_prizes: number; rules: { tier: RatingTier; place: number; points: number }[] }
export interface RatingOut {
  season: Season;
  as_of: string;
  age_group: { id: number; name: string } | null;
  min_rank: { id: number; name: string } | null;
  settings: RatingSettings;
  tables: RatingTable[];
}
export interface Squad {
  id: number;
  title: string;
  season: Season;
  discipline: DisciplineRef;
  age_group: { id: number; name: string } | null;
  status: "draft" | "approved";
  order_number: string | null;
  created_at: string;
  members: { position: number; athlete_id: number; athlete_name: string; birth_date: string; rating_points: string; organization: string | null; rank: string | null; coach: string | null; note: string | null }[];
}

export interface HeadcountRow { label: string; extra: string; counts: Record<string, number> }
export interface Headcount {
  years: number[];
  total: Record<string, number>;
  new: Record<string, number>;
  coaches: Record<string, number>;
  judges: Record<string, number>;
  municipalities: HeadcountRow[];
  organizations: HeadcountRow[];
  disciplines: HeadcountRow[];
  age_groups: HeadcountRow[];
}

export interface Page { slug: string; title: string; body_md: string }
export interface Navigator {
  about: Page[];
  guide: Page[];
  disciplines: { id: number; code: string; name: string; description: string | null; athletes: number }[];
  municipalities: { municipality: string; organizations: { id: number; name: string; type: string }[] }[];
  upcoming: Competition[];
  regions: RegionPoint[];
  stats: { athletes: number; organizations: number; competitions_this_year: number; open_registrations: number };
}
export interface RegistrationOptions {
  disciplines: { id: number; name: string; code: string }[];
  municipalities: { id: number; name: string }[];
  organizations: { id: number; name: string; municipality_id: number }[];
}
export interface NotificationSettings {
  in_app: boolean;
  email: string;
  email_notifications_configured: boolean;
  email_notifications_enabled: boolean;
}

export interface Certificate {
  id: number;
  number: string;
  verify_token: string;
  verify_url: string;
  issued_at: string;
  revoked: boolean;
  competition_title: string;
  discipline: string;
  place: number | null;
  participants: number;
}
export interface Verification {
  valid: boolean;
  status: "valid" | "revoked";
  number: string;
  issued_at: string;
  athlete_name: string;
  competition_title: string;
  discipline: string;
  level: CompetitionLevel;
  start_date: string;
  end_date: string;
  place: number | null;
  participants: number;
  score: string | null;
}

export interface RegionPoint { name: string; athletes: number; organizations: number }
export interface LeaderRow { place: number; name: string; organization: string | null; municipality: string | null; points: string; prizes: number }
export interface FeedItem { competition_id: number; title: string; discipline: string; published_at: string | null; participants: number; winner: string | null }

export interface Paged<T> { items: T[]; total: number; limit: number; offset: number }

export interface RegistryAthleteDiscipline {
  discipline: DisciplineRef;
  organization: string | null;
  training_stage: string | null;
  since: string;
  rank: string | null;
  rank_valid_until: string | null;
  coach: string | null;
}
export interface RegistryAthlete {
  id: number;
  full_name: string;
  birth_date: string;
  age: number;
  gender: "male" | "female";
  municipality: string | null;
  email: string | null;
  disciplines: RegistryAthleteDiscipline[];
}
export interface RegistryCoach { id: number; full_name: string; organization: string | null; municipality: string | null; disciplines: string[]; athletes: number; is_judge: boolean }
export interface RegistryJudge { id: number; full_name: string; organization: string | null; municipality: string | null; category: string | null; valid_until: string | null; expired: boolean; assignments: number }
export interface RegistryOrganization { id: number; name: string; type: string; municipality: string; address: string | null; disciplines: string[]; athletes: number; coaches: number }

export interface AuditItem {
  id: number;
  created_at: string;
  user: UserRef | null;
  active_role: Role | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  diff: Record<string, unknown> | null;
  ip: string | null;
}
export interface AuditPage extends Paged<AuditItem> { actions: string[] }

export type SanctionKind = "disqualification" | "suspension";
export interface Sanction {
  id: number;
  athlete: UserRef;
  kind: SanctionKind;
  date_from: string;
  date_to: string | null;
  reason: string;
  competition: { id: number; name: string } | null;
  active: boolean;
  created_at: string;
}

export interface LinkHistory { old_status: LinkStatus | null; new_status: LinkStatus; changed_by: UserRef; changed_at: string; comment: string | null }

export interface EvskCandidate { athlete_id: number; full_name: string; place: number; rank_id: number; rank: string; current_rank: string | null; kind: RequestKind; request_pending: boolean }

export interface ProfileDiscipline {
  discipline: DisciplineRef;
  organization: string | null;
  training_stage: string | null;
  since: string;
  rank: ValidityInfo | null;
  coach: string | null;
}
export interface MyProfile {
  user: UserOut;
  full_name: string;
  age: number;
  municipality: string | null;
  roles: Role[];
  active_role: Role;
  registered_at: string;
  consent: { accepted: boolean; has_scan: boolean; signed_by: string | null; is_guardian: boolean };
  email_notifications_enabled: boolean;
  athlete: {
    disciplines: ProfileDiscipline[];
    starts: number;
    prizes: number;
    antidoping_course_date: string | null;
    antidoping_cert_url: string | null;
    guardian_name: string | null;
    guardian_phone: string | null;
  } | null;
  coach: { organization: string | null; athletes: number; disciplines: string[] } | null;
  judge: { organization: string | null; category: ValidityInfo | null; assignments: number } | null;
}
