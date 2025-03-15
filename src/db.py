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
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()

# Association tables
message_fact_association = Table(
    "message_fact_association",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("messages.id")),
    Column("fact_id", Integer, ForeignKey("facts.id")),
)

message_entity_association = Table(
    "message_entity_association",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("messages.id")),
    Column("entity_id", Integer, ForeignKey("entities.id")),
)


class ContextItem(Base):
    __tablename__ = "context_items"
    id = Column(Integer, primary_key=True)
    usefulness_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    retired_by = Column(Integer, ForeignKey("context_items.id"), nullable=True)


class KeyInfoSummary(ContextItem):
    __tablename__ = "key_info_summaries"
    id = Column(Integer, ForeignKey("context_items.id"), primary_key=True)
    content = Column(Text)


class Message(ContextItem):
    __tablename__ = "messages"
    id = Column(Integer, ForeignKey("context_items.id"), primary_key=True)
    body = Column(Text)
    sender = Column(String)
    facts = relationship(
        "Fact", secondary=message_fact_association, back_populates="messages"
    )
    entities = relationship(
        "Entity", secondary=message_entity_association, back_populates="messages"
    )
    summary_id = Column(Integer, ForeignKey("message_summaries.id"))


class MessageSummary(ContextItem):
    __tablename__ = "message_summaries"
    id = Column(Integer, ForeignKey("context_items.id"), primary_key=True)
    text_body = Column(Text)
    contained_messages = relationship("Message", backref="containing_summary")
    parent_summary_id = Column(Integer, ForeignKey("message_summaries.id"))
    child_summaries = relationship(
        "MessageSummary", backref="parent_summary", remote_side=[id]
    )


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True)
    aliases = relationship("EntityAlias", back_populates="entity")
    brief = Column(Text)
    facts = relationship("Fact", back_populates="entity")
    fact_summary_id = Column(Integer, ForeignKey("entity_fact_summaries.id"))
    fact_summary = relationship("EntityFactSummary", back_populates="entity")


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


class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True)
    body = Column(Text)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    entity = relationship("Entity", back_populates="facts")
    importance = Column(Integer)
    salience = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fact_type = Column(Enum(FactType), default=FactType.BASE)
    messages = relationship(
        "Message", secondary=message_fact_association, back_populates="facts"
    )

    # For theories
    evidence_ids = Column(Integer, ForeignKey("facts.id"))
    # For objectives
    parent_objective_id = Column(Integer, ForeignKey("facts.id"))


class EntityFactSummary(Base):
    __tablename__ = "entity_fact_summaries"
    id = Column(Integer, primary_key=True)
    summary = Column(Text)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    entity = relationship("Entity", back_populates="fact_summary")
    summarized_fact_ids = Column(String)  # Comma-separated list of fact IDs


def get_engine(db_url="sqlite:///memory.db"):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    engine = engine or get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()
