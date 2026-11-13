# 3. Read job requests with Claude into the service catalogue, and check the answer

## Context

Customers describe faults their own way ("leaves water at the bottom", "won't spin"). The planner and the van kit
need a skill, a fault from the catalogue, the brand and a time window.

## Decision

- Claude (`claude-opus-5-5`, low effort, refusal fallbacks) fills a strict tool whose skill and fault are enums from
  the catalogue, with the brand, the window and the exact words describing the fault.
- Code checks it: the fault must belong to the skill and its quote must be in the message, or rules decide the fault;
  the brand must appear in the message. A brand with no history is kept and flagged, so the dispatcher knows the van
  kit is planned from the fault alone.
- Without a key, or on a refusal, keyword rules read what they can.

## Consequences

- Claude can't invent a fault outside the catalogue, and a fault without words in the message to support it is not
  used.
- **Claude's accuracy is not measured here**; the tests check the request shape and the checks through the real SDK
  with canned responses.
