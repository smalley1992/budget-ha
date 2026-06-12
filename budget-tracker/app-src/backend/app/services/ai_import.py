import base64
import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import get_settings

logger = logging.getLogger("app.ai_import")

RETRYABLE_GOOGLE_STATUS_CODES = {429, 500, 502, 503, 504}
GOOGLE_AI_MAX_ATTEMPTS = 3
DEFAULT_GOOGLE_AI_MODEL = "gemma-4-26b-a4b-it"
GOOGLE_AI_MODEL_FALLBACKS = {
    "gemma-4-31b-it": ["gemma-4-26b-a4b-it"],
}
GOOGLE_AI_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


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
    logger.info(f"Validating upload file: name={file.filename}, suffix={suffix}, size={size_bytes} bytes, MIME={file.content_type}")
    if mime_type is None:
        logger.error(f"Validation failed: unsupported file type {suffix}")
        raise HTTPException(status_code=400, detail="Upload must be a PDF or image")
    if file.content_type != mime_type:
        logger.error(f"Validation failed: MIME type mismatch (ext={mime_type}, content_type={file.content_type})")
        raise HTTPException(status_code=400, detail="File MIME type does not match its extension")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        logger.error(f"Validation failed: File size {size_bytes} exceeds limit {max_bytes}")
        raise HTTPException(status_code=413, detail="File is too large")
    logger.info("Validation successful")
    return mime_type


def build_import_prompt(period: str, view: str, context: dict[str, Any]) -> str:
    logger.info(f"Building import prompt: period={period}, view={view}")
    logger.info(
        f"Context summary: {len(context.get('existing_budget_lines', []))} budget lines, "
        f"{len(context.get('users', []))} users, "
        f"{len(context.get('categories', []))} categories, "
        f"{len(context.get('debts', []))} debts, "
        f"{len(context.get('savings_pots', []))} savings pots"
    )
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
- A same obligation can be an approximate merchant match plus amount within GBP 1.50. Example: existing "Water" 52 and document "North Water" 51.99 is likely the same line.
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
    
    # 1. Try markdown code block extraction
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", trimmed, flags=re.DOTALL | re.IGNORECASE)
    if match:
        json_text = match.group(1).strip()
        try:
            parsed = json.loads(json_text)
            logger.info(f"Successfully extracted JSON from markdown block. proposals count: {len(parsed.get('proposals', []))}")
            logger.info(f"AI Response Details: document_type={parsed.get('document_type')}, summary='{parsed.get('summary')}'")
            return parsed
        except json.JSONDecodeError:
            logger.warning("Markdown block content was not valid JSON, trying curly braces fallback...")
            
    # 2. Try extracting the outer-most curly braces { ... }
    start = trimmed.find("{")
    end = trimmed.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_text = trimmed[start:end + 1]
        try:
            parsed = json.loads(json_text)
            logger.info(f"Successfully extracted JSON from outermost curly braces. proposals count: {len(parsed.get('proposals', []))}")
            logger.info(f"AI Response Details: document_type={parsed.get('document_type')}, summary='{parsed.get('summary')}'")
            return parsed
        except json.JSONDecodeError:
            logger.warning("Outermost curly braces content was not valid JSON, trying direct parsing...")

    # 3. Direct parsing fallback
    try:
        parsed = json.loads(trimmed)
        logger.info(f"Successfully parsed raw text directly as JSON. proposals count: {len(parsed.get('proposals', []))}")
        logger.info(f"AI Response Details: document_type={parsed.get('document_type')}, summary='{parsed.get('summary')}'")
        return parsed
    except json.JSONDecodeError as exc:
        logger.error(f"AI response was not valid JSON: {str(exc)}")
        logger.error(f"Raw response text was not logged because uploaded documents can contain financial data. Length: {len(trimmed)} characters.")
        raise HTTPException(status_code=502, detail="AI response was not valid JSON") from exc


def normalize_google_ai_model(model: str) -> str:
    model_id = model.strip()
    if model_id.startswith("models/"):
        model_id = model_id.removeprefix("models/")
    if not model_id:
        model_id = DEFAULT_GOOGLE_AI_MODEL
    if not GOOGLE_AI_MODEL_ID_PATTERN.fullmatch(model_id):
        logger.error("Google AI model validation failed: invalid model id.")
        raise HTTPException(status_code=400, detail="Google AI model id is invalid")
    return model_id


def _google_ai_model_attempts(model: str) -> list[str]:
    model_id = normalize_google_ai_model(model)
    attempts = [model_id]
    attempts.extend(fallback for fallback in GOOGLE_AI_MODEL_FALLBACKS.get(model_id, []) if fallback not in attempts)
    return attempts


def _call_google_ai_model(api_key: str, model: str, prompt: str, mime_type: str, content: bytes) -> dict[str, Any]:
    if not api_key.strip():
        logger.error("API key validation failed: empty API key.")
        raise HTTPException(status_code=400, detail="Google AI API key is required")
    
    logger.info(f"Preparing Google AI API request. Model: {model}, Mime: {mime_type}, Size: {len(content)} bytes")
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
    request_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    request_data = json.dumps(body).encode("utf-8")
    last_message = "Google AI request failed"

    for attempt in range(1, GOOGLE_AI_MAX_ATTEMPTS + 1):
        logger.info(f"Sending POST request to Generative Language API endpoint for model: {model} (attempt {attempt}/{GOOGLE_AI_MAX_ATTEMPTS})")
        start_time = time.time()
        request = urllib.request.Request(
            request_url,
            data=request_data,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
                elapsed = time.time() - start_time
                logger.info(f"API request completed successfully in {elapsed:.2f} seconds on attempt {attempt}.")
                break
        except urllib.error.HTTPError as exc:
            elapsed = time.time() - start_time
            try:
                error_body = exc.read().decode("utf-8")
                error_payload = json.loads(error_body)
                last_message = error_payload.get("error", {}).get("message", "Google AI request failed")
            except Exception:
                last_message = "Google AI request failed"

            retryable = exc.code in RETRYABLE_GOOGLE_STATUS_CODES and attempt < GOOGLE_AI_MAX_ATTEMPTS
            log_method = logger.warning if retryable else logger.error
            log_method(
                f"Google AI API request failed with HTTP status {exc.code} after {elapsed:.2f} seconds "
                f"on attempt {attempt}/{GOOGLE_AI_MAX_ATTEMPTS}. Error: {last_message}"
            )
            if retryable:
                time.sleep(1.5 * attempt)
                continue
            raise HTTPException(status_code=502, detail=f"{last_message} Try again in a moment.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            elapsed = time.time() - start_time
            last_message = "Google AI request failed"
            retryable = attempt < GOOGLE_AI_MAX_ATTEMPTS
            log_method = logger.warning if retryable else logger.error
            log_method(
                f"Google AI API request failed/timed out after {elapsed:.2f} seconds "
                f"on attempt {attempt}/{GOOGLE_AI_MAX_ATTEMPTS}: {str(exc)}"
            )
            if retryable:
                time.sleep(1.5 * attempt)
                continue
            raise HTTPException(status_code=502, detail="Google AI request failed. Try again in a moment.") from exc
    else:
        raise HTTPException(status_code=502, detail=f"{last_message} Try again in a moment.")

    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    # Filter out parts marked as thought/reasoning (where part.get("thought") is truthy)
    clean_parts = [part for part in parts if isinstance(part, dict) and not part.get("thought")]
    text = "".join(part.get("text", "") for part in clean_parts)
    if not text:
        logger.error("AI response content candidate parts was empty after filtering thought blocks.")
        raise HTTPException(status_code=502, detail="Google AI returned no parse result")
    
    logger.info(f"AI response candidate text size: {len(text)} characters.")
    return _extract_json(text)


def call_google_ai(api_key: str, model: str, prompt: str, mime_type: str, content: bytes) -> dict[str, Any]:
    model_attempts = _google_ai_model_attempts(model)
    last_error: HTTPException | None = None
    for index, model_id in enumerate(model_attempts):
        try:
            if index > 0:
                logger.warning(f"Retrying Google AI import with fallback model: {model_id}")
            return _call_google_ai_model(api_key, model_id, prompt, mime_type, content)
        except HTTPException as exc:
            last_error = exc
            has_fallback = index < len(model_attempts) - 1
            if not has_fallback or exc.status_code < 500:
                raise
            logger.warning(f"Google AI model {model_id} failed with status {exc.status_code}; fallback model will be tried.")
    if last_error:
        raise last_error
    raise HTTPException(status_code=502, detail="Google AI request failed")
