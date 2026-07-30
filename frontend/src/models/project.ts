export interface Project {
  id: string;
  name: string;
  owner_email: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskSummary {
  id: string;
  type: "compliance" | "generation";
  status: string;
  summary: string;
  created_at: string;
  market?: string;
  ethnicity?: string;
  age_group?: string;
  platform?: string;
  media_type?: string;
}

export interface ViolationSummary {
  type: string;
  severity: string;
  description: string;
}

export interface ComplianceTaskDetail extends TaskSummary {
  type: "compliance";
  compliance: {
    risk_percentage: number | null;
    status: string;
    market: string;
    ethnicity?: string;
    age_group?: string;
    media_type?: string;
    violations: ViolationSummary[];
    s3_upload_key: string | null;
    s3_segmented_key: string | null;
    s3_remix_key: string | null;
    result_json: Record<string, unknown> | null;
  };
  pipeline_state?: Record<string, unknown>;
}

export interface GenerationTaskDetail extends TaskSummary {
  type: "generation";
  pipeline_state: import("@/components/workspace/canvas/graphModel").PipelineState;
}

export type TaskDetail = ComplianceTaskDetail | GenerationTaskDetail;
