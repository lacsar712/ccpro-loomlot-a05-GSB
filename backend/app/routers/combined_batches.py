from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.combined_batch import CombinedBatch, CombinedBatchMember
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.user import User
from app.models.vat import Vat
from app.schemas.combined_batch import (
    CombinedBatchCreate,
    CombinedBatchUpdate,
    CombinedBatchOut,
    MemberAdd,
)

router = APIRouter(prefix="/api/combined-batches", tags=["combined-batches"])

# 锁定所需的最少成员缸数
MIN_LOCK_MEMBERS = 2


def _get_batch(db: Session, batch_id: int) -> CombinedBatch:
    item = db.query(CombinedBatch).filter(CombinedBatch.id == batch_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="合批不存在")
    return item


@router.get("", response_model=List[CombinedBatchOut])
def list_combined_batches(
    dye_house_id: Optional[int] = Query(None, alias="dyeHouseId"),
    batch_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CombinedBatch)
    if dye_house_id is not None:
        q = q.filter(CombinedBatch.dye_house_id == dye_house_id)
    if batch_status is not None:
        q = q.filter(CombinedBatch.status == batch_status)
    return q.order_by(CombinedBatch.id).all()


@router.post("", response_model=CombinedBatchOut, status_code=status.HTTP_201_CREATED)
def create_combined_batch(
    payload: CombinedBatchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    house = db.query(DyeHouse).filter(DyeHouse.id == payload.dye_house_id).first()
    if not house:
        raise HTTPException(status_code=400, detail="染坊不存在")
    item = CombinedBatch(
        dye_house_id=payload.dye_house_id,
        batch_no=payload.batch_no,
        max_fabric_kg=payload.max_fabric_kg,
        status="grouping",
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊合批号已存在")
    db.refresh(item)
    return item


@router.get("/{batch_id}", response_model=CombinedBatchOut)
def get_combined_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return _get_batch(db, batch_id)


@router.put("/{batch_id}", response_model=CombinedBatchOut)
def update_combined_batch(
    batch_id: int,
    payload: CombinedBatchUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = _get_batch(db, batch_id)
    if item.status == "locked":
        raise HTTPException(status_code=409, detail="合批已锁定，禁止修改")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊合批号已存在")
    db.refresh(item)
    return item


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_combined_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = _get_batch(db, batch_id)
    if item.status == "locked":
        raise HTTPException(status_code=409, detail="合批已锁定，禁止删除")
    db.delete(item)
    db.commit()


@router.post(
    "/{batch_id}/members",
    response_model=CombinedBatchOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    batch_id: int,
    payload: MemberAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch(db, batch_id)
    if batch.status != "grouping":
        raise HTTPException(status_code=409, detail="合批已锁定，禁止改动成员")
    vat = db.query(Vat).filter(Vat.id == payload.vat_id).first()
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")
    if vat.dye_house_id != batch.dye_house_id:
        raise HTTPException(status_code=409, detail="染缸须属同坊，不能跨坊入批")
    if vat.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"染缸状态为「{vat.status}」，仅就绪染缸可入批",
        )
    occupied = (
        db.query(CombinedBatchMember)
        .join(CombinedBatch, CombinedBatchMember.batch_id == CombinedBatch.id)
        .filter(
            CombinedBatchMember.vat_id == vat.id,
            CombinedBatch.status.in_(["grouping", "locked"]),
        )
        .first()
    )
    if occupied:
        if occupied.batch_id == batch.id:
            raise HTTPException(status_code=409, detail="该染缸已在本合批中")
        raise HTTPException(status_code=409, detail="该染缸已在其他合批中，一口缸同时只能进一个合批")
    db.add(CombinedBatchMember(batch_id=batch.id, vat_id=vat.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该染缸已在本合批中")
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}/members/{vat_id}", response_model=CombinedBatchOut)
def remove_member(
    batch_id: int,
    vat_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch(db, batch_id)
    if batch.status != "grouping":
        raise HTTPException(status_code=409, detail="合批已锁定，禁止改动成员")
    member = (
        db.query(CombinedBatchMember)
        .filter(
            CombinedBatchMember.batch_id == batch.id,
            CombinedBatchMember.vat_id == vat_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="该染缸不在本合批中")
    db.delete(member)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{batch_id}/lock", response_model=CombinedBatchOut)
def lock_combined_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """锁定合批：至少两口成员缸，且各缸最新染程布重之和不超过布重上限。"""
    batch = _get_batch(db, batch_id)
    if batch.status == "locked":
        raise HTTPException(status_code=409, detail="合批已锁定")
    members = (
        db.query(CombinedBatchMember)
        .filter(CombinedBatchMember.batch_id == batch.id)
        .all()
    )
    if len(members) < MIN_LOCK_MEMBERS:
        raise HTTPException(
            status_code=409,
            detail=f"锁定需至少 {MIN_LOCK_MEMBERS} 口成员缸，当前 {len(members)} 口",
        )
    total = 0.0
    for m in members:
        latest = (
            db.query(DyeLot)
            .filter(DyeLot.vat_id == m.vat_id)
            .order_by(DyeLot.started_at.desc(), DyeLot.id.desc())
            .first()
        )
        if latest:
            total += latest.fabric_kg
    if total > batch.max_fabric_kg:
        raise HTTPException(
            status_code=409,
            detail=f"成员缸最新染程布重合计 {total:.1f}kg，超过布重上限 {batch.max_fabric_kg:.1f}kg",
        )
    batch.status = "locked"
    db.commit()
    db.refresh(batch)
    return batch
