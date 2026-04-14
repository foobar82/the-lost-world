"""Centralised constants for the pipeline package.

All magic numbers and repeated configuration values used across pipeline
agents, utilities, and budget tracking live here.  Individual modules
should import from this file rather than defining their own copies.
"""

try:
    from .config import PIPELINE_CONFIG
except ImportError:
    # Fallback for tests that add pipeline/ directly to sys.path.
    from config import PIPELINE_CONFIG

# ── Network / Ollama ──────────────────────────────────────────────────

OLLAMA_URL: str = PIPELINE_CONFIG["ollama_url"]
OLLAMA_CHAT_MODEL: str = PIPELINE_CONFIG["local_model"]
EMBEDDING_MODEL: str = PIPELINE_CONFIG["embedding_model"]

# ── Anthropic model defaults ──────────────────────────────────────────

DEFAULT_WRITER_MODEL: str = PIPELINE_CONFIG["writer_model"]
DEFAULT_REVIEWER_MODEL: str = PIPELINE_CONFIG["reviewer_model"]

# ── Budget caps ───────────────────────────────────────────────────────

DAILY_CAP_GBP: float = PIPELINE_CONFIG["daily_budget_gbp"]
WEEKLY_CAP_GBP: float = PIPELINE_CONFIG["weekly_budget_gbp"]

# Approximate blended cost per token in GBP (input + output averaged).
COST_PER_TOKEN_GBP: float = 0.000012

# ── HTTP / subprocess timeouts ────────────────────────────────────────

HTTP_TIMEOUT_SECONDS: int = 30
# Theme agent sends all clusters in one prompt — allow extra time for the
# larger payload compared to single-item Ollama calls.
OLLAMA_THEME_TIMEOUT_SECONDS: int = 120
# Local LLM inference (llama3.1:8b with full source context) can take several
# minutes — use a dedicated, longer timeout for Ollama writer calls.
OLLAMA_WRITER_TIMEOUT_SECONDS: int = 300
DEFAULT_COMMAND_TIMEOUT_SECONDS: int = 300
PIPELINE_SCRIPT_TIMEOUT_SECONDS: int = 600
DEPLOY_SCRIPT_TIMEOUT_SECONDS: int = 600

# ── LLM token limits ─────────────────────────────────────────────────

WRITER_MAX_TOKENS: int = 4096
REVIEWER_MAX_TOKENS: int = 2048

# Conservative output-token estimates used when Ollama doesn't report
# exact counts and for dry-run budget projections.
ESTIMATED_TOKENS_PER_SUMMARY: int = 500
ESTIMATED_OUTPUT_TOKENS_WRITER: int = 500
ESTIMATED_OUTPUT_TOKENS_REVIEWER: int = 300

# ── ChromaDB ──────────────────────────────────────────────────────────

CHROMADB_MAX_RESULTS: int = 50
CLUSTER_DISTANCE_THRESHOLD: float = PIPELINE_CONFIG["cluster_distance_threshold"]
CLUSTER_DISTANCE_METRIC: str = PIPELINE_CONFIG["cluster_distance_metric"]

# ── Output truncation ─────────────────────────────────────────────────

OUTPUT_TRUNCATION_LENGTH: int = 2000

# ── Amendment process ─────────────────────────────────────────────────

# Number of distinct tasks that must fail on the same protected test
# before an amendment proposal is raised.
AMENDMENT_FAILURE_THRESHOLD: int = 3

# Look-back window in days for historical failure analysis.
AMENDMENT_WINDOW_DAYS: int = 14
