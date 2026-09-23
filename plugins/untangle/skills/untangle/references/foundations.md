# The foundations check

Once the spine is known and decided, ask one question of it: is the spine built on a choice
that will hurt? This is a decision-level review, not a code review.

## Belongs here

A finding is a foundation finding when changing it later would mean rewriting a large part of
the spine. Examples:

- hand-rolled authentication, crypto, or session handling where a standard library exists;
- data kept in flat JSON files where the spine clearly needs concurrent or queryable storage;
- two frameworks or two runtimes doing one job inside the spine;
- a command-line tool whose real logic lives inside a web handler, or the reverse;
- a dependency on a service or SDK that is deprecated or unmaintained;
- no way to run the spine from a clean checkout (missing lockfile, undocumented variables).

## Does not belong here

- naming, formatting, file layout, function length, duplication inside one module;
- missing tests for individual functions;
- error handling style, logging, comments;
- anything the host's code review or simplify tools would report on a diff;
- architecture-depth judgments about module boundaries.

Those belong to the checklist's final handoff item: run the host's review tool over the spine
paths. Write that item; do not perform that review yourself inside untangle.

## Writing a finding

At most three. Each row needs:

- **Finding**: one plain sentence a non-developer can act on.
- **Evidence**: the paths and the signal that support it.
- **Cost of keeping**: what gets harder if nothing changes.
- **Cost of changing now**: rough size of the change today.
- **Cost of changing later**: how the change grows as the spine grows.

If none qualifies, write `None.` under the table. A spine built on standard choices produces
no findings, and inventing one to fill the section is a failure of the check.

If critical-thinking is installed, the user may hand one finding to it for a stress test. If it
is not installed, the finding stands as a labeled hypothesis in the plan.
