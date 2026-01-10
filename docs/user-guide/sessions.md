# Sessions

Sessions are the core of ContextHarness. Each session maintains context for a specific feature or task.

## Session Structure

Each session is stored in its own directory:

```
.context-harness/sessions/
├── login-feature/
│   └── SESSION.md
├── TICKET-1234/
│   └── SESSION.md
└── api-refactor/
    └── SESSION.md
```

## SESSION.md Sections

| Section | Purpose |
|---------|---------|
| **Active Work** | Current task, status, blockers |
| **Key Files** | Files being modified with purposes |
| **Decisions Made** | Important decisions with rationale |
| **Documentation References** | Relevant docs with links |
| **Next Steps** | Prioritized action items |
| **Completed This Session** | Archived completed work |
| **GitHub Integration** | Branch, issue, and PR links |

## Session Lifecycle

### 1. Creation

When you run `/ctx my-feature`:

1. Directory created at `.context-harness/sessions/my-feature/`
2. SESSION.md initialized from template
3. Git branch `feature/my-feature` created (if `gh` available)
4. Session becomes active

### 2. Active Work

During development:

- Files you modify are tracked in **Key Files**
- Important decisions are recorded in **Decisions Made**
- Documentation you reference is saved

### 3. Compaction

Every 2nd user interaction (or manual `/compact`):

1. `@compaction-guide` analyzes current state
2. Recommends what to preserve
3. SESSION.md is updated with latest context

### 4. Switching

When you switch sessions with `/ctx other-feature`:

1. Current session is saved
2. New session is loaded
3. Context is restored from SESSION.md

## Naming Conventions

Sessions can be named:

- **Feature names**: `login-feature`, `oauth-integration`, `dashboard-redesign`
- **Ticket IDs**: `TICKET-1234`, `JIRA-567`, `GH-89`
- **Story IDs**: `STORY-456`, `US-789`

## GitHub Integration

When `gh` CLI is available, sessions integrate with GitHub:

```markdown
## GitHub Integration

**Branch**: feature/login-feature
**Issue**: #65 - https://github.com/org/repo/issues/65
**PR**: #72 - https://github.com/org/repo/pull/72
```

### Automatic Branch Creation

`/ctx login-feature` creates branch `feature/login-feature`

### Issue Linking

`/issue` creates an issue and links it to the session

### PR Creation

`/pr` creates a PR with context from the session

## Best Practices

1. **One feature per session**: Keep sessions focused on a single feature or task
2. **Use descriptive names**: `user-authentication` is better than `feature1`
3. **Compact before switching**: Ensures context is saved
4. **Reference issues in names**: `TICKET-1234` makes tracking easy
