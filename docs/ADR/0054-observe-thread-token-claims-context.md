# ADR-0054: Observe effective-token claims and genuine context

## Context

Actual021 still returned C0000002 from XAML Site B. Static evidence supplied
by the producer identifies token-6 at both callers, XAML+36a44a and+5d625d,
forwarded unchanged by+704cbc. The r6 generated table only covers token-4.
The earlier description of the pointer shape did not establish token-4.

Whiny main bf40ff9 supplied r8, SHA-256
`5acbb35eaa18c874272e91a1169b997373496aa6277f9ccbb7f3bcc3d840b9ed`,
from observations
`8b373b3d7a809d9d313464e0f93f2f7240fb071b3ef8aa71f8492f928681deb1`.
The producer reports nine-case parity in three host contexts. The new cell
observes unpackaged token-6 returning C0000225, preserving claim and clearing
attributes. Packaged token-6 remains unobserved.

## Decision

Import r8 unchanged in a fresh022 sibling and preserve genuine predicates.
Never alias token-6 to token-4 or infer packaged success. Keep all020
diagnostics and frozen predecessors. The wrapper logs fixed handle category
(including thread effective token), seven optional-pointer presence bits,
both genuine context booleans and the actual return status during Run.
No raw handles, pointer addresses, claim values or arbitrary strings appear.

The booleans are genuine context samples before the generated call. They
are not direct tracing of its selected branch or an atomic identity snapshot.
The generated function still invokes its original predicate. Cap source
emission at128 plus one limit marker; collector retains128 with explicit loss.

## Consequences

Host tests compile the actual wrapper, predicate and unchanged artifact,
checking unpackaged-6 C0000225, packaged-6 C0000002, unchanged packaged-4
success, output canaries, redaction and limit grammar. The exclusive runtime
owner performs one fresh private-prefix no-input022 observation. A C0000225
Site B result may allow XAML to continue; only actual lifecycle evidence
establishes progress. No source test is UI, game or native parity acceptance.
