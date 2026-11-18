#!/usr/bin/env python3
"""Render X-ray state to local HTML using Graphviz."""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


STATUS = {
    "planned": "Planned",
    "in-progress": "In progress",
    "implemented": "Implemented",
    "blocked": "Blocked",
    "verified": "Verified",
    "superseded": "Superseded",
}

STYLE = """
:root { color-scheme: light; font: 16px/1.5 Inter, system-ui, sans-serif;
  color: #162c32; background: #f8faf9; }
* { box-sizing: border-box; }
body { margin: 0; }
main { max-width: 90rem; margin: auto; padding: clamp(1rem, 4vw, 3rem); }
header { border-bottom: 1px solid #d3dfdd; padding-bottom: 1rem; }
h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(1.85rem, 5vw, 3rem); margin: .6rem 0; }
h2 { margin: 1.75rem 0 .65rem; }
h3 { margin: 1.2rem 0 .5rem; }
p { max-width: 76ch; }
a { color: #005e68; text-underline-offset: .18em; }
a:focus-visible, button:focus-visible, select:focus-visible, .viewport:focus-visible {
  outline: 3px solid #005e68; outline-offset: 3px; }
button, select { font: inherit; color: inherit; background: white; border: 1px solid #a8bdb9;
  border-radius: .35rem; min-height: 2.75rem; padding: .4rem .65rem; max-width: 100%; }
button { cursor: pointer; }
button:hover { background: #edf6f4; }
.topnav { position: sticky; top: 0; z-index: 5; background: #f8faf9f5;
  border-bottom: 1px solid #d3dfdd; padding: .6rem max(1rem, calc((100% - 84rem) / 2));
  display: flex; align-items: center; flex-wrap: wrap; gap: .5rem 1rem; }
.topnav label { display: flex; align-items: center; gap: .5rem; min-width: 0; flex: 1 1 15rem; }
.topnav select { min-width: 0; width: 100%; max-width: 30rem; }
[id] { scroll-margin-top: 8rem; }
figure, .step { background: white; border: 1px solid #d3dfdd; border-radius: .6rem; }
figure { margin: 1rem 0; overflow: hidden; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem;
  padding: .65rem; border-bottom: 1px solid #d3dfdd; }
.toolbar label { display: flex; gap: .4rem; align-items: center; min-width: 0; }
.toolbar select { min-width: 0; max-width: 18rem; }
.zoom-level { min-width: 4ch; text-align: center; font-variant-numeric: tabular-nums; }
.viewport { height: clamp(20rem, 65svh, 48rem); position: relative; overflow: hidden;
  touch-action: pan-y; cursor: grab; background: #fcfefd; }
.viewport.dragging { cursor: grabbing; }
.diagram-layout, .diagram-layout svg { width: 100%; height: 100%; display: block; }
.diagram-layout[data-layout="vertical"] { display: none; }
.diagram[data-orientation="vertical"] [data-layout="horizontal"] { display: none; }
.diagram[data-orientation="vertical"] [data-layout="vertical"] { display: block; }
.node.focused polygon, .node.focused path, .node.focused ellipse { stroke: #bb4a15; stroke-width: 3; }
figcaption { padding: .5rem .8rem; color: #4d6267; font-size: .85rem; }
dialog { width: calc(100% - 1rem); max-width: none; height: calc(100% - 1rem);
  max-height: none; padding: 0; border: 1px solid #a8bdb9; border-radius: .6rem; }
dialog::backdrop { background: #162c32bb; }
dialog .diagram { margin: 0; height: 100%; display: flex; flex-direction: column; border: 0; }
dialog .viewport { flex: 1; height: auto; min-height: 8rem; touch-action: none; }
.step-nav { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
@media (max-width: 640px) {
  [id] { scroll-margin-top: 1rem; }
  .topnav { position: static; }
  .topnav label, .toolbar label { flex: 1 1 100%; }
  .toolbar label select { flex: 1; max-width: none; width: 0; }
  .diagram[data-orientation="auto"] [data-layout="horizontal"] { display: none; }
  .diagram[data-orientation="auto"] [data-layout="vertical"] { display: block; }
}
@media print {
  .topnav, .toolbar, figcaption { display: none; }
  .viewport { height: auto; }
  .diagram-layout svg { height: auto; }
}
@media (max-height: 30rem) {
  .topnav { position: static; }
  .viewport { height: 60svh; }
}
.steps { padding: 0; list-style: none; }
.step { margin: .45rem 0; padding: .8rem 1rem; display: flex; gap: .7rem;
  justify-content: space-between; align-items: baseline; flex-wrap: wrap; }
.status { font-size: .85rem; font-weight: 650; color: #34494e;
  background: #edf2f1; padding: .13rem .55rem; border-radius: .25rem; }
.verified { background: #ddf2e6; color: #19563b; }
.blocked { background: #f9e8e1; color: #8b3020; }
.in-progress, .implemented { background: #e2f1f6; color: #164e60; }
.context { color: #4d6267; font-size: .95rem; }
"""

SCRIPT = r"""
document.querySelectorAll('[data-page-nav]').forEach(select => {
  select.addEventListener('change', () => { if (select.value) location.href = select.value; });
  window.addEventListener('pageshow', () => {
    select.selectedIndex = Math.max(0, [...select.options].findIndex(option => option.defaultSelected));
  });
});
document.querySelectorAll('[data-diagram]').forEach(figure => {
  const viewport = figure.querySelector('.viewport');
  const layout = figure.querySelector('[data-layout-choice]');
  const focus = figure.querySelector('[data-focus-node]');
  const zoomLabel = figure.querySelector('.zoom-level');
  const expand = figure.querySelector('[data-action="expand"]');
  const variants = Object.fromEntries([...figure.querySelectorAll('[data-layout]')].map(el =>
    [el.dataset.layout, el.querySelector('svg')]));
  const bounds = new Map(Object.values(variants).map(svg => [svg, {
    x: svg.viewBox.baseVal.x, y: svg.viewBox.baseVal.y,
    width: svg.viewBox.baseVal.width, height: svg.viewBox.baseVal.height}]));
  let svg, base, scale = 1, cx = 0, cy = 0, fitting = true, dragged = false;
  let dialog, marker;
  const pointers = new Map();
  const size = () => ({width: viewport.clientWidth, height: viewport.clientHeight});
  const fitScale = () => Math.min(size().width / base.width, size().height / base.height) * .94;
  function draw() {
    const {width, height} = size();
    if (!width || !height) return;
    svg.setAttribute('viewBox', `${cx - width / scale / 2} ${cy - height / scale / 2} ${width / scale} ${height / scale}`);
    zoomLabel.textContent = `${Math.round(scale * 100)}%`;
  }
  function fit() {
    fitting = true; scale = fitScale();
    cx = base.x + base.width / 2; cy = base.y + base.height / 2;
    draw();
  }
  function zoom(next, x = size().width / 2, y = size().height / 2) {
    const old = scale;
    scale = Math.max(fitScale() / 4, Math.min(Math.max(4, fitScale() * 8), next));
    cx += (x - size().width / 2) * (1 / old - 1 / scale);
    cy += (y - size().height / 2) * (1 / old - 1 / scale);
    fitting = false; draw();
  }
  function focusNode() {
    figure.querySelectorAll('.focused').forEach(node => node.classList.remove('focused'));
    if (!focus.value) { fit(); return; }
    const node = [...svg.querySelectorAll('.node')].find(node => node.querySelector('title')?.textContent === focus.value);
    if (!node) return;
    node.classList.add('focused');
    const box = node.getBBox();
    const matrix = svg.getScreenCTM().inverse().multiply(node.getScreenCTM());
    const corners = [[box.x, box.y], [box.x + box.width, box.y + box.height]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(matrix));
    const width = Math.abs(corners[1].x - corners[0].x) + 64;
    const height = Math.abs(corners[1].y - corners[0].y) + 64;
    cx = (corners[0].x + corners[1].x) / 2; cy = (corners[0].y + corners[1].y) / 2;
    scale = Math.min(2, size().width / width, size().height / height);
    fitting = false; draw();
  }
  function resize() {
    const {width, height} = size();
    const direction = layout.value === 'auto' ?
      (width <= 640 || height > width * 1.1 ? 'vertical' : 'horizontal') : layout.value;
    const changed = svg !== variants[direction];
    figure.dataset.orientation = direction;
    svg = variants[direction]; base = bounds.get(svg);
    if (changed) { pointers.clear(); focus.value ? focusNode() : fit(); }
    else if (fitting) fit();
    else draw();
  }
  function toggleExpanded() {
    if (dialog) { dialog.close(); return; }
    marker = document.createComment('diagram position');
    figure.before(marker);
    dialog = document.createElement('dialog');
    dialog.setAttribute('aria-label', figure.getAttribute('aria-label'));
    document.body.append(dialog); dialog.append(figure);
    expand.textContent = 'Close expanded view'; expand.setAttribute('aria-expanded', 'true');
    dialog.addEventListener('close', () => {
      marker.replaceWith(figure); dialog.remove(); dialog = null;
      expand.textContent = 'Expand'; expand.setAttribute('aria-expanded', 'false');
      expand.focus(); resize();
    }, {once: true});
    dialog.showModal(); resize();
  }
  figure.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.action;
    if (action === 'in') zoom(scale * 1.25);
    if (action === 'out') zoom(scale / 1.25);
    if (action === 'actual') zoom(1);
    if (action === 'fit') { focus.value = ''; focusNode(); }
    if (action === 'expand') toggleExpanded();
  }));
  layout.addEventListener('change', resize);
  focus.addEventListener('change', () => { focusNode(); viewport.scrollIntoView({block: 'nearest'}); });
  viewport.addEventListener('focusin', event => {
    const node = event.target.closest('.node');
    if (node) { focus.value = node.querySelector('title').textContent; focusNode(); }
  });
  viewport.addEventListener('keydown', event => {
    if (event.target !== viewport && !event.target.closest('.node a')) return;
    const pans = {ArrowLeft: [-60, 0], ArrowRight: [60, 0], ArrowUp: [0, -60], ArrowDown: [0, 60]};
    if (pans[event.key]) { const [x, y] = pans[event.key]; cx += x / scale; cy += y / scale; fitting = false; draw(); }
    else if (event.key === '+' || event.key === '=') zoom(scale * 1.25);
    else if (event.key === '-') zoom(scale / 1.25);
    else if (event.key === '0') { focus.value = ''; focusNode(); }
    else return;
    event.preventDefault();
  });
  viewport.addEventListener('wheel', event => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const rect = viewport.getBoundingClientRect();
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size().height : 1);
    zoom(scale * Math.max(.8, Math.min(1.25, Math.exp(-delta * .01))),
      event.clientX - rect.left, event.clientY - rect.top);
  }, {passive: false});
  viewport.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    if (!pointers.size) dragged = false;
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY});
  });
  viewport.addEventListener('pointermove', event => {
    const previous = pointers.get(event.pointerId);
    if (!previous) return;
    if (!dragged && Math.hypot(event.clientX - previous.startX, event.clientY - previous.startY) < 5) return;
    dragged = true; fitting = false;
    viewport.classList.add('dragging'); viewport.setPointerCapture(event.pointerId);
    const other = [...pointers.entries()].find(([id]) => id !== event.pointerId)?.[1];
    if (other) {
      const oldDistance = Math.hypot(previous.x - other.x, previous.y - other.y);
      const nextDistance = Math.hypot(event.clientX - other.x, event.clientY - other.y);
      const rect = viewport.getBoundingClientRect();
      if (oldDistance > 0) zoom(scale * nextDistance / oldDistance,
        (previous.x + other.x) / 2 - rect.left, (previous.y + other.y) / 2 - rect.top);
      cx -= (event.clientX - previous.x) / 2 / scale;
      cy -= (event.clientY - previous.y) / 2 / scale;
    } else {
      cx -= (event.clientX - previous.x) / scale; cy -= (event.clientY - previous.y) / scale;
    }
    pointers.set(event.pointerId, {...previous, x: event.clientX, y: event.clientY}); draw();
  });
  function release(event) {
    pointers.delete(event.pointerId);
    if (!pointers.size) viewport.classList.remove('dragging');
  }
  viewport.addEventListener('pointerup', release);
  viewport.addEventListener('pointercancel', release);
  viewport.addEventListener('lostpointercapture', event => { if (event.target === viewport) release(event); });
  viewport.addEventListener('pointerleave', event => { if (!viewport.hasPointerCapture(event.pointerId)) release(event); });
  viewport.addEventListener('click', event => {
    if (dragged && event.detail > 0) { dragged = false; event.preventDefault(); event.stopPropagation(); }
  }, true);
  window.addEventListener('beforeprint', () => svg.setAttribute('viewBox', `${base.x} ${base.y} ${base.width} ${base.height}`));
  window.addEventListener('afterprint', draw);
  new ResizeObserver(resize).observe(viewport);
  resize();
});
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)


def required_text(record, fields, context):
    for field in fields:
        value = record.get(field)
        require(isinstance(value, str) and value.strip(), f"{context} needs a {field}")


def plan_reference(path, output):
    if not path:
        return ""
    require(isinstance(path, str) and path == path.strip(), "Invalid plan path")
    url = urlsplit(path)
    if url.scheme == "https" and url.netloc:
        return f'<p><a href="{html.escape(path)}">Source plan</a></p>'
    local = PurePosixPath(path)
    require(not url.scheme and not url.netloc and ".." not in local.parts, f"Invalid plan path: {path}")
    source = output.parent / Path(path)
    if source.is_file():
        relative = quote(os.path.relpath(source, output / "steps"))
        return f'<p><a href="{html.escape(relative)}">Source plan</a></p>'
    return f'<p>Source plan unavailable at <code>{html.escape(path)}</code></p>'


def graph(spec, links, direction="LR"):
    def dot(value):
        return json.dumps(value, ensure_ascii=False)

    lines = [
        "digraph schematic {",
        f'graph [rankdir={direction}, bgcolor="transparent", pad=0.2, nodesep=0.35, ranksep=0.65];',
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13, '
        'color="#b3cac6", fillcolor="#edf6f4", fontcolor="#162c32", margin="0.16,0.12"];',
        'edge [fontname="Helvetica", fontsize=10, color="#527477", fontcolor="#34494e"];',
    ]
    known = set()
    for node in spec["nodes"]:
        key = node["id"]
        require(identifier(key) and key not in known, f"Duplicate or invalid node ID: {key}")
        required_text(node, ("label",), key)
        known.add(key)
        attrs = [f"label={dot(node['label'])}"]
        if "step" in node:
            require(node["step"] in links, f"Unknown step linked from node {key}: {node['step']}")
            attrs.append(f"URL={dot(links[node['step']])}")
            attrs.append('color="#00717a", penwidth=2')
        lines.append(f"{dot(key)} [{', '.join(attrs)}];")
    require(known, "A schematic needs at least one node")
    for edge in spec["edges"]:
        start, end = edge["from"], edge["to"]
        require(start in known and end in known, f"Unknown diagram node in edge: {start} → {end}")
        required_text(edge, ("label",), f"Edge {start} → {end}")
        lines.append(f"{dot(start)} -> {dot(end)} [label={dot(edge['label'])}];")
    lines.append("}")
    result = subprocess.run(
        ["dot", "-Tsvg"], input="\n".join(lines), capture_output=True,
        encoding="utf-8", check=True, timeout=30,
    )
    return result.stdout[result.stdout.index("<svg"):]


def diagram(spec, links, label):
    variants = []
    for orientation, direction in (("horizontal", "LR"), ("vertical", "TB")):
        svg = graph(spec, links, direction)
        # Graphviz restarts element IDs for each SVG. Keep both variants unique.
        svg = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{orientation}-{m[1]}"', svg)
        variants.append(f'<div class="diagram-layout" data-layout="{orientation}">{svg}</div>')
    options = ''.join(f'<option value="{node["id"]}">{html.escape(node["label"])}</option>'
                      for node in spec["nodes"])
    return (
        f'<figure class="diagram" data-diagram data-orientation="auto" aria-label="{html.escape(label)}">'
        '<div class="toolbar" role="group" aria-label="Diagram controls">'
        '<button type="button" data-action="out" aria-label="Zoom out">−</button>'
        '<output class="zoom-level" aria-live="polite" aria-label="Zoom level"></output>'
        '<button type="button" data-action="in" aria-label="Zoom in">+</button>'
        '<button type="button" data-action="fit">Fit</button>'
        '<button type="button" data-action="actual">100%</button>'
        '<button type="button" data-action="expand" aria-expanded="false">Expand</button>'
        '<label>Layout <select data-layout-choice aria-label="Diagram layout">'
        '<option value="auto">Auto</option><option value="horizontal">Horizontal</option>'
        '<option value="vertical">Vertical</option></select></label>'
        '<label>Focus <select data-focus-node aria-label="Focus on a component">'
        f'<option value="">Whole diagram</option>{options}</select></label></div>'
        '<div class="viewport" tabindex="0" role="region" aria-label="Interactive diagram" '
        'aria-describedby="diagram-help">' + ''.join(variants) + '</div>'
        '<figcaption id="diagram-help">Drag to pan · Pinch or Ctrl/⌘ + scroll to zoom · '
        'On touch, swipe vertically to scroll; expand for free panning · '
        'Keyboard: arrows to pan, +/− to zoom, 0 to fit · Escape closes expanded view</figcaption></figure>'
    )


def navigation(steps, current=None):
    prefix = "" if current is None else "../"
    options = ['<option value="">Jump to a build step…</option>']
    for key, step in steps.items():
        selected = ' selected' if key == current else ''
        options.append(f'<option value="{prefix}steps/{key}.html"{selected}>'
                       f'{html.escape(step["workstream"])} · {step_title(step)}</option>')
    return (f'<nav class="topnav" aria-label="Project navigation"><a href="{prefix}index.html">Project map</a>'
            f'<a href="#diagram">Diagram</a><a href="{prefix}index.html#build-steps">Build steps</a>'
            '<label>Go to <select data-page-nav aria-label="Go to a build step">'
            + ''.join(options) + '</select></label></nav>')


def page(title, body, nav=""):
    return (
        '<!doctype html>\n<html lang="en"><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style>\n"
        f"<body>{nav}<main>{body}</main><script>{SCRIPT}</script></body></html>\n"
    )


def badge(status):
    return f'<span class="status {status}">{STATUS[status]}</span>'


def step_title(step):
    return html.escape(f"{step['unit']} · {step['title']}")


def step_page(step, steps, output):
    heading = step_title(step)
    content = (
        '<header><nav><a href="../index.html">← Project map</a></nav>'
        f'<p class="context">{html.escape(step["workstream"])}</p>'
        f'<h1>{heading}</h1>{badge(step["status"])}</header>'
        f'<p>{html.escape(step["summary"])}</p>'
        '<section id="diagram" aria-label="Build step schematic">'
        f'{diagram(step["diagram"], {key: f"{key}.html" for key in steps}, "Build step schematic")}</section>'
    )
    if step["depends_on"]:
        dependencies = [
            f'<li><a href="{key}.html">{html.escape(steps[key]["workstream"])} · '
            f'{step_title(steps[key])}</a></li>' for key in step["depends_on"]
        ]
        content += '<h2>Depends on</h2><ul>' + ''.join(dependencies) + '</ul>'
    if step["evidence"]:
        evidence = ''.join(f'<li>{html.escape(item)}</li>' for item in step["evidence"])
        content += f'<h2>Evidence</h2><ul>{evidence}</ul>'
    content += plan_reference(step["plan"], output)
    keys = list(steps)
    index = keys.index(step["id"])
    adjacent = []
    for position, label in ((index - 1, "← Previous step"), (index + 1, "Next step →")):
        if 0 <= position < len(keys):
            key = keys[position]
            adjacent.append(f'<a href="{key}.html">{label}: {step_title(steps[key])}</a>')
    content += '<nav class="step-nav" aria-label="Adjacent build steps">' + ''.join(adjacent) + '</nav>'
    return page(step["title"], content, navigation(steps, step["id"]))


def render(state, output):
    required_text(state, ("title", "summary"), "Project")
    steps = {}
    workstreams = defaultdict(list)
    for step in state["steps"]:
        key = step["id"]
        require(identifier(key) and key not in steps, f"Duplicate or invalid step ID: {key}")
        required_text(step, ("unit", "workstream", "title", "summary"), key)
        require(step["status"] in STATUS, f"Invalid status for {key}: {step['status']}")
        evidence = step["evidence"]
        require(isinstance(evidence, list) and all(isinstance(e, str) and e.strip() for e in evidence),
                f"Evidence for {key} must be a list of nonempty strings")
        require(step["status"] != "verified" or evidence, f"Verified step {key} needs evidence")
        steps[key] = step
        workstreams[step["workstream"]].append(key)
    for key, step in steps.items():
        dependencies = step["depends_on"]
        require(isinstance(dependencies, list) and all(dep in steps and dep != key for dep in dependencies),
                f"Step {key} has an invalid dependency")

    links = {key: f"steps/{key}.html" for key in steps}
    pages = {links[key]: step_page(step, steps, output) for key, step in steps.items()}
    architecture = diagram(state["diagram"], links, "Project architecture")
    body = (
        f'<header><h1>{html.escape(state["title"])}</h1><p>{html.escape(state["summary"])}</p></header>'
        f'<section id="diagram"><h2>Project architecture</h2>{architecture}</section>'
    )
    if workstreams:
        body += '<h2 id="build-steps">Build steps</h2>'
    for name, keys in workstreams.items():
        body += f'<h3>{html.escape(name)}</h3><ul class="steps">'
        for key in keys:
            step = steps[key]
            body += (f'<li class="step"><a href="{links[key]}">{step_title(step)}</a>'
                     f'{badge(step["status"])}</li>')
        body += '</ul>'
    pages["index.html"] = page(state["title"], body, navigation(steps))
    return pages


def replace_if_changed(path, content):
    # Each replacement is atomic. Publish step pages before their index links.
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, encoding="utf-8", mode="w", delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(content)
            output.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate and render in memory without writing HTML")
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    try:
        state_path = args.state.resolve(strict=True)
        pages = render(json.loads(state_path.read_text(encoding="utf-8")), state_path.parent)
        require(state_path.name not in pages, "Choose a state file name other than index.html")
        if args.check:
            print(f"X-ray checked {len(pages)} {'page' if len(pages) == 1 else 'pages'}.")
            return
        for name, content in pages.items():
            replace_if_changed(state_path.parent / name, content)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"X-ray: Graphviz could not render a schematic: {error.stderr.strip()}\n")
    except (AttributeError, KeyError, OSError, ValueError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"X-ray: {error}\n")
    print(state_path.parent / "index.html")


if __name__ == "__main__":
    main()
