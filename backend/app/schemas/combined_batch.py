from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

BatchStatus = Literal["grouping", "locked"]


class CombinedBatchCreate(BaseModel):
    dye_house_id: int = Field(..., alias="dyeHouseId")
    batch_no: str = Field(..., min_length=1, max_length=64, alias="batchNo")
    max_fabric_kg: float = Field(..., gt=0, alias="maxFabricKg")

    model_config = ConfigDict(populate_by_name=True)


class CombinedBatchUpdate(BaseModel):
    batch_no: Optional[str] = Field(None, min_length=1, max_length=64, alias="batchNo")
    max_fabric_kg: Optional[float] = Field(None, gt=0, alias="maxFabricKg")

    model_config = ConfigDict(populate_by_name=True)


class MemberAdd(BaseModel):
    vat_id: int = Field(..., alias="vatId")

    model_config = ConfigDict(populate_by_name=True)


class CombinedBatchMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    batch_id: int = Field(serialization_alias="batchId")
    vat_id: int = Field(serialization_alias="vatId")


class CombinedBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dye_house_id: int = Field(serialization_alias="dyeHouseId")
    batch_no: str = Field(serialization_alias="batchNo")
    max_fabric_kg: float = Field(serialization_alias="maxFabricKg")
    status: BatchStatus
    members: List[CombinedBatchMemberOut] = []
