import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


RENDERER = Path(__file__).resolve().parents[1] / "skills/x-ray/scripts/render.py"


class RenderPreflightTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.state_file = self.output / "state.json"
        diagram = {"nodes": [{"id": "entry", "label": "Entry"}], "edges": []}
        self.state = {
            "title": "Project", "summary": "Project summary", "diagram": diagram,
            "steps": [{
                "id": "build-u1", "unit": "U1", "workstream": "Build", "title": "First step",
                "plan": "", "status": "planned", "depends_on": [], "summary": "Step summary",
                "diagram": diagram, "evidence": [],
            }],
        }
        self.save_state()

    def save_state(self):
        self.state_file.write_text(json.dumps(self.state), encoding="utf-8")

    def run_renderer(self, *flags):
        return subprocess.run(
            [sys.executable, str(RENDERER), *flags, str(self.state_file)],
            capture_output=True, text=True,
        )

    def test_check_reports_page_count_without_creating_or_replacing_pages(self):
        fresh = self.run_renderer("--check")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn("2 pages", fresh.stdout)
        self.assertEqual(list(self.output.iterdir()), [self.state_file])

        self.assertEqual(self.run_renderer().returncode, 0)
        index = self.output / "index.html"
        page = self.output / "steps/build-u1.html"
        self.assertIn('href="steps/build-u1.html"', index.read_text())
        self.assertIn("<svg", page.read_text())
        previous = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (index, page)}

        self.state["title"] = "A changed title that would refresh the map"
        self.state["steps"][0]["title"] = "A changed title that would refresh the step page"
        self.save_state()
        checked = self.run_renderer("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in previous}, previous)

    def test_check_reports_validation_failure_and_preserves_previous_pages(self):
        self.assertEqual(self.run_renderer().returncode, 0)
        previous = {path: path.read_bytes() for path in self.output.rglob("*.html")}
        self.state["diagram"]["edges"] = [{"from": "entry", "to": "missing", "label": "bad link"}]
        self.save_state()
        checked = self.run_renderer("--check")
        self.assertEqual(checked.returncode, 1, checked.stderr)
        self.assertIn("Unknown diagram node", checked.stderr)
        self.assertEqual({path: path.read_bytes() for path in previous}, previous)

    def test_large_graph_has_both_orientations_and_preserves_node_links(self):
        self.state["diagram"] = {
            "nodes": [{"id": f"node-{i}", "label": f"Component {i}", "step": "build-u1"}
                      for i in range(12)],
            "edges": [{"from": f"node-{i}", "to": f"node-{i+1}", "label": "passes records"}
                      for i in range(11)],
        }
        self.save_state()
        self.assertEqual(self.run_renderer().returncode, 0)

        class Diagrams(HTMLParser):
            def __init__(self):
                super().__init__()
                self.boxes = []
                self.links = []
                self.ids = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "svg":
                    self.boxes.append([float(v) for v in attrs["viewbox"].split()])
                if "id" in attrs:
                    self.ids.append(attrs["id"])
                if tag == "a" and "xlink:href" in attrs:
                    self.links.append(attrs["xlink:href"])

        diagrams = Diagrams()
        diagrams.feed((self.output / "index.html").read_text())
        self.assertEqual(len(diagrams.boxes), 2)
        horizontal, vertical = diagrams.boxes
        self.assertGreater(horizontal[2], horizontal[3])
        self.assertGreater(vertical[3], vertical[2])
        self.assertEqual(diagrams.links, ["steps/build-u1.html"] * 24)
        self.assertEqual(len(diagrams.ids), len(set(diagrams.ids)))

    def test_step_diagram_links_use_the_step_directory(self):
        self.state["steps"][0]["diagram"] = {
            "nodes": [{"id": "related", "label": "Related step", "step": "build-u1"}], "edges": [],
        }
        self.save_state()
        result = self.run_renderer()
        self.assertEqual(result.returncode, 0, result.stderr)
        page = (self.output / "steps/build-u1.html").read_text()
        self.assertEqual(page.count('xlink:href="build-u1.html"'), 2)
