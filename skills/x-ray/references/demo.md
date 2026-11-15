# Demo: Reading queue

Ask your agent to “Use X-ray to run the reading queue demo and show me the map after each verified step.” The demo uses a scratch directory and the files included with the skill. It needs Python 3.9+, Graphviz `dot`, and standard shell tools.

1. Set `XRAY_SKILL` to the absolute path of the installed `x-ray` directory. Copy the plan and initial state into a scratch directory.

   ```sh
   demo=$(mktemp -d)
   cd "$demo"
   mkdir -p docs .x-ray
   cp "$XRAY_SKILL/assets/demo/plan.md" docs/plan.md
   cp "$XRAY_SKILL/assets/demo/state.json" .x-ray/state.json
   python3 "$XRAY_SKILL/scripts/render.py" .x-ray/state.json
   ```

2. Open `.x-ray/index.html`. Both steps should be **Planned**. Open U2 and follow its link to U1. Verify that each step links to `docs/plan.md` and back to the map.
3. Run U1 and its `cmp` check from `docs/plan.md`. In `.x-ray/state.json`, set `reading-u1` to `verified`, record what `cmp` checked in its `evidence` array, and remove `(planned)` from the queue labels in the map and U1 schematic. Run the renderer again. The map and U1 should show the verified state, with U2 still planned.
4. Run U2 and its `cmp` check. Update `reading-u2`, its evidence, and the two preview labels the same way, then render again. Both steps should now be **Verified**. The output files are `.x-ray/index.html` and the two pages in `.x-ray/steps/`.

Run the renderer with `--check` to validate the state before replacing the existing pages. Keep the demo workspace long enough to inspect the HTML and its source plan links.
