"""
All limits and policies in one place. The stop rule numbers live here so the
tests, the agent and the report all quote the same values.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Model -----------------------------------------------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
TEMPERATURE = 0.0  # reproducible evals

# --- Stop rule (Task 2.1) -------------------------------------------------
MAX_MODEL_CALLS = 15        # hard cap on LLM calls per run -> ModelCallLimitMiddleware(run_limit=...)
MAX_TOOL_CALLS = 25         # hard cap on tool calls per run -> ToolCallLimitMiddleware
MAX_WRITES_PER_RUN = 10     # policy cap on write tools per run (injection blast-radius limit)
MAX_REPEATED_CALL = 2       # same tool + same args more than this = loop -> stop
MAX_COST_USD = 0.05         # per-run budget; tracked from token usage

# --- Retries (Task 2.5) ---------------------------------------------------
MAX_TOOL_RETRIES = 2        # only for TOOL_UNAVAILABLE / TIMEOUT
TOOL_TIMEOUT_SECONDS = 5

# --- Human checkpoint (Task 2.4) -------------------------------------------
# Every write tool interrupts and waits for a decision.
# send_reply can also be edited by the human before it goes out.
CHECKPOINT_POLICY = {
    "apply_label": ["approve", "reject"],
    "archive_email": ["approve", "reject"],
    "draft_reply": ["approve", "edit", "reject"],
    "send_reply": ["approve", "edit", "reject"],
}

# --- Sandbox ---------------------------------------------------------------
SANDBOX_DB = os.getenv("SANDBOX_DB", "sandbox/mailbox.db")
