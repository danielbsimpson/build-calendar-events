# Deliver sports events through a subscribed calendar

Milestone 3 will use one public, combined Sports feed as the normal delivery path, preserving event-attachment email only as an explicitly requested manual mode. The subscriber accepts a read-only calendar and a shared color for enabled F1 and UFC events in exchange for avoiding repeated imports and invitation handling.

Apple documents external ICS subscriptions and calendar-color controls, but BUG-001 must remain open until an actual iPhone test demonstrates subscription, color selection, and an event update without re-subscribing. No fixed client refresh latency is promised.

Every successful publication will contain the complete upcoming collection within the configured look-ahead window, not just new events. The manual-email delivery ledger remains separate and is not needed by the scheduled feed job.

The window remains 120 days. Include events that have not ended and start within that window; retaining a historical archive is out of scope. After a validated fetch, missing events are omitted rather than assigned an inferred cancellation status. Partial but nonempty source results remain a known risk; actual client removal behavior must be tested.

GitHub Pages will host the public feed at a stable HTTPS URL. This avoids a separate hosting account and deployment credentials; changing the URL later may require subscribers to change subscriptions.

GitHub Actions will attempt publication roughly monthly with both F1 and UFC enabled. Daily attempts were considered and rejected because long periods of stale data are acceptable for this use case. Occasional schedule re-enabling is accepted: GitHub can disable scheduled workflows in public repositories after 60 days without repository activity, and scheduled jobs can be delayed or dropped. This is not a guaranteed unattended scheduler.

If either source fails fetching or validation, the entire new publication is rejected and the last-good feed remains hosted. Healthy-source changes wait for a successful run rather than introducing per-source snapshot merging.

An enabled source returning zero upcoming events blocks publication unless explicitly authorized for that run. This deliberately trades occasional intervention during legitimate empty schedules for protection against a silently broken scraper.

Stable identity across changes to event details is a release requirement when the source exposes a stable identity. The existing UFC name/date-derived identity must not be assumed sufficient for reschedules. Unresolvable continuity must be flagged rather than guessed; live-source identity behavior remains to be established and tested during implementation.

The exact candidate ICS and its matching public identity/revision state will be versioned together on a dedicated repository branch, separate from the manual-email ledger. Caches and expiring workflow artifacts are not authoritative state. Runs must be serialized; missing or corrupt state after initial setup must fail explicitly, and failed state persistence or deployment must leave the hosted last-good feed intact. A saved candidate is not evidence of successful publication; a failed deployment can retry that candidate without re-scraping or resetting revisions.

## Operations and scope

- Use GitHub workflow-failure notifications, with notification settings enabled and tested as part of acceptance. They do not detect a run that never starts; independent heartbeat monitoring is out of scope.
- Do not add SMTP credentials to CI. Preserve local secrets for the existing manual-email mode. Use the workflow's repository token and narrowly scoped job permissions for state persistence and Pages deployment, not a separate long-lived hosting credential.
- Provide workflow summaries rather than success-summary emails, including unchanged runs. Summaries report source counts, additions/changes/removals, and publication outcome; every attempt still fetches and validates the complete collection.
- Provide manual workflow triggering for testing and recovery in addition to the monthly schedule.
- Preserve configured event alarms in the feed and verify actual iPhone alert behavior. Do not equate serialized alarms with proven client notifications.
- Certify the iPhone subscription path only. Document Google Calendar and Outlook subscription options as unverified, distinguishing URL subscription from one-time import.
- Keep HTTPS as the canonical feed address. Treat a webcal link as an optional entry point to test, not a distinct hosted feed or a universal subscription guarantee.
- Document careful, one-time manual cleanup or hiding of old imported sports copies after the subscription is verified. Never automate deleting personal-calendar events; matching UIDs do not guarantee deduplication across calendars.
- Provide a cron example for the same feed-generation command with persistent local state and output, absolute paths, venv execution, environment loading, logging, and nonzero failure exits. External hosting/upload and a second publisher to Pages are out of scope; file generation alone is not publication.
- Preserve Python 3.10+, the requirements.txt/venv workflow, and the existing non-secret configuration versus environment-secret separation.

## First slice and acceptance

Start with a controlled fixture feed published by a manually triggered Actions run to a separate test URL. Do not publish synthetic test events at the production subscription URL.

Before wiring live F1/UFC publication:

1. Subscribe on the actual iPhone through Add Subscription Calendar using the HTTPS URL, and select a calendar color.
2. Deploy a second candidate that changes an event without changing its UID and omits another event.
3. Observe the correction and removal in the existing subscription, with the chosen color preserved and without importing or re-subscribing. Record observed refresh latency rather than promise an undocumented deadline.
4. Verify configured alarm behavior on the device and record any client limitations; revisit unmet reminder needs before calling the migration complete.
5. Verify another run reloads durable identity/revision state, and retrying the same candidate does not reset identity or invent changes.
6. Exercise failed publication and a failed workflow notification; verify the hosted last-good feed is unchanged.

The live-source stage must then prove stable source identities, complete-window publication, changed/unchanged events, missing events, authorized versus unauthorized empty sources, partial-source failure, state recovery failures, and serialized scheduled/manual runs. The final production acceptance includes the live F1/UFC feed, enabled monthly workflow on the default branch, verified subscription behavior, and documented recovery/migration steps.

The user confirmed this shared understanding and requested that the interview end with these design documents, without starting implementation. These are agreed design decisions, not evidence that the implementation or device tests have passed.

## Sources

- [Apple: Set up multiple calendars on iPhone](https://support.apple.com/guide/iphone/use-multiple-calendars-iph3d1110d4/ios)
- [GitHub: Creating a Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)
- [GitHub: Scheduled workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
