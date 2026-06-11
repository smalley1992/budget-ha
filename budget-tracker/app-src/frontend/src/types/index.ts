export type UserSlug = string;
export type ViewSlug = UserSlug | "combined";
export type BudgetLineType = "bill" | "expense" | "savings_contribution" | "debt_payment";
export type BudgetLineStatus = "planned" | "paid";

export interface User {
  id: UserSlug;
  name: string;
  icon: string | null;
  salary: number;
}

export interface SummaryTotals {
  income: number;
  bills: number;
  expenses: number;
  savings_contributions: number;
  debt_payments: number;
  outgoings: number;
  leftover: number;
}

export interface Summary {
  period: string;
  view: ViewSlug;
  totals: SummaryTotals;
  by_user: Record<string, SummaryTotals> | null;
}

export interface IncomeLine {
  id: number;
  user_id: UserSlug;
  period: string;
  name: string;
  amount: number;
  is_static: boolean;
  notes: string | null;
}

export interface BudgetLine {
  id: number;
  user_id: UserSlug;
  period: string;
  type: BudgetLineType;
  name: string;
  amount: number;
  due_day: number | null;
  status: BudgetLineStatus;
  paid_date: string | null;
  is_static: boolean;
  notes: string | null;
  linked_debt_id: number | null;
  linked_savings_pot_id: number | null;
  attachment_count: number;
}

export interface Debt {
  id: number;
  user_id: UserSlug;
  name: string;
  starting_balance: number;
  paid_amount: number;
  current_balance: number;
  notes: string | null;
}

export interface SavingsPot {
  id: number;
  user_id: UserSlug;
  name: string;
  starting_balance: number;
  contributed_amount: number;
  current_balance: number;
  target_amount: number | null;
  notes: string | null;
}

export interface Attachment {
  id: number;
  budget_line_id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export type AiImportAction = "create" | "update_existing" | "ignore";
export type AiImportItemKind = "budget" | "income";

export interface AiImportConfig {
  configured: boolean;
  model: string;
  daily_request_design: string;
}

export interface AiImportProposal {
  source_text: string;
  date: string | null;
  action: AiImportAction;
  item_kind: AiImportItemKind;
  user_id: UserSlug;
  period: string;
  type: BudgetLineType | null;
  name: string;
  amount: number;
  status: BudgetLineStatus;
  paid_date: string | null;
  linked_debt_id: number | null;
  linked_savings_pot_id: number | null;
  match_existing_line_id: number | null;
  confidence: number;
  reasoning: string;
}

export interface AiImportPreview {
  document_type: string;
  summary: string;
  proposals: AiImportProposal[];
}
