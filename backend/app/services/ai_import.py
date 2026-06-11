import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import get_settings


ALLOWED_AI_IMPORT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def validate_ai_import_file(file: UploadFile, size_bytes: int) -> str:
    suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    mime_type = ALLOWED_AI_IMPORT_TYPES.get(suffix)
    if mime_type is None:
        raise HTTPException(status_code=400, detail="Upload must be a PDF or image")
    if file.content_type != mime_type:
        raise HTTPException(status_code=400, detail="File MIME type does not match its extension")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(status_code=413, detail="File is too large")
    return mime_type


def build_import_prompt(period: str, view: str, context: dict[str, Any]) -> str:
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    return f"""
You extract budget entries from one uploaded UK household finance document: a bill, receipt, or bank statement.

Return strict JSON only. Do not include markdown.

Current month: {period}
Current view: {view}
Known app context:
{context_json}

Output shape:
{{
  "document_type": "bill|receipt|bank_statement|unknown",
  "summary": "short plain English summary",
  "proposals": [
    {{
      "source_text": "merchant or statement text that caused this line",
      "date": "YYYY-MM-DD or null",
      "action": "create|update_existing|ignore",
      "item_kind": "budget|income",
      "user_id": "one users[].id",
      "period": "{period}",
      "type": "bill|expense|savings_contribution|debt_payment or null for income",
      "name": "short label",
      "amount": 0.0,
      "status": "paid|planned",
      "paid_date": "YYYY-MM-DD or null",
      "linked_debt_id": null,
      "linked_savings_pot_id": null,
      "match_existing_line_id": null,
      "confidence": 0.0,
      "reasoning": "one sentence"
    }}
  ]
}}

Rules:
- Create one proposal per real transaction or bill total, not per OCR line.
- Amounts are positive GBP values.
- For bank statement money out, use budget item_kind.
- For salary/refunds/money in, payslips, or salary statements, use income item_kind (do not categorize payslips under budget item_kind or bills).
- If the document is a bill with one total due, create or update one bill line.
- For utility bills (e.g. energy bills like Octopus) or recurring bills paid by Direct Debit, extract the regular monthly Direct Debit / collection payment amount rather than the closing account balance or total outstanding account balance.
- If an existing budget line looks like the same obligation, set action to update_existing and match_existing_line_id.
- A same obligation can be an approximate merchant match plus amount within £1.50. Example: existing "Water" 52 and document "North Water" 51.99 is likely the same line.
- Payments to credit cards, lenders, or names like MBNA, Barclaycard, Capital One, Amex, Mastercard, Visa are usually type debt_payment. Link to a matching debt if present.
- Transfers to savings accounts or pots are usually savings_contribution. Link to a matching savings pot if present.
- Groceries, retail, food, fuel, travel, subscriptions, and card purchases are usually expense.
- Utilities, council tax, rent, mortgage, insurance, phone, broadband are usually bill.
- If uncertain, still propose the best classification but lower confidence.
- Ignore pending balances, brought-forward balances, account numbers, sort codes, and non-transaction text.
- Never return secrets, account numbers, sort codes, full card numbers, or access tokens.
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    trimmed = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", trimmed, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        trimmed = fenced.group(1).strip()
    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI response was not valid JSON") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("proposals"), list):
        raise HTTPException(status_code=502, detail="AI response did not contain proposals")
    return parsed


def call_google_ai(api_key: str, model: str, prompt: str, mime_type: str, content: bytes) -> dict[str, Any]:
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="Google AI API key is required")
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(content).decode("ascii")}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    model_path = model if model.startswith("models/") else f"models/{model}"
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            message = error_payload.get("error", {}).get("message", "Google AI request failed")
        except Exception:
            message = "Google AI request failed"
        raise HTTPException(status_code=502, detail=message) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="Google AI request failed") from exc

    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text:
        raise HTTPException(status_code=502, detail="Google AI returned no parse result")
    return _extract_json(text)
