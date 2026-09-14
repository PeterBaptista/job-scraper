/**
 * The contract with the FastAPI resume API. These mirror `scraper/resume.py`'s
 * CONTENT dict exactly — the PDF renderer destructures them, so the shapes are
 * not free to drift.
 */

/**
 * [category, "comma, separated, values"]. Kept as a tuple, not an object:
 * `resume.py` does `for category, values in c["skills"]`, so normalising this
 * into {category, values} would break rendering after a JSON round trip.
 */
export type ResumeSkill = [string, string];

export interface ResumeExperience {
  title: string;
  company: string;
  period: string;
  bullets: string[];
}

export interface ResumeProject {
  name: string;
  tech?: string;
  bullets: string[];
}

export interface ResumeEducation {
  degree: string;
  institution: string;
  period?: string;
  detail?: string;
}

export interface ResumeContent {
  title: string;
  location?: string;
  summary: string;
  skills: ResumeSkill[];
  experience: ResumeExperience[];
  projects?: ResumeProject[];
  education?: ResumeEducation[];
  // Section headings (h_summary, h_experience, …) travel through untouched.
  [key: string]: unknown;
}

/** tailor()'s `_meta`. Stored separately — build_with_content only tolerates keys it knows. */
export interface ResumeMeta {
  pruned?: string[];
  omitted_requirements?: string[];
  ats_passes?: number;
  reason?: string;
  language?: string;
}

export interface AtsResult {
  score: number;
  raw_score: number;
  matched: string[];
  missing: string[];
  off_stack: string[];
  requirements: number;
  /** An empty or stack-less posting is unknown fit, not bad fit. Never render this as 0. */
  indeterminate: boolean;
  indeterminate_reason?: string;
}

export interface FitResult {
  pages: number;
  /** 1 default · 2 tighter · 3 smaller body · 4 bullets dropped · 5 gave up on one page. */
  tier: number;
  dropped_bullets: string[];
}

export type ResumeDraftStatus = 'tailoring' | 'ready' | 'failed';

export interface ResumeDraft {
  id: string;
  jobId: string;
  status: ResumeDraftStatus;
  language: string;
  content: ResumeContent | null;
  generatedContent: ResumeContent | null;
  meta: ResumeMeta | null;
  atsScore: number | null;
  atsDetail: AtsResult | null;
  extraPrompt: string | null;
  error: string | null;
  pdfPath: string | null;
  pdfCommittedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
  /** True when edits postdate the committed PDF — applying now would send the old CV. */
  stale: boolean;
}

export interface AnalysisResponse {
  /** Post-fitting content: what the PDF actually says, not what was submitted. */
  content: ResumeContent;
  ats: AtsResult;
  violations: string[];
  over_pruned: string[];
  /**
   * Missing terms the profile actually backs. Adding one of these recovers a
   * fact; adding any other missing term invents one and will block commit.
   */
  coverable: string[];
}

export interface PreviewResponse extends AnalysisResponse {
  pdf_base64: string;
  fit: FitResult;
}

export interface CommitResponse extends PreviewResponse {
  resume_path: string;
}
