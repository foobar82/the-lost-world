"""Pipeline configuration — all tuneable values in one place."""

PIPELINE_CONFIG = {
    "daily_budget_gbp": 2.00,
    "weekly_budget_gbp": 8.00,
    "writer_model": "claude-sonnet-4-20250514",
    "reviewer_model": "claude-sonnet-4-20250514",
    "local_model": "llama3.1:8b",
    "embedding_model": "nomic-embed-text",
    "ollama_url": "http://localhost:11434",
    "max_writer_retries": 2,
    "repo_path": ".",  # Override per environment
    "contract_file": "contract.md",
    "db_url": "sqlite:///./lost_world.db",
}
