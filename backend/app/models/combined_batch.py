from typing import List, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_house import DyeHouse
    from app.models.vat import Vat


class CombinedBatch(Base):
    __tablename__ = "combined_batches"
    __table_args__ = (UniqueConstraint("dye_house_id", "batch_no", name="uq_house_batch_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_house_id: Mapped[int] = mapped_column(ForeignKey("dye_houses.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    max_fabric_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="grouping")

    dye_house: Mapped["DyeHouse"] = relationship("DyeHouse", back_populates="combined_batches")
    members: Mapped[List["CombinedBatchMember"]] = relationship(
        "CombinedBatchMember", back_populates="batch", cascade="all, delete-orphan"
    )


class CombinedBatchMember(Base):
    __tablename__ = "combined_batch_members"
    __table_args__ = (UniqueConstraint("batch_id", "vat_id", name="uq_batch_vat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("combined_batches.id"), nullable=False, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)

    batch: Mapped["CombinedBatch"] = relationship("CombinedBatch", back_populates="members")
    vat: Mapped["Vat"] = relationship("Vat")
