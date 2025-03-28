from typing import List, Optional, Dict

from sqlalchemy import (
    create_engine,
    Column,
    String,
    ForeignKey,
    Table,
    Text,
    Enum,
    CheckConstraint,
    Integer,
    JSON,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    mapped_column,
    Mapped,
)
import enum

from src.conversation import Role

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


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    context_item_id: Mapped[int] = mapped_column(ForeignKey("context_items.id"))
    created_at_message_index: Mapped[int] = mapped_column()
    usefulness: Mapped[int] = mapped_column(Integer)

    context_item: Mapped["ContextItem"] = relationship(
        "ContextItem", back_populates="usage_records"
    )

    __table_args__ = (CheckConstraint("usefulness >= 0 AND usefulness <= 2"),)


class ContextItem(Base):
    __tablename__ = "context_items"
    __mapper_args__ = {
        "polymorphic_on": "item_type",
        "polymorphic_identity": "context_item",
    }
    item_type: Mapped[str] = mapped_column(String(50))

    id: Mapped[int] = mapped_column(primary_key=True)

    importance: Mapped[int] = mapped_column()
    # salience: Mapped[int] = mapped_column()
    created_at_message_index: Mapped[int] = mapped_column()
    updated_at_message_index: Mapped[int] = mapped_column(nullable=True)

    usage_records: Mapped[List["UsageRecord"]] = relationship(
        back_populates="context_item", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("importance >= 0 AND importance <= 5"),)

    retired_by: Mapped[int] = mapped_column(
        ForeignKey("context_items.id"), nullable=True
    )

    @property
    def times_provided(self):
        """Backward compatibility property that counts all usage records"""
        return len(self.usage_records) if self.usage_records else 0

    @property
    def times_useful(self):
        """Backward compatibility property that counts usage records with usefulness > 0"""
        if not self.usage_records:
            return 0
        return sum(1 for record in self.usage_records if record.usefulness > 0)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    body: Mapped[str] = mapped_column(Text)
    sender: Mapped[Role] = mapped_column(Enum(Role))
    summary_id: Mapped[int] = mapped_column(
        ForeignKey("message_summaries.id"), nullable=True
    )
    part_lengths: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    # JSON structure: {
    #   "chat_history": int,  # characters in chat history
    #   "facts": int,         # characters in facts
    #   "summaries": int,     # characters in summaries
    #   "entities": int,      # characters in entities
    # }

    summary: Mapped["MessageSummary"] = relationship(back_populates="messages")

    def __str__(self):
        return self.body


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

    def __str__(self):
        return self.body


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

    def __str__(self):
        return ", ".join([alias.alias for alias in self.aliases]) + "\n" + self.brief


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False)

    entity: Mapped["Entity"] = relationship(back_populates="aliases")

    def __str__(self):
        return self.alias


def get_entity_by_name(session, entity_name: str) -> Optional[Entity]:
    # todo prefer earlier alias for tie breaking? First alias is more likely canon.
    alias_rows = (
        session.query(EntityAlias).filter(EntityAlias.alias == entity_name).all()
    )
    if not alias_rows:
        print("WARN: entity alias not found: ", entity_name)
        return None
    if len(alias_rows) > 1:
        print("WARN: entity alias not unique: ", entity_name)
    alias_row = alias_rows[0]
    return alias_row.entity


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
        secondary=message_summary_fact_association, back_populates="facts"
    )

    def __str__(self):
        return self.body

    # supported_theories: Mapped[List["Fact"]] = relationship(
    #     secondary=theory_evidence_association,
    #     primaryjoin="Fact.id==theory_evidence_association.c.evidence_id",
    #     secondaryjoin="Fact.id==theory_evidence_association.c.theory_id",
    #     back_populates="evidence",
    # )
    #
    # # For questions
    # possible_theories: Mapped[List["Fact"]] = relationship(
    #     # primaryjoin="Fact.id==Fact.relevant_question_id",
    #     foreign_keys="[Fact.relevant_question_id]",
    #     back_populates="relevant_question",
    # )
    #
    # # For theories
    # evidence: Mapped[List["Fact"]] = relationship(
    #     secondary=theory_evidence_association,
    #     primaryjoin="Fact.id==theory_evidence_association.c.theory_id",
    #     secondaryjoin="Fact.id==theory_evidence_association.c.evidence_id",
    #     back_populates="supported_theories",
    # )
    # relevant_question_id: Mapped[int] = mapped_column(
    #     ForeignKey("facts.id"), nullable=True
    # )
    # relevant_question: Mapped["Fact"] = relationship(
    #     foreign_keys=[relevant_question_id],
    #     back_populates="possible_theories",
    #     remote_side="Fact.id",
    # )
    #
    # # For objectives
    # parent_objective_id: Mapped[int] = mapped_column(
    #     ForeignKey("facts.id"), nullable=True
    # )
    # parent_objective: Mapped["Fact"] = relationship(
    #     foreign_keys=[parent_objective_id],
    #     back_populates="child_objectives",
    #     remote_side="Fact.id",
    # )
    # child_objectives: Mapped[List["Fact"]] = relationship(
    #     foreign_keys=[parent_objective_id], back_populates="parent_objective"
    # )


def _get_engine(db_url=None):
    if db_url is None:
        db_url = "sqlite:///memory.db"
    return create_engine(db_url)


def _get_sessionmaker(engine=None):
    engine = engine or _get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Usage:
# SessionLocal = get_sessionmaker()
# with SessionLocal() as session:
#     ...


def get_db_factory(db_url="sqlite:///memory.db"):
    engine = _get_engine(db_url=db_url)
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    SessionLocal = _get_sessionmaker()
    return SessionLocal
