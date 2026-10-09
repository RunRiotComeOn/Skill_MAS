# VitaBench profile (`vitabench`)

Adapted from [optimized_skill/vitabench.md](https://github.com/linhh29/Skill_MAS/blob/b55d47e/optimized_skill/vitabench.md).
Use for multi-step tool workflows with selection and dependent actions.

1. **Map constraints and handoffs.** Record each relevant constraint, its source,
   affected steps, and priority. Mark assumptions as assumptions. Carry forward
   identifiers, dates, and other values needed by dependent steps.
2. **Split at capability boundaries.** Separate information acquisition,
   candidate evaluation/selection, and state-changing execution. Keep unrelated
   chains independent unless they share a real constraint or resource.
3. **Explore before selecting.** Retrieve a useful candidate set and compare it
   against all known constraints. Return a structured selection contract with the
   chosen identifier, relevant values, evidence, and rationale. If no candidate
   meets essential requirements, surface the conflict before acting.
4. **Use explicit decisions.** Pass structured fields to dependent actions rather
   than inferring decisions from loose prose. If extracting a value fails, obtain
   it from an authoritative source or ask for missing information when necessary;
   do not substitute a guessed default. Resolve relative dates against the actual
   time, timezone, and available authoritative calendar data.
5. **Check reality before execution.** Revalidate identity, target identifiers,
   timing, availability, and existing authorization immediately before a state
   change. Execute dependent actions in order and avoid concurrent writes to the
   same resource. Retry a state-changing action only after checking whether it
   already succeeded and whether repeating it is safe.
6. **Verify completion.** Compare observed tool results with the original
   constraints. Correct unmet requirements within the authorized scope and retry
   budget. Summarize completed actions, confirmations, partial results, and
   remaining work without presenting a proposed action as executed.

The host's actual tools replace VitaBench's simulator. Use distinct roles where
they add value; the source's minimum-agent/tool-call counts do not justify
unnecessary calls. No benchmark identities, dates, or transactional tools are
assumed to exist in the user's environment.
