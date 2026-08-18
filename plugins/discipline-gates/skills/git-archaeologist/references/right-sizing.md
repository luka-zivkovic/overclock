# Git Archaeologist Right-sizing

Answer one binary question:

> Would this requested change delete, bypass, or reduce the protection of a guard, invalid-state
> early return, retry/backoff, protective delay, lock, clamp, bound, or explicitly defensive check
> that already exists in committed history?

If no, or if `anti-triggers.md` applies, stay silent. If yes, recover history and current-state
evidence before the weakening. Do not engage because code merely looks surprising or important.
