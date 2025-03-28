from abc import ABC, abstractmethod
from typing import List, Literal, Optional, Type, TypeVar

from pydantic import Field, BaseModel, conint
from pydantic_ai.messages import ModelResponse, TextPart, ModelRequest, UserPromptPart
from sqlalchemy.orm import Session

from db import MessageSummary, Entity, Fact, Base, Role, UsageRecord

T = TypeVar("T")


class DbModel(BaseModel, ABC):
    """Base class for all Pydantic models that sync with the database"""

    db_id: Optional[int] = None

    @classmethod
    @abstractmethod
    def from_db(cls: Type[T], db_obj) -> T:
        """Convert from SQLAlchemy model to this Pydantic model"""
        raise NotImplementedError()

    @abstractmethod
    def to_db(self, session: Session, db_class) -> Base:
        """Convert this Pydantic model to a SQLAlchemy model"""
        raise NotImplementedError()

    def sync_id(self, db_obj):
        """Update this model's db_id from a database object"""
        self.db_id = db_obj.id


# todo prevent multiple entities with same primary alias?
#  more specifically we want them to be appropriately merged.
#  could keep earliest, could keep latest, could request merge (probably increasing in length)
class EntityModel(DbModel):
    aliases: List[str] = Field(
        description="1 or more names for the entity. Make the first one the most clear and canonical, as it will be used by default."
    )
    brief: str = Field(
        description="1-2 sentence summary of the entity and your relationship with it."
    )

    @classmethod
    def from_db(cls, db_obj):
        return cls(
            db_id=db_obj.id,
            aliases=[alias.alias for alias in db_obj.aliases],
            brief=db_obj.brief,
        )

    def to_db(self, session, db_class):
        db_obj = db_class(
            brief=self.brief,
        )
        if self.db_id:
            db_obj.id = self.db_id

        # Handle aliases relationship
        from src.db import EntityAlias

        db_obj.aliases = [EntityAlias(alias=alias) for alias in self.aliases]

        return db_obj

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(Entity).all()
        return [cls.from_db(row) for row in rows]


importance_to_num = {
    "trivial": 1,
    "probably not important": 2,
    "probably important": 3,
    "clearly important": 4,
    "critically important": 5,
}
num_to_importance = {v: k for k, v in importance_to_num.items()}


class ContextItemModel(DbModel, ABC):
    importance: Literal[
        "trivial",
        "probably not important",
        "probably important",
        "clearly important",
        "critically important",
    ] = Field(
        description="Strategic importance. One of: trivial, unimportant, probably important, very important, critically important"
    )
    created_at_message_index: int = Field(description="Message index when this item was created")
    updated_at_message_index: Optional[int] = Field(description="Message index when this item was last updated", default=None)
    usage_records: List["UsageRecordModel"] = Field(default_factory=list)

    def _get_importance_value(self) -> int:
        return importance_to_num[self.importance]

    @classmethod
    def _get_importance_string(cls, value: int) -> str:
        return num_to_importance[value]

    def get_avg_usefulness(self) -> float:
        """Get average usefulness score from usage records"""
        if not self.usage_records:
            return 0.0
        return sum(record.usefulness for record in self.usage_records) / len(self.usage_records)

    # importance: conint(ge=1, le=10) = Field(
    #     description="Strategic importance. 1 is trivial, 5 is probably important, and 10 is absolutely critical"
    # )
    # salience: conint(ge=1, le=10) = Field(
    #     description="Emotional valence. 1 is has no affect on you, 5 has some emotional impact, and 10 is a burned in part of your identity"
    # )


class UsageRecordModel(DbModel):
    """Model for tracking how useful a context item was in a conversation"""
    context_item_id: int
    created_at_message_index: int
    usefulness: conint(ge=0, le=2) = Field(description="How useful this item was: 0=not used, 1=mentioned, 2=key insight")

    @classmethod
    def from_db(cls, db_obj: UsageRecord):
        return cls(
            db_id=db_obj.id,
            context_item_id=db_obj.context_item_id,
            created_at_message_index=db_obj.created_at_message_index,
            usefulness=db_obj.usefulness
        )

    def to_db(self, session, db_class) -> UsageRecord:
        db_obj = db_class(
            context_item_id=self.context_item_id,
            created_at_message_index=self.created_at_message_index,
            usefulness=self.usefulness
        )
        if self.db_id:
            db_obj.id = self.db_id
        return db_obj


class FactModel(ContextItemModel):
    body: str = Field(
        "~1 sentence. Facts should be largely timeless, not about events or current status"
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities related to this fact. Use the aliases of new or existing entities exactly.",
    )

    def __str__(self):
        return f"I:{self.importance} {self.body}"

    @classmethod
    def from_db(cls, db_obj):
        return cls(
            db_id=db_obj.id,
            body=db_obj.body,
            relevant_entity_names=[
                entity.aliases[0].alias for entity in db_obj.entities
            ],
            importance=cls._get_importance_string(db_obj.importance),
            created_at_message_index=db_obj.created_at_message_index,
            updated_at_message_index=db_obj.updated_at_message_index,
            usage_records=[UsageRecordModel.from_db(record) for record in db_obj.usage_records]
        )

    def to_db(self, session, db_class):
        db_obj = db_class(
            body=self.body,
            importance=self._get_importance_value(),
            created_at_message_index=self.created_at_message_index,
            updated_at_message_index=self.updated_at_message_index,
        )
        if self.db_id:
            db_obj.id = self.db_id

        # Handle entity relationships
        from src.db import get_entity_by_name

        db_obj.entities = [
            get_entity_by_name(session, name)
            for name in self.relevant_entity_names
            if get_entity_by_name(session, name) is not None
        ]

        # Handle usage records
        from src.db import UsageRecord
        db_obj.usage_records = [
            record.to_db(session, UsageRecord)
            for record in self.usage_records
        ]

        return db_obj

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(Fact).all()
        return [cls.from_db(row) for row in rows]


class MessageSummaryModel(ContextItemModel):
    body: str = Field(
        description="Stay concise and focus on events rather than factual statements (handled elsewhere). Write it like how you'd recall a memory, focusing on what stands out or seems important."
    )
    relevant_entity_names: List[str] = Field(
        description="Names of any entities in or closely related to these events. Use the aliases of new or existing entities exactly.",
    )

    @classmethod
    def from_db(cls, db_obj):
        return cls(
            db_id=db_obj.id,
            body=db_obj.body,
            relevant_entity_names=[
                entity.aliases[0].alias for entity in db_obj.entities
            ],
            importance=cls._get_importance_string(db_obj.importance),
            created_at_message_index=db_obj.created_at_message_index,
            updated_at_message_index=db_obj.updated_at_message_index,
            usage_records=[UsageRecordModel.from_db(record) for record in db_obj.usage_records]
        )

    def to_db(self, session, db_class):
        db_obj = db_class(
            body=self.body,
            importance=self._get_importance_value(),
        )
        if self.db_id:
            db_obj.id = self.db_id

        # Handle entity relationships
        from src.db import get_entity_by_name

        db_obj.entities = [
            get_entity_by_name(session, name)
            for name in self.relevant_entity_names
            if get_entity_by_name(session, name) is not None
        ]

        return db_obj

    @classmethod
    def get_all(cls, session: Session):
        rows = session.query(MessageSummary).all()
        return [cls.from_db(row) for row in rows]


class ChatMessage(DbModel):
    content: str
    role: Role
    ephemeral: bool = False
    hidden: bool = False
    num_words: int = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.role == Role.SYSTEM:
            self.role = Role.USER
            self.content = f"SYSTEM: {self.content}"
        if not self.content:
            raise ValueError("Message cannot be empty")
        self.num_words = len(self.content.split())

    @classmethod
    def from_db(cls, db_obj):
        return cls(
            db_id=db_obj.id,
            content=db_obj.body,
            role=db_obj.sender,
            ephemeral=False,  # These aren't stored in DB
            hidden=False,
        )

    def to_db(self, session, db_class):
        db_obj = db_class(
            body=self.content,
            sender=self.role,
        )
        if self.db_id:
            db_obj.id = self.db_id
        return db_obj

    def __str__(self):
        return f"{self.role.value}: {self.content}\n"

    def to_llm_friendly(self):
        return {"role": self.role.value, "content": self.content}

    def to_pydantic_ai(self):
        if self.role == Role.ASSISTANT:
            return ModelResponse(parts=[TextPart(content=self.content)])
        else:
            return ModelRequest(parts=[UserPromptPart(content=self.content)])
