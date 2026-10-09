# Deep Research Bench profile (`drb`)

Adapted from [optimized_skill/drb.md](https://github.com/linhh29/Skill_MAS/blob/b55d47e/optimized_skill/drb.md).
Use for multi-perspective research and synthesis.

1. **Scope first.** Establish the question, time range, terminology, comparison
   dimensions, and evidence standard in the main agent. Share this context with
   every branch.
2. **Fan out.** Assign up to four distinct analytical perspectives in parallel,
   with one owner per perspective and one final synthesis. Keep independent
   analysis flat; introduce a dependency only if the task actually requires it.
3. **Contract for coverage.** Specify each branch's required questions, evidence,
   and concise output budget. A branch returns findings, source links or file
   locations, disagreements, and gaps. Validate coverage and support, not length
   or the mere presence of keywords.
4. **Preserve useful partial work.** If a branch misses a required dimension,
   request a targeted correction within the shared retry limit. Retain verified
   findings and pass explicit gap notes to synthesis.
5. **Separate shared and local context.** Keep a short shared summary per branch
   with evidence pointers; leave long working notes local. The synthesizer must
   have access to the underlying evidence when resolving conflicts.
6. **Check before synthesis.** Ensure each requested dimension is covered, then
   integrate the branches into a coherent report. Resolve contradictions or state
   them; do not silently turn incomplete evidence into a factual conclusion.

The source's fixed token minima, mandatory estimates for missing data, and
length-based pass thresholds are intentionally replaced by task-sized budgets,
explicit uncertainty, and evidence/coverage checks in this adaptation.
