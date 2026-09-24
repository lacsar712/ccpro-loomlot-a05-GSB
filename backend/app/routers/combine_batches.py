from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.combine_batch import CombineBatch, CombineBatchVat
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.user import User
from app.models.vat import Vat
from app.schemas.combine_batch import (
    CombineBatchCreate,
    CombineBatchUpdate,
    CombineMemberUpdate,
    CombineBatchOut,
    CombineBatchMemberOut,
)

router = APIRouter(prefix="/api/combine-batches", tags=["combine-batches"])

GROUPING = "grouping"
LOCKED = "locked"


def latest_fabric_map(db: Session, vat_ids: List[int]) -> Dict[int, float]:
    """各缸最新染程（started_at 最大、并列取 id 最大）的布重；无染程按 0。"""
    result: Dict[int, float] = {vid: 0.0 for vid in vat_ids}
    if not vat_ids:
        return result
    lots = (
        db.query(DyeLot)
        .filter(DyeLot.vat_id.in_(vat_ids))
        .order_by(DyeLot.vat_id, DyeLot.started_at.desc(), DyeLot.id.desc())
        .all()
    )
    seen: set = set()
    for lot in lots:
        if lot.vat_id not in seen:
            seen.add(lot.vat_id)
            result[lot.vat_id] = lot.fabric_kg
    return result


def serialize(db: Session, batch: CombineBatch) -> CombineBatchOut:
    member_rows = batch.members
    weights = latest_fabric_map(db, [m.vat_id for m in member_rows])
    vat_map = {v.id: v for v in db.query(Vat).filter(Vat.id.in_([m.vat_id for m in member_rows])).all()}
    members = [
        CombineBatchMemberOut(
            id=m.id,
            vat_id=m.vat_id,
            vat_code=vat_map[m.vat_id].vat_code if m.vat_id in vat_map else str(m.vat_id),
            latest_fabric_kg=weights.get(m.vat_id, 0.0),
        )
        for m in member_rows
    ]
    return CombineBatchOut(
        id=batch.id,
        dye_house_id=batch.dye_house_id,
        batch_code=batch.batch_code,
        fabric_limit_kg=batch.fabric_limit_kg,
        status=batch.status,
        members=members,
        total_fabric_kg=sum(weights.get(m.vat_id, 0.0) for m in member_rows),
    )


def _get_batch_or_404(db: Session, batch_id: int) -> CombineBatch:
    batch = db.query(CombineBatch).filter(CombineBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="合批不存在")
    return batch


def _validate_members(
    db: Session,
    dye_house_id: int,
    vat_ids: List[int],
    self_batch_id: Optional[int] = None,
):
    """校验成员缸：存在、同坊、就绪、不重复、未被其它组批中合批占用。

    返回去重后的 vat_id 列表。任何一项不满足抛 400/409。
    """
    if len(vat_ids) != len(set(vat_ids)):
        raise HTTPException(status_code=400, detail="成员染缸不可重复")

    vats = db.query(Vat).filter(Vat.id.in_(vat_ids)).all() if vat_ids else []
    if len(vats) != len(vat_ids):
        raise HTTPException(status_code=400, detail="存在不属于本坊或不存在的染缸")
    for vat in vats:
        if vat.dye_house_id != dye_house_id:
            raise HTTPException(status_code=400, detail=f"染缸 {vat.vat_code} 不属于该染坊")
        if vat.status != "ready":
            raise HTTPException(
                status_code=409,
                detail=f"染缸 {vat.vat_code} 状态为「{vat.status}」，仅就绪缸可入合批",
            )

    # 一口缸同时只能进一个组批中合批（已锁定合批同样占用，不可改挂）
    q = (
        db.query(CombineBatchVat)
        .join(CombineBatch, CombineBatchVat.batch_id == CombineBatch.id)
        .filter(CombineBatchVat.vat_id.in_(vat_ids))
    )
    if self_batch_id is not None:
        q = q.filter(CombineBatch.id != self_batch_id)
    occupied = q.first()
    if occupied:
        other = db.query(CombineBatch).filter(CombineBatch.id == occupied.batch_id).first()
        raise HTTPException(
            status_code=409,
            detail=f"染缸已在合批「{other.batch_code if other else occupied.batch_id}」中，不可重复组批",
        )
    return list(dict.fromkeys(vat_ids))


def _replace_members(db: Session, batch: CombineBatch, vat_ids: List[int]) -> None:
    db.query(CombineBatchVat).filter(CombineBatchVat.batch_id == batch.id).delete()
    db.flush()
    for vat_id in vat_ids:
        db.add(CombineBatchVat(batch_id=batch.id, vat_id=vat_id))
    db.flush()


@router.get("", response_model=List[CombineBatchOut])
def list_batches(
    dye_house_id: Optional[int] = Query(None, alias="dyeHouseId"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CombineBatch)
    if dye_house_id is not None:
        q = q.filter(CombineBatch.dye_house_id == dye_house_id)
    if status_filter is not None:
        q = q.filter(CombineBatch.status == status_filter)
    batches = q.order_by(CombineBatch.id.desc()).all()
    return [serialize(db, b) for b in batches]


@router.post("", response_model=CombineBatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: CombineBatchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    house = db.query(DyeHouse).filter(DyeHouse.id == payload.dye_house_id).first()
    if not house:
        raise HTTPException(status_code=400, detail="染坊不存在")

    vat_ids = _validate_members(db, payload.dye_house_id, payload.vat_ids)

    batch = CombineBatch(
        dye_house_id=payload.dye_house_id,
        batch_code=payload.batch_code,
        fabric_limit_kg=payload.fabric_limit_kg,
        status=GROUPING,
    )
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊合批号已存在")

    _replace_members(db, batch, vat_ids)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊合批号已存在")
    db.refresh(batch)
    return serialize(db, batch)


@router.get("/{batch_id}", response_model=CombineBatchOut)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return serialize(db, _get_batch_or_404(db, batch_id))


@router.put("/{batch_id}", response_model=CombineBatchOut)
def update_batch(
    batch_id: int,
    payload: CombineBatchUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch_or_404(db, batch_id)
    data = payload.model_dump(exclude_unset=True)

    new_house_id = data.pop("dye_house_id", None)
    if new_house_id is not None and new_house_id != batch.dye_house_id:
        # 成员均属旧坊，跨坊迁移需先清空成员，这里直接拒绝，保持同坊约束
        raise HTTPException(status_code=409, detail="合批已有成员时不可更换染坊")

    if batch.status == LOCKED and ("batch_code" in data or "fabric_limit_kg" in data):
        raise HTTPException(status_code=409, detail="合批已锁定，禁止修改合批字段")

    for k, v in data.items():
        setattr(batch, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊合批号已存在")
    db.refresh(batch)
    return serialize(db, batch)


@router.put("/{batch_id}/members", response_model=CombineBatchOut)
def update_members(
    batch_id: int,
    payload: CombineMemberUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch_or_404(db, batch_id)
    if batch.status == LOCKED:
        raise HTTPException(status_code=409, detail="合批已锁定，禁止增删成员")

    vat_ids = _validate_members(db, batch.dye_house_id, payload.vat_ids, self_batch_id=batch.id)
    _replace_members(db, batch, vat_ids)
    db.commit()
    db.refresh(batch)
    return serialize(db, batch)


@router.post("/{batch_id}/lock", response_model=CombineBatchOut)
def lock_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch_or_404(db, batch_id)
    if batch.status == LOCKED:
        raise HTTPException(status_code=400, detail="合批已锁定，无需重复锁定")

    member_vat_ids = [m.vat_id for m in batch.members]
    if len(member_vat_ids) < 2:
        raise HTTPException(status_code=409, detail="成员至少两口缸方可锁定")

    weights = latest_fabric_map(db, member_vat_ids)
    total = sum(weights.values())
    if total > batch.fabric_limit_kg:
        raise HTTPException(
            status_code=409,
            detail=f"各缸最新染程布重合计 {total:g}kg 超过布重上限 {batch.fabric_limit_kg:g}kg",
        )

    batch.status = LOCKED
    db.commit()
    db.refresh(batch)
    return serialize(db, batch)


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    batch = _get_batch_or_404(db, batch_id)
    if batch.status == LOCKED:
        raise HTTPException(status_code=409, detail="合批已锁定，禁止删除")
    db.delete(batch)
    db.commit()
