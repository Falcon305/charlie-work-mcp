CHARACTER_LIMIT = 25000

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

CERT_WARN_DAYS = 30

STATE_DIRNAME = ".charlie-work"
LEDGER_FILENAME = "ledger.json"

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
    ".next",
    "coverage",
    ".idea",
    ".tox",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rb",
    ".rs",
    ".java",
    ".kt",
    ".php",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cs",
    ".swift",
    ".scala",
    ".sh",
    ".bash",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".cfg",
    ".ini",
    ".env",
    ".md",
    ".txt",
    ".sql",
    ".tf",
    ".gradle",
    ".make",
    ".mk",
}

MAX_FILE_BYTES = 1_500_000
