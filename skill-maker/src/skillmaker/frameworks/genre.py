#!/usr/bin/env python3
"""
genre.py -- what a skill is *for*, which decides its shape and its roles.

A skill is not only data. Skills differ in purpose, and purpose changes
things the data does not:

* **the middle of SKILL.md** -- a lookup skill explains indexes, an apply skill
  explains how to choose a scope and stop, a setup skill explains how to
  validate a connection;
* **the roles it ships** -- an apply skill is only useful with a pipeline
  (decide whether this applies, fetch the minimum, answer, check the answer);
  a lookup skill needs none.

Naming that explicitly is what makes "any kind of framework" true.  A new
purpose is a new :class:`GenreSpec` plus one partial, not a new builder.

The genres here are deliberately few.  Each one earns its place by changing the
generated artefacts, not just their wording.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class Genre(str, Enum):
    """Why someone opens the skill."""

    LOOKUP = "lookup"
    """Find, read and cite material.  The reader drives; no pipeline."""

    APPLY = "apply"
    """Apply a method to a problem.  Needs classify, retrieve, answer, review."""

    SETUP = "setup"
    """Install and validate a connection to a service."""

    MAINTAIN = "maintain"
    """Keep a derived artefact in step with its source."""


@dataclass(frozen=True)
class GenreSpec:
    """The artefacts a genre adds on top of the data."""

    genre: Genre
    label: str
    summary: str
    partial: str
    """Template under ``templates/genres/`` for the middle of SKILL.md."""

    roles: Tuple[str, ...] = ()
    """Role templates under ``templates/roles/``, in pipeline order."""

    def describe(self) -> str:
        roles = ", ".join(self.roles) or "none"
        return f"{self.genre.value:<10} roles: {roles:<46} {self.summary}"


GENRES: Dict[Genre, GenreSpec] = {
    Genre.LOOKUP: GenreSpec(
        genre=Genre.LOOKUP,
        label="Lookup",
        summary="find, read and cite; the reader drives",
        partial="lookup.md",
        roles=(),
    ),
    Genre.APPLY: GenreSpec(
        genre=Genre.APPLY,
        label="Apply",
        summary="apply a method to a problem, with a checking step",
        partial="apply.md",
        roles=("classifier", "retriever", "reasoner", "reviewer"),
    ),
    Genre.SETUP: GenreSpec(
        genre=Genre.SETUP,
        label="Setup",
        summary="install and prove a connection works",
        partial="setup.md",
        roles=("installer", "validator"),
    ),
    Genre.MAINTAIN: GenreSpec(
        genre=Genre.MAINTAIN,
        label="Maintain",
        summary="keep derived artefacts in step with the source",
        partial="maintain.md",
        roles=("sync",),
    ),
}


def by_value(value: str) -> GenreSpec:
    """Look up a genre by its CLI value."""
    for genre, spec in GENRES.items():
        if genre.value == value.strip().lower():
            return spec
    known = ", ".join(g.value for g in Genre)
    raise KeyError(f"unknown genre {value!r}; known genres: {known}")


def default_for(kind: str) -> GenreSpec:
    """The genre a publication kind gets unless it says otherwise.

    Pattern-bearing publications are read and cited; guides are read whole.
    Nothing here is a setup or a maintenance artefact, so those genres are
    chosen explicitly.
    """
    return GENRES[Genre.LOOKUP]


def describe_all() -> str:
    lines = ["Genre      Roles" + " " * 40 + "What it is for"]
    lines.append("-" * 96)
    for spec in GENRES.values():
        lines.append(spec.describe())
    return "\n".join(lines)
