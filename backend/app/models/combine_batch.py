from typing import List, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_house import DyeHouse
    from app.models.vat import Vat


class CombineBatch(Base):
    """拼缸合染批次：一批可挂多口同坊染缸，合计布重受布重上限约束。"""

    __tablename__ = "combine_batches"
    __table_args__ = (
        UniqueConstraint("dye_house_id", "batch_code", name="uq_house_batch_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_house_id: Mapped[int] = mapped_column(
        ForeignKey("dye_houses.id"), nullable=False, index=True
    )
    batch_code: Mapped[str] = mapped_column(String(64), nullable=False)
    fabric_limit_kg: Mapped[float] = mapped_column(Float, nullable=False)
    # grouping=组批中（可加减成员），locked=已锁定（成员冻结）
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="grouping")

    dye_house: Mapped["DyeHouse"] = relationship("DyeHouse")
    members: Mapped[List["CombineBatchVat"]] = relationship(
        "CombineBatchVat",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="CombineBatchVat.id",
    )


class CombineBatchVat(Base):
    """合批成员行：合批编号 + 染缸编号。一口缸同时只能挂在一个合批上。"""

    __tablename__ = "combine_batch_vats"
    __table_args__ = (
        UniqueConstraint("batch_id", "vat_id", name="uq_batch_vat"),
        UniqueConstraint("vat_id", name="uq_combine_vat_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("combine_batches.id"), nullable=False, index=True
    )
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)

    batch: Mapped["CombineBatch"] = relationship("CombineBatch", back_populates="members")
    vat: Mapped["Vat"] = relationship("Vat")
