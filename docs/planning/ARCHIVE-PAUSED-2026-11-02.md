# User-requested download pause — 2026-11-02

User requested all downloads stop after current responses finish, with a resumable
checkpoint, to prepare for Plexo and USB tethering.

## Confirmed checkpoint

- Historical downloader exited; no remaining archive download process.
- The five open response streams were allowed to finish. Their raw files were
  structurally inspected and finalized with checksums/metadata after draining.
- 2,631 unique expected-year files saved, 29,209,568,241 bytes (~29.21 GB).
- 60 earlier provider HTTP 404 responses remain recorded as unavailable files.
- No incomplete `.part` files remained in the canonical monthly archive.
- `data/btc-perp/cryptohftdata-monthly/status.json` says `paused`.
- Full local `manifest.json` regenerated from saved per-file metadata.
- Local `PAUSE` marker prevents accidental restart before user resumes.
- Keys remain private outside the repository; no archive data are pushed.

The old running implementation lacked a cooperative drain hook. New job filesystem
access was blocked before any further request could start, while all five workers
were verified to have open response files. Open streams continued writing through
their existing handles until completion. The output namespace was restored only
after process exit; all five resulting complete files were finalized offline.
The final checkpoint excludes these artificial stop errors from provider-gap counts.

## Resume

Do not restart until the user is ready. Remove the local PAUSE marker, then use the
command in YEAR-ARCHIVE-DOWNLOAD-2026-11-02.md. Completed files are checksum-verified
and skipped; it resumes at missing file boundaries without downloading saved files
again. API tokens are obtained afresh. A full year is still incomplete and not
training-ready.

Plexo installation alone does not reroute this Python downloader. Its download
authentication, independent internet routes, request limits and integrity checks
must be integrated/tested before claiming downloads run through Plexo.

## Live recording

Live collector also stopped cleanly via its cleanup path. It flushed raw output,
closed streams and wrote final status/manifests. Counts: 64,753 depth messages,
64,750 reconstructed books, 76,550 market messages and 220 REST records.
Live data cannot resume an unrecorded time interval: restarting must use a fresh
snapshot and record the pause as a gap. Historical archive resumption is unaffected.
