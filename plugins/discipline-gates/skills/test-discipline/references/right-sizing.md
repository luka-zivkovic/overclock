# Test Discipline Right-sizing

Answer one question:

> Is the next authorized action a bug fix with an observable symptom, an inadequately covered
> refactor of existing behavior, a test-only request for named existing behavior, or an explicitly
> requested mutation check of a fresh green test?

If no, or if `anti-triggers.md` applies, stay silent. If yes, select exactly one mode from the
skill's routing table. The concrete action class is the right-size gate; never engage merely because
an edit feels risky.
