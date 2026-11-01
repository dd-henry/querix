# Analytical Query Intelligence Context

## User Decision

The user selected architecture C after clarifying that it should be the
orchestrated pipeline enriched with a dedicated semantic layer.

The semantic layer will live inside the existing FastAPI process as a typed
service with an in-memory cache. It will not become a separately deployed
service in this feature.

## Resolved Gray Areas

| Area | Decision | Rationale |
| --- | --- | --- |
| Schema examples | Store structural metadata and safe aggregates, not raw sample rows | The feature must improve planning without leaking business data into prompts. |
| Date interpretation | Resolve common Portuguese temporal expressions deterministically before planning | Dates are a correctness boundary and should not rely only on probabilistic interpretation. |
| Repair attempts | Allow at most one automatic SQL repair per execution | A bounded repair improves recoverability without creating loops or hiding repeated failures. |
| Empty results | Report zero rows explicitly and expose the interpretation/diagnostic instead of inventing values | An empty result can be valid business data. |
| User transparency | Show the interpreted intent and assumptions before or alongside the result | Users need a way to catch a wrong interpretation. |
| Evaluation data | Accept user-provided benchmark cases and keep the repository fixture domain-neutral | The application must remain plug-in friendly for any business domain. |

## Deferred Ideas

- Persistent organization-specific semantic catalogs managed through an admin
  UI.
- Automatic learning from accepted corrections.
- A separately deployed semantic service.
