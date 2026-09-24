from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.database import SessionLocal
from app.models.combined_batch import CombinedBatch, CombinedBatchMember
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        hashed_password=hash_password("123456"),
                        role="admin",
                        display_name="染坊主管",
                    ),
                    User(
                        username="dyer",
                        hashed_password=hash_password("123456"),
                        role="dyer",
                        display_name="染程操作员",
                    ),
                ]
            )
            db.commit()

        if db.query(DyeHouse).count() == 0:
            h1 = DyeHouse(
                name="蓝靛一号坊",
                water_note="软化井水，硬度约 80ppm",
                notes="主做棉麻靛蓝与草木染",
            )
            h2 = DyeHouse(
                name="青石二号坊",
                water_note="河溪砂滤水，日供约 12 吨",
                notes="专职丝绢与混纺缸染",
            )
            db.add_all([h1, h2])
            db.flush()

            v1 = Vat(
                dye_house_id=h1.id,
                vat_code="V-01",
                fiber_type="棉",
                capacity_l=800.0,
                status="dyeing",
            )
            v2 = Vat(
                dye_house_id=h1.id,
                vat_code="V-02",
                fiber_type="麻",
                capacity_l=600.0,
                status="ready",
            )
            v3 = Vat(
                dye_house_id=h2.id,
                vat_code="S-01",
                fiber_type="丝",
                capacity_l=350.0,
                status="ready",
            )
            v4 = Vat(
                dye_house_id=h2.id,
                vat_code="S-02",
                fiber_type="混纺",
                capacity_l=500.0,
                status="drain",
            )
            v5 = Vat(
                dye_house_id=h1.id,
                vat_code="V-03",
                fiber_type="棉",
                capacity_l=700.0,
                status="ready",
            )
            db.add_all([v1, v2, v3, v4, v5])
            db.flush()

            now = datetime.now(timezone.utc)
            lot1 = DyeLot(
                vat_id=v1.id,
                recipe_name="靛蓝冷染三浸",
                fabric_kg=42.5,
                started_at=now - timedelta(hours=6),
                operator_name="染程操作员",
            )
            lot2 = DyeLot(
                vat_id=v3.id,
                recipe_name="青蓝套染",
                fabric_kg=18.0,
                started_at=now - timedelta(days=2),
                operator_name="染坊主管",
            )
            # 拼缸合染演示：V-02 / V-03 各挂一条最新染程，合计 60kg < 上限 120kg，可锁定
            lot3 = DyeLot(
                vat_id=v2.id,
                recipe_name="靛蓝薄染一浸",
                fabric_kg=26.0,
                started_at=now - timedelta(hours=3),
                operator_name="染程操作员",
            )
            lot4 = DyeLot(
                vat_id=v5.id,
                recipe_name="靛蓝薄染一浸",
                fabric_kg=34.0,
                started_at=now - timedelta(hours=2),
                operator_name="染程操作员",
            )
            db.add_all([lot1, lot2, lot3, lot4])
            db.flush()

            # lot2 was on ready vat historically — keep v3 ready for demo create path
            # Re-set: creating lot2 would have set dyeing; for seed we leave one dyeing + one ready
            # v2 / v5 同理：染程直插不改缸态，保持 ready 以演示入批
            v3.status = "ready"
            batch1 = CombinedBatch(
                dye_house_id=h1.id,
                batch_no="PB-001",
                max_fabric_kg=120.0,
                status="grouping",
            )
            db.add(batch1)
            db.flush()
            db.add_all(
                [
                    CombinedBatchMember(batch_id=batch1.id, vat_id=v2.id),
                    CombinedBatchMember(batch_id=batch1.id, vat_id=v5.id),
                ]
            )
            db.add_all(
                [
                    FastnessCheck(
                        dye_lot_id=lot1.id,
                        checked_at=now - timedelta(hours=1),
                        wash_fastness=4,
                        rub_fastness=3.5,
                        temp_c=40.0,
                        notes="湿摩略偏，可出货",
                    ),
                    FastnessCheck(
                        dye_lot_id=lot2.id,
                        checked_at=now - timedelta(days=1),
                        wash_fastness=5,
                        rub_fastness=4.0,
                        temp_c=37.0,
                        notes=None,
                    ),
                ]
            )
            db.commit()
            print("Seed data inserted.")
        else:
            print("Seed skipped (data exists).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
