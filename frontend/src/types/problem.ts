export type ProblemSeverity = "warning" | "error";

export type ProblemStage = "import" | "normalize" | "grouping" | "compliance" | "comparison";

export interface ProblemItem {
  id: string;
  stage: ProblemStage;
  targetId: string;
  description: string;
  severity: ProblemSeverity;
}

export interface ProblemGroup {
  type: string;
  label: string;
  stage: ProblemStage;
  severity: ProblemSeverity;
  count: number;
  items: ProblemItem[];
}
