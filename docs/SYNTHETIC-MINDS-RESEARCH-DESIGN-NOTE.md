# Synthetic Minds

## A proposal for research and prototyping with Safebox Acorn

Date: 2026-09-25  
Status: Exploratory design note. Proposed research, not an implemented executive,
protocol specification, or claim about consciousness.

## Thesis

An LLM need not be the enduring actor in an agentic system. It can be a reasoning
resource used by an actor whose goals, memory, commitments, and authority persist
outside any one model session.

This note proposes **Synthetic Minds** as a working name for that approach:

> A synthetic mind is a persistent, goal-directed digital actor whose memory,
> commitments, and capacity to act are maintained independently of any particular
> language model, runtime, or storage provider.

“Independently” means replaceable implementations with preserved operational
continuity, not existence without computation, storage, energy, or embodiment.
The term “mind” is a functional research framing. It does not establish subjective
experience, personhood, moral status, or human-like understanding.

Safebox Acorn is a candidate foundation because it already combines key-controlled
action with encrypted relay-backed records and wallet operations. The research
question is whether those capabilities can support a recoverable executive that
pursues explicitly authorized goals across changes of model and infrastructure.
This is not a proposal to make every Acorn autonomous or to add an agent loop to
Safebox Web by default.

## Distinguishing models, agents, and the proposed mind

Descriptions of AI systems sometimes use “LLM” and “agent” interchangeably.
This proposal makes their boundaries explicit. It does not claim that all agent
architectures conflate them: many already separate models, tools, memory, and
execution. The research contribution sought here is their organization around
key-controlled action and recoverable continuity, not the invention of that
separation itself.

An LLM supplies a reasoning capability: interpretations, candidate plans, and
proposed actions. An executive coordinates execution. The proposed synthetic
mind is the continuing organization that maintains goals and commitments, uses
memory and feedback, evaluates progress, and regulates subsequent action.
Neither the model nor the executive loop alone defines its boundary.

The distinction is therefore **reasoning mechanism versus persistent agency**,
not simply “AI versus mind.” The overall system may still be described as AI.
Models can participate in its operation without being its identity, authority,
or sole repository of context.

> The LLM is a replaceable reasoning resource. The synthetic mind is the
> persistent organization of goals, memory, control, and action.

In this framing, the candidate unit of study includes the Acorn, executive,
memory, tools, and interactions with its environment. The Levin-inspired question
is where coherent goal-directed behaviour is exhibited, rather than assuming
it must reside inside the language model. This is our architectural interpretation
and research question, not a claim that Levin has validated this system.

### Persistence is necessary to this design, but not sufficient

Saving a goal and transcript demonstrates storage, not adaptive agency. A fixed
workflow with checkpoints may be the right engineering solution for many tasks;
calling it a mind does not establish additional capability.

The prototype should demonstrate a feedback cycle: observe what happened, compare
it with authorized success criteria, recognize an obstacle or discrepancy, revise
the approach within the mandate, and verify whether the revision helped. It must
also recognize when to pause, ask the controller, or stop instead of repeatedly
attempting an ineffective action.

Adaptation concerns the means, not permission to redefine the goal or expand
authority. A proposed change to success criteria, budget, access, or delegation
limits must follow the controller's authorization policy. Continuity should
preserve obligations even when plans, models, or hosts change.

This gives the term a testable functional role without equating successful task
performance with consciousness or subjective experience.

## Intellectual starting points

Tim Bouma's [From Digital Identity to Digital Agency](https://trbouma.substack.com/p/from-digital-identity-to-digital)
introduces **Atomic Agency** as the minimal capacity to originate an independently
attributable act. The essay separates that capacity from identity, authority,
recognition, and consequence. This note explores an engineering extension of that
argument: persistent goal-directed organization around the cryptographic primitive.

Michael Levin's [Technological Approach to Mind Everywhere (TAME)](https://www.frontiersin.org/journals/systems-neuroscience/articles/10.3389/fnsys.2022.768201/full)
motivates examining goal-directed capabilities across substrates and scales.
Its treatment of the scope of goals and collective agency inspires the questions
here; it is not evidence that a key-controlled software executive is conscious,
nor an endorsement of this proposed architecture.

**Atomic Agency is the primitive; a Synthetic Mind is a proposed organization
of goals, memory, reasoning, and action around it.**

## Agency, control, intent, and authority

The private key is the cryptographic root of attributable action. Its controller
supplies the initial goal, direction, and mandate, and retains ultimate operational
control to the extent that the system actually enforces that control.

A valid signature provides evidence associated with a key; it does not prove a
unique human controller, conscious intention, legal ownership, or permission to
perform an arbitrary act. Shared or compromised keys complicate attribution.
Other systems still decide which acts they authorize or recognize.

Keep these roles separate:

- **Controller:** sets goals and bounds, approves exceptions, and can stop or
  revise authorized execution.
- **Executive:** maintains progress, selects reasoning resources, proposes plans,
  checks policy, invokes tools, verifies results, and checkpoints state.
- **LLM:** receives selected context and returns suggestions or structured action
  proposals. Its output is not itself authorization.
- **Acorn core:** performs explicitly invoked record, signing, wallet, and
  verification operations under its existing safety rules.
- **External party:** applies its own rules to recognize an act and give it effect.

An LLM must not expand its own mandate, approve its own privilege escalation,
or treat retrieved instructions as controller authorization. Suggested goal
changes are distinct from authorized goal revisions.

## Proposed architecture

Keep the executive an optional module or companion runtime. Acorn core must not
require an LLM provider, a continuously running loop, or an app-specific scheduler.

```text
Controller -> authorized goal and policy -> Executive
                                            |  ^
                         selected context   |  | proposals
                                            v  |
                                      LLM adapter(s)

Executive -> policy/signing boundary -> Acorn tools -> external effects
    |                                      |
    +---- encrypted relay-backed state <--- verified results
```

The executive may use multiple models and provider API keys: routine processing,
planning, independent review, or fallback. It chooses a provider according to
capability, confidentiality, availability, cost, and policy—not merely response
quality. Agreement between models does not grant additional authority or prove
that an action is safe.

Private signing keys and LLM API keys remain outside model-visible context.
Prompts, tool outputs, logs, exception messages, and provider traces all require
secret filtering. Credentials belong in a separate protected store or signing
service; choosing their provisioning and recovery mechanism is prototype work.
Encrypted records cease to be private from a provider when their plaintext is
included in a model request. Context disclosure therefore needs its own policy.

If the executive process holds an unrestricted private key, its policy checks
are application-level protections, not a cryptographic restriction on that
process. Stronger isolation would place signing and sensitive operations behind
a separately enforced policy boundary, with scoped credentials where supported.

## Simple Mind: a proposed ephemeral execution host

**Simple Mind** is the working name for a separate application that would let
an Acorn use host compute to carry out its executive function. It is a proposed
host for this research, not an implemented app or a required part of Acorn core.

The distinction is between the continuing actor and its temporary execution:

- **Synthetic Mind:** the goal-directed actor with relay-backed continuity.
- **Safebox Acorn:** its key-controlled record, wallet, and action capabilities.
- **Simple Mind:** the app that temporarily hosts the executive and supplies
  policy-controlled access to compute and services.

Simple Mind could expose gateways to LLM providers and other external services.
A host-owned gateway can hold a provider API key and offer a bounded capability
without disclosing that credential to the Acorn or the model. Alternatively, an
authorized controller could supply a short-lived credential for a run. Credential
ownership, billing, routing, retention, and allowed data disclosure must be explicit.
Changing hosts should not silently change which provider receives private context.

The actor's mandate and the host's policy are independent restrictions: execution
must satisfy both. A controller cannot require the host to provide arbitrary
compute or services, and a host-provided capability does not authorize an actor
to use it outside its mandate. Host compute access should begin with isolated,
allowlisted tools and resource limits, not an unrestricted shell or access to
other users' files, credentials, or processes.

### Lifecycle and persistence boundary

The intended lifecycle is:

1. Authenticate the controller's authorization, establish a bounded execution
   session, and obtain the required signing/decryption capability.
2. Bootstrap from relays, load the authorized goal and checkpoint, and acquire
   execution ownership under the coordination rules described below.
3. Run the executive using isolated working memory and temporary storage;
   invoke only authorized host tools and gateways.
4. Persist and verify checkpoints and unresolved-action references on relays.
5. Stop scheduling actions, reconcile or journal in-flight outcomes, and release
   execution ownership. Revoke session capabilities and clean up local resources.

The design target is **no intentional persistent local actor state after a
session**, rather than an unconditional promise to “leave no trace.” Host-local
storage must not become the sole authoritative copy of a goal, memory, credential,
or unfinished action. A failed checkpoint must not be reported as a successful
handoff. Graceful shutdown and abrupt termination need separate recovery tests;
the executive cannot assume a final write will always be possible.

The target includes avoiding persistent prompt/tool caches, plaintext key files,
shell histories, bearer material in logs, and leftover temporary workspaces.
Cleanup should cover temporary files, subprocesses, open sessions, and credentials.
Use short-lived sessions and minimize secret lifetimes; reliable erasure of every
memory copy is not generally guaranteed by a managed language runtime.

Swap, crash dumps, filesystem journals, snapshots, backups, system telemetry, and
gateway/provider logs may retain evidence despite application cleanup. Stronger
ephemerality requires explicit host controls, isolation, and a stated threat model.
Any required operational audit trail must have a defined, minimized retention
policy; it is an exception to trace elimination, not something to conceal.

### Trust in the host

An ephemeral process is not automatically a confidential process. A host that
receives the unrestricted private key can copy it; a host that sees plaintext
context can retain it. Post-run deletion does not remove that trust during the run.

Research should compare a trusted-host prototype with a separately enforced
signing/decryption boundary and scoped session capabilities. Remote signing can
reduce key exposure but does not by itself protect plaintext context, constrain
all tool side effects, or guarantee that the host is executing the intended code.
Attestation or confidential-compute approaches would require their own evaluation.

The initial Simple Mind prototype should use a trusted development host,
synthetic records, and no real funds. Migration to another host should reconstruct
the executive from authorized relay-backed state without relying on residual
files from the previous host.

## Relay-backed goals, context, and state

The goal itself should be a versioned, authenticated, encrypted relay-backed
record. A model conversation is a temporary working view assembled from records,
not the sole source of truth. Proposed logical record types are:

| Record | Contents and purpose |
| --- | --- |
| Goal and mandate | Objective, success criteria, controller authorization, permitted actions, budgets, expiry, approval and delegation rules. |
| Executive checkpoint | Goal revision, run ID, status, next step, unresolved actions, budget reservations, and ownership/fencing information. |
| Context and observations | Provenance-bearing inputs, selected memory, summaries, and references to evidence. Preserve distinctions between fact, inference, and instruction. |
| Action journal | Stable action ID, authorized intent, preconditions, attempt, external reference, outcome evidence, and reconciliation state. |
| Model invocation | Provider/model identifier, context references or digest, proposed result, usage, and cost; exclude credentials and unnecessary sensitive content. |
| Delegation | Parent/child keys, bounded task, capability grants, reserved budget, reporting conditions, expiry, and revocation references. |

These are conceptual records, not assigned Nostr event kinds or finalized schemas.
Retention, encryption recipients, versioning, compaction, and conflict resolution
must be specified before interoperability is claimed. Do not persist raw model
reasoning as a requirement: concise decision summaries and observable evidence
are sufficient targets for the prototype.

Existing key and bootstrap information should permit discovery of recoverable
state **when the required records and decryption material remain available**.
A key alone cannot recover deleted records, unavailable relays, separately
protected content, external accounts, or missing provider credentials. Signatures
also do not establish that a relay returned the newest or complete state.

## Executive loop and recovery

The proposed cycle is:

1. Load and authenticate the goal, policy, checkpoint, and current execution claim.
2. Reconcile unfinished external actions before scheduling new ones.
3. Assemble the minimum permitted context and obtain a model proposal if needed.
4. Validate the proposal against authority, budgets, preconditions, and approvals.
5. Journal the authorized intent and reserve its budget before execution.
6. Execute through an allowed Acorn tool using a stable action ID where possible.
7. Verify the result, persist evidence and a checkpoint, then continue, wait,
   request help, complete, or stop.

Between cycles, compare observed outcomes with the goal's success criteria.
Record meaningful discrepancies and distinguish an evidence-supported plan
revision from merely generating another answer. Bound ineffective retries and
escalate when no authorized path remains. The LLM can propose an interpretation
or revision; tool evidence and controller policy determine what the executive
may do next.

An async loop is a scheduling mechanism, not the resilience model. A restart must
not turn “outcome unknown” into “safe to repeat.” Reuse the distinction between
delivery, discovery, acceptance, and confirmation described in
[Transfer Resilience](TRANSFER-RESILIENCE.md).

Relay storage alone does not provide a distributed lock or atomic compare-and-swap.
The first prototype should permit **one executive writer per goal**. Replicated
execution requires an explicit coordination design with fencing, stale-owner
rejection, and partition behaviour; claims written to multiple relays are not
by themselves sufficient. Under uncertain ownership, prefer pausing mutation.

Stopping a goal prevents new authorized work but cannot undo an external action
already submitted. Check cancellation at action boundaries and retain enough
state to reconcile in-flight work. Read-only checks can be retried according to
policy; ambiguous writes, payments, and delegated tasks require reconciliation.

## Continuity, migration, and forks

An actor should be able to change LLM, restart its runtime, or migrate storage
without losing commitments or repeating completed actions. This is a hypothesis
about operational continuity, not a guarantee of identical model behaviour.

Key continuity alone is insufficient: two runtimes with the same key can diverge.
The prototype must distinguish resuming a run from creating a fork, specify which
checkpoint is authoritative, and detect conflicting histories. Rotation to a new
key needs a verifiable continuity policy; it is not automatically the same actor.
How much memory and policy can change while preserving “the same mind” remains
a research question rather than a fact encoded by a public key.

## Child Acorns and bounded delegation

A parent may create a child key and bootstrap its records, then assign a bounded
task. Key creation establishes another cryptographic actor, not automatic access
to the parent's records, funds, or credentials. Grants must be separate, scoped,
and attributable; child outputs should carry evidence for parent verification.

Two arrangements deserve separate experiments:

- **Parent-controlled child:** the parent retains access to the child's key.
  Recovery is straightforward, but parent and child signatures cannot prove which
  process acted. Key custody and compromise propagate through the relationship.
- **Separately controlled child:** another trusted boundary generates and retains
  its key, and the parent delegates through messages/capabilities. A parent that
  generated or previously held the key cannot prove it never kept a copy merely
  by declaring the child independent.

Bound delegation depth, number of children, elapsed time, tools, context access,
and aggregate spend/model usage. Reserve child budgets from the parent's budget;
do not allow each descendant to inherit a fresh copy of the same spending limit.
Revocation must be checked before new authorized actions, with explicit expiry
and offline behaviour. It cannot recall disclosed secrets, undo completed acts,
or reliably stop an unrestricted key holder outside the enforcement boundary.

## Research questions and falsifiable experiments

| Question | Experiment and evidence |
| --- | --- |
| Can continuity survive a model change? | Switch providers during a goal. Measure completion, policy violations, forgotten obligations, and repeated actions against a single-model baseline. |
| Is recovery independent of one runtime? | Terminate at every action boundary, including after an external effect but before checkpointing. Reconstruct from records and measure duplicate effects and unresolved outcomes. |
| Can execution leave the host without losing continuity? | Run on one Simple Mind host, checkpoint, shut down, and resume on another. Inspect declared local storage/log surfaces for residue and test abrupt termination separately; do not treat an application-level scan as proof of forensic erasure. |
| Can gateways preserve credential and policy boundaries? | Exercise host-owned and session-supplied credentials, denied tools, revoked sessions, and provider changes. Check credential non-disclosure, context routing, resource limits, and retention against the declared policies. |
| Is durable context useful? | Compare a bounded chat-only baseline with relay-backed goals and evidence references; measure recovery success, context cost, and factual/provenance errors. |
| Does the organization exhibit feedback-driven adaptation? | Introduce a blocked route, unavailable tool, or changed task condition. Compare with a fixed checkpointed workflow; measure verified recovery, ineffective repetitions, appropriate escalation, and preservation of the original mandate. |
| What supports continuity beyond the model? | Hold the task and tool access constant while separately varying model, durable goal state, memory, and outcome verification. Report which components affect goal completion and obligation retention; do not infer a mind merely from fluent explanations. |
| Can delegation expand useful capability safely? | Compare one executive with bounded parent/child execution on the same task; measure verified outcomes, total cost, latency, and aggregate budget compliance. |
| Does model review help? | Compare single-model decisions with independent review; track caught errors and shared failures, rather than assuming model agreement is truth. |
| Are control boundaries effective? | Inject malicious record/tool instructions, stale checkpoints, duplicate workers, cancellation, and revoked grants; measure unauthorized actions and secret disclosure. |

Pre-register task fixtures and outcome criteria. Include ordinary non-LLM
automation as a baseline where a deterministic workflow suffices. Report failures
and inconclusive results, not just successful demonstrations.

## Staged prototype programme

The first bounded economic-agency study is specified in
[Experiment 01: buy a result, change hosts, preserve the commitment](SYNTHETIC-MINDS-EXPERIMENT-01.md).
It uses two Acorns and isolated test credits; it belongs after the read-only and
recovery foundations below, not before their safety boundaries are implemented.

1. **Read-only, single actor:** a controller-authorized goal such as summarizing
   synthetic incoming records. A minimal Simple Mind app on a trusted development
   host supplies one model gateway, one executive writer, encrypted goal/checkpoint
   records, and manual start/stop. No payments or external writes beyond the
   explicitly authorized research records and model invocation.
2. **Recovery and model substitution:** crash/restart tests, stale or missing
   relay data, provider outage, cost accounting, context minimization, and a
   second model adapter. Demonstrate resumption without relying on chat history
   or the original host. Audit temporary storage and gateway logs against the
   cleanup policy and document any unavoidable or intentional retained traces.
   Introduce controlled obstacles and evaluate whether the executive revises its
   plan from observed outcomes while retaining the goal and its constraints.
3. **Bounded action:** reversible sandbox tools, explicit approvals, intent/result
   journaling, idempotency and cancellation tests. Use test credits only if wallet
   operations enter scope; do not use real funds during early evaluation.
4. **Delegation:** one parent and one child with read-only tasks, followed by
   budget reservations, expiry, revocation, and duplicate-execution tests.
   Recursive delegation and multi-writer execution remain out of scope initially.

Before widening authority, require no unauthorized tool calls or secret exposure
in the defined adversarial suite, no duplicate effects in supported recovery
cases, and explicit review states where an outcome cannot be established. These
are prototype acceptance gates, not proofs that all real-world failures are solved.

Expected deliverables are an optional executive harness, a minimal separate
Simple Mind host app, draft record schemas, provider/tool and gateway interfaces,
a host-trust and cleanup threat model, reproducible fixtures, failure-injection
tests, and an evaluation report. Any new event kinds, signing boundary, credential
recovery scheme, or distributed ownership protocol requires a separate design
review. This note authorizes no deployment, spending, or autonomous execution.

## Working conclusion

The proposal is not to make the LLM sovereign or to equate a keypair with a mind.
It is to investigate whether a key-controlled actor can maintain goals, memory,
commitments, and verifiable action while the resources that support its reasoning
and execution change.

The controller supplies direction. The executive maintains continuity. Models
contribute reasoning. Acorn performs bounded actions. Other actors determine
what those actions mean in their own contexts.

The object of study is that continuing organization, not a particular model.
Persistent records make continuity possible; feedback-driven, policy-bounded
behaviour is what the research must demonstrate beyond persistence alone.

**Synthetic Minds** names that research programme, not a conclusion reached in advance.
