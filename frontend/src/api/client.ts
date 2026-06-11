import type {
  Attachment,
  AiImportConfig,
  AiImportPreview,
  BudgetLine,
  Debt,
  IncomeLine,
  SavingsPot,
  Summary,
  User,
  UserSlug,
  ViewSlug,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function filenameFromDisposition(header: string | null): string {
  const match = header?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match ? decodeURIComponent(match[1]) : "budget-tracker.sqlite3";
}

async function downloadFile(path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed with ${response.status}`);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("content-disposition")),
  };
}

export const api = {
  attachmentDownloadUrl: (id: number) => `${API_BASE}/attachments/${id}/download`,
  listUsers: () => request<User[]>("/users"),
  createUser: (payload: unknown) => request<User>("/users", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (id: UserSlug, payload: unknown) => request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteUser: (id: UserSlug) => request<void>(`/users/${id}`, { method: "DELETE" }),
  listMonths: () => request<{ id: number; period: string }[]>("/months"),
  createMonth: (period: string) => request<{ id: number; period: string }>("/months", { method: "POST", body: JSON.stringify({ period }) }),
  rollover: (source_period: string, target_period: string) =>
    request<{ copied_income_lines: number; copied_budget_lines: number }>("/months/rollover", {
      method: "POST",
      body: JSON.stringify({ source_period, target_period }),
    }),
  summary: (period: string, view: ViewSlug) => request<Summary>(`/summary?period=${period}&view=${view}`),
  incomeLines: (period: string, userId: UserSlug) => request<IncomeLine[]>(`/income-lines?period=${period}&user_id=${userId}`),
  createIncomeLine: (payload: unknown) => request<IncomeLine>("/income-lines", { method: "POST", body: JSON.stringify(payload) }),
  updateIncomeLine: (id: number, payload: unknown) => request<IncomeLine>(`/income-lines/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteIncomeLine: (id: number) => request<void>(`/income-lines/${id}`, { method: "DELETE" }),
  budgetLines: (period: string, userId: UserSlug) => request<BudgetLine[]>(`/budget-lines?period=${period}&user_id=${userId}`),
  createBudgetLine: (payload: unknown) => request<BudgetLine>("/budget-lines", { method: "POST", body: JSON.stringify(payload) }),
  updateBudgetLine: (id: number, payload: unknown) => request<BudgetLine>(`/budget-lines/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteBudgetLine: (id: number) => request<void>(`/budget-lines/${id}`, { method: "DELETE" }),
  markPaid: (id: number) => request<BudgetLine>(`/budget-lines/${id}/mark-paid`, { method: "POST" }),
  markPlanned: (id: number) => request<BudgetLine>(`/budget-lines/${id}/mark-planned`, { method: "POST" }),
  debts: (userId: UserSlug) => request<Debt[]>(`/debts?user_id=${userId}`),
  createDebt: (payload: unknown) => request<Debt>("/debts", { method: "POST", body: JSON.stringify(payload) }),
  updateDebt: (id: number, payload: unknown) => request<Debt>(`/debts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteDebt: (id: number) => request<void>(`/debts/${id}`, { method: "DELETE" }),
  savingsPots: (userId: UserSlug) => request<SavingsPot[]>(`/savings-pots?user_id=${userId}`),
  createSavingsPot: (payload: unknown) => request<SavingsPot>("/savings-pots", { method: "POST", body: JSON.stringify(payload) }),
  updateSavingsPot: (id: number, payload: unknown) => request<SavingsPot>(`/savings-pots/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSavingsPot: (id: number) => request<void>(`/savings-pots/${id}`, { method: "DELETE" }),
  attachments: (lineId: number) => request<Attachment[]>(`/budget-lines/${lineId}/attachments`),
  uploadAttachment: (lineId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Attachment>(`/budget-lines/${lineId}/attachments`, { method: "POST", body: form });
  },
  deleteAttachment: (id: number) => request<void>(`/attachments/${id}`, { method: "DELETE" }),
  exportDatabase: () => downloadFile("/backups/database"),
  importDatabase: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ ok: boolean; message: string }>("/backups/database/import", { method: "POST", body: form });
  },
  aiImportConfig: () => request<AiImportConfig>("/ai-import/config"),
  previewAiImport: (file: File, period: string, view: ViewSlug, apiKey: string) => {
    const form = new FormData();
    form.append("period", period);
    form.append("view", view);
    form.append("api_key", apiKey);
    form.append("file", file);
    return request<AiImportPreview>("/ai-import/preview", { method: "POST", body: form });
  },
};
