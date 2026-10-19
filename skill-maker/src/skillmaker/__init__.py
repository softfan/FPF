"""skillmaker -- turn the Library's publications into agent skills.

The package is self-contained on purpose: a built skill carries a copy of it
under ``scripts/skillmaker/`` (see ``split_spec._copy_scripts``), so the tools
that generated a skill are the same tools that rebuild it, with or without the
repository around them.

Entry points are run as files, not installed::

    python skill-maker/src/skillmaker/mcp_server.py --http 127.0.0.1:8765

so each one puts this package's parent on ``sys.path`` for itself before it
imports anything from here.
"""
