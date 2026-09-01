from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState


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


class BorrowerModel(Base):
    __tablename__ = "borrowers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    phone_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    state: Mapped[BorrowerState] = mapped_column(
        SQLEnum(BorrowerState),
        nullable=False,
        default=BorrowerState.ELIGIBLE,
    )


class CallModel(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    borrower_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    state: Mapped[CallState] = mapped_column(
        SQLEnum(CallState),
        nullable=False,
        default=CallState.QUEUED,
    )


class ReservationModel(Base):
    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    agent_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    call_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    worker_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )