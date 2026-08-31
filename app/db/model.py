from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.domain.agent import AgentState


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    state: Mapped[AgentState] = mapped_column(
        SQLEnum(AgentState),
        nullable=False,
        default=AgentState.OFFLINE,
    )