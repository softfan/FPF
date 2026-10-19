#!/usr/bin/env python3
"""
test_mcp_server.py -- tests for the local MCP server.

The server is checked the way a client uses it: as a subprocess speaking
newline-delimited JSON-RPC on stdin/stdout.  That covers the parts a unit test
would miss -- framing, flushing, and surviving a bad message.

Three questions:

1. **Does it speak MCP?**  Handshake, tool listing, tool calls, errors.
2. **Does it honour its own contract?**  ``READING_TOOLS`` declares the exact
   argument set of every reading tool; the tests assert equality, so an
   argument cannot appear or vanish unnoticed.
3. **Does it answer correctly?**  Counts, reads, search, backlinks and the
   skill-maker tools must return real data from the built tree.

Usage from repo root::

    python skill-maker/tests/test_mcp_server.py
    python skill-maker/tests/test_mcp_server.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
_MAKER_DIR = _TESTS_DIR.parent                 # skill-maker/
_PKG_PARENT = _MAKER_DIR / "src"
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))
_SCRIPT_DIR = _PKG_PARENT / "skillmaker"        # the package: entry points, templates
_REPO_ROOT = _MAKER_DIR.parent                  # repository root
SERVER = _SCRIPT_DIR / "mcp_server.py"
SKILLS = _REPO_ROOT / "skills"

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

from skillmaker.mcp_server import DERIVED_TOOLS, MAKER_TOOLS, READING_TOOLS  # noqa: E402

PARITY_TOOLS = tuple(READING_TOOLS)
PARITY_ARGS = {name: set(args) for name, args in READING_TOOLS.items()}


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed.append(name)
            if self.verbose:
                print(f"  \u2713 {name}")
        else:
            self.failed.append((name, detail))
            print(f"  \u2717 {name}: {detail}")

    def equal(self, name: str, actual, expected):
        self.check(name, actual == expected, f"expected {expected!r}, got {actual!r}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'=' * 60}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed / {total} total")
        if self.failed:
            print("\nFailed tests:")
            for name, detail in self.failed:
                print(f"  \u2717 {name}: {detail}")
        print("=" * 60)
        return 0 if not self.failed else 1


class Client:
    """Minimal MCP client: writes JSON lines, reads JSON lines."""

    def __init__(self, skills_root: Path = SKILLS):
        # Explicit UTF-8 on both pipes: the server writes UTF-8, and on Windows
        # the locale codec would fail on the first non-ASCII pattern title.
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--skills-root", str(skills_root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self._id = 0

    def send(self, method: str, params: Optional[Dict] = None,
             notify: bool = False) -> Optional[Dict]:
        if not notify:
            self._id += 1
        message: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            message["id"] = self._id
        if params is not None:
            message["params"] = params
        # MCP stdio: one JSON object per line, no embedded newlines.
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"server closed the stream after {method}")
        return json.loads(line)

    def call(self, name: str, arguments: Optional[Dict] = None) -> Dict:
        response = self.send("tools/call", {"name": name, "arguments": arguments or {}})
        return response["result"]

    def payload(self, name: str, arguments: Optional[Dict] = None) -> Dict:
        result = self.call(name, arguments)
        return json.loads(result["content"][0]["text"])

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


# ---------------------------------------------------------------------------

def test_handshake(t: TestRunner) -> None:
    print("\n[1] Handshake and framing")
    c = Client()
    try:
        init = c.send("initialize", {"protocolVersion": "2025-06-18",
                                     "capabilities": {},
                                     "clientInfo": {"name": "test", "version": "1"}})
        t.equal("jsonrpc version", init.get("jsonrpc"), "2.0")
        result = init["result"]
        t.equal("protocol version", result["protocolVersion"], "2025-06-18")
        t.check("server info has a name", bool(result["serverInfo"]["name"]))
        t.check("declares tools capability", "tools" in result["capabilities"])

        c.send("notifications/initialized", notify=True)
        ping = c.send("ping")
        t.check("ping answered", "result" in ping, str(ping))

        listing = c.send("tools/list")
        tools = listing["result"]["tools"]
        t.check("tools listed", len(tools) >= 11, str(len(tools)))
        for tool in tools:
            t.check(f"{tool['name']} has a schema",
                    isinstance(tool.get("inputSchema"), dict))
            t.check(f"{tool['name']} is read-only",
                    tool.get("annotations", {}).get("readOnlyHint", True) is not False)
    finally:
        c.close()


def test_parity(t: TestRunner) -> None:
    print("\n[2] Reading-tool contract")
    c = Client()
    try:
        c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "1"}})
        tools = {tool["name"]: tool for tool in c.send("tools/list")["result"]["tools"]}

        for name in PARITY_TOOLS:
            t.check(f"exposes {name}", name in tools, str(sorted(tools)))

        for name, expected in PARITY_ARGS.items():
            if name not in tools:
                continue
            actual = set(tools[name]["inputSchema"].get("properties", {}))
            t.check(f"{name} matches its declared arguments",
                    actual == expected,
                    f"missing {sorted(expected - actual)}, "
                    f"extra {sorted(actual - expected)}")

        # A continuation carries the snapshot it was given, so every reading
        # tool must accept one even when it does not need it.
        status = c.payload("get_corpus_status")
        result = c.call("search", {"q": "decision", "limit": 1,
                                   "expected_snapshot": status["snapshot"]})
        t.check("accepts expected_snapshot", result["isError"] is False,
                result["content"][0]["text"][:200])

        # kind / suite filters behave, rather than being accepted and ignored.
        frameworks = c.payload("list_publications", {"kind": "DPF", "limit": 100})
        t.check("kind=DPF filters to frameworks",
                frameworks["total"] >= 10, str(frameworks["total"]))
        t.check("kind=DPF excludes fpf",
                all(p["id"] != "fpf" for p in frameworks["publications"]))

        suites = c.payload("list_publications", {"suite": "engineering", "limit": 100})
        t.equal("suite=engineering finds one skill", suites["total"], 1)
        t.equal("suite filter resolves the -suite name",
                suites["publications"][0]["id"], "engineering-suite")

        truncated = c.payload("read_pattern", {"pattern_id": "SYSE.24", "limit": 120})
        t.check("read_pattern honours limit",
                len(truncated["markdown"]) == 120, str(len(truncated["markdown"])))
        t.check("truncation reports continuation",
                truncated.get("next_offset") == 120, str(truncated.get("next_offset")))

        rng = c.payload("read_section", {"publication": "PSDA", "section": "PSDA.1",
                                         "through": "PSDA.2"})
        t.equal("through reads an inclusive range", rng["units"], ["PSDA.1", "PSDA.2"])

        stale = c.call("search", {"q": "decision", "expected_snapshot": "local-stale"})
        t.check("stale snapshot is refused", stale["isError"] is True)
        t.check("stale snapshot explains the fix",
                "restart discovery" in stale["content"][0]["text"],
                stale["content"][0]["text"][:160])

        extra = set(tools) - set(PARITY_TOOLS)
        expected_extra = set(DERIVED_TOOLS) | set(MAKER_TOOLS)
        t.check("adds derived and skill-maker tools", extra == expected_extra,
                f"missing {sorted(expected_extra - extra)}, "
                f"unexpected {sorted(extra - expected_extra)}")
        for name in DERIVED_TOOLS + MAKER_TOOLS:
            t.check(f"adds {name}", name in tools)
    finally:
        c.close()


def test_reading(t: TestRunner) -> None:
    print("\n[3] Reading tools")
    c = Client()
    try:
        c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "1"}})

        status = c.payload("get_corpus_status")
        t.equal("15 skills served", status["skills"], 15)
        t.equal("885 patterns served", status["patterns"], 885)
        t.check("snapshot reported", status["snapshot"].startswith("local-"),
                status["snapshot"])

        pubs = c.payload("list_publications", {"limit": 100})
        t.equal("lists 15 publications", pubs["total"], 15)
        ids = {p["id"] for p in pubs["publications"]}
        t.check("lists readable skill names", "decision-design" in ids, str(sorted(ids)))
        t.check("lists the suites", "engineering-suite" in ids)
        row = next(p for p in pubs["publications"] if p["id"] == "decision-design")
        t.equal("publication carries its DocID", row["docids"], ["PSDA"])

        # Pagination continues rather than truncating silently.
        page = c.payload("list_publications", {"limit": 5})
        t.check("pagination reports next_offset", page["next_offset"] == 5,
                str(page["next_offset"]))
        rest = c.payload("list_publications", {"limit": 5, "offset": 5})
        t.check("second page differs", rest["publications"] != page["publications"])

        found = c.payload("search", {"q": "decision", "limit": 5})
        t.check("search finds units", found["total"] > 0, str(found["total"]))
        t.check("search rows name a file",
                all("file" in r for r in found["results"]))

        by_id = c.payload("search", {"q": "PSDA.1", "limit": 3})
        t.check("search matches an ID", by_id["total"] > 0)
        t.equal("ID search ranks the exact unit first",
                by_id["results"][0]["pattern_id"], "PSDA.1")

        scoped = c.payload("search", {"q": "pattern", "publication": "PSDA", "limit": 50})
        t.check("search scopes to a publication",
                all(r["publication"] == "decision-design" for r in scoped["results"]),
                str({r["publication"] for r in scoped["results"]}))

        unit = c.payload("read_pattern", {"pattern_id": "SYSE.24"})
        t.equal("read_pattern publication", unit["publication"], "engineering-suite")
        t.check("read_pattern returns markdown", len(unit["markdown"]) > 500,
                str(len(unit["markdown"])))
        t.check("read_pattern names the file",
                unit["file"].startswith("skills/engineering-suite/reference/syse/"),
                unit["file"])

        hub = c.payload("read_section", {"publication": "PSDA"})
        t.check("read_section defaults to SKILL.md", "name: decision-design" in hub["markdown"],
                hub["markdown"][:120])

        intro = c.payload("read_section", {"publication": "decision-design",
                                           "section": "practical_entries"})
        t.check("read_section reads an intro", "Practical entries" in intro["markdown"],
                intro["markdown"][:120])

        doc = c.payload("read_section", {"publication": "fpf", "section": "using-fpf"})
        t.check("read_section reads a document", "Using FPF Library" in doc["markdown"],
                doc["markdown"][:120])

        toc = c.payload("get_table_of_contents", {"publication": "PSDA", "limit": 200})
        t.check("toc lists sections", toc["total"] > 40, str(toc["total"]))
        keys = {s["key"] for s in toc["sections"]}
        t.check("toc includes units", "PSDA.1" in keys)
        t.check("toc includes intros", any(k.startswith("intro:") for k in keys))

        only = c.payload("get_table_of_contents",
                         {"publication": "PSDA", "patterns_only": True, "limit": 200})
        t.equal("patterns_only filters", only["total"], 18)

        back = c.payload("backlinks", {"pattern_id": "PSDA.1", "limit": 100})
        t.check("backlinks finds mentions", back["total"] > 0, str(back["total"]))
        t.check("backlinks excludes the unit itself",
                all(r["pattern_id"] != "PSDA.1" for r in back["results"]))
    finally:
        c.close()


def test_skill_maker_tools(t: TestRunner) -> None:
    print("\n[4] Skill-maker tools")
    c = Client()
    try:
        c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "1"}})

        route = c.payload("route", {"pattern_id": "PSDA.1"})
        t.check("route names prerequisites", bool(route.get("direct")), str(route)[:200])
        t.check("route gives a chain", len(route.get("chain", [])) > 1)
        t.check("route names the checking section", bool(route.get("acceptance")),
                str(route.get("acceptance")))

        found = c.payload("entries", {"q": "formulations", "limit": 5})
        t.check("entries match a situation", found["total"] > 0, str(found["total"]))
        t.check("entries name a starting unit",
                all(e["start_with"] for e in found["entries"]))

        terms = c.payload("glossary", {"q": "boundary", "limit": 5})
        t.check("glossary finds terms", terms["total"] > 0, str(terms["total"]))
        t.check("glossary quotes a meaning",
                all(len(e["meaning"]) > 20 for e in terms["entries" if False else "terms"]))

        profiles = c.payload("list_profiles")
        t.equal("lists 8 profiles", len(profiles["profiles"]), 8)
        kinds = {p["kind"] for p in profiles["profiles"]}
        t.check("profiles cover extension kinds",
                {"ADR", "Standards", "Generic"} <= kinds, str(sorted(kinds)))

        probe = c.payload("probe_document", {"path": "DPFs/README.md"})
        t.equal("probe finds a Guide", probe["kind"], "Guide")
        t.check("probe reports evidence", bool(probe["evidence"]), str(probe))

        probe2 = c.payload("probe_document",
                           {"path": "DPFs/Management DPF Suite/LEADERSHIP-PRINCIPLES-FRAMEWORK.md"})
        t.equal("probe finds a DPF", probe2["kind"], "DPF")
        t.equal("probe counts patterns", probe2["patterns"], 3)

        plan = c.payload("plan_decomposition", {"path": "DPFs/README.md", "skill": "guide"})
        t.check("plan lists artefacts", len(plan["artefacts"]) >= 3, str(plan["artefacts"]))
        t.check("plan writes nothing",
                not (_REPO_ROOT / "guide").exists())
    finally:
        c.close()


def test_errors(t: TestRunner) -> None:
    print("\n[5] Error handling")
    c = Client()
    try:
        c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "1"}})

        bad = c.call("read_pattern", {"pattern_id": "NOPE.99"})
        t.check("unknown unit is an error", bad["isError"] is True)
        t.check("error message is useful", "NOPE.99" in bad["content"][0]["text"],
                bad["content"][0]["text"][:120])

        bad_pub = c.call("get_table_of_contents", {"publication": "nope"})
        t.check("unknown publication is an error", bad_pub["isError"] is True)

        unknown_tool = c.call("no_such_tool", {})
        t.check("unknown tool is an error", unknown_tool["isError"] is True)

        # A malformed line must not kill the server.
        c.proc.stdin.write("this is not json\n")
        c.proc.stdin.flush()
        line = c.proc.stdout.readline()
        parsed = json.loads(line)
        t.check("malformed input gets a parse error",
                parsed.get("error", {}).get("code") == -32700, str(parsed)[:160])

        after = c.payload("get_corpus_status")
        t.check("server survives a bad message", after["skills"] == 15)

        missing = c.call("probe_document", {"path": "does/not/exist.md"})
        t.check("missing file is an error", missing["isError"] is True)
    finally:
        c.close()


def test_cli(t: TestRunner) -> None:
    print("\n[6] CLI")
    r = subprocess.run([sys.executable, str(SERVER), "--selftest"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(_REPO_ROOT))
    t.check("--selftest exits 0", r.returncode == 0, ((r.stdout or "") + (r.stderr or ""))[-400:])
    t.check("--selftest reports PASSED", "PASSED" in (r.stdout or ""), (r.stdout or "")[-200:])

    r = subprocess.run([sys.executable, str(SERVER), "--list-tools"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(_REPO_ROOT))
    t.check("--list-tools exits 0", r.returncode == 0, (r.stderr or "")[-300:])
    tools = json.loads(r.stdout)
    t.check("--list-tools prints JSON", len(tools) >= 11, str(len(tools)))


# ---------------------------------------------------------------------------

def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("=" * 60)
    print("MCP Server -- Tests")
    print("=" * 60)

    if not SKILLS.exists():
        print("skills/ not found -- run bash skill-maker/build.sh first",
              file=sys.stderr)
        return 1

    t = TestRunner(verbose=verbose)
    test_handshake(t)
    test_parity(t)
    test_reading(t)
    test_skill_maker_tools(t)
    test_errors(t)
    test_cli(t)
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
