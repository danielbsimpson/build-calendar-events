# Sports Calendar

Public sporting-event schedules followed through calendar subscriptions.

## Language

**Sports feed**:
A publicly readable collection combining enabled F1 and UFC events that is the normal delivery channel for calendar subscribers. It contains public event information, not personal information or credentials.
_Avoid_: Invite stream

**Subscribed sports calendar**:
A read-only calendar populated from a sports feed, with a color selected by the subscriber. Corrections come from the feed rather than personal edits to its events.
_Avoid_: Imported calendar

**Manual event email**:
An explicitly requested email delivery of an event attachment, separate from the normal sports-feed delivery path.
_Avoid_: Feed notification

**Upcoming collection**:
The complete set of sporting events that have not ended and start within the configured look-ahead window, including events previously published.
_Avoid_: New-event batch

**Email delivery ledger**:
The record used to distinguish new, changed, and unchanged events for manual event emails. It is separate from the upcoming collection and does not define sports-feed membership.
_Avoid_: Feed store

**Last-good feed**:
The most recent combined sports feed successfully published after all enabled sources passed fetching and validation. It remains published when a later attempt fails.
_Avoid_: Partial feed

**Candidate feed**:
A validated upcoming collection prepared for publication, retained together with its matching event identity and revision records. A candidate is not the last-good feed until publication succeeds.
_Avoid_: Published feed

**Missing event**:
A previously published event absent from a later validated upcoming collection. Absence alone does not establish that the sporting event was cancelled.
_Avoid_: Cancelled event
