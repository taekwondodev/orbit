# Issue tracker: GitHub

Issues, specifications, implementation tickets and decision maps live in GitHub Issues for `taekwondodev/orbit`. Before GitHub operations, load `github-cli` for command selection and readback. Use the [label policy](triage-labels.md) when creating, starting, publishing or parking issue-backed work, and the [delivery policy](delivery.md) before delivery.

When publishing a specification for an existing issue, update its body in place, preserving its number and comments. A new implementation slice gets its own issue. Keep task evidence and unresolved decisions with the issue they concern.

## Wayfinding operations

- **Map and children:** use a map issue with the `wayfinder:map` label. Link child issues through GitHub sub-issues (`gh-axi issue subissue add <map> <child>`). If sub-issues are unavailable, use a task list in the map and `Part of #<map>` in each child.
- **Blocking:** use native issue dependencies. Add an edge with `gh-axi api POST /repos/taekwondodev/orbit/issues/<child>/dependencies/blocked_by --field issue_id=<blocker-db-id>`. The value is the blocker's numeric database ID, not its issue number or GraphQL node ID. Read it from the blocker's REST representation.
- **Fallback:** if native dependencies are unavailable, record `Blocked by: #<n>, #<n>` in the child. Use one representation consistently for that map.
- **Frontier:** read the map's children and retain open, unassigned issues with no open blocker. Native open-blocker counts are in `issue_dependencies_summary.blocked_by`; resolve referenced issues when using the fallback. Preserve map order.
- **Claim:** when an issue is selected for implementation, assign it to the driving developer and apply the work-start label transition in the same update. Read back assignee and labels.
- **Resolve:** record the answer on the child, close it, and add a concise decision pointer with its link to the map.

## Native development links

Use GraphQL through `gh-axi api POST /graphql --field query='<operation>' --full`.

- **Branch readback:** query `Issue.linkedBranches`, matching each ref by repository and branch name; reuse existing associations.
- **New remote branch:** use `createLinkedBranch(input: ...)` before the first push creates the ref, with explicit `issueId`, `repositoryId`, `name` and `oid`. IDs are GraphQL node IDs; `oid` is the branch-point commit already available in that repository. Read back the association and ref.
- **Existing remote branch:** use a supported linking operation that preserves the ref. Report unavailable operations as pending associations.
- **PR readback:** query `PullRequest.closingIssuesReferences` and compare qualified issue identities. A body mention alone is not a native closing link.

Linked branches can propagate issue links to future PRs. Verify the resulting closing references rather than assuming that the branch association is sufficient.
