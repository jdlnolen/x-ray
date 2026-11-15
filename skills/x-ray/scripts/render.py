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
main { max-width: 68rem; margin: auto; padding: clamp(1rem, 4vw, 3rem); }
header { border-bottom: 1px solid #d3dfdd; padding-bottom: 1rem; }
h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(1.85rem, 5vw, 3rem); margin: .6rem 0; }
h2 { margin: 1.75rem 0 .65rem; }
h3 { margin: 1.2rem 0 .5rem; }
p { max-width: 76ch; }
a { color: #005e68; text-underline-offset: .18em; }
a:focus-visible { outline: 2px solid #005e68; outline-offset: 3px; }
figure, .step { background: white; border: 1px solid #d3dfdd; border-radius: .6rem; }
figure { overflow: auto; margin: 1rem 0; padding: .7rem; }
figure svg { display: block; margin: auto; }
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


def graph(spec, links):
    def dot(value):
        return json.dumps(value, ensure_ascii=False)

    lines = [
        "digraph schematic {",
        'graph [rankdir=LR, bgcolor="transparent", pad=0.2, nodesep=0.35, ranksep=0.65];',
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


def page(title, body):
    return (
        '<!doctype html>\n<html lang="en"><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style>\n"
        f"<main>{body}</main></html>\n"
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
        f'<figure aria-label="Build step schematic">{graph(step["diagram"], {})}</figure>'
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
    return page(step["title"], content)


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
    architecture = graph(state["diagram"], links)
    body = (
        f'<header><h1>{html.escape(state["title"])}</h1><p>{html.escape(state["summary"])}</p></header>'
        f'<h2>Project architecture</h2><figure aria-label="Project architecture">{architecture}</figure>'
    )
    if workstreams:
        body += '<h2>Build steps</h2>'
    for name, keys in workstreams.items():
        body += f'<h3>{html.escape(name)}</h3><ul class="steps">'
        for key in keys:
            step = steps[key]
            body += (f'<li class="step"><a href="{links[key]}">{step_title(step)}</a>'
                     f'{badge(step["status"])}</li>')
        body += '</ul>'
    pages["index.html"] = page(state["title"], body)
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
