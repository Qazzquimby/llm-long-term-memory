from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    Text,
    Enum,
    CheckConstraint,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    mapped_column,
    Mapped,
)
from datetime import datetime
import enum

Base = declarative_base()

message_summary_fact_association = Table(
    "message_summary_fact_association",
    Base.metadata,
    Column("message_summary_id", ForeignKey("message_summaries.id"), primary_key=True),
    Column("fact_id", ForeignKey("facts.id"), primary_key=True),
)

message_summary_entity_association = Table(
    "message_summary_entity_association",
    Base.metadata,
    Column("message_summary_id", ForeignKey("message_summaries.id"), primary_key=True),
    Column("entity_id", ForeignKey("entities.id"), primary_key=True),
)

entity_fact_association = Table(
    "entity_fact_association",
    Base.metadata,
    Column("fact_id", ForeignKey("facts.id"), primary_key=True),
    Column("entity_id", ForeignKey("entities.id"), primary_key=True),
)

theory_evidence_association = Table(
    "theory_evidence_association",
    Base.metadata,
    Column("theory_id", ForeignKey("facts.id"), primary_key=True),
    Column("evidence_id", ForeignKey("facts.id"), primary_key=True),
)


class ContextItem(Base):
    __tablename__ = "context_items"
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "context_item"}
    type: Mapped[str] = mapped_column(String(50))

    id: Mapped[int] = mapped_column(primary_key=True)
    usefulness_score: Mapped[int] = mapped_column(default=0)
    importance: Mapped[int] = mapped_column()
    salience: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    last_updated: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        CheckConstraint(
            "importance >= 0 AND importance <= 10 AND salience >= 0 AND salience <= 10"
        ),
    )

    retired_by: Mapped[int] = mapped_column(
        ForeignKey("context_items.id"), nullable=True
    )


class SenderType(enum.Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    sender: Mapped[SenderType] = mapped_column(Enum(SenderType))
    summary_id: Mapped[int] = mapped_column(ForeignKey("message_summaries.id"))

    summary: Mapped["MessageSummary"] = relationship(back_populates="messages")


# todo may need an 'in world time' for fiction?
class MessageSummary(ContextItem):
    __tablename__ = "message_summaries"
    __mapper_args__ = {"polymorphic_identity": "message_summary"}

    id: Mapped[int] = mapped_column(ForeignKey("context_items.id"), primary_key=True)
    body: Mapped[str] = mapped_column(Text)

    facts: Mapped[List["Fact"]] = relationship(
        secondary=message_summary_fact_association, back_populates="message_summaries"
    )
    entities: Mapped[List["Entity"]] = relationship(
        secondary=message_summary_entity_association, back_populates="message_summaries"
    )
    messages: Mapped[List["Message"]] = relationship(back_populates="summary")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief: Mapped[str] = mapped_column(Text)

    aliases: Mapped[List["EntityAlias"]] = relationship(back_populates="entity")
    facts: Mapped[List["Fact"]] = relationship(
        secondary=entity_fact_association, back_populates="entities"
    )
    message_summaries: Mapped[List["MessageSummary"]] = relationship(
        secondary=message_summary_entity_association, back_populates="entities"
    )


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False)

    entity: Mapped["Entity"] = relationship(back_populates="aliases")


class FactType(enum.Enum):
    BASE = "fact"
    QUESTION = "question"
    OBJECTIVE = "objective"
    THEORY = "theory"


class Fact(ContextItem):
    __tablename__ = "facts"
    __mapper_args__ = {"polymorphic_identity": "fact"}

    id: Mapped[int] = mapped_column(ForeignKey("context_items.id"), primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    fact_type: Mapped[FactType] = mapped_column(Enum(FactType), default=FactType.BASE)

    entities: Mapped[List["Entity"]] = relationship(
        secondary=entity_fact_association, back_populates="facts"
    )

    message_summaries: Mapped[List["MessageSummary"]] = relationship(
        secondary=message_summary_fact_association, back_populates="message_summaries"
    )
    supported_theories: Mapped[List["Fact"]] = relationship(
        secondary=theory_evidence_association, back_populates="evidence"
    )

    # For questions
    possible_theories: Mapped[List["Fact"]] = relationship(
        back_populates="relevant_question"
    )

    # For theories
    evidence: Mapped[List["Fact"]] = relationship(
        secondary=theory_evidence_association, back_populates="supported_theories"
    )
    relevant_question_id: Mapped[int] = mapped_column(
        ForeignKey("facts.id"), nullable=True
    )
    relevant_question: Mapped["Fact"] = relationship(
        foreign_keys=[relevant_question_id], back_populates="possible_theories"
    )

    # For objectives
    parent_objective_id: Mapped[int] = mapped_column(
        ForeignKey("facts.id"), nullable=True
    )
    parent_objective: Mapped["Fact"] = relationship(back_populates="child_objectives")
    child_objectives: Mapped[List["Fact"]] = relationship(
        foreign_keys=[parent_objective_id], back_populates="parent_objective"
    )


def get_engine(db_url="sqlite:///memory.db"):
    return create_engine(db_url)


def get_sessionmaker(engine=None):
    engine = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Usage:
# SessionLocal = get_sessionmaker()
# with SessionLocal() as session:
#     ...
