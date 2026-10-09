# HLEMath profile (`hlemath`)

Adapted from [optimized_skill/hlemath.md](https://github.com/linhh29/Skill_MAS/blob/b55d47e/optimized_skill/hlemath.md).
Use for mathematical derivations, formal reasoning, and interpretation-sensitive
problems.

1. **Fix the interpretation.** Record ambiguous terms, plausible readings, the
   chosen reading and justification, and alternatives to revisit if it leads to a
   contradiction. When the statement is clear, keep this register brief. Pass the
   same assumptions to every solver and verifier.
2. **Separate solving and checking.** Delegate independent derivations or assign
   a solver and an independent verifier where the task warrants it. Ask for an
   answer with a concise justification, assumptions, and a verification report.
3. **Calibrate on small cases.** For a critical formula or numerical claim,
   compare a derivation with a second suitable method: smallest nontrivial cases,
   brute-force enumeration, symbolic checks, bounds, or numerical evaluation.
   Record what was actually checked. Small-case agreement is not a general proof.
4. **Reconcile discrepancies.** The verification role compares results and
   reports, looking for shared assumption errors as well as calculation errors.
   Revisit an interpretation centrally and propagate any revision to affected
   branches. Use targeted recovery, at most two corrective attempts per failed
   node, instead of voting away a contradiction.
5. **Format after verification.** Check the answer against the original question,
   then present the proof, explanation, or final value the user requested. Validate
   a required machine-readable or boxed format separately from correctness.

The source's benchmark-only final-answer extraction and mandatory delimiter are
not imposed on ordinary conversations. Distinguish proved results, empirical
checks, and unresolved conjectures.
