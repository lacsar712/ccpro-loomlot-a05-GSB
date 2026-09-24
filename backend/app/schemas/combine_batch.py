from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

CombineBatchStatus = Literal["grouping", "locked"]


class CombineBatchCreate(BaseModel):
    dye_house_id: int = Field(..., alias="dyeHouseId")
    batch_code: str = Field(..., min_length=1, max_length=64, alias="batchCode")
    fabric_limit_kg: float = Field(..., gt=0, alias="fabricLimitKg")
    vat_ids: List[int] = Field(default_factory=list, alias="vatIds")

    model_config = ConfigDict(populate_by_name=True)


class CombineBatchUpdate(BaseModel):
    batch_code: Optional[str] = Field(None, min_length=1, max_length=64, alias="batchCode")
    fabric_limit_kg: Optional[float] = Field(None, gt=0, alias="fabricLimitKg")
    dye_house_id: Optional[int] = Field(None, alias="dyeHouseId")

    model_config = ConfigDict(populate_by_name=True)


class CombineMemberUpdate(BaseModel):
    """整表替换成员；组批中允许，已锁定返回 409。"""

    vat_ids: List[int] = Field(..., alias="vatIds")

    model_config = ConfigDict(populate_by_name=True)


class CombineBatchMemberOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    vat_id: int = Field(serialization_alias="vatId")
    vat_code: str = Field(serialization_alias="vatCode")
    latest_fabric_kg: float = Field(serialization_alias="latestFabricKg")


class CombineBatchOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    dye_house_id: int = Field(serialization_alias="dyeHouseId")
    batch_code: str = Field(serialization_alias="batchCode")
    fabric_limit_kg: float = Field(serialization_alias="fabricLimitKg")
    status: CombineBatchStatus
    members: List[CombineBatchMemberOut] = Field(default_factory=list)
    total_fabric_kg: float = Field(serialization_alias="totalFabricKg")
