# Changelog

Delete Me Before Merge

## Deterministic Dependency Tree

### Problem

Prebake previously used `random.shuffle` to reorder stages and dependencies before grouping them into parallel build groups. The `--optimize` flag attempted to compensate by running the entire pipeline N times with different random orderings and picking the result with the fewest groups. This meant:

- Different runs could produce different build group arrangements
- There was no guarantee the result was optimal
- Cross-platform inconsistency (the TODO on the shuffle noted Windows and Linux produced different orderings)

### Solution

Replaced the randomized grouping with **Kahn's algorithm** (BFS-based topological level assignment), which deterministically produces the provably minimum number of parallel build groups in a single pass.

#### How Kahn's algorithm works here

The dependency relationships between Docker stages form a Directed Acyclic Graph (DAG). Each stage depends on its base image and any stages referenced via `COPY --from=` or `--mount=...from=`. The goal is to assign each stage to a "level" such that all of its dependencies are in earlier levels. Stages at the same level have no dependencies on each other and can be built in parallel.

1. **Build the graph** -- For each stage, count how many of its dependencies are other known stages (its "in-degree"). Also build a reverse map tracking which stages depend on each stage.
2. **Seed level 0** -- All stages with in-degree 0 (their only dependencies are external base images like `ubuntu`, `node`, etc.) go into the first build group.
3. **Process each level** -- For every stage in the current level, decrement the in-degree of each stage that depends on it. Any stage whose in-degree drops to 0 is ready to build and goes into the next level.
4. **Repeat** until all stages are assigned a level.
5. **Cycle detection** -- If any stages remain with in-degree > 0 after exhaustion, there is a circular dependency.

Stages within each level are sorted alphabetically for consistent ordering across runs and platforms.

#### Example

Given these stages:

```
base-tools   -> (depends on: ubuntu)
base-libs    -> (depends on: ubuntu)
app-build    -> (depends on: base-tools, base-libs)
test-deps    -> (depends on: base-libs)
final-image  -> (depends on: app-build, test-deps)
```

The algorithm produces:

| Level | Stages | Rationale |
|-------|--------|-----------|
| 0 | base-tools, base-libs | Only depend on external `ubuntu` |
| 1 | app-build, test-deps | All their internal deps are in level 0 |
| 2 | final-image | Its deps are in levels 0 and 1 |

This is 3 groups -- the theoretical minimum. No amount of reordering can do better.

### What changed

#### Removed

| Item | Location | Why |
|------|----------|-----|
| `import random` | Top of file | No more randomization |
| `random.shuffle(stages)` | `main()` | Source of non-determinism |
| `optimize()` function | Optimize Logic region | Brute-force random re-runs replaced by single deterministic pass |
| `--optimize` CLI argument | argparse block | No longer needed |
| `OneTimeBoolean` class | Logic Sorting region | Only used by the old barrier-based grouping |
| `DockerStage.usage_dependencies_list` | DockerStage class | Only used by the old optimizer |
| `DockerStage.init_optimize_dependencies_list()` | DockerStage class | Only used by the old optimizer |

#### Replaced

`group_stages_by_build_order()` -- Previously contained:
- `order_stages_by_dependency_count()` (pre-sort)
- `kahns_algo()` (was actually a DFS topological sort, not Kahn's)
- `group_stages_by_dependency_barrier()` (stateful barrier grouping with `OneTimeBoolean`)

Now contains a single Kahn's BFS implementation that produces leveled groups directly.

#### Unchanged

- Dockerfile parsing (`parse_dockerfiles`, `find_dockerfiles`)
- Cross-over stage detection (`find_crossover_stages`)
- Deep dependency search (transitive dependency flattening for display)
- Bake file generation (HCL and JSON output)
- All CLI display functions
