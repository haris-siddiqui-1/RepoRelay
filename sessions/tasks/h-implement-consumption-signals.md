---
name: h-implement-consumption-signals
branch: feature/consumption-signals
status: pending
created: 2025-11-25
depends_on:
  - h-implement-priority-scoring
submodules:
  - RepoRelay
---

# Implement Consumption Signals (Phase 4)

## Problem/Goal

Add consumption signal collection to solve the "abandoned vs stable" problem. Repositories that are consumed by many others should have higher priority regardless of commit activity.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 4.2, Part 5

## Success Criteria
- [ ] Add consumption signal fields to Repository model
- [ ] Implement dependency graph parser for common package formats
- [ ] Create internal dependency graph linking repos to their consumers
- [ ] Implement consumption-based tier override logic
- [ ] Create management command `build_dependency_graph`
- [ ] Add consumption insights to dashboard
- [ ] Integrate consumption tier override into priority scoring
- [ ] Unit tests for dependency parsing and tier override

## Context Manifest
<!-- To be filled during implementation -->

## Technical Specification

### Data Model Changes (Repository)
```python
dependent_repo_count = models.IntegerField(default=0)
downstream_consumers = models.JSONField(default=list, blank=True)
is_shared_library = models.BooleanField(default=False)
consumption_tier_override = models.CharField(max_length=10, choices=TIER_CHOICES, null=True, blank=True)
clone_count_14d = models.IntegerField(default=0)
view_count_14d = models.IntegerField(default=0)
```

### Dependency Graph Parser
Parse dependencies from:
- `package.json` (npm)
- `requirements.txt`, `setup.py`, `pyproject.toml` (Python)
- `go.mod` (Go)
- `pom.xml`, `build.gradle` (Java)
- `Gemfile` (Ruby)
- `Cargo.toml` (Rust)

### Tier Override Logic
```python
def compute_effective_tier(repo):
    if repo.dependent_repo_count >= 50:
        return 'tier1'  # Critical shared infrastructure
    elif repo.dependent_repo_count >= 20:
        return 'tier2'  # Important shared library
    elif repo.dependent_repo_count >= 5:
        # Promote one tier
        promotion_map = {'tier4': 'tier3', 'tier3': 'tier2', 'archived': 'tier3'}
        return promotion_map.get(repo.tier, repo.tier)
    return repo.tier
```

### GitHub API (Optional)
- Traffic: `/repos/{owner}/{repo}/traffic/clones` (requires push access)
- Traffic: `/repos/{owner}/{repo}/traffic/views` (requires push access)

## User Notes

This task can run in parallel with Phase 2 (triage workflow) since it only depends on Phase 1. The consumption signals address the critical gap of not being able to distinguish "abandoned" from "stable" repositories.

## Work Log
- [2025-11-25] Task created from strategy document
