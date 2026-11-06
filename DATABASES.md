# Databases not stored in git

Three SQLite files are too large for a git repo. Download them from this repo's **Releases** page (release `data`), and unzip each one into the folder shown:

| Download | Unzipped | Put it in | Rebuild instead |
|---|---|---|---|
| `rdpr_star.sqlite.zip` (681 MB) | 4.2 GB | `DB/` | `python warehouse/build_warehouse.py` |
| `FA_Finance.sqlite.zip` (209 MB) | 1.0 GB | `Finance_Accounting/` | supplied data (the `csv/` tables are in the repo) |
| `RV_Revenue.sqlite.zip` (62 MB) | 220 MB | `Revenue/` | supplied data (the `csv/` tables are in the repo) |

The AI app's key goes in `ai_app/.env` (copy `ai_app/.env.example`). See [README.md](README.md) and [HANDOFF.md](HANDOFF.md) to run it.
