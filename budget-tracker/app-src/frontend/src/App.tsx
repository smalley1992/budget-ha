import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Banknote,
  CalendarPlus,
  Check,
  CircleUserRound,
  Download,
  FileUp,
  FileSearch,
  Moon,
  Paperclip,
  PiggyBank,
  Plus,
  RefreshCw,
  Settings,
  Sun,
  Trash2,
  Upload,
  WalletCards,
  X,
} from "lucide-react";
import { api } from "./api/client";
import type { AiImportConfig, AiImportProposal, Attachment, BudgetLine, BudgetLineStatus, BudgetLineType, Debt, IncomeLine, SavingsPot, Summary, User, UserSlug, ViewSlug } from "./types";

const lineTypes: { id: BudgetLineType; label: string; button: string }[] = [
  { id: "bill", label: "Bills", button: "Bill" },
  { id: "expense", label: "Expenses", button: "Expense" },
  { id: "savings_contribution", label: "Savings", button: "Saving" },
  { id: "debt_payment", label: "Debt payments", button: "Debt" },
];

const emptySummary: Summary = {
  period: "",
  view: "combined",
  totals: { income: 0, bills: 0, expenses: 0, savings_contributions: 0, debt_payments: 0, outgoings: 0, leftover: 0 },
  by_user: null,
};

type Theme = "light" | "dark";
type ModalState =
  | { kind: "income" }
  | { kind: "budget"; type: BudgetLineType; title?: string }
  | { kind: "debt" }
  | { kind: "saving" }
  | { kind: "profile"; userId: UserSlug }
  | { kind: "user" }
  | { kind: "ai_import" }
  | null;

function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function nextPeriod(period: string): string {
  let [year, month] = period.split("-").map(Number);
  month += 1;
  if (month > 12) {
    year += 1;
    month = 1;
  }
  return `${year}-${String(month).padStart(2, "0")}`;
}

function monthLabel(period: string): string {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) {
    return period;
  }
  return new Intl.DateTimeFormat("en-GB", { month: "long" }).format(new Date(year, month - 1, 1));
}

function money(value: number): string {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);
}

function visibleUsers(view: ViewSlug, users: User[]): UserSlug[] {
  if (view === "combined") {
    return users.map((user) => user.id);
  }
  return users.some((user) => user.id === view) ? [view] : [];
}

function storedView(): ViewSlug {
  const saved = localStorage.getItem("budget-tracker-view");
  return saved || "combined";
}

function storedStatus(): BudgetLineStatus {
  return localStorage.getItem("budget-tracker-default-status") === "planned" ? "planned" : "paid";
}

function storedTheme(): Theme {
  return localStorage.getItem("budget-tracker-theme") === "dark" ? "dark" : "light";
}

function storedAiModel(): string {
  return localStorage.getItem("budget-tracker-ai-model") || "gemma-4-26b-a4b-it";
}

function lineLabel(type: BudgetLineType): string {
  return lineTypes.find((item) => item.id === type)?.label ?? type;
}

function targetName(line: BudgetLine, debts: Debt[], pots: SavingsPot[]): string {
  if (line.type === "debt_payment") {
    return debts.find((debt) => debt.id === line.linked_debt_id)?.name ?? "Needs target";
  }
  if (line.type === "savings_contribution") {
    return pots.find((pot) => pot.id === line.linked_savings_pot_id)?.name ?? "General savings";
  }
  return "";
}

function fallbackUserName(userId: UserSlug): string {
  return userId || "User";
}

function userName(users: User[], userId: UserSlug): string {
  return users.find((user) => user.id === userId)?.name ?? fallbackUserName(userId);
}

function userIcon(users: User[], userId: UserSlug): string {
  const user = users.find((row) => row.id === userId);
  return user?.icon || user?.name?.slice(0, 1) || fallbackUserName(userId).slice(0, 1);
}

export function App() {
  const [view, setView] = useState<ViewSlug>(storedView);
  const [users, setUsers] = useState<User[]>([]);
  const [period, setPeriod] = useState(currentPeriod());
  const [months, setMonths] = useState<string[]>([]);
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [income, setIncome] = useState<IncomeLine[]>([]);
  const [lines, setLines] = useState<BudgetLine[]>([]);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [pots, setPots] = useState<SavingsPot[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [attachmentLine, setAttachmentLine] = useState<BudgetLine | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [heroDrilldown, setHeroDrilldown] = useState<keyof Summary["totals"] | "debt_balance" | "savings_balance" | null>(null);
  const [soloTab, setSoloTab] = useState<"budget" | "savings" | "debts">("budget");
  const [incomeOpen, setIncomeOpen] = useState(false);
  const [defaultStatus, setDefaultStatus] = useState<BudgetLineStatus>(storedStatus);
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const aiImportInputRef = useRef<HTMLInputElement | null>(null);
  const [aiConfig, setAiConfig] = useState<AiImportConfig | null>(null);
  const [aiApiKey, setAiApiKey] = useState(() => localStorage.getItem("budget-tracker-ai-api-key") || "");
  const [aiModel, setAiModel] = useState(storedAiModel);
  const [aiReview, setAiReview] = useState<{ summary: string; documentType: string; proposals: AiImportProposal[] } | null>(null);
  const [aiImportLoading, setAiImportLoading] = useState(false);
  const [aiImportStatus, setAiImportStatus] = useState("");

  const [incomeForm, setIncomeForm] = useState({ name: "", amount: "", is_static: false });
  const [lineForm, setLineForm] = useState({ name: "", amount: "", due_day: "", is_static: false, linked_debt_id: "", linked_savings_pot_id: "" });
  const [debtForm, setDebtForm] = useState({ name: "", starting_balance: "" });
  const [potForm, setPotForm] = useState({ name: "", starting_balance: "", target_amount: "" });
  const [profileForm, setProfileForm] = useState({ name: "", icon: "", salary: "" });
  const [userForm, setUserForm] = useState({ name: "", icon: "", salary: "" });

  const canEdit = view !== "combined" && users.some((user) => user.id === view);
  const activeUser = canEdit ? view : users[0]?.id ?? "";
  const debtsForActiveUser = useMemo(() => debts.filter((debt) => debt.user_id === activeUser), [debts, activeUser]);
  const potsForActiveUser = useMemo(() => pots.filter((pot) => pot.user_id === activeUser), [pots, activeUser]);
  const unallocatedPaidDebt = useMemo(
    () => lines.filter((line) => line.type === "debt_payment" && line.status === "paid" && line.linked_debt_id === null).reduce((total, line) => total + line.amount, 0),
    [lines],
  );
  const debtOverviewTotal = useMemo(() => Math.max(0, debts.reduce((total, debt) => total + debt.current_balance, 0) - unallocatedPaidDebt), [debts, unallocatedPaidDebt]);
  const savingsOverviewTotal = useMemo(() => pots.reduce((total, pot) => total + pot.current_balance, 0), [pots]);

  async function loadAll() {
    setBusy(true);
    try {
      await api.createMonth(period);
      const [userRows, monthRows] = await Promise.all([api.listUsers(), api.listMonths()]);
      let nextView = view;
      if (nextView !== "combined" && !userRows.some((user) => user.id === nextView)) {
        nextView = userRows[0]?.id ?? "combined";
      }
      const summaryRow = await api.summary(period, nextView);
      const people = visibleUsers(nextView, userRows);
      const incomeRows = (await Promise.all(people.map((user) => api.incomeLines(period, user)))).flat();
      const budgetRows = (await Promise.all(people.map((user) => api.budgetLines(period, user)))).flat();
      const debtRows = (await Promise.all(people.map((user) => api.debts(user)))).flat();
      const potRows = (await Promise.all(people.map((user) => api.savingsPots(user)))).flat();
      setUsers(userRows);
      setMonths(monthRows.map((month) => month.period));
      setSummary(summaryRow);
      setIncome(incomeRows);
      setLines(budgetRows);
      setDebts(debtRows);
      setPots(potRows);
      if (nextView !== view) {
        setView(nextView);
      }
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load budget data");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    localStorage.setItem("budget-tracker-view", view);
    void loadAll();
  }, [view, period]);

  useEffect(() => {
    localStorage.setItem("budget-tracker-default-status", defaultStatus);
  }, [defaultStatus]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("budget-tracker-theme", theme);
  }, [theme]);

  useEffect(() => {
    api.aiImportConfig()
      .then((config) => {
        setAiConfig(config);
        if (!localStorage.getItem("budget-tracker-ai-model")) {
          setAiModel(config.model || config.default_model || "gemma-4-26b-a4b-it");
        }
      })
      .catch(() => setAiConfig(null));
  }, []);

  useEffect(() => {
    localStorage.setItem("budget-tracker-ai-model", aiModel);
  }, [aiModel]);

  async function run(action: () => Promise<unknown>, done = "Saved") {
    setBusy(true);
    try {
      await action();
      setMessage(done);
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function exportDatabase() {
    setBusy(true);
    try {
      const { blob, filename } = await api.exportDatabase();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("Database export downloaded");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not export database");
    } finally {
      setBusy(false);
    }
  }

  async function importDatabase(file: File) {
    const confirmed = window.confirm("Restore this database backup? This replaces the current budget database. Make an export first if you need to keep the current data.");
    if (!confirmed) {
      return;
    }
    await run(async () => {
      await api.importDatabase(file);
      setView("combined");
      setShowSettings(false);
    }, "Database restored");
  }

  async function convertPdfToImageFile(file: File): Promise<File> {
    const arrayBuffer = await file.arrayBuffer();
    // @ts-ignore
    const pdfjsLib = window.pdfjsLib;
    if (!pdfjsLib) {
      throw new Error("PDF.js library is not loaded.");
    }
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Could not get 2D context for canvas.");
    }
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    await page.render({ canvasContext: context, viewport: viewport }).promise;
    
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error("Could not convert PDF canvas to blob"));
          return;
        }
        const newFile = new File([blob], file.name.replace(/\.pdf$/i, ".jpg"), { type: "image/jpeg" });
        resolve(newFile);
      }, "image/jpeg", 0.85);
    });
  }

  async function startAiImport(file: File) {
    if (!aiConfig?.configured && !aiApiKey.trim()) {
      window.alert("Please configure a Google AI API Key in the Settings panel or the Home Assistant Add-on configuration before uploading documents.");
      return;
    }
    setAiImportLoading(true);
    setAiImportStatus("Preparing document...");
    try {
      let fileToSend = file;
      if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
        setAiImportStatus("Converting PDF locally to image...");
        try {
          fileToSend = await convertPdfToImageFile(file);
        } catch (pdfError) {
          throw new Error("Failed to convert PDF locally: " + (pdfError instanceof Error ? pdfError.message : String(pdfError)));
        }
      }
      setAiImportStatus("Calling AI to analyze document...");
      const preview = await api.previewAiImport(fileToSend, period, view, aiApiKey.trim(), aiModel);
      setAiReview({
        summary: preview.summary,
        documentType: preview.document_type,
        proposals: preview.proposals.map((proposal) => ({
          ...proposal,
          period: proposal.period || period,
          user_id: proposal.user_id || users[0]?.id || "",
          action: proposal.action || "create",
          item_kind: proposal.item_kind || "budget",
          type: proposal.item_kind === "income" ? null : proposal.type || "expense",
          status: proposal.status || "paid",
          amount: Number(proposal.amount || 0),
          confidence: Number(proposal.confidence || 0),
        })),
      });
      setModal(null);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Could not parse document");
    } finally {
      setAiImportLoading(false);
      setAiImportStatus("");
    }
  }

  async function previewAiImport(file: File) {
    if (!aiConfig?.configured && !aiApiKey.trim()) {
      window.alert("Please configure a Google AI API Key in the Settings panel or the Home Assistant Add-on configuration before uploading documents.");
      return;
    }
    setBusy(true);
    setMessage("Preparing document...");
    try {
      let fileToSend = file;
      if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
        try {
          fileToSend = await convertPdfToImageFile(file);
        } catch (pdfError) {
          throw new Error("Failed to convert PDF locally: " + (pdfError instanceof Error ? pdfError.message : String(pdfError)));
        }
      }
      setMessage("Calling AI to analyze document...");
      const preview = await api.previewAiImport(fileToSend, period, view, aiApiKey.trim(), aiModel);
      setAiReview({
        summary: preview.summary,
        documentType: preview.document_type,
        proposals: preview.proposals.map((proposal) => ({
          ...proposal,
          period: proposal.period || period,
          user_id: proposal.user_id || users[0]?.id || "",
          action: proposal.action || "create",
          item_kind: proposal.item_kind || "budget",
          type: proposal.item_kind === "income" ? null : proposal.type || "expense",
          status: proposal.status || "paid",
          amount: Number(proposal.amount || 0),
          confidence: Number(proposal.confidence || 0),
        })),
      });
      setShowSettings(false);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not parse document");
    } finally {
      setBusy(false);
    }
  }

  async function applyAiImport() {
    if (!aiReview) {
      return;
    }
    const proposals = aiReview.proposals.filter((proposal) => proposal.action !== "ignore" && proposal.amount > 0 && proposal.user_id);
    await run(async () => {
      for (const proposal of proposals) {
        if (proposal.item_kind === "income") {
          await api.createIncomeLine({
            user_id: proposal.user_id,
            period,
            name: proposal.name,
            amount: proposal.amount,
            is_static: false,
          });
          continue;
        }

        if (proposal.action === "update_existing" && proposal.match_existing_line_id) {
          await api.updateBudgetLine(proposal.match_existing_line_id, {
            type: proposal.type || "expense",
            name: proposal.name,
            amount: proposal.amount,
            status: proposal.status,
            paid_date: proposal.paid_date,
            linked_debt_id: proposal.linked_debt_id,
            linked_savings_pot_id: proposal.linked_savings_pot_id,
          });
        } else {
          await api.createBudgetLine({
            user_id: proposal.user_id,
            period,
            type: proposal.type || "expense",
            name: proposal.name,
            amount: proposal.amount,
            status: proposal.status,
            paid_date: proposal.paid_date,
            linked_debt_id: proposal.linked_debt_id,
            linked_savings_pot_id: proposal.linked_savings_pot_id,
          });
        }
      }
      setAiReview(null);
    }, `${proposals.length} line${proposals.length === 1 ? "" : "s"} added`);
  }

  function openBudgetModal(type: BudgetLineType, title?: string, name = "") {
    setLineForm({ name, amount: "", due_day: "", is_static: false, linked_debt_id: "", linked_savings_pot_id: "" });
    setModal({ kind: "budget", type, title });
    setAddMenuOpen(false);
  }

  function openModal(nextModal: ModalState) {
    if (nextModal?.kind === "income") {
      setIncomeForm({ name: "", amount: "", is_static: false });
    }
    if (nextModal?.kind === "debt") {
      setDebtForm({ name: "", starting_balance: "" });
    }
    if (nextModal?.kind === "saving") {
      setPotForm({ name: "", starting_balance: "", target_amount: "" });
    }
    if (nextModal?.kind === "user") {
      setUserForm({ name: "", icon: "", salary: "" });
    }
    if (nextModal?.kind === "profile") {
      const profile = users.find((user) => user.id === nextModal.userId);
      setProfileForm({
        name: profile?.name ?? fallbackUserName(nextModal.userId),
        icon: profile?.icon ?? "",
        salary: profile?.salary ? String(profile.salary) : "",
      });
    }
    setModal(nextModal);
    setAddMenuOpen(false);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Budget Tracker</h1>
          <p>{summary.period || period}</p>
        </div>
        <div className="topbar-controls">
          <label className="month-control">
            <strong>{monthLabel(period)}</strong>
            <input list="known-months" type="month" value={period} onChange={(event) => setPeriod(event.target.value)} aria-label="Month" />
            <datalist id="known-months">
              {months.map((month) => (
                <option key={month} value={month} />
              ))}
            </datalist>
          </label>
          <button className="icon-text" disabled={busy} onClick={() => void run(() => api.rollover(period, nextPeriod(period)), `Rolled into ${nextPeriod(period)}`)} title="Create next month">
            <CalendarPlus size={18} />
            Next Month
          </button>
          <button className="icon-button" disabled={busy} onClick={() => setShowSettings(true)} title="Settings">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {users.length > 0 && (
        <div className="viewbar">
          <UserSwitcher users={users} view={view} onChange={setView} />
        </div>
      )}

      {message && <div className="notice">{message}</div>}

      {users.length === 0 && (
        <FirstRunSetup
          userForm={userForm}
          setUserForm={setUserForm}
          busy={busy}
          onSubmit={() => void run(async () => {
            const created = await api.createUser({ name: userForm.name, icon: userForm.icon, salary: Number(userForm.salary || 0) });
            setUserForm({ name: "", icon: "", salary: "" });
            setView(created.id);
          }, "Family member added")}
        />
      )}

      <section className="metrics" aria-label="Budget totals">
        <Metric icon={<Banknote />} label="Income" value={summary.totals.income} onClick={view === "combined" ? () => setHeroDrilldown("income") : () => setIncomeOpen(true)} />
        <Metric icon={<WalletCards />} label="Outgoings" value={summary.totals.outgoings} onClick={view === "combined" ? () => setHeroDrilldown("outgoings") : undefined} />
        <Metric icon={<PiggyBank />} label="Savings" value={savingsOverviewTotal || summary.totals.savings_contributions} onClick={view === "combined" ? () => setHeroDrilldown("savings_balance") : undefined} />
        <Metric icon={<Check />} label="Leftover" value={summary.totals.leftover} emphasis={summary.totals.leftover >= 0 ? "good" : "bad"} onClick={view === "combined" ? () => setHeroDrilldown("leftover") : undefined} />
      </section>

      {view === "combined" ? (
        <CombinedOverview
          users={users}
          summary={summary}
          income={income}
          lines={lines}
          debts={debts}
          pots={pots}
          heroDrilldown={heroDrilldown}
          setHeroDrilldown={setHeroDrilldown}
        />
      ) : (
        <section className="panel tab-panel">
          <div className="section-tabs">
            <button className={soloTab === "budget" ? "active" : ""} onClick={() => setSoloTab("budget")}>Budget Lines</button>
            <button className={soloTab === "savings" ? "active" : ""} onClick={() => setSoloTab("savings")}>Savings</button>
            <button className={soloTab === "debts" ? "active" : ""} onClick={() => setSoloTab("debts")}>Debts</button>
          </div>
          {soloTab === "budget" && (
            <BudgetLineTable
              lines={lines}
              debts={debts}
              pots={pots}
              users={users}
              canEdit={canEdit}
              run={run}
              onAttachments={setAttachmentLine}
            />
          )}
          {soloTab === "savings" && (
            <>
              <CompactSummary rows={[["Saved total", money(savingsOverviewTotal)], ["Pots", String(pots.length)]]} />
              <BalanceLineList rows={pots} users={users} canEdit={canEdit} kind="saving" onPatch={(id, payload) => run(() => api.updateSavingsPot(id, payload))} onDelete={(id) => run(() => api.deleteSavingsPot(id), "Deleted")} />
            </>
          )}
          {soloTab === "debts" && (
            <>
              <CompactSummary rows={unallocatedPaidDebt > 0 ? [["Debt total", money(debtOverviewTotal)], ["Needs target", money(unallocatedPaidDebt)]] : [["Debt total", money(debtOverviewTotal)], ["Accounts", String(debts.length)]]} />
              <BalanceLineList rows={debts} users={users} canEdit={canEdit} kind="debt" onPatch={(id, payload) => run(() => api.updateDebt(id, payload))} onDelete={(id) => run(() => api.deleteDebt(id), "Deleted")} />
            </>
          )}
        </section>
      )}

      {canEdit && (
        <div className="fab-wrap">
          {addMenuOpen && (
            <div className="fab-menu">
              <button onClick={() => { setAddMenuOpen(false); setModal({ kind: "ai_import" }); }} style={{ fontWeight: "bold", borderBottom: "1px solid var(--border)" }}>Upload doc</button>
              <button onClick={() => openModal({ kind: "income" })}>Income</button>
              <button onClick={() => openBudgetModal("bill", "Add bill")}>Bill</button>
              <button onClick={() => openBudgetModal("expense", "Add expense")}>Expense</button>
              <button onClick={() => openBudgetModal("expense", "Add subscription", "Subscription")}>Subscription</button>
              <button onClick={() => openBudgetModal("savings_contribution", "Add savings contribution")}>Savings</button>
              <button onClick={() => openBudgetModal("debt_payment", "Add debt payment")}>Debt payment</button>
              <button onClick={() => openModal({ kind: "debt" })}>Debt account</button>
              <button onClick={() => openModal({ kind: "saving" })}>Savings pot</button>
            </div>
          )}
          <button className={`fab ${addMenuOpen ? "open" : ""}`} onClick={() => setAddMenuOpen(!addMenuOpen)} title="Add">
            <Plus size={26} />
          </button>
        </div>
      )}

      {modal && (
        <EntryModal title={modal.kind === "budget" ? (modal.title ?? `Add ${lineTypes.find((item) => item.id === modal.type)?.button}`) : modal.kind === "income" ? "Add income" : modal.kind === "debt" ? "Add debt account" : modal.kind === "saving" ? "Add savings pot" : modal.kind === "user" ? "Add family member" : modal.kind === "ai_import" ? "Upload document" : "User profile"} onClose={() => setModal(null)}>
          {modal.kind === "income" && (
            <form
              className="modal-form"
              onSubmit={(event) => {
                event.preventDefault();
                void run(async () => {
                  await api.createIncomeLine({ user_id: activeUser, period, name: incomeForm.name, amount: Number(incomeForm.amount), is_static: incomeForm.is_static });
                  setIncomeForm({ name: "", amount: "", is_static: false });
                  setModal(null);
                });
              }}
            >
              <input required placeholder="Name" value={incomeForm.name} onChange={(event) => setIncomeForm({ ...incomeForm, name: event.target.value })} />
              <input required min="0" step="0.01" type="number" placeholder="Amount" value={incomeForm.amount} onChange={(event) => setIncomeForm({ ...incomeForm, amount: event.target.value })} />
              <label className="checkline"><input type="checkbox" checked={incomeForm.is_static} onChange={(event) => setIncomeForm({ ...incomeForm, is_static: event.target.checked })} /> Static / recurring</label>
              <button className="primary-button">Save income</button>
            </form>
          )}

          {modal.kind === "budget" && (
            <form
              className="modal-form"
              onSubmit={(event) => {
                event.preventDefault();
                void run(async () => {
                  await api.createBudgetLine({
                    user_id: activeUser,
                    period,
                    type: modal.type,
                    name: lineForm.name,
                    amount: Number(lineForm.amount),
                    due_day: lineForm.due_day ? Number(lineForm.due_day) : null,
                    status: defaultStatus,
                    is_static: lineForm.is_static,
                    linked_debt_id: lineForm.linked_debt_id ? Number(lineForm.linked_debt_id) : null,
                    linked_savings_pot_id: lineForm.linked_savings_pot_id ? Number(lineForm.linked_savings_pot_id) : null,
                  });
                  setModal(null);
                });
              }}
            >
              <input required placeholder="Name" value={lineForm.name} onChange={(event) => setLineForm({ ...lineForm, name: event.target.value })} />
              <input required min="0" step="0.01" type="number" placeholder="Amount" value={lineForm.amount} onChange={(event) => setLineForm({ ...lineForm, amount: event.target.value })} />
              <input min="1" max="31" type="number" placeholder="Due day" value={lineForm.due_day} onChange={(event) => setLineForm({ ...lineForm, due_day: event.target.value })} />
              {modal.type === "debt_payment" && (
                <select value={lineForm.linked_debt_id} onChange={(event) => setLineForm({ ...lineForm, linked_debt_id: event.target.value })}>
                  <option value="">No target yet</option>
                  {debtsForActiveUser.map((debt) => <option key={debt.id} value={debt.id}>{debt.name}</option>)}
                </select>
              )}
              {modal.type === "savings_contribution" && (
                <select value={lineForm.linked_savings_pot_id} onChange={(event) => setLineForm({ ...lineForm, linked_savings_pot_id: event.target.value })}>
                  <option value="">General savings</option>
                  {potsForActiveUser.map((pot) => <option key={pot.id} value={pot.id}>{pot.name}</option>)}
                </select>
              )}
              <label className="checkline"><input type="checkbox" checked={lineForm.is_static} onChange={(event) => setLineForm({ ...lineForm, is_static: event.target.checked })} /> Static / recurring</label>
              <p className="form-hint">New budget lines are currently saved as {defaultStatus}.</p>
              <button className="primary-button">Save {lineTypes.find((item) => item.id === modal.type)?.button}</button>
            </form>
          )}

          {modal.kind === "debt" && (
            <form className="modal-form" onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await api.createDebt({ user_id: activeUser, name: debtForm.name, starting_balance: Number(debtForm.starting_balance) });
                setDebtForm({ name: "", starting_balance: "" });
                setModal(null);
              });
            }}>
              <input required placeholder="Name" value={debtForm.name} onChange={(event) => setDebtForm({ ...debtForm, name: event.target.value })} />
              <input required min="0" step="0.01" type="number" placeholder="Balance" value={debtForm.starting_balance} onChange={(event) => setDebtForm({ ...debtForm, starting_balance: event.target.value })} />
              <button className="primary-button">Save debt</button>
            </form>
          )}

          {modal.kind === "saving" && (
            <form className="modal-form" onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await api.createSavingsPot({ user_id: activeUser, name: potForm.name, starting_balance: Number(potForm.starting_balance || 0), target_amount: potForm.target_amount ? Number(potForm.target_amount) : null });
                setPotForm({ name: "", starting_balance: "", target_amount: "" });
                setModal(null);
              });
            }}>
              <input required placeholder="Name" value={potForm.name} onChange={(event) => setPotForm({ ...potForm, name: event.target.value })} />
              <input min="0" step="0.01" type="number" placeholder="Balance" value={potForm.starting_balance} onChange={(event) => setPotForm({ ...potForm, starting_balance: event.target.value })} />
              <input min="0" step="0.01" type="number" placeholder="Target" value={potForm.target_amount} onChange={(event) => setPotForm({ ...potForm, target_amount: event.target.value })} />
              <button className="primary-button">Save pot</button>
            </form>
          )}

          {modal.kind === "profile" && (
            <form className="modal-form" onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await api.updateUser(modal.userId, {
                  name: profileForm.name,
                  icon: profileForm.icon,
                  salary: Number(profileForm.salary || 0),
                });
                setModal(null);
              }, "Profile saved");
            }}>
              <input required placeholder="Name" value={profileForm.name} onChange={(event) => setProfileForm({ ...profileForm, name: event.target.value })} />
              <input maxLength={8} placeholder="Icon or initials" value={profileForm.icon} onChange={(event) => setProfileForm({ ...profileForm, icon: event.target.value })} />
              <input min="0" step="0.01" type="number" placeholder="Salary" value={profileForm.salary} onChange={(event) => setProfileForm({ ...profileForm, salary: event.target.value })} />
              <p className="form-hint">Salary is stored on the profile for planning; monthly income lines still control this month's budget totals.</p>
              <button className="primary-button">Save profile</button>
              <button
                type="button"
                className="danger-text-button"
                onClick={() => void run(async () => {
                  await api.deleteUser(modal.userId);
                  setModal(null);
                  setView("combined");
                }, "Family member deleted")}
              >
                Delete profile
              </button>
            </form>
          )}

          {modal.kind === "user" && (
            <form className="modal-form" onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                const created = await api.createUser({ name: userForm.name, icon: userForm.icon, salary: Number(userForm.salary || 0) });
                setUserForm({ name: "", icon: "", salary: "" });
                setModal(null);
                setView(created.id);
              }, "Family member added");
            }}>
              <input required placeholder="Name" value={userForm.name} onChange={(event) => setUserForm({ ...userForm, name: event.target.value })} />
              <input maxLength={8} placeholder="Icon or initials" value={userForm.icon} onChange={(event) => setUserForm({ ...userForm, icon: event.target.value })} />
              <input min="0" step="0.01" type="number" placeholder="Salary" value={userForm.salary} onChange={(event) => setUserForm({ ...userForm, salary: event.target.value })} />
              <p className="form-hint">Everyone added here is part of the same local family budget.</p>
              <button className="primary-button">Add family member</button>
            </form>
          )}

          {modal.kind === "ai_import" && (
            <div className="modal-form" style={{ gap: "14px" }}>
              {aiImportLoading ? (
                <div style={{ textAlign: "center", padding: "30px 10px", display: "grid", gap: "16px", justifyItems: "center" }}>
                  <div className="spinner" style={{
                    width: "40px",
                    height: "40px",
                    border: "4px solid var(--border)",
                    borderTopColor: "var(--accent)",
                    borderRadius: "50%",
                    animation: "spin 1s linear infinite"
                  }}></div>
                  <style>{`
                    @keyframes spin {
                      to { transform: rotate(360deg); }
                    }
                  `}</style>
                  <strong style={{ fontSize: "16px", color: "var(--text)" }}>{aiImportStatus}</strong>
                  <p style={{ color: "var(--muted)", margin: 0, fontSize: "13px" }}>Please wait while the document is being processed.</p>
                </div>
              ) : (
                <div className="settings-list" style={{ gap: "12px" }}>
                  {(!aiConfig?.configured && !aiApiKey.trim()) && (
                    <div className="target-badge" style={{ display: "block", background: "rgba(245, 124, 0, 0.08)", borderColor: "rgba(245, 124, 0, 0.4)", color: "#b25e00", borderRadius: "8px", padding: "12px", marginBottom: "4px" }}>
                      <strong>⚠️ API Key Required:</strong>
                      <p style={{ margin: "4px 0 0", fontSize: "12px", lineHeight: "1.4" }}>
                        Paste your Google AI API key below to upload documents. This key is stored securely in your browser.
                      </p>
                    </div>
                  )}
                  
                  {(!aiConfig?.configured) && (
                    <label className="settings-group">
                      <span style={{ fontSize: "13px", color: "var(--muted)", fontWeight: "bold" }}>Google AI Studio API Key</span>
                      <input
                        type="password"
                        placeholder="Paste your key here"
                        value={aiApiKey}
                        onChange={(event) => {
                          const val = event.target.value;
                          setAiApiKey(val);
                          if (val.trim()) {
                            localStorage.setItem("budget-tracker-ai-api-key", val.trim());
                          } else {
                            localStorage.removeItem("budget-tracker-ai-api-key");
                          }
                        }}
                        autoComplete="off"
                        style={{ width: "100%" }}
                      />
                    </label>
                  )}

                  <label className="upload-target" style={{ minHeight: "140px", flexDirection: "column", background: "var(--panel-soft)" }}>
                    <FileSearch size={32} style={{ marginBottom: "6px" }} />
                    <span style={{ fontWeight: "bold", textAlign: "center" }}>Select or drop a bill, receipt, or statement</span>
                    <span style={{ fontSize: "12px", color: "var(--muted)", marginTop: "4px" }}>Supports PDF, JPG, PNG, WEBP (Max 10MB)</span>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.pdf"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (file) {
                          void startAiImport(file);
                        }
                      }}
                    />
                  </label>
                  
                  <button className="icon-text" style={{ justifyContent: "center", minHeight: "42px", marginTop: "4px" }} onClick={() => setModal(null)}>Cancel</button>
                </div>
              )}
            </div>
          )}
        </EntryModal>
      )}

      {showSettings && (
        <EntryModal title="Settings" onClose={() => setShowSettings(false)}>
          <div className="settings-list">
            <div className="settings-group">
              <h3>Profiles</h3>
              {users.map((user) => (
                <button
                  className="settings-profile"
                  key={user.id}
                  onClick={() => {
                    setShowSettings(false);
                    openModal({ kind: "profile", userId: user.id });
                  }}
                >
                  <span className="avatar">{userIcon(users, user.id)}</span>
                  <strong>{userName(users, user.id)}</strong>
                </button>
              ))}
              <button
                className="settings-profile"
                onClick={() => {
                  setShowSettings(false);
                  openModal({ kind: "user" });
                }}
              >
                <span className="avatar"><CircleUserRound size={16} /></span>
                <strong>Add family member</strong>
              </button>
            </div>
            <label className="setting-row">
              <span>New budget lines default to paid</span>
              <input type="checkbox" checked={defaultStatus === "paid"} onChange={(event) => setDefaultStatus(event.target.checked ? "paid" : "planned")} />
            </label>
            <label className="setting-row">
              <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
              <button className="icon-text" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
                {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
                Toggle
              </button>
            </label>
            <button className="setting-row setting-action" disabled={busy} onClick={() => void loadAll()}>
              <span>Refresh data</span>
              <RefreshCw size={16} />
            </button>
            <div className="settings-group">
              <h3>Database backup</h3>
              <button className="setting-row setting-action" disabled={busy} onClick={() => void exportDatabase()}>
                <span>Export database</span>
                <Download size={16} />
              </button>
              <button className="setting-row setting-action" disabled={busy} onClick={() => importInputRef.current?.click()}>
                <span>Import database</span>
                <Upload size={16} />
              </button>
              <input
                ref={importInputRef}
                className="hidden-file-input"
                type="file"
                accept=".db,.sqlite,.sqlite3"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) {
                    void importDatabase(file);
                  }
                }}
              />
              <p className="form-hint">Imports only replace this app's SQLite budget database. Attachment files are not included in the database export.</p>
            </div>
            <div className="settings-group">
              <h3>AI import</h3>
              <input
                type="password"
                placeholder={aiConfig?.configured ? "Google AI key configured in HA" : "Paste Google AI key for this session"}
                value={aiApiKey}
                onChange={(event) => {
                  const val = event.target.value;
                  setAiApiKey(val);
                  if (val.trim()) {
                    localStorage.setItem("budget-tracker-ai-api-key", val.trim());
                  } else {
                    localStorage.removeItem("budget-tracker-ai-api-key");
                  }
                }}
                autoComplete="off"
              />
              <label className="settings-field">
                <span>Model</span>
                <select
                  value={aiConfig?.models.some((modelOption) => modelOption.id === aiModel) ? aiModel : "custom"}
                  onChange={(event) => {
                    if (event.target.value === "custom") {
                      setAiModel("");
                      return;
                    }
                    setAiModel(event.target.value);
                  }}
                >
                  {(aiConfig?.models ?? []).map((modelOption) => (
                    <option key={modelOption.id} value={modelOption.id}>{modelOption.label}</option>
                  ))}
                  <option value="custom">Custom model id</option>
                </select>
              </label>
              {(!aiConfig?.models.some((modelOption) => modelOption.id === aiModel) || !aiModel) && (
                <label className="settings-field">
                  <span>Custom model id</span>
                  <input
                    value={aiModel}
                    onChange={(event) => setAiModel(event.target.value)}
                    placeholder={aiConfig?.model || "gemma-4-26b-a4b-it"}
                    autoComplete="off"
                  />
                </label>
              )}
              <div className="model-limit-list">
                {(aiConfig?.models ?? []).map((modelOption) => (
                  <div className={`model-limit ${modelOption.id === aiModel ? "active" : ""}`} key={modelOption.id}>
                    <strong>{modelOption.label}</strong>
                    <span>{modelOption.free_tier}</span>
                    <small>{modelOption.note}</small>
                  </div>
                ))}
              </div>
              <p className="form-hint">{aiConfig?.rate_limit_note || "Google API limits vary by project, model, and tier. Check Google AI Studio for live free-tier quotas."}</p>
              <button className="setting-row setting-action" disabled={busy} onClick={() => aiImportInputRef.current?.click()}>
                <span>Upload bill, receipt, or statement</span>
                <FileSearch size={16} />
              </button>
              <input
                ref={aiImportInputRef}
                className="hidden-file-input"
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) {
                    void previewAiImport(file);
                  }
                }}
              />
              <p className="form-hint">One AI request is used per document. Results are reviewed before anything is added.</p>
            </div>
          </div>
        </EntryModal>
      )}

      {aiReview && (
        <EntryModal title="Review import" onClose={() => setAiReview(null)}>
          <div className="ai-review">
            <p className="form-hint">{aiReview.documentType} / {aiReview.summary || "Review the proposed lines before adding them."}</p>
            <div className="ai-review-list">
              {aiReview.proposals.map((proposal, index) => (
                <div className="ai-review-row" key={`${proposal.source_text}-${index}`}>
                  <div className="ai-review-head">
                    <select
                      value={proposal.action}
                      onChange={(event) => {
                        const proposals = [...aiReview.proposals];
                        proposals[index] = { ...proposal, action: event.target.value as AiImportProposal["action"] };
                        setAiReview({ ...aiReview, proposals });
                      }}
                    >
                      <option value="create">Add</option>
                      <option value="update_existing">Update match</option>
                      <option value="ignore">Skip</option>
                    </select>
                    <button
                      className="icon-button danger"
                      title="Remove"
                      onClick={() => setAiReview({ ...aiReview, proposals: aiReview.proposals.filter((_, rowIndex) => rowIndex !== index) })}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <div className="ai-review-grid">
                    <select
                      value={proposal.item_kind}
                      onChange={(event) => {
                        const itemKind = event.target.value as AiImportProposal["item_kind"];
                        const proposals = [...aiReview.proposals];
                        proposals[index] = { ...proposal, item_kind: itemKind, type: itemKind === "income" ? null : proposal.type || "expense" };
                        setAiReview({ ...aiReview, proposals });
                      }}
                    >
                      <option value="budget">Budget line</option>
                      <option value="income">Income</option>
                    </select>
                    <select
                      value={proposal.user_id}
                      onChange={(event) => {
                        const proposals = [...aiReview.proposals];
                        proposals[index] = { ...proposal, user_id: event.target.value };
                        setAiReview({ ...aiReview, proposals });
                      }}
                    >
                      {users.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
                    </select>
                    {proposal.item_kind === "budget" && (
                      <select
                        value={proposal.type || "expense"}
                        onChange={(event) => {
                          const proposals = [...aiReview.proposals];
                          proposals[index] = { ...proposal, type: event.target.value as BudgetLineType };
                          setAiReview({ ...aiReview, proposals });
                        }}
                      >
                        {lineTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                      </select>
                    )}
                    <input
                      value={proposal.name}
                      onChange={(event) => {
                        const proposals = [...aiReview.proposals];
                        proposals[index] = { ...proposal, name: event.target.value };
                        setAiReview({ ...aiReview, proposals });
                      }}
                    />
                    <input
                      min="0"
                      step="0.01"
                      type="number"
                      value={proposal.amount}
                      onChange={(event) => {
                        const proposals = [...aiReview.proposals];
                        proposals[index] = { ...proposal, amount: Number(event.target.value || 0) };
                        setAiReview({ ...aiReview, proposals });
                      }}
                    />
                    {proposal.item_kind === "budget" && (
                      <select
                        value={proposal.status}
                        onChange={(event) => {
                          const proposals = [...aiReview.proposals];
                          proposals[index] = { ...proposal, status: event.target.value as BudgetLineStatus };
                          setAiReview({ ...aiReview, proposals });
                        }}
                      >
                        <option value="paid">Paid</option>
                        <option value="planned">Planned</option>
                      </select>
                    )}
                    {proposal.item_kind === "budget" && proposal.type === "debt_payment" && (
                      <select
                        value={proposal.linked_debt_id ?? ""}
                        onChange={(event) => {
                          const proposals = [...aiReview.proposals];
                          proposals[index] = { ...proposal, linked_debt_id: event.target.value ? Number(event.target.value) : null };
                          setAiReview({ ...aiReview, proposals });
                        }}
                      >
                        <option value="">No debt link</option>
                        {debts.filter((debt) => debt.user_id === proposal.user_id).map((debt) => <option key={debt.id} value={debt.id}>{debt.name}</option>)}
                      </select>
                    )}
                    {proposal.item_kind === "budget" && proposal.type === "savings_contribution" && (
                      <select
                        value={proposal.linked_savings_pot_id ?? ""}
                        onChange={(event) => {
                          const proposals = [...aiReview.proposals];
                          proposals[index] = { ...proposal, linked_savings_pot_id: event.target.value ? Number(event.target.value) : null };
                          setAiReview({ ...aiReview, proposals });
                        }}
                      >
                        <option value="">No savings link</option>
                        {pots.filter((pot) => pot.user_id === proposal.user_id).map((pot) => <option key={pot.id} value={pot.id}>{pot.name}</option>)}
                      </select>
                    )}
                  </div>
                  <p className="form-hint">{Math.round((proposal.confidence || 0) * 100)}% / {proposal.reasoning || proposal.source_text}</p>
                  {(() => {
                    if (proposal.item_kind === "income") {
                      const duplicate = income.find((line) => line.name.toLowerCase() === proposal.name.toLowerCase());
                      if (duplicate) {
                        return <p className="form-hint warning-hint" style={{ color: "#b25e00", margin: "4px 0 0" }}>⚠️ An income line named "{duplicate.name}" ({money(duplicate.amount)}) already exists for this month.</p>;
                      }
                    } else {
                      if (proposal.action === "update_existing" && proposal.match_existing_line_id) {
                        const matched = lines.find((line) => line.id === proposal.match_existing_line_id);
                        if (matched) {
                          return <p className="form-hint match-hint" style={{ color: "#205c4f", margin: "4px 0 0" }}>🔄 Will update existing line: "{matched.name}" ({money(matched.amount)})</p>;
                        }
                      }
                      const duplicate = lines.find((line) => line.name.toLowerCase() === proposal.name.toLowerCase() && line.id !== proposal.match_existing_line_id);
                      if (duplicate) {
                        return <p className="form-hint warning-hint" style={{ color: "#b25e00", margin: "4px 0 0" }}>⚠️ A budget line named "{duplicate.name}" ({money(duplicate.amount)}) already exists for this month.</p>;
                      }
                    }
                    return null;
                  })()}
                </div>
              ))}
            </div>
            <div className="line-controls">
              <button className="primary-button" disabled={busy || aiReview.proposals.every((proposal) => proposal.action === "ignore")} onClick={() => void applyAiImport()}>
                Apply import
              </button>
              <button className="icon-text" disabled={busy} onClick={() => setAiReview(null)}>Cancel</button>
            </div>
          </div>
        </EntryModal>
      )}

      {incomeOpen && (
        <EntryModal title="Income" onClose={() => setIncomeOpen(false)}>
          <div className="income-manager">
            <div className="income-manager-hero">
              <span>Monthly income</span>
              <strong>{money(summary.totals.income)}</strong>
              <p>{income.length ? `${income.length} income line${income.length === 1 ? "" : "s"}` : "No income yet"}</p>
            </div>
            <IncomeList income={income} users={users} canEdit={canEdit} run={run} />
            <button className="primary-button" onClick={() => {
              setIncomeOpen(false);
              openModal({ kind: "income" });
            }}>Add income or bonus</button>
          </div>
        </EntryModal>
      )}

      {attachmentLine && <AttachmentDrawer line={attachmentLine} canEdit={canEdit} onClose={() => setAttachmentLine(null)} onChanged={loadAll} />}
    </main>
  );
}

function UserSwitcher({ users, view, onChange }: { users: User[]; view: ViewSlug; onChange: (view: ViewSlug) => void }) {
  const options: { id: ViewSlug; label: string; icon: string }[] = users.map((user) => ({
    id: user.id,
    label: user.name,
    icon: userIcon(users, user.id),
  }));
  options.push({ id: "combined", label: "Combined", icon: "H" });

  return (
    <div className="user-switcher" aria-label="Active view">
      {options.map((option) => (
        <button key={option.id} className={view === option.id ? "active" : ""} onClick={() => onChange(option.id)}>
          <span>{option.icon}</span>
          {option.label}
        </button>
      ))}
    </div>
  );
}

function CombinedOverview({ users, summary, income, lines, debts, pots, heroDrilldown, setHeroDrilldown }: {
  users: User[];
  summary: Summary;
  income: IncomeLine[];
  lines: BudgetLine[];
  debts: Debt[];
  pots: SavingsPot[];
  heroDrilldown: keyof Summary["totals"] | "debt_balance" | "savings_balance" | null;
  setHeroDrilldown: (value: keyof Summary["totals"] | "debt_balance" | "savings_balance" | null) => void;
}) {
  const byUserSavings = (userId: UserSlug) => pots.filter((pot) => pot.user_id === userId).reduce((total, pot) => total + pot.current_balance, 0);
  const paidSavingsLines = lines.filter((line) => line.type === "savings_contribution" && line.status === "paid");
  const byUserSavingsThisMonth = (userId: UserSlug) => paidSavingsLines.filter((line) => line.user_id === userId).reduce((total, line) => total + line.amount, 0);
  const savingsActivityByPot = paidSavingsLines.reduce<Record<number, number>>((totals, line) => {
    if (line.linked_savings_pot_id) {
      totals[line.linked_savings_pot_id] = (totals[line.linked_savings_pot_id] ?? 0) + line.amount;
    }
    return totals;
  }, {});
  const title =
    heroDrilldown === "income" ? "Income breakdown"
    : heroDrilldown === "outgoings" ? "Household outgoings"
    : heroDrilldown === "savings_balance" ? "Savings breakdown"
    : heroDrilldown === "leftover" ? "Leftover split"
    : "Household overview";

  return (
    <div className="combined-grid">
      <section className="panel wide-combined combined-focus">
        <PanelHeader
          title={title}
          action={heroDrilldown && <button className="icon-text" onClick={() => setHeroDrilldown(null)}><X size={16} /> Close</button>}
        />
        {!heroDrilldown && (
          <div className="hero-prompt">
            <strong>Tap a top card to inspect the household numbers.</strong>
            <span>Income shows each income list, Outgoings shows every line, Savings opens pots and contributions, and Leftover compares each person.</span>
          </div>
        )}
        {heroDrilldown === "income" && (
          <IncomeList income={income} users={users} canEdit={false} />
        )}
        {heroDrilldown === "outgoings" && (
          <ReadOnlyLineList lines={lines} debts={debts} pots={pots} users={users} />
        )}
        {heroDrilldown === "savings_balance" && (
          <div className="drill-stack">
            <div className="person-total-list">
              {users.map((user) => (
                <PersonTotalCard
                  key={user.id}
                  tone="saving"
                  users={users}
                  userId={user.id}
                  label="Savings"
                  name={`${userName(users, user.id)} overall savings`}
                  value={byUserSavings(user.id)}
                  subvalue={`+${money(byUserSavingsThisMonth(user.id))} this month`}
                />
              ))}
            </div>
            <BalanceLineList rows={pots} users={users} canEdit={false} kind="saving" monthlyActivity={savingsActivityByPot} />
          </div>
        )}
        {heroDrilldown === "leftover" && (
          <div className="person-total-list">
            {users.map((user) => {
              const totals = summary.by_user?.[user.id];
              const salary = user.salary ?? 0;
              return (
                <PersonTotalCard
                  key={user.id}
                  tone={totals && totals.leftover < 0 ? "debt" : "saving"}
                  users={users}
                  userId={user.id}
                  label="Leftover"
                  name={`${userName(users, user.id)} spare money`}
                  value={totals?.leftover ?? 0}
                  subvalue={`Income ${money(totals?.income ?? 0)} / Outgoings ${money(totals?.outgoings ?? 0)}${salary > 0 ? ` / Salary ${money(salary)}` : ""}`}
                />
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function FirstRunSetup({ userForm, setUserForm, busy, onSubmit }: {
  userForm: { name: string; icon: string; salary: string };
  setUserForm: (value: { name: string; icon: string; salary: string }) => void;
  busy: boolean;
  onSubmit: () => void;
}) {
  return (
    <section className="panel setup-panel">
      <div className="setup-copy">
        <CircleUserRound size={22} />
        <div>
          <h2>Create your first family member</h2>
          <p>Add a profile to start tracking income, bills, savings, debts, and the combined household view.</p>
        </div>
      </div>
      <form className="setup-form" onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}>
        <input required placeholder="Name" value={userForm.name} onChange={(event) => setUserForm({ ...userForm, name: event.target.value })} />
        <input maxLength={8} placeholder="Icon or initials" value={userForm.icon} onChange={(event) => setUserForm({ ...userForm, icon: event.target.value })} />
        <input min="0" step="0.01" type="number" placeholder="Salary" value={userForm.salary} onChange={(event) => setUserForm({ ...userForm, salary: event.target.value })} />
        <button className="primary-button" disabled={busy}>Create profile</button>
      </form>
    </section>
  );
}

function PersonTotalCard({ users, userId, label, name, value, subvalue, tone }: {
  users: User[];
  userId: UserSlug;
  label: string;
  name: string;
  value: number;
  subvalue?: string;
  tone: "saving" | "debt";
}) {
  return (
    <article className={`line-card person-total-card ${tone}`}>
      <div className="line-main read-only">
        <span className="line-chip-row">
          <span className="line-user">{userIcon(users, userId)}</span>
          <span className="line-type">{label}</span>
        </span>
        <strong className="line-name">
          {name}
          {subvalue && <span className="line-subvalue">{subvalue}</span>}
        </strong>
        <b className="line-amount">{money(value)}</b>
      </div>
    </article>
  );
}

function BudgetLineTable({ lines, debts, pots, users, canEdit, run, onAttachments }: {
  lines: BudgetLine[];
  debts: Debt[];
  pots: SavingsPot[];
  users: User[];
  canEdit: boolean;
  run: (action: () => Promise<unknown>, done?: string) => Promise<void>;
  onAttachments: (line: BudgetLine) => void;
}) {
  const [expandedLineId, setExpandedLineId] = useState<number | null>(null);

  return (
    <div className="line-list">
          <div className="line-list-head">
            <span>User / Type</span>
            <span>Name</span>
            <span>Amount</span>
          </div>
      {lines.map((line) => {
        const expanded = expandedLineId === line.id;
        return (
          <article className={`line-card ${line.type} ${expanded ? "expanded" : ""}`} key={line.id}>
            <button className="line-main" onClick={() => setExpandedLineId(expanded ? null : line.id)}>
              <span className="line-chip-row">
                <span className="line-user">{userName(users, line.user_id)}</span>
                <span className="line-type">{lineTypes.find((item) => item.id === line.type)?.button}</span>
              </span>
              <strong className="line-name">{line.name}</strong>
              <b className="line-amount">{money(line.amount)}</b>
            </button>
            {expanded && (
              <div className="line-details">
                <div className="detail-grid">
                  {canEdit ? (
                    <>
                      <label>Name<input defaultValue={line.name} onBlur={(event) => void run(() => api.updateBudgetLine(line.id, { name: event.target.value }))} /></label>
                      <label>Amount<input type="number" step="0.01" defaultValue={line.amount} onBlur={(event) => void run(() => api.updateBudgetLine(line.id, { amount: Number(event.target.value) }))} /></label>
                      <label>Due day<input type="number" min="1" max="31" defaultValue={line.due_day ?? ""} onBlur={(event) => void run(() => api.updateBudgetLine(line.id, { due_day: event.target.value ? Number(event.target.value) : null }))} /></label>
                    </>
                  ) : null}
                  <div><span>Target</span><strong>{targetName(line, debts, pots) || "None"}</strong></div>
                  <div><span>Status</span><strong>{line.status}</strong></div>
                  <div><span>Recurring</span><strong>{line.is_static ? "Yes" : "No"}</strong></div>
                </div>
                {canEdit && (
                  <div className="line-controls">
                    {line.type === "debt_payment" && (
                      <select className={line.linked_debt_id ? "" : "needs-target-select"} value={line.linked_debt_id ?? ""} onChange={(event) => void run(() => api.updateBudgetLine(line.id, { linked_debt_id: event.target.value ? Number(event.target.value) : null }))}>
                        <option value="">Needs target</option>
                        {debts.filter((debt) => debt.user_id === line.user_id).map((debt) => <option key={debt.id} value={debt.id}>{debt.name}</option>)}
                      </select>
                    )}
                    {line.type === "savings_contribution" && (
                      <select value={line.linked_savings_pot_id ?? ""} onChange={(event) => void run(() => api.updateBudgetLine(line.id, { linked_savings_pot_id: event.target.value ? Number(event.target.value) : null }))}>
                        <option value="">General savings</option>
                        {pots.filter((pot) => pot.user_id === line.user_id).map((pot) => <option key={pot.id} value={pot.id}>{pot.name}</option>)}
                      </select>
                    )}
                    {line.type === "debt_payment" && line.linked_debt_id === null && <span className="target-badge">Needs target</span>}
                    <button className={`pill ${line.status}`} onClick={() => void run(() => line.status === "paid" ? api.markPlanned(line.id) : api.markPaid(line.id))}>
                      {line.status === "paid" ? "Paid" : "Planned"}
                    </button>
                    <label className="checkline"><input type="checkbox" checked={line.is_static} onChange={(event) => void run(() => api.updateBudgetLine(line.id, { is_static: event.target.checked }))} /> Static / recurring</label>
                    <button className="icon-button" title="Attachments" onClick={() => onAttachments(line)}><Paperclip size={16} /><span>{line.attachment_count}</span></button>
                    <button className="icon-button danger" title="Delete" onClick={() => void run(() => api.deleteBudgetLine(line.id), "Deleted")}><Trash2 size={16} /></button>
                  </div>
                )}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ReadOnlyLineList({ lines, debts, pots, users }: { lines: BudgetLine[]; debts: Debt[]; pots: SavingsPot[]; users: User[] }) {
  return (
    <div className="line-list read-only-lines">
      <div className="line-list-head">
        <span>User / Type</span>
        <span>Name</span>
        <span>Amount</span>
      </div>
      {lines.length === 0 && <div className="empty-state">No lines to show yet.</div>}
      {lines.map((line) => {
        const target = targetName(line, debts, pots);
        const targetSubvalue = line.type === "debt_payment" && line.linked_debt_id === null ? "" : line.type === "debt_payment" || line.type === "savings_contribution" ? target : "";
        return (
          <article className={`line-card ${line.type}`} key={line.id}>
            <div className="line-main read-only">
              <span className="line-chip-row">
                <span className="line-user">{userName(users, line.user_id)}</span>
                <span className="line-type">{lineTypes.find((item) => item.id === line.type)?.button}</span>
              </span>
              <strong className="line-name">
                {line.name}
                {targetSubvalue && <span className="line-subvalue">{targetSubvalue}</span>}
                {line.type === "debt_payment" && line.linked_debt_id === null && <span className="target-badge inline">Needs target</span>}
              </strong>
              <b className="line-amount">{money(line.amount)}</b>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function IncomeList({ income, users, canEdit, run }: {
  income: IncomeLine[];
  users: User[];
  canEdit: boolean;
  run?: (action: () => Promise<unknown>, done?: string) => Promise<void>;
}) {
  return (
    <div className="income-list">
      {income.length === 0 && <div className="empty-state">No income lines yet.</div>}
      {income.map((row) => (
        <article className="income-row" key={row.id}>
          <div className="income-row-main">
            <span className="avatar">{userIcon(users, row.user_id)}</span>
            <div>
              {canEdit && run ? (
                <input defaultValue={row.name} aria-label="Income name" onBlur={(event) => void run(() => api.updateIncomeLine(row.id, { name: event.target.value }))} />
              ) : (
                <strong>{row.name}</strong>
              )}
              <p>{userName(users, row.user_id)}{row.is_static ? " / Recurring" : ""}</p>
            </div>
          </div>
          <div className="income-row-side">
            {canEdit && run ? (
              <input className="money-input" type="number" step="0.01" defaultValue={row.amount} aria-label="Income amount" onBlur={(event) => void run(() => api.updateIncomeLine(row.id, { amount: Number(event.target.value) }))} />
            ) : (
              <b>{money(row.amount)}</b>
            )}
            {canEdit && run && (
              <div className="income-row-actions">
                <label className="checkline"><input type="checkbox" checked={row.is_static} onChange={(event) => void run(() => api.updateIncomeLine(row.id, { is_static: event.target.checked }))} /> Static</label>
                <button className="icon-button danger" title="Delete" onClick={() => void run(() => api.deleteIncomeLine(row.id), "Deleted")}><Trash2 size={16} /></button>
              </div>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}

function Metric({ icon, label, value, emphasis, onClick }: { icon: ReactNode; label: string; value: number; emphasis?: "good" | "bad"; onClick?: () => void }) {
  const Component = onClick ? "button" : "article";
  return (
    <Component className={`metric ${emphasis ?? ""} ${onClick ? "clickable" : ""}`} onClick={onClick}>
      <span>{icon}</span>
      <div>
        <p>{label}</p>
        <strong>{money(value)}</strong>
      </div>
    </Component>
  );
}

function PanelHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="panel-header">
      <h2>{title}</h2>
      {action}
    </div>
  );
}

function CompactSummary({ rows }: { rows: [string, string][] }) {
  return (
    <div className="compact-summary">
      {rows.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function DataTable({ children }: { children: ReactNode }) {
  return <div className="table-wrap"><table>{children}</table></div>;
}

function BalanceLineList({ rows, users, canEdit, kind, monthlyActivity = {}, onPatch, onDelete }: {
  rows: Debt[] | SavingsPot[];
  users: User[];
  canEdit: boolean;
  kind: "debt" | "saving";
  monthlyActivity?: Record<number, number>;
  onPatch?: (id: number, payload: unknown) => void;
  onDelete?: (id: number) => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div className="line-list balance-line-list">
      <div className="line-list-head">
        <span>User / {kind === "debt" ? "Debt" : "Pot"}</span>
        <span>Name</span>
        <span>{kind === "debt" ? "Current" : "Saved"}</span>
      </div>
      {rows.length === 0 && <div className="empty-state">Nothing here yet.</div>}
      {rows.map((row) => {
        const current = row.current_balance;
        const progress = "paid_amount" in row ? row.paid_amount : row.contributed_amount;
        const expanded = expandedId === row.id;
        const activity = monthlyActivity[row.id] ?? 0;
        return (
          <article className={`line-card entity-card ${kind} ${expanded ? "expanded" : ""}`} key={row.id}>
            <button className="line-main" onClick={() => setExpandedId(expanded ? null : row.id)}>
              <span className="line-chip-row">
                <span className="line-user">{userName(users, row.user_id)}</span>
                <span className="line-type">{kind === "debt" ? "Debt" : "Savings"}</span>
              </span>
              <strong className="line-name">
                {row.name}
                {activity > 0 && <span className="line-subvalue">+{money(activity)} this month</span>}
              </strong>
              <b className="line-amount">{money(current)}</b>
            </button>
            {expanded && (
              <div className="line-details">
                <div className="detail-grid">
                  {canEdit && onPatch ? (
                    <>
                      <label>Name<input defaultValue={row.name} onBlur={(event) => onPatch(row.id, { name: event.target.value })} /></label>
                      <label>Starting balance<input type="number" step="0.01" defaultValue={row.starting_balance} onBlur={(event) => onPatch(row.id, { starting_balance: Number(event.target.value) })} /></label>
                      {kind === "saving" && "target_amount" in row && (
                        <label>Target<input type="number" step="0.01" defaultValue={row.target_amount ?? ""} onBlur={(event) => onPatch(row.id, { target_amount: event.target.value ? Number(event.target.value) : null })} /></label>
                      )}
                    </>
                  ) : null}
                  <div><span>{kind === "debt" ? "Current balance" : "Saved balance"}</span><strong>{money(current)}</strong></div>
                  <div><span>{kind === "debt" ? "Paid down" : "Added"}</span><strong>{money(progress)}</strong></div>
                  {activity > 0 && <div><span>This month</span><strong>+{money(activity)}</strong></div>}
                  {"target_amount" in row && <div><span>Target</span><strong>{row.target_amount ? money(row.target_amount) : "None"}</strong></div>}
                </div>
                {canEdit && onDelete && (
                  <div className="line-controls">
                    <button className="icon-button danger" title="Delete" onClick={() => onDelete(row.id)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function EntryModal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <section className="modal-card" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button className="icon-button" title="Close" onClick={onClose}><X size={18} /></button>
        </header>
        {children}
      </section>
    </div>
  );
}

function AttachmentDrawer({ line, canEdit, onClose, onChanged }: { line: BudgetLine; canEdit: boolean; onClose: () => void; onChanged: () => void }) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setAttachments(await api.attachments(line.id));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load attachments");
    }
  }

  useEffect(() => {
    void load();
  }, [line.id]);

  return (
    <div className="drawer-backdrop">
      <aside className="drawer">
        <header>
          <div>
            <h2>{line.name}</h2>
            <p>Attachments</p>
          </div>
          <button className="icon-button" title="Close" onClick={onClose}><X size={18} /></button>
        </header>
        {error && <div className="notice">{error}</div>}
        {canEdit && (
          <label className="upload-target">
            <FileUp size={20} />
            <span>Upload</span>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                void api.uploadAttachment(line.id, file)
                  .then(load)
                  .then(onChanged)
                  .catch((caught) => setError(caught instanceof Error ? caught.message : "Upload failed"));
              }}
            />
          </label>
        )}
        <div className="attachment-list">
          {attachments.map((attachment) => (
            <div className="attachment-row" key={attachment.id}>
              <a href={api.attachmentDownloadUrl(attachment.id)} target="_blank" rel="noreferrer">{attachment.original_filename}</a>
              <span>{Math.ceil(attachment.size_bytes / 1024)} KB</span>
              {canEdit && <button className="icon-button danger" title="Delete" onClick={() => void api.deleteAttachment(attachment.id).then(load).then(onChanged)}><Trash2 size={16} /></button>}
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
