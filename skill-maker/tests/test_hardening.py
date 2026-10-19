#!/usr/bin/env python3
"""Offline regression tests for review findings; no third-party dependencies."""
from __future__ import annotations

import contextlib
import copy
import http.client
import io
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "skill-maker" / "src"))
from skillmaker._fpf_common import ensure_utf8_stdio
from skillmaker import frameworks as F
from skillmaker import fpf_update, skill_index
from skillmaker.build_generic import build, config_for
from skillmaker.http_transport import HttpServer, SessionStore
from skillmaker.mcp_server import Server, serve
from skillmaker.skill_config import DPF_SKILL_CONFIGS
from skillmaker.split_spec import build_skill, _source_digest
from skillmaker.skill_config import DocSpec

ensure_utf8_stdio()


class TestRunner:
    def __init__(self, verbose=False):
        self.passed = 0
        self.failed = 0
        self.failures = []
        self.verbose = verbose
        self.output = sys.stdout

    def check(self, name, condition):
        if condition:
            self.passed += 1
            if self.verbose:
                print(f"  PASS {name}", file=self.output)
        else:
            self.failed += 1
            self.failures.append(name)
            print(f"  FAIL {name}", file=self.output)

    def rejects(self, name, action):
        try:
            action()
        except (ValueError, OSError):
            self.check(name, True)
        else:
            self.check(name, False)


def fixture(base):
    root = base / "workspace" / "skills"
    skill = root / "demo"
    ref = skill / "reference" / "demo"
    ref.mkdir(parents=True)
    (root / "index.json").write_bytes(json.dumps({"skills": [
        {"name": "demo", "kind": "Framework", "docids": ["DEMO"]}
    ]}).encode())
    (skill / ".demo_manifest.json").write_bytes(json.dumps([
        {"kind": "unit", "id": "DEMO.1", "title": "Example", "role": "pattern",
         "framework": "demo", "key": "DEMO.1.md"}
    ]).encode())
    unit = ref / "DEMO.1.md"
    unit.write_bytes(b"## DEMO.1 - Example\n\nEdition one.\n")
    return root, unit


def rpc(name, args):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


def test_mcp(t, base):
    root, unit = fixture(base)
    server = Server(root)
    unread = Server(root)
    snapshot = server.library.snapshot
    t.check("snapshot stable for unchanged corpus", unread.library.snapshot == snapshot)
    old = server.call("read_pattern", {"pattern_id": "DEMO.1"})
    unit.write_bytes(b"## DEMO.1 - Example\n\nEdition TWO.\n")
    newer = Server(root)
    t.check("text-only change updates snapshot", newer.library.snapshot != snapshot)
    t.rejects("old snapshot rejected", lambda: newer.call("read_pattern", {
        "pattern_id": "DEMO.1", "expected_snapshot": snapshot}))
    t.check("running corpus stays immutable", server.call("read_pattern", {
        "pattern_id": "DEMO.1"})["markdown"] == old["markdown"])
    t.check("previously unread text stays immutable", unread.library.body(unit) == old["markdown"])
    unit.unlink()
    t.check("deleted on-disk unit stays readable", server.call("read_pattern", {
        "pattern_id": "DEMO.1"})["markdown"] == old["markdown"])
    for name, args in (("read_pattern", {"pattern_id": "DEMO.1"}),
                       ("search", {"q": "example"}),
                       ("get_table_of_contents", {"publication": "demo"}),
                       ("backlinks", {"pattern_id": "DEMO.1"})):
        t.check(f"{name} returns snapshot", server.call(name, args).get("snapshot") == snapshot)
    for name, args in (("search", {"q": "x", "limit": -1}),
                       ("search", {"q": "x", "limit": True}),
                       ("search", {"q": "x", "limit": 201}),
                       ("search", {"q": "x", "extra": 1}),
                       ("read_pattern", {}), ("no_such_tool", {}),
                       ("search", []), ("search", {"q": "x", "offset": -1}),
                       ("read_pattern", {"pattern_id": "DEMO.1", "tier": "wrong"})):
        response = server.handle(rpc(name, args))
        t.check(f"invalid tool call {name} {args}", response.get("error", {}).get("code") == -32602)
    for message in ([], None, "x", {"method": "ping", "id": 1},
                    {"jsonrpc": "2.0", "method": "tools/call", "params": [], "id": 1}):
        output = io.StringIO()
        try:
            serve(server, io.StringIO(json.dumps(message) + '\n{"jsonrpc":"2.0","method":"ping","id":2}\n'), output)
            responses = [json.loads(line) for line in output.getvalue().splitlines()]
            t.check(f"invalid envelope survives {message!r}",
                    len(responses) == 2 and responses[0].get("error", {}).get("code") == -32600
                    and responses[1].get("id") == 2)
        except Exception:
            t.check(f"invalid envelope survives {message!r}", False)
    unknown = server.handle({"jsonrpc": "2.0", "method": "unknown", "id": None})
    t.check("null id still receives a response", isinstance(unknown, dict)
            and unknown.get("error", {}).get("code") == -32601)
    t.check("non-string tool name is invalid params", server.handle(rpc([], {})).get(
        "error", {}).get("code") == -32602)
    response = server.call("read_pattern", {"pattern_id": "DEMO.1", "limit": 7})
    t.check("paged byte count describes returned markdown",
            response["returned_bytes"] == len(response["markdown"].encode("utf-8")))
    t.rejects("unknown publication hint is rejected", lambda: server.call(
        "read_pattern", {"pattern_id": "DEMO.1", "publication": "missing"}))
    for version in ("2025-06-18", "2025-03-26"):
        init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": version}})
        t.check(f"initialization negotiates {version}", init["result"]["protocolVersion"] == version)
    for message in ({"jsonrpc": "2.0", "id": 1, "method": ""},
                    {"jsonrpc": "2.0", "id": 1, "method": "ping", "result": {}},
                    {"jsonrpc": "2.0", "id": True, "method": "ping"},
                    {"jsonrpc": "2.0", "id": 1, "result": {}, "error": {}}):
        t.check("ambiguous envelope rejected", server.handle(message).get("error", {}).get("code") == -32600)
    for malformed in ('{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":NaN}}',
                      '{"jsonrpc":"2.0","id":1,"method":"ping","method":"initialize"}'):
        output = io.StringIO()
        serve(server, io.StringIO(malformed + '\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n'), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        t.check("nonstandard JSON rejected without killing stdio", responses[0].get("error", {}).get("code") == -32700
                and responses[1].get("id") == 2)
    output = io.StringIO()
    serve(server, io.StringIO('{"jsonrpc":"2.0","method":"bad","id":"\\ud800"}\n'), output)
    t.check("surrogate id response stays valid UTF-8", bool(output.getvalue().encode("utf-8")))
    output = io.StringIO()
    serve(server, io.StringIO("[" * 1200 + "]" * 1200
          + '\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n'), output)
    t.check("deep JSON survives stdio", [json.loads(line).get("id")
            for line in output.getvalue().splitlines()] == [None, 2])
    outside = base / "private.md"
    outside.write_bytes(b"# Private\n")
    for name in ("probe_document", "plan_decomposition"):
        for value in (str(outside), "../private.md", "."):
            t.rejects(f"{name} confines {value}", lambda n=name, v=value: server.call(n, {"path": v}))
    inside = root.parent / "notes.md"
    inside.write_bytes(b"# Notes\n")
    t.check("inside Markdown allowed", server.call("probe_document", {"path": "notes.md"})["kind"] == "Generic")
    t.check("valid notification has no response", server.handle({
        "jsonrpc": "2.0", "method": "notifications/initialized"}) is None)
    link = root.parent / "escape.md"
    try:
        link.symlink_to(outside)
    except OSError:
        print("  SKIP symlink creation unavailable")
    else:
        t.rejects("symlink escape rejected", lambda: server.call("probe_document", {"path": "escape.md"}))
    oversized = root.parent / "large.md"
    with oversized.open("wb") as stream:
        stream.truncate(33 * 1024 * 1024)
    t.rejects("oversized document rejected", lambda: server.call("probe_document", {"path": "large.md"}))
    if hasattr(os, "mkfifo"):
        fifo = root.parent / "pipe.md"
        os.mkfifo(fifo)
        t.rejects("special file rejected", lambda: server.call("probe_document", {"path": "pipe.md"}))


def test_build(t, base):
    base.mkdir(parents=True)
    source = base / "notes.md"
    source.write_bytes(b"# Notes\n\nSome notes.\n")
    cfg = config_for(source, F.by_key("generic"), "notes", base / "notes", "lookup")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        build_skill(cfg)
        apply = config_for(source, F.by_key("generic"), "notes", cfg.output, "apply")
        build_skill(apply)
        t.check("genre change creates roles", (cfg.output / "roles" / "reasoner.md").is_file())
        boot = cfg.output / "boot.md"
        boot.unlink()
        build_skill(apply)
        t.check("missing boot restored", boot.is_file())
        cache = cfg.output / ".notes_hashes.json"
        cache.write_bytes(b"invalid json")
        build_skill(apply)
        t.check("corrupt hash registry repaired", isinstance(json.loads(cache.read_text("utf-8")), dict))
        for value in (b"[]", b"null", b'"text"'):
            cache.write_bytes(value)
            build_skill(apply)
            t.check(f"wrong-shape hash registry {value!r} repaired",
                    isinstance(json.loads(cache.read_text("utf-8")), dict))
        manifest = cfg.output / ".notes_manifest.json"
        manifest.write_bytes(b"[]")
        build_skill(apply)
        t.check("edited manifest restored", bool(json.loads(manifest.read_text("utf-8"))))
        registry = json.loads(cache.read_text("utf-8"))
        registry.pop("boot.md")
        cache.write_bytes(json.dumps(registry).encode())
        boot.unlink()
        build_skill(apply)
        t.check("deleted registry entry cannot hide missing output", boot.is_file())
        dpf = copy.deepcopy(next(c for c in DPF_SKILL_CONFIGS.values() if c.name == "decision-design"))
        dpf.output = base / "decision-design"
        build_skill(dpf, emit_views=True)
        view = next(dpf.output.rglob("contract/*.md"))
        view.unlink()
        build_skill(dpf, emit_views=True)
        t.check("individual missing view restored", view.is_file())
        for value in (b"[]", b"null", b'"text"'):
            (cfg.output / ".notes_build.json").write_bytes(value)
            try:
                build_skill(apply)
                valid = isinstance(json.loads((cfg.output / ".notes_build.json").read_text("utf-8")), dict)
            except (AttributeError, TypeError):
                valid = False
            t.check(f"wrong-shape stamp {value!r} repaired", valid)
        build_skill(apply, force=True)
        boot.write_bytes(b"corrupted generated content\n")
        build_skill(apply)
        t.check("changed generated output restored", boot.read_bytes() != b"corrupted generated content\n")
        curated = dpf.output / "curated-routes.json"
        curated.write_bytes(b'{"routes":[{"id":"PSDA.1","chain":["PSDA.1"],"review":"manual"}]}')
        build_skill(dpf)
        routes = json.loads((dpf.output / "reference/routes.json").read_text("utf-8"))
        t.check("curated route edit invalidates build", any(
            route.get("review") == "manual" for route in routes["routes"]))
        curated.write_bytes(b"[]")
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            rc = build_skill(dpf)
        t.check("wrong-shape curated routes warn rather than crash", rc == 0
                and "ignored" in diagnostics.getvalue() and curated.read_bytes() == b"[]")
        original_source = source.read_bytes()
        sentinel = base / "unrelated.txt"
        sentinel.write_bytes(b"do not delete")
        t.check("builder rejects output containing source", build(source, "unsafe", "generic", base) == 1)
        t.check("unsafe output leaves source intact", source.exists() and source.read_bytes() == original_source)
        t.check("unsafe output leaves unrelated files intact", sentinel.is_file())
        t.check("engine also rejects output containing source", build_skill(
            config_for(source, F.by_key("generic"), "unsafe", base)) == 1)
        other_output = base / "unmarked"
        other_output.mkdir()
        (other_output / "important.txt").write_bytes(b"retain me")
        t.check("generic builder rejects unmarked nonempty output", build(
            source, "unmarked", "generic", other_output) == 1)
        t.check("unmarked files not pruned", (other_output / "important.txt").read_bytes() == b"retain me")
        t.check("generic builder rejects different skill marker", build(
            source, "different", "generic", cfg.output) == 1)
        # Two publications can change while their concatenated bytes stay equal.
        first = base / "first.md"
        second = base / "second.md"
        first.write_bytes(b"abc")
        second.write_bytes(b"def")
        framed = copy.deepcopy(cfg)
        framed.docs = [DocSpec(first, "first", "First", ""),
                       DocSpec(second, "second", "Second", "")]
        before = _source_digest(framed)
        first.write_bytes(b"abcd")
        second.write_bytes(b"ef")
        t.check("source fingerprint preserves publication boundaries", _source_digest(framed) != before)
        second.write_bytes(b"")
        before = _source_digest(framed)
        second.unlink()
        t.check("missing source differs from empty source", _source_digest(framed) != before)
    with patch.object(skill_index, "SKILLS_ROOT", base):
        rows = skill_index.collect()
    t.check("generic skill discovered in index", any(r["name"] == "notes" for r in rows))
    custom = base / "custom"
    custom.mkdir()
    (custom / ".skill.json").write_bytes(b'{"name":"custom","title":"Custom"}')
    (custom / ".custom_manifest.json").write_bytes(json.dumps([
        {"kind": "unit", "id": "ZZ.1", "role": "pattern", "framework": "zz", "key": "ZZ.1.md"}
    ]).encode())
    with patch.object(skill_index, "SKILLS_ROOT", base):
        t.check("custom DocID appears in routing", skill_index.payload(skill_index.collect())["docid_to_skill"].get("ZZ") == "custom")
    duplicate_rows = [{"name": "first", "docids": ["ZZ"]}, {"name": "second", "docids": ["zz"]}]
    t.rejects("ambiguous DocID routing rejected", lambda: skill_index.payload(duplicate_rows))
    incomplete = base / "incomplete"
    incomplete.mkdir()
    (incomplete / ".skill.json").write_bytes(b'{"name":"incomplete"}')
    with patch.object(skill_index, "SKILLS_ROOT", base):
        t.check("unfinished custom skill not advertised", not any(
            row["name"] == "incomplete" for row in skill_index.collect()))
    moved = base / "moved"
    cfg.output.rename(moved)
    with patch.object(skill_index, "SKILLS_ROOT", base):
        t.check("renamed skill directory discovered via marker", any(
            row["name"] == "moved" and row["built"] for row in skill_index.collect()))
        duplicates = base / "duplicates"
        duplicates.mkdir()
        (duplicates / ".duplicates_manifest.json").write_bytes((custom / ".custom_manifest.json").read_bytes())
        t.rejects("index rejects duplicate units", lambda: skill_index._all_units([
            {"name": "custom", "built": True}, {"name": "duplicates", "built": True}]))
    cross = {"demo": [{"id": "A.1", "title": "Example", "skill": "fpf"}]}
    text = skill_index.render_cross([], cross)
    t.check("cross links stay under skills", "(fpf/)" in text and "(../fpf/)" not in text)


def test_update(t, base):
    base.mkdir(parents=True)
    names = [name for name, _ in fpf_update.LIBRARY_DOCS] + ["DPFs/fake.md"]
    for name in names:
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"old edition\n")
    urls = []
    def download(url, dest):
        urls.append(url)
        if dest.name == "fake.md":
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"new edition\n")
        return True
    with patch.object(fpf_update, "_REPO_ROOT", base), \
         patch.object(fpf_update, "_resolve_revision", return_value="a" * 40), \
         patch.object(fpf_update, "download_file", side_effect=download), \
         contextlib.redirect_stdout(io.StringIO()):
        t.check("DPF failure propagates", not fpf_update.step_download(with_dpfs=True))
        t.check("failed update leaves all sources unchanged", all(
            (base / name).read_bytes() == b"old edition\n" for name in names))
        t.check("downloads pin a single commit", all('/' + 'a' * 40 + '/' in url for url in urls))
        urls.clear()
        t.check("successful staged update", fpf_update.step_download())
        t.check("all requested documents replaced", all(
            (base / name).read_bytes() == b"new edition\n" for name, _ in fpf_update.LIBRARY_DOCS))
        write_bytes = Path.write_bytes
        interrupted = base / "USING-FPF.md"
        def fail_once(path, data):
            if path == interrupted and data == b"new edition\n":
                raise OSError("simulated replacement failure")
            return write_bytes(path, data)
        for name, _ in fpf_update.LIBRARY_DOCS:
            (base / name).write_bytes(b"old edition\n")
        with patch.object(Path, "write_bytes", fail_once):
            t.check("replacement failure reported", not fpf_update.step_download())
        t.check("replacement failure restores previous bytes", all(
            (base / name).read_bytes() == b"old edition\n" for name, _ in fpf_update.LIBRARY_DOCS))
    commands = []
    with patch.object(fpf_update, "_run", side_effect=lambda cmd: commands.append(cmd) or 0), \
         contextlib.redirect_stdout(io.StringIO()):
        t.check("DPF split workflow succeeds", fpf_update.step_split(with_dpfs=True))
        t.check("DPF update rebuilds all skills", any("split_dpf_spec.py" in cmd[1] and "--all" in cmd for cmd in commands))
        t.check("update rebuilds index", any("skill_index.py" in cmd[1] for cmd in commands))
        commands.clear()
        t.check("DPF verification workflow succeeds", fpf_update.step_test(with_dpfs=True))
        t.check("DPF verification includes catalogue checks", any("test_frameworks.py" in cmd[1] for cmd in commands))
    with patch.object(fpf_update, "_MAKER_DIR", base / "missing-tests"), contextlib.redirect_stdout(io.StringIO()):
        t.check("missing verification suite fails update", not fpf_update.step_test())
    originals = {name: (base / name).read_bytes() for name, _ in fpf_update.LIBRARY_DOCS}
    recovery = base / "recovery"
    recovery.mkdir()
    mkdtemp = tempfile.mkdtemp
    def recovery_directory(*args, **kwargs):
        if kwargs.get("prefix") == "fpf-update-recovery-":
            return str(recovery)
        return mkdtemp(*args, **kwargs)
    first = base / "FPF-Spec.md"
    def fail_and_block_rollback(path, data):
        if path == interrupted and data == b"new edition\n":
            raise OSError("simulated replacement failure")
        if path == first and data == originals[first.name]:
            raise OSError("simulated rollback failure")
        return write_bytes(path, data)
    diagnostics = io.StringIO()
    with patch.object(fpf_update, "_REPO_ROOT", base), \
         patch.object(fpf_update, "_resolve_revision", return_value="a" * 40), \
         patch.object(fpf_update, "download_file", side_effect=download), \
         patch.object(fpf_update.tempfile, "mkdtemp", side_effect=recovery_directory), \
         patch.object(Path, "write_bytes", fail_and_block_rollback), \
         contextlib.redirect_stdout(diagnostics):
        t.check("incomplete rollback fails update", not fpf_update.step_download())
    t.check("rollback failure reported honestly", "Rollback incomplete" in diagnostics.getvalue())
    t.check("rollback recovery preserves original bytes", all(
        (recovery / name).read_bytes() == data for name, data in originals.items()))
    dest = base / "download.md"
    for body in (b"", b" \n\t", b"\xff", b"# Valid publication\n"):
        with patch.object(fpf_update.urllib.request, "urlopen", return_value=io.BytesIO(body)), \
             contextlib.redirect_stdout(io.StringIO()):
            ok = fpf_update.download_file("https://example.invalid/source", dest)
        t.check(f"download validates bytes {body!r}", ok == (body == b"# Valid publication\n"))
    linked = base / "linked-root"
    linked.mkdir()
    outside = base / "outside.md"
    outside.write_bytes(b"private source\n")
    try:
        (linked / "FPF-Spec.md").symlink_to(outside)
    except OSError:
        print("  SKIP update destination symlink unavailable")
    else:
        with patch.object(fpf_update, "_REPO_ROOT", linked), \
             patch.object(fpf_update, "_resolve_revision") as resolve, \
             contextlib.redirect_stdout(io.StringIO()):
            t.check("updater rejects symlink before network access", not fpf_update.step_download()
                    and resolve.call_count == 0 and outside.read_bytes() == b"private source\n")


def test_http(t, base):
    root, _ = fixture(base)
    httpd = HttpServer(("127.0.0.1", 0), Server(root), lambda: "test")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    def request(method, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=3)
        try:
            conn.request(method, "/mcp", body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()
    try:
        _, headers, _ = request("POST", json.dumps({"jsonrpc": "2.0", "id": 1,
            "method": "initialize", "params": {}}))
        sid = headers["Mcp-Session-Id"]
        code, _, _ = request("DELETE", headers={"Mcp-Session-Id": sid, "MCP-Protocol-Version": "1999-01-01"})
        t.check("DELETE checks version", code == 400)
        t.check("invalid DELETE retains session", httpd.sessions.valid(sid))
        if not httpd.sessions.valid(sid):
            sid = httpd.sessions.create()
        _, _, body = request("POST", json.dumps({"jsonrpc": "2.0", "id": 2,
            "method": "tools/list"}), {"Mcp-Session-Id": sid})
        tools = json.loads(body)["result"]["tools"]
        t.check("HTTP maker tools disabled", not any(tool["name"] == "probe_document" for tool in tools))
        t.check("HTTP status reports enabled tools", httpd.mcp.call("get_corpus_status", {})["tools"] == len(tools))
        for method in ("GET", "DELETE"):
            code, headers, _ = request(method, b"unexpected body", {"Mcp-Session-Id": sid})
            t.check(f"{method} body rejected without desynchronizing connection",
                    code == 400 and headers.get("Connection") == "close")
        t.check("rejected DELETE body retains session", httpd.sessions.valid(sid))
        _, _, body = request("POST", json.dumps(rpc("probe_document", {"path": "notes.md"})), {"Mcp-Session-Id": sid})
        t.check("disabled maker tool cannot be called", json.loads(body).get("error", {}).get("code") == -32602)
        code, _, _ = request("POST", "[]", {"Mcp-Session-Id": sid})
        t.check("HTTP rejects array envelope", code == 400)
        code, _, _ = request("POST", json.dumps({"jsonrpc": "2.0", "method": "ping"}), {"Mcp-Session-Id": sid})
        t.check("HTTP notification accepted", code == 202)
        code, _, _ = request("POST", json.dumps({"jsonrpc": "2.0", "id": 9, "result": {}}), {"Mcp-Session-Id": sid})
        t.check("HTTP response accepted", code == 202)
        code, _, _ = request("POST", "{}", {"Transfer-Encoding": "chunked"})
        t.check("unsupported transfer encoding rejected", code == 400)
        for body in ("{" * 1200, "[" * 1200 + "]" * 1200,
                     '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":NaN}}'):
            code, _, _ = request("POST", body, {"Mcp-Session-Id": sid})
            t.check("malformed/deep JSON gets HTTP error", code == 400)
        for origin in ("http://localhost:bad", "http://user@localhost", "http://localhost/path", "null"):
            code, _, _ = request("POST", "{}", {"Origin": origin})
            t.check(f"malformed origin rejected {origin}", code == 403)
        sessions_before = len(httpd.sessions)
        code, _, _ = request("POST", '{"jsonrpc":"2.0","method":"initialize"}')
        t.check("initialize notification creates no session", code == 400 and len(httpd.sessions) == sessions_before)
        code, _, _ = request("POST", '{"jsonrpc":"2.0","method":"notifications/initialized","id":1}',
                             {"Mcp-Session-Id": sid})
        t.check("notification method with id rejected", code == 400)
        code, _, _ = request("POST", "{}", {"Content-Length": "+2"})
        t.check("non-decimal content length rejected", code == 400)
        code, headers, _ = request("GET")
        t.check("405 declares allowed methods", code == 405 and headers.get("Allow") == "POST, DELETE")
        connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=3)
        try:
            connection.putrequest("POST", "/mcp")
            connection.putheader("Origin", "http://localhost")
            connection.putheader("Origin", "https://example.com")
            connection.putheader("Content-Length", "2")
            connection.endheaders(b"{}")
            response = connection.getresponse()
            t.check("duplicate Origin rejected", response.status == 403)
            response.read()
        finally:
            connection.close()
        try:
            code, _, _ = request("POST", b"x", {"Content-Length": str(2 * 1024 * 1024)})
            t.check("oversized body rejected before read", code == 413)
        except TimeoutError:
            t.check("oversized body rejected before read", False)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
    store = SessionStore()
    token = store.create()
    t.check("new session is valid", store.valid(token))
    with patch("skillmaker.http_transport.time.monotonic", return_value=float("inf")):
        t.check("expired session rejected", not store.valid(token) and len(store) == 0)
    store._ids = {str(i): float("inf") for i in range(1024)}
    t.rejects("session count is bounded", store.create)
    t.check("dropping unknown session returns false", not store.drop("unknown"))
    store._ids = {"expired": 0}
    t.check("expired session cannot be dropped as valid", not store.drop("expired"))
    opt_in = HttpServer(("127.0.0.1", 0), Server(root), lambda: "test", allow_maker_tools=True)
    try:
        t.check("HTTP maker tools require explicit opt-in", any(
            tool["name"] == "probe_document" for tool in opt_in.mcp.tools()))
    finally:
        opt_in.server_close()
    saturated = HttpServer(("127.0.0.1", 0), Server(root), lambda: "test")
    try:
        for _ in range(32):
            saturated._connections.acquire()
        with patch.object(saturated, "shutdown_request") as closed:
            saturated.process_request(object(), ("127.0.0.1", 0))
            t.check("connection limit rejects before spawning thread", closed.call_count == 1)
    finally:
        saturated.server_close()


def test_snapshot_edges(t, base):
    root, unit = fixture(base)
    server = Server(root)
    stamp = root / "demo" / ".demo_build.json"
    stamp.write_bytes(b'{"engine":"machine-specific-path"}')
    t.check("machine build metadata does not change content snapshot",
            Server(root).library.snapshot == server.library.snapshot)
    moved = root / "renamed"
    (root / "demo" / ".skill.json").write_bytes(b'{"name":"demo"}')
    (root / "demo").rename(moved)
    (root / "index.json").unlink()
    t.check("renamed skill readable via marker", Server(root).call("read_pattern", {
        "pattern_id": "DEMO.1"})["publication"] == "renamed")
    unit = moved / "reference/demo/DEMO.1.md"
    unit.unlink()
    t.rejects("incomplete corpus rejected before serving", lambda: Server(root))
    unit.write_bytes(b"## DEMO.1 - Example\n")
    duplicate = root / "duplicate"
    duplicate.mkdir()
    (duplicate / ".duplicate_manifest.json").write_bytes((moved / ".demo_manifest.json").read_bytes())
    path = duplicate / "reference/demo/DEMO.1.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(unit.read_bytes())
    t.rejects("duplicate unit ids rejected", lambda: Server(root))


def test_publication_boundaries(t, base):
    root, unit = fixture(base)
    manifest = root / "demo/.demo_manifest.json"
    original = manifest.read_bytes()
    other = root / "other/private.md"
    other.parent.mkdir()
    other.write_bytes(b"Private material\n")
    for key in (str(other.resolve()), "../../../other/private.md", "..\\..\\private.md"):
        entries = json.loads(original)
        entries[0]["key"] = key
        manifest.write_bytes(json.dumps(entries).encode())
        t.rejects(f"MCP rejects manifest escape {key}", lambda: Server(root))
        with patch.object(skill_index, "SKILLS_ROOT", root):
            t.rejects(f"index rejects manifest escape {key}", lambda: skill_index._manifest_by_name("demo"))
    manifest.write_bytes(original)
    (root / "index.json").write_bytes(b'{"skills":[{"name":"demo","docids":[123]}]}')
    t.rejects("malformed metadata rejected at startup", lambda: Server(root))
    (root / "index.json").write_bytes(b'{"skills":[{"name":"demo","docids":["DEMO"]}]}')
    # Mutate a file already read when a later corpus file is opened. Loading
    # must fail rather than silently freezing a mixed build.
    read_bytes = Path.read_bytes
    changed = False
    def change_during_scan(path):
        nonlocal changed
        if path == root / "index.json" and not changed:
            changed = True
            unit.write_bytes(b"## DEMO.1 - Example\n\nChanged during load.\n")
        return read_bytes(path)
    with patch.object(Path, "read_bytes", change_during_scan):
        t.rejects("changing corpus rejected during startup", lambda: Server(root))


def test_evals_and_metadata(t):
    data = json.loads((_REPO_ROOT / "skill-maker/evals/cases.json").read_text("utf-8"))
    t.check("quality evals have three distinct tasks", len({case["id"] for case in data["cases"]}) >= 3)
    for case in data["cases"]:
        t.check(f"{case['id']} has objective checks", bool(case["prompt"]) and len(case["assertions"]) >= 3)
        t.check(f"{case['id']} has positive and negative triggers",
                {query["should_trigger"] for query in case["trigger_queries"]} == {True, False})
    for path in sorted((_REPO_ROOT / "skills").glob("*/SKILL.md")):
        text = path.read_text("utf-8")
        front = text.split("---", 2)[1]
        name = re.search(r"^name: (.+)$", front, re.MULTILINE)
        description = front.split("description:", 1)[1].strip().removeprefix(">").strip()
        t.check(f"{path.parent.name} metadata matches format", bool(name)
                and name[1] == path.parent.name and len(name[1]) <= 64
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name[1]) is not None
                and 0 < len(description) <= 1024)


def test_graph_runtime_paths(t, base):
    """Graph-guided checks for the non-MCP lookup and rebuild entry points."""
    import pickle
    from skillmaker.fpf_lookup import PatternIndex
    from skillmaker.split_spec import rebuild_spec
    from skillmaker.skill_config import SkillConfig

    skill = base / "demo"
    pdir = skill / "reference/fpf-patterns"
    pdir.mkdir(parents=True)
    (pdir / "index.md").write_bytes(
        b"| ID | Title | Role | Status | File |\n"
        b"| :--- | :--- | :--- | :--- | :--- |\n"
        b"| A.1 | Test | pattern | stable | A.1.md |\n")
    (pdir / "A.1.md").write_bytes(b"## A.1 - Test\n\nBody.\n")
    marker = base / "pickle-executed"
    class CacheProbe:
        def __reduce__(self):
            return (Path.touch, (marker,))
    cache = skill / ".fpf_index.pickle"
    cache.write_bytes(pickle.dumps(CacheProbe()))
    index = PatternIndex(skill)
    try:
        entries = index.entries
    except (AttributeError, TypeError):
        entries = {}
    t.check("legacy pickle cache never executes", not marker.exists())
    t.check("lookup parses canonical index despite legacy cache", "A.1" in entries)
    t.check("valid lookup still reads a pattern", index.read_pattern("a.1") == (pdir / "A.1.md").read_text("utf-8"))
    outside = base / "private.md"
    outside.write_bytes(b"Private outside text\n")
    for value in ("../../../private", str(outside.with_suffix("")), "A.*", "..\\..\\private"):
        try:
            text = index.read_pattern(value)
            safe = text is None
        except (ValueError, OSError):
            safe = True
        t.check(f"lookup rejects unsafe id {value}", safe)
    cfg = SkillConfig(name="demo", output=skill)
    manifest = skill / ".demo_manifest.json"
    dest = base / "reconstructed.md"
    dest.write_bytes(b"retain previous reconstruction\n")
    entries = [{"kind": "unit", "id": "A.1", "key": str(outside),
                "framework": "fpf-patterns", "order": 0}]
    manifest.write_bytes(json.dumps(entries).encode())
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        t.rejects("rebuild rejects outside manifest path", lambda: rebuild_spec(cfg, dest))
        t.check("rejected rebuild leaves destination unchanged", dest.read_bytes() == b"retain previous reconstruction\n")
        entries[0]["key"] = "MISSING.md"
        manifest.write_bytes(json.dumps(entries).encode())
        t.rejects("missing rebuild input is an error", lambda: rebuild_spec(cfg, dest))
        t.check("incomplete rebuild leaves destination unchanged", dest.read_bytes() == b"retain previous reconstruction\n")
        entries[0]["key"] = "A.1.md"
        manifest.write_bytes(json.dumps(entries).encode())
        rebuild_spec(cfg, dest)
        t.check("valid rebuild preserves source bytes", dest.read_bytes() == (pdir / "A.1.md").read_bytes())
        t.rejects("rebuild cannot overwrite its unit", lambda: rebuild_spec(cfg, pdir / "A.1.md"))
    links = [pdir / "A.2.md", skill / "reference/intro/private.md", skill / "reference/docs/private.md"]
    try:
        for link in links:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
    except OSError:
        print("  SKIP lookup symlink creation unavailable")
    else:
        t.check("lookup rejects symlink unit escape", index.read_pattern("A.2") is None)
        t.check("lookup rejects symlink intro escape", index.read_intro("private") is None)
        t.check("lookup rejects symlink document escape", index.read_doc("private") is None)


def test_text_output(t, base):
    """Existing hidden/system files must not be reopened with CREATE_ALWAYS."""
    import errno
    from skillmaker import _fpf_common as common

    target = base / "nested/.demo_manifest.json"
    common.write_text_lf(target, "Пример\nsecond line\n")
    t.check("text output creates parents and writes UTF-8/LF bytes",
            target.read_bytes() == "Пример\nsecond line\n".encode("utf-8"))
    common.write_text_lf(target, "é\n")
    t.check("shorter text output truncates stale UTF-8 bytes", target.read_bytes() == "é\n".encode("utf-8"))
    common.write_text_lf(target, "")
    t.check("empty text output truncates existing file", target.read_bytes() == b"")

    target.write_bytes(b"old manifest data\n")
    real_open = os.open
    real_text_open = open
    flags_seen = []
    def hidden_file_open(name, flags, *args, **kwargs):
        flags_seen.append(flags)
        if flags & os.O_CREAT and flags & os.O_TRUNC:
            raise PermissionError(errno.EACCES, "simulated Windows hidden file", str(name))
        return real_open(name, flags, *args, **kwargs)
    def hidden_text_open(name, mode, *args, **kwargs):
        if "w" in mode and "opener" not in kwargs:
            raise PermissionError(errno.EACCES, "simulated Windows hidden file", str(name))
        return real_text_open(name, mode, *args, **kwargs)
    with patch.object(os, "open", hidden_file_open), patch.object(common, "open", hidden_text_open, create=True):
        try:
            common.write_text_lf(target, "new\n")
            written = True
        except PermissionError:
            written = False
    t.check("hidden-file CREATE_ALWAYS rejection does not prevent overwrite", written)
    t.check("hidden-file overwrite removes old tail", target.read_bytes() == b"new\n")
    t.check("text opener does not request O_TRUNC", bool(flags_seen) and not flags_seen[0] & os.O_TRUNC)
    t.check("text opener retains write access", bool(flags_seen) and bool(flags_seen[0] & os.O_WRONLY))
    t.check("text opener retains create-if-missing", bool(flags_seen) and bool(flags_seen[0] & os.O_CREAT))

    target.write_bytes(b"retain on access failure\n")
    with patch.object(common, "open", side_effect=PermissionError(errno.EACCES, "access denied", str(target)), create=True):
        t.rejects("real access denial is not bypassed", lambda: common.write_text_lf(target, "replacement"))
    t.check("failed open leaves existing text untouched", target.read_bytes() == b"retain on access failure\n")

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        set_attributes = kernel.SetFileAttributesW
        set_attributes.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
        set_attributes.restype = wintypes.BOOL
        original = target.stat().st_file_attributes
        for label, attributes in (("hidden", 2), ("system", 4), ("hidden+system", 6)):
            try:
                if not set_attributes(str(target), attributes):
                    raise ctypes.WinError(ctypes.get_last_error())
                common.write_text_lf(target, "native\n")
                t.check(f"native {label} text can be overwritten", target.read_bytes() == b"native\n")
                t.check(f"native {label} attributes retained", target.stat().st_file_attributes & attributes == attributes)
            finally:
                if not set_attributes(str(target), original):
                    raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not set_attributes(str(target), original | 1):
                raise ctypes.WinError(ctypes.get_last_error())
            t.rejects("native readonly text stays protected", lambda: common.write_text_lf(target, "denied"))
            t.check("native readonly failure retains bytes", target.read_bytes() == b"native\n")
        finally:
            if not set_attributes(str(target), original):
                raise ctypes.WinError(ctypes.get_last_error())


def main():
    t = TestRunner(verbose="-v" in sys.argv)
    preferred = Path("/tmp/opencode")
    with tempfile.TemporaryDirectory(prefix="skillmaker-hardening-",
                                     dir=preferred if preferred.is_dir() else None) as tmp:
        base = Path(tmp)
        test_mcp(t, base / "mcp")
        test_build(t, base / "build")
        test_update(t, base / "update")
        test_http(t, base / "http")
        test_snapshot_edges(t, base / "snapshot")
        test_publication_boundaries(t, base / "boundaries")
        test_graph_runtime_paths(t, base / "graph-runtime")
        test_evals_and_metadata(t)
        test_text_output(t, base / "text-output")
    print(f"Results: {t.passed} passed, {t.failed} failed / {t.passed + t.failed} total")
    for name in t.failures:
        print(f"  FAIL {name}")
    return int(bool(t.failed))


if __name__ == "__main__":
    sys.exit(main())
