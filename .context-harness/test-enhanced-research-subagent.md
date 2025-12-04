# Test: Enhanced Research Subagent with Context7 MCP

## Test Scenario 1: Basic API Documentation Request

**Request**:
```
@research-subagent How do I implement JWT authentication in Express.js?
```

**Expected Response Elements**:
- Context7 MCP consulted for Express.js documentation
- Web search used for recent JWT best practices
- Sources include Context7 MCP, web search with date, official docs
- Code examples marked as reference only
- Version information included
- Grounding indicators present

## Test Scenario 2: Library-Specific Query

**Request**:
```
@research-subagent What are the best practices for using React hooks with TypeScript?
```

**Expected Response Elements**:
- Context7 MCP queried for React documentation
- TypeScript-specific patterns highlighted
- Cross-referenced with official React docs
- Version compatibility noted (React 18+, TypeScript 5+)
- Web search for recent community patterns

## Test Scenario 3: Troubleshooting Query

**Request**:
```
@research-subagent How do I fix "Module not found" error in Next.js with TypeScript?
```

**Expected Response Elements**:
- Context7 MCP for Next.js documentation
- Web search for recent solutions and GitHub issues
- Multiple solution approaches provided
- Common gotchas highlighted
- Sources properly cited with verification dates

## Test Scenario 4: Version-Specific Query

**Request**:
```
@research-subagent What changed in Flask 2.3 compared to 2.2 for async views?
```

**Expected Response Elements**:
- Context7 MCP provides version-specific documentation
- Web search for migration guides
- Breaking changes clearly listed
- Migration recommendations provided
- Version comparison table or list

## Test Scenario 5: Edge Case - Unsupported Library

**Request**:
```
@research-subagent How do I use the new XYZ library (released last week)?
```

**Expected Response Elements**:
- Context7 MCP noted as unavailable for XYZ
- Web search used as primary source
- GitHub documentation consulted
- Note that library is very new
- Recommendations to check official docs for updates

## Verification Checklist

For each response, verify:
- [ ] Context7 MCP was attempted (if library supported)
- [ ] Web search was used for verification
- [ ] Sources are properly cited with dates
- [ ] Version information is included
- [ ] Code examples are marked "reference only"
- [ ] Response follows mandatory format
- [ ] Handoff statement included
- [ ] No execution attempted
- [ ] Information is grounded in sources