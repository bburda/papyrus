"""Pydantic data models for Papyrus needs."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NeedType(str, Enum):
    """The 7 memory types."""

    MEM = "mem"
    DEC = "dec"
    FACT = "fact"
    PREF = "pref"
    RISK = "risk"
    GOAL = "goal"
    Q = "q"

    @property
    def prefix(self) -> str:
        return self.value.upper() + "_"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Scope(str, Enum):
    LOCAL = "local"
    PROGRAM = "program"
    ORG = "org"


class Status(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PROMOTED = "promoted"
    REVIEW = "review"
    DEPRECATED = "deprecated"


class LinkType(str, Enum):
    RELATES = "relates"
    SUPPORTS = "supports"
    DEPENDS = "depends"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    DERIVES = "derives"
    SATISFIES = "satisfies"


class Link(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: LinkType
    target: str = Field(min_length=1)


class Need(BaseModel):
    """A single memory record."""

    id: str = Field(min_length=1)
    type: NeedType
    title: str = Field(min_length=1)
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    scope: Scope = Scope.LOCAL
    status: Status = Status.ACTIVE
    created_at: datetime
    updated_at: datetime
    review_after: datetime | None = None
    source: str = ""
    links: list[Link] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id must not be empty or whitespace-only")
        return v

    @model_validator(mode="after")
    def _id_matches_type_prefix(self) -> Need:
        if not self.id.startswith(self.type.prefix):
            raise ValueError(f"id {self.id!r} must start with {self.type.prefix!r}")
        return self
