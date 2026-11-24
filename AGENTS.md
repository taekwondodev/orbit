## Project workflow

- Before reading or updating issues and tickets, read [the issue tracker adapter](docs/agents/issue-tracker.md).
- Before assigning or changing issue labels, read [the label policy](docs/agents/triage-labels.md).
- Before implementation or delivery, read [the delivery policy](docs/agents/delivery.md) for route, target and verification requirements.
- Before using domain terminology or changing architecture, read [the domain documentation guide](docs/agents/domain.md).

## Comments

Express intent through names, types and structure; a comment or docstring that restates the code goes. Comment only what the code cannot say: behavior of an external system, races, security constraints, the reason for a magic number, an unobvious trick. Design rationale belongs in `docs/adr` and `docs/design`, not in comments.
