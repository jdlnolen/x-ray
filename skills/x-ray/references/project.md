# Project setup and state

Store `.x-ray/` at the project root. When Git has linked worktrees, use the primary checkout (the first worktree in `git worktree list --porcelain`), or the specific map directory already named in project instructions. This keeps the map in the same place when a build moves checkouts. In Git projects, first check that `.x-ray/` contains no tracked paths and no unrelated content. For a new directory, add `.x-ray/.gitignore` containing `*` so generated pages and their state do not enter the worktree's Git status. Confirm with `git check-ignore .x-ray/state.json` from the map checkout. Preserve an existing X-ray state and ignore rules. If the project already uses that path for another purpose, agree on a separate project-local path and record it in the opt-in block. If the configured map cannot be updated, report its path and the missed checkpoint. Show the map's absolute path when handing off.

For ongoing updates, add this block once to the project's `AGENTS.md` or equivalent. If a branch or worktree is used for implementation, carry the instruction forward. Existing project rules govern commit and publication choices.

```markdown
<!-- x-ray:start -->
Use the `x-ray` skill for implementation plans in this project. Create or
refresh the map and step schematics before editing implementation files. Update
and render the map after verifying each step, before handling the next completed
step. When a step is blocked, refresh its schematic and record the blocker.
For work completed elsewhere, update the map after integration and verification.
Reuse the X-ray directory across workstreams and worktrees. Reconcile diagrams
after review fixes. Share the local map at the start and at handoff.
<!-- x-ray:end -->
```

Update the existing `state.json` at each checkpoint. Read it again before editing and merge only the observed changes. The host is the writer. Keep stable lowercase IDs with letters, digits, and hyphens. A step key such as `sync-u1` combines the stable workstream key `sync` with CE unit `U1`. Include cross-workstream dependencies only if documented or confirmed. Use short graph labels and keep the details in `summary` and `evidence`.

```json
{
  "title": "Research dashboard",
  "summary": "Shows recent research from the briefing index.",
  "diagram": {
    "nodes": [
      {"id": "briefings", "label": "Briefing index"},
      {"id": "dashboard", "label": "Dashboard (proposed)", "step": "sync-u1"}
    ],
    "edges": [{"from": "briefings", "to": "dashboard", "label": "provides briefing records"}]
  },
  "steps": [
    {
      "id": "sync-u1",
      "unit": "U1",
      "workstream": "Briefing sync",
      "title": "Read and display the briefing index",
      "plan": "docs/plans/briefing-sync.md",
      "status": "planned",
      "depends_on": [],
      "summary": "Read the index and list the newest issue first.",
      "diagram": {
        "nodes": [
          {"id": "index", "label": "Index file"},
          {"id": "load", "label": "Load and sort records"},
          {"id": "list", "label": "Issue list"}
        ],
        "edges": [
          {"from": "index", "to": "load", "label": "records"},
          {"from": "load", "to": "list", "label": "newest first"}
        ]
      },
      "evidence": []
    }
  ]
}
```

Status values are `planned`, `in-progress`, `implemented`, `blocked`, `verified`, and `superseded`. For `verified`, supply at least one concrete evidence string naming the host-observed check and outcome, plus a commit or source path where available. For `blocked`, explain the unresolved condition. In `plan`, use the path relative to the map checkout, an absolute path to a plan in another worktree, or its durable HTTPS URL. Prefer the durable URL for a temporary worktree when available. A missing local plan shows its original path as text. For loose requests without a saved plan, use an empty string and cite the source in `summary`.

From the skill installation directory, run `python3 scripts/render.py /absolute/path/to/.x-ray/state.json`. The command needs Python 3.9+ and Graphviz `dot` in `PATH`. It validates links and renders the diagrams before replacing pages. Open `index.html` in the same directory. Step pages are under `steps/`, carry a link back to the map, and link directly to dependencies. The pages render locally without internet access.

To check a state change before replacing the current map, run the renderer with `--check`.

```bash
python3 scripts/render.py --check /absolute/path/to/.x-ray/state.json
```

This runs validation and Graphviz in memory. It reports the page count on success and exits nonzero with a diagnostic on failure. Both outcomes leave generated HTML untouched. Run the command without `--check` when you are ready to update the map and schematics.
