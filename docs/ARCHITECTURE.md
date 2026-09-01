# Architecture

```text
Campaign tick
    → PredictivePacingEngine.recommend(snapshot)   # request only
    → SafetyController.authorize(requested, snapshot, mode)
    → ProgressiveDialer and/or PredictiveDialer
    → TelecomProvider.place_call
    → ProviderEventProcessor.handle
```

Prediction can be aggressive. Execution is capped by Safety Controller. Predictive code never calls the provider itself.

## State machines

**Agent:** OFFLINE → AVAILABLE → RESERVED → DIALING → CONNECTED → WRAP_UP → AVAILABLE

**Call:** QUEUED → RESERVED → INITIATED → RINGING → ANSWERED → CONNECTED → COMPLETED  
Failures: FAILED / CANCELLED

**Borrower:** ELIGIBLE → IN_CALL → ELIGIBLE or COMPLETED

## Safety vs pacing

- Pacing engine outputs an integer request.
- Safety may approve, reduce, reject (0), or fall back to progressive 1:1.
- Progressive: one AVAILABLE agent, one ELIGIBLE borrower, one call.
- Predictive overdial: extra originates without an agent; on ANSWERED we bind an agent or abandon.

## Concurrency

Allocation is `UPDATE ... WHERE state = ...` in PostgreSQL. `rowcount == 1` wins. No in-process lock as the source of truth.

## Providers

- A: fast, low failure.
- B: timeouts plus duplicate / out-of-order event scripts.
- Dialer depends only on `TelecomProvider.place_call`.

## Domain state machines vs SQL

Agent, Call, and Borrower have in-memory `STATE + EVENT → NEW STATE` tables. Persistence uses conditional `UPDATE ... WHERE state = ...`.

Those are two layers on purpose for now:

- The domain table is the legal lifecycle (for tests and interviews).
- The SQL `WHERE` is the concurrency control (the row lock that two workers share).

We should not “call `Agent.transition()` inside the UPDATE.” A Python transition on one worker does not stop another worker. The next refinement is to keep the same legal pairs in one module and have SQL encode those pairs, not to replace SQL with in-process mutations.

## Recovery

Reservations have `expires_at`. `ReservationRecovery.recover_expired` fails setup calls and frees agents/borrowers after a worker crash.
