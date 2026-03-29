# Activation Shareable Source Package

This package is a clean handoff snapshot prepared for reuse.

## Removed before export
- Historical runtime data and logs
- Cookies, account state, and private license records
- Personal contact information and branded external links
- Notification integration and private credentials
- Local caches, snapshots, and compiled artifacts

## Included in this package
- Streamlit admin backend source
- Redeem and worker service source
- Public web pages under `web/`
- Helper scripts under `tools/` and `app_code/`
- Empty starter data files for a clean first run

## Reset starter files
- `state.json`
- `accounts_db.json`
- `at_fail_state.json`
- `licenses.json`
- `queue.txt`
- `history.txt`
- `invite_log.txt`
- `redeem_log.txt`
- `invalid_email_log.txt`

## Handoff notes
1. Review branding, domain names, and page copy before production use.
2. Fill in your own runtime data files after deployment.
3. Add your own notification integration if needed.
4. The root landing page was replaced with a neutral default page for sharing.
