# Superseded build scripts (not used)

`build_star_db.py` -> `post_build_fixes_and_views.py` -> `build_mart_views.py` was the original three-step build of
`DB/rdpr_star.sqlite` (core tables, data-gap fixes and roll-up views, then the chatbot's `mart_*` views).
All three are replaced by the single staged build `warehouse/build_warehouse.py`
(sources -> staging -> core -> reconcile -> mart -> semantic -> ledger -> checks -> export), which writes physical
mart tables, the pre-summed `mart_agg_taluk_*` tables, the build ledger and 30 fail-the-build checks.
Kept for reference only; they still carry the original author's absolute paths.
