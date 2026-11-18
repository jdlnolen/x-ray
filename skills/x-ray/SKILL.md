---
name: x-ray
description: Maintain one navigable project architecture map with a linked schematic for each build step. Use when asked to map a project or implementation plan, diagram progress, or update verified steps during Compound Engineering work.
---

# X-ray

Keep one map of the project and one linked schematic per meaningful build step. Make the diagrams answer what each part does, what flows between parts, and where the current work fits.

Open the generated HTML to explore diagrams with zoom, fit, component focus, expanded view, and project/step navigation. Auto layout adapts the graph direction to the available space; readers can also choose Horizontal or Vertical. See [viewer controls](references/project.md#viewing-large-diagrams). After a renderer update, re-render existing saved state to add the current controls.

To try the skill with synthetic inputs, follow the [reading queue demo](references/demo.md). The renderer requires Python 3.9+ and Graphviz `dot` on `PATH`. Compound Engineering is optional. See the [MIT license](references/LICENSE.txt).

1. Read [the project setup and state format](references/project.md) on first use. Reuse the project's `.x-ray/state.json` across workstreams and worktrees. Inspect implementation evidence in the checkout where the host verified it. The renderer uses Python 3 and Graphviz `dot` to produce self-contained local HTML under `.x-ray/`.
2. Read the selected plan and enough of the existing implementation to map its main boundaries. Give each workstream a stable key. Use each build step's ID and documented dependencies. Choose stable IDs for steps in a plan without them. Scope IDs by workstream so two plans can both have `U1`. Use the repository's actual modules, services, or deliverables as map nodes. Use labelled arrows for their real relationships. Distinguish proposed architecture from existing architecture in the diagram labels and describe unconfirmed relationships as open in the notes.
3. Before implementation starts, create a planned schematic for every in-scope unit. Show the affected part of the project and its intended inputs, processing, and outputs or handoffs. Use a small component, sequence, state, or flow diagram that suits the unit. Include a short explanation and the source plan path. Render the whole map, then share its local index path.
4. Update X-ray for **each step** as soon as the agent responsible for the project verifies completion, before handling the next completed step. In `ce-work`, the host owns this update. For work completed elsewhere, wait until the change is integrated and its verification has been checked. Inspect the actual change and verification result, reconcile the schematic and any architecture changes, record the evidence and status, and render again. Mark blocked or incomplete work as such. A worker result, a plan checkbox, or an unverified commit alone does not establish completion. Apply the same checkpoint when a previously completed step is verified during resume.
5. After review, reconcile the affected diagrams with any verified fixes. If a plan changes, retain links and evidence for completed units and mark removed units `superseded`. A rerun refreshes the same map. If a checkpoint was missed, recover it from current code and available verification evidence and mark any gaps. Report renderer failures and the affected unit, preserve the last rendered view, and retry the refresh after repair.

When asked to enable ongoing updates, add the project instruction in [project.md](references/project.md) to the target project's applicable agent instructions. A one-off map request does not enable it for future work. The owning workflow handles verification, Git, and shipping. The renderer reads the saved state and writes the map and schematics into `.x-ray/`.
