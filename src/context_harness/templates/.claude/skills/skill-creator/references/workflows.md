# Workflow Patterns for Skills

## Sequential Workflows

For multi-step processes with a fixed order:

```markdown
## Workflow

1. **Step 1**: [Action]
   - Substep details
   
2. **Step 2**: [Action]
   - Depends on Step 1 output
   
3. **Step 3**: [Action]
   - Final step
```

## Conditional Workflows

For processes with decision points:

```markdown
## Workflow

1. **Analyze** the input
2. **Determine** which path:
   - If condition A: See [path-a.md](references/path-a.md)
   - If condition B: See [path-b.md](references/path-b.md)
3. **Execute** chosen path
4. **Verify** results
```

## Iterative Workflows

For processes that may need multiple passes:

```markdown
## Workflow

1. **Initial attempt**
2. **Validate** results
3. **If issues found**:
   - Analyze failure
   - Adjust approach
   - Return to step 1
4. **Finalize** when validation passes
```

## Error Handling

Always include error recovery:

```markdown
## Error Handling

- **[Error type]**: [Recovery action]
- **[Error type]**: [Recovery action]
```
