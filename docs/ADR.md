# Architecture decisions

## Database is authoritative

Allocation state lives in PostgreSQL. A cache, if added later, must not override agent/call/borrower state for safety-critical claims.

## Conditional UPDATE, not SELECT then UPDATE

Two workers can both read AVAILABLE. Only `UPDATE ... WHERE state = AVAILABLE` with `rowcount` is atomic across processes.

## Separate Agent and Call machines

Predictive calls can ring before an agent is reserved. Merging the machines would hide that gap (the abandoned-call problem).

## Safety Controller cannot be bypassed

`SmartDialer.tick` always calls `SafetyController.authorize` before originate. The pacing engine has no provider handle.

## Progressive is the fallback

If an answered call has no agent (`answered_unmatched > 0`) or the provider is unhealthy, safety falls back to 1:1 progressive or originations of 0.

## Out-of-order events

Late events are ignored (monotonic). Early `COMPLETED` is stashed in `pending_events` and applied after the call is `CONNECTED`.

## Domain table vs SQL claim

Legal transitions live in domain objects. Cross-worker claims live in SQL `WHERE state = ...`. Do not replace the SQL claim with `agent.transition()` in one process. Next step is sharing the same allowed pairs, not a rewrite of allocation.

## Stack

Python + PostgreSQL + SQLAlchemy. No Kafka/Redis/K8s. The assignment prefers a simple architecture that you can defend.

## Scale: what breaks first

At ~1,000 agents, the bottleneck is row contention and sequential `SELECT ... LIMIT 1` pairing in the dialer, not “number of servers.” Fix: `FOR UPDATE SKIP LOCKED` work queues and batched originates. At ~10,000 agents, a single Postgres primary for every originate becomes the limit; shard by campaign or move matching to a dedicated allocator with still-authoritative DB claims. “Add more app servers” without changing the claim path just increases lock contention.

## Combining predictive utilization with progressive safety

Let pacing estimate how many originates would keep agents busy (`available / answer_rate`, plus wrap-up lookahead). Never send that number to the network. Send it to a Safety Controller that (1) caps concurrent in-flight calls against a deterministic overdial budget, (2) falls back to 1:1 when an answered call cannot be joined to an agent, (3) stops originates on provider failure. Utilization comes from the request. Safety comes from the cap and the fallback.
