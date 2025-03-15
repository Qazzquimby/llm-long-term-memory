from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Table,
    Text,
    Enum,
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

fact_entity_association = Table(
    "fact_entity_association",
    Base.metadata,
    Column("fact_id", ForeignKey("facts.id"), primary_key=True),
    Column("entity_id", ForeignKey("entities.id"), primary_key=True),
)


class ContextItem(Base):
    __tablename__ = "context_items"
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "context_item"}
    type: Mapped[str] = mapped_column(String(50))

    id: Mapped[int] = mapped_column(primary_key=True)
    usefulness_score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    last_updated: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )
    retired_by: Mapped[int] = mapped_column(
        ForeignKey("context_items.id"), nullable=True
    )


class SenderType(enum.Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class Message(ContextItem):
    __tablename__ = "messages"
    __mapper_args__ = {"polymorphic_identity": "message"}

    id: Mapped[int] = mapped_column(ForeignKey("context_items.id"), primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    sender: Mapped[SenderType] = mapped_column(Enum(SenderType))

    # gets retired by MessageSummary


class MessageSummary(ContextItem):
    __tablename__ = "message_summaries"
    __mapper_args__ = {"polymorphic_identity": "message_summary"}

    id: Mapped[int] = mapped_column(ForeignKey("context_items.id"), primary_key=True)
    text_body: Mapped[str] = mapped_column(Text)

    facts: Mapped[List["Fact"]] = relationship(
        secondary=message_summary_fact_association, back_populates="message_summaries"
    )
    entities: Mapped[List["Entity"]] = relationship(
        secondary=message_summary_fact_association, back_populates="message_summaries"
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief: Mapped[str] = Column(Text)

    aliases: Mapped[List["EntityAlias"]] = relationship(back_populates="entity")
    facts: Mapped[List["Fact"]] = relationship(back_populates="entity")
    message_summaries: Mapped[List["MessageSummary"]] = relationship(
        secondary=message_summary_entity_association, back_populates="entities"
    )


# todo
class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    id = Column(Integer, primary_key=True)
    alias = Column(String)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    entity = relationship("Entity", back_populates="aliases")


class FactType(enum.Enum):
    BASE = "fact"
    QUESTION = "question"
    OBJECTIVE = "objective"
    THEORY = "theory"


class Fact(ContextItem):
    __tablename__ = "facts"
    __mapper_args__ = {"polymorphic_identity": "fact"}

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = Column(Text)

    importance: Mapped[int] = Column()
    salience: Mapped[int] = Column()
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    fact_type = Column(Enum(FactType), default=FactType.BASE)

    message_summaries: Mapped[List["MessageSummary"]] = relationship(
        secondary=message_summary_entity_association, back_populates="entities"
    )

    # todo
    # For theories
    evidence_ids = Column(Integer, ForeignKey("facts.id"), nullable=True)

    # For objectives
    parent_objective_id = Column(Integer, ForeignKey("facts.id"), nullable=True)


def get_engine(db_url="sqlite:///memory.db"):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    engine = engine or get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()
