import { WorkflowExecutionStatusType, TaskExecutionStatusType } from "./api";

export interface StatusConfig {
  label: string;
  variant: "default" | "success" | "warning" | "danger" | "info" | "neutral";
  description: string;
}

export const WORKFLOW_STATUS_CONFIG: Record<
  WorkflowExecutionStatusType,
  StatusConfig
> = {
  QUEUED: {
    label: "Queued",
    variant: "neutral",
    description: "Waiting in scheduler queue for worker acquisition.",
  },
  RUNNING: {
    label: "Running",
    variant: "info",
    description: "Execution in progress with active DAG tasks.",
  },
  PAUSED: {
    label: "Paused",
    variant: "warning",
    description: "Paused awaiting manual intervention or approval.",
  },
  COMPLETED: {
    label: "Completed",
    variant: "success",
    description: "All tasks completed and verified successfully.",
  },
  FAILED: {
    label: "Failed",
    variant: "danger",
    description: "Execution failed due to unrecoverable task error.",
  },
  CANCELLED: {
    label: "Cancelled",
    variant: "neutral",
    description: "Cancelled by operator or system signal.",
  },
  TIMED_OUT: {
    label: "Timed Out",
    variant: "danger",
    description: "Execution exceeded maximum allowed duration.",
  },
};

export const TASK_STATUS_CONFIG: Record<TaskExecutionStatusType, StatusConfig> =
  {
    PENDING: {
      label: "Pending",
      variant: "neutral",
      description: "Initialized and pending dependency resolution.",
    },
    BLOCKED: {
      label: "Blocked",
      variant: "neutral",
      description: "Waiting for upstream prerequisite tasks to finish.",
    },
    READY: {
      label: "Ready",
      variant: "info",
      description: "Dependencies satisfied; ready for agent worker dispatch.",
    },
    RUNNING: {
      label: "Running",
      variant: "info",
      description: "Agent actively executing with model provider.",
    },
    COMPLETED: {
      label: "Completed",
      variant: "success",
      description: "Task executed successfully and output contract verified.",
    },
    FAILED: {
      label: "Failed",
      variant: "danger",
      description: "Task execution or validation failed unrecoverably.",
    },
    WAITING_APPROVAL: {
      label: "Waiting Approval",
      variant: "warning",
      description: "Human operator review required before proceeding.",
    },
    ESCALATED: {
      label: "Escalated",
      variant: "danger",
      description: "Quality evaluation or operator rejection triggered escalation.",
    },
    TIMED_OUT: {
      label: "Timed Out",
      variant: "danger",
      description: "Task duration exceeded defined timeout.",
    },
    CANCELLED: {
      label: "Cancelled",
      variant: "neutral",
      description: "Task cancelled prior to completion.",
    },
  };
