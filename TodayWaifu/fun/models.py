"""今日老婆 数据表：打卡运势 / 鹿扣日历 / 签到 / 积分 / 兑换。

所有数据库访问都封装在模型类里，写操作挂 with_session、纯查询挂 with_read_session。
聚合统计在 Python 侧完成：单群单月行数有上界（≤31 天 × 群人数），比 ORM 聚合更好读。
"""

from typing import Optional

from sqlmodel import Field, col, delete, select
from sqlalchemy import UniqueConstraint
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.server import on_core_start
from gsuid_core.webconsole.mount_app import PageSchema, GsAdminModel, site
from gsuid_core.utils.database.startup import ensure_core_database_tables
from gsuid_core.utils.database.base_models import BaseModel, with_session, with_read_session

STATUS_PENDING = 'pending'
STATUS_CONFIRMED = 'confirmed'

THEME_DEER = 'deer'


class XfLuckRecord(BaseModel, table=True):
    """每日幸运值打卡记录：每人每天一条，pending 表示低分待重抽。"""

    __table_args__ = (
        UniqueConstraint('date', 'bot_id', 'user_id', name='uq_xf_luck_day'),
        {'extend_existing': True},
    )

    group_id: str = Field(default='', title='群号')
    date: str = Field(default='', title='日期', index=True)
    luck: int = Field(default=0, title='幸运值')
    name: str = Field(default='', title='昵称')
    avatar: str = Field(default='', title='头像链接')
    bg_id: str = Field(default='', title='面板ID')
    bg_path: str = Field(default='', title='面板路径')
    status: str = Field(default=STATUS_CONFIRMED, title='状态')

    @classmethod
    @with_read_session
    async def get_record(cls, session: AsyncSession, user_id: str, bot_id: str, date: str) -> Optional['XfLuckRecord']:
        stmt = select(cls).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.date) == date,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def upsert(
        cls,
        session: AsyncSession,
        *,
        user_id: str,
        bot_id: str,
        group_id: str,
        date: str,
        luck: int,
        name: str,
        avatar: str,
        bg_id: str,
        bg_path: str,
        status: str,
    ) -> 'XfLuckRecord':
        record = await cls.get_record(user_id, bot_id, date)
        if record is None:
            record = cls(
                user_id=user_id,
                bot_id=bot_id,
                group_id=group_id,
                date=date,
                luck=luck,
                name=name,
                avatar=avatar,
                bg_id=bg_id,
                bg_path=bg_path,
                status=status,
            )
        else:
            record.group_id = group_id
            record.luck = luck
            record.name = name
            record.avatar = avatar
            record.bg_id = bg_id
            record.bg_path = bg_path
            record.status = status
        session.add(record)
        return record

    @classmethod
    @with_read_session
    async def confirmed_of_day(cls, session: AsyncSession, date: str) -> list['XfLuckRecord']:
        stmt = select(cls).where(col(cls.date) == date, col(cls.status) == STATUS_CONFIRMED)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    @with_read_session
    async def recent_confirmed_dates(
        cls,
        session: AsyncSession,
        user_id: str,
        bot_id: str,
        since: str,
    ) -> set[str]:
        """取指定日期之后的打卡成功日期，供连续打卡天数计算。

        一次性取回一段时间而非逐天查询：连续天数上限由 since 控制，避免长连签
        触发 N 次往返查询。
        """
        stmt = select(cls.date).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.date) >= since,
            col(cls.status) == STATUS_CONFIRMED,
        )
        result = await session.execute(stmt)
        return {value for value in result.scalars().all() if isinstance(value, str)}


class XfCalendarRecord(BaseModel, table=True):
    """鹿 / 扣 打卡记录：每人每天每主题一条，count 为当天累计次数。"""

    __table_args__ = (
        UniqueConstraint('theme', 'date', 'bot_id', 'user_id', name='uq_xf_calendar_day'),
        {'extend_existing': True},
    )

    theme: str = Field(default=THEME_DEER, title='主题', index=True)
    group_id: str = Field(default='', title='群号', index=True)
    date: str = Field(default='', title='日期', index=True)
    count: int = Field(default=0, title='当日次数')
    name: str = Field(default='', title='昵称')

    @classmethod
    @with_read_session
    async def get_day(
        cls, session: AsyncSession, theme: str, user_id: str, bot_id: str, date: str
    ) -> Optional['XfCalendarRecord']:
        stmt = select(cls).where(
            col(cls.theme) == theme,
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.date) == date,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def change_count(
        cls,
        session: AsyncSession,
        *,
        theme: str,
        user_id: str,
        bot_id: str,
        group_id: str,
        date: str,
        name: str,
        delta: int,
        cap: int,
    ) -> tuple[int, int]:
        """增减当天次数，返回 (本次实际计入, 变更后总数)。cap<=0 表示不限制。"""
        record = await cls.get_day(theme, user_id, bot_id, date)
        current = record.count if record is not None else 0
        target = current + delta
        if target < 0:
            target = 0
        counted = target - current
        if cap > 0 and counted > 0:
            room = cap - current
            counted = min(counted, max(0, room))
            target = current + counted

        if record is None:
            if target <= 0:
                return (0, 0)
            record = cls(
                theme=theme,
                user_id=user_id,
                bot_id=bot_id,
                group_id=group_id,
                date=date,
                count=target,
                name=name,
            )
        else:
            record.count = target
            record.name = name
            record.group_id = group_id
        session.add(record)
        return (counted, target)

    @classmethod
    @with_read_session
    async def range_records(
        cls,
        session: AsyncSession,
        theme: str,
        bot_id: str,
        start_date: str,
        end_date: str,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> list['XfCalendarRecord']:
        stmt = select(cls).where(
            col(cls.theme) == theme,
            col(cls.bot_id) == bot_id,
            col(cls.date) >= start_date,
            col(cls.date) <= end_date,
        )
        if user_id is not None:
            stmt = stmt.where(col(cls.user_id) == user_id)
        if group_id is not None:
            stmt = stmt.where(col(cls.group_id) == group_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    @with_read_session
    async def all_records(
        cls, session: AsyncSession, theme: str, user_id: str, bot_id: str
    ) -> list['XfCalendarRecord']:
        stmt = select(cls).where(
            col(cls.theme) == theme,
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    @with_read_session
    async def first_of_day(
        cls, session: AsyncSession, theme: str, bot_id: str, date: str, group_id: Optional[str] = None
    ) -> Optional['XfCalendarRecord']:
        stmt = select(cls).where(
            col(cls.theme) == theme,
            col(cls.bot_id) == bot_id,
            col(cls.date) == date,
        )
        if group_id is not None:
            stmt = stmt.where(col(cls.group_id) == group_id)
        stmt = stmt.order_by(col(cls.id).asc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def clear_user(cls, session: AsyncSession, theme: str, user_id: str, bot_id: str) -> int:
        stmt = delete(cls).where(
            col(cls.theme) == theme,
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
        )
        result = await session.execute(stmt)
        return result.rowcount if isinstance(result, CursorResult) else 0


class XfSignRecord(BaseModel, table=True):
    """签到记录：每人每天一条，streak 为截至当日的连续天数。"""

    __table_args__ = (
        UniqueConstraint('date', 'bot_id', 'user_id', name='uq_xf_sign_day'),
        {'extend_existing': True},
    )

    group_id: str = Field(default='', title='群号')
    date: str = Field(default='', title='日期', index=True)
    streak: int = Field(default=1, title='连续天数')
    points: int = Field(default=0, title='当次获得积分')
    name: str = Field(default='', title='昵称')

    @classmethod
    @with_read_session
    async def get_day(cls, session: AsyncSession, user_id: str, bot_id: str, date: str) -> Optional['XfSignRecord']:
        stmt = select(cls).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.date) == date,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_read_session
    async def last_before(cls, session: AsyncSession, user_id: str, bot_id: str, date: str) -> Optional['XfSignRecord']:
        stmt = (
            select(cls)
            .where(
                col(cls.user_id) == user_id,
                col(cls.bot_id) == bot_id,
                col(cls.date) < date,
            )
            .order_by(col(cls.date).desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_read_session
    async def history(cls, session: AsyncSession, user_id: str, bot_id: str) -> list['XfSignRecord']:
        stmt = select(cls).where(col(cls.user_id) == user_id, col(cls.bot_id) == bot_id).order_by(col(cls.date).desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def add(
        cls,
        session: AsyncSession,
        *,
        user_id: str,
        bot_id: str,
        group_id: str,
        date: str,
        streak: int,
        points: int,
        name: str,
    ) -> 'XfSignRecord':
        record = cls(
            user_id=user_id,
            bot_id=bot_id,
            group_id=group_id,
            date=date,
            streak=streak,
            points=points,
            name=name,
        )
        session.add(record)
        return record

    @classmethod
    @with_session
    async def drop_day(cls, session: AsyncSession, user_id: str, bot_id: str, date: str) -> bool:
        """删除当天签到，供商城「今日免签」类道具使用。"""
        stmt = delete(cls).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.date) == date,
        )
        result = await session.execute(stmt)
        return bool(result.rowcount) if isinstance(result, CursorResult) else False


class XfPointRecord(BaseModel, table=True):
    """积分余额：每人每个 bot 一条。"""

    __table_args__ = (
        UniqueConstraint('bot_id', 'user_id', name='uq_xf_point_user'),
        {'extend_existing': True},
    )

    points: int = Field(default=0, title='可用积分')
    earned: int = Field(default=0, title='累计获得')
    spent: int = Field(default=0, title='累计消耗')

    @classmethod
    @with_read_session
    async def get_record(cls, session: AsyncSession, user_id: str, bot_id: str) -> Optional['XfPointRecord']:
        stmt = select(cls).where(col(cls.user_id) == user_id, col(cls.bot_id) == bot_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def add_points(cls, session: AsyncSession, user_id: str, bot_id: str, amount: int) -> 'XfPointRecord':
        record = await cls.get_record(user_id, bot_id)
        if record is None:
            record = cls(user_id=user_id, bot_id=bot_id, points=0, earned=0, spent=0)
        record.points += amount
        if amount > 0:
            record.earned += amount
        session.add(record)
        return record

    @classmethod
    @with_session
    async def spend(cls, session: AsyncSession, user_id: str, bot_id: str, cost: int) -> bool:
        record = await cls.get_record(user_id, bot_id)
        if record is None or record.points < cost:
            return False
        record.points -= cost
        record.spent += cost
        session.add(record)
        return True

    @classmethod
    @with_session
    async def transfer(
        cls,
        session: AsyncSession,
        from_user_id: str,
        to_user_id: str,
        bot_id: str,
        amount: int,
    ) -> bool:
        """赠送积分：同一事务内扣减赠送方并增加接收方，避免中途失败只扣不加。"""
        if amount <= 0 or from_user_id == to_user_id:
            return False
        sender = await cls.get_record(from_user_id, bot_id)
        if sender is None or sender.points < amount:
            return False
        receiver = await cls.get_record(to_user_id, bot_id)
        if receiver is None:
            receiver = cls(user_id=to_user_id, bot_id=bot_id, points=0, earned=0, spent=0)
        sender.points -= amount
        sender.spent += amount
        receiver.points += amount
        receiver.earned += amount
        session.add(sender)
        session.add(receiver)
        return True


class XfPointGrantRecord(BaseModel, table=True):
    """积分发放流水：按天按来源记录已发额度，用于「每个指令每天最多 N 分」的限额。"""

    __table_args__ = (
        UniqueConstraint('bot_id', 'user_id', 'day', 'source', name='uq_xf_point_grant'),
        {'extend_existing': True},
    )

    day: str = Field(default='', title='日期', index=True)
    source: str = Field(default='', title='来源', index=True)
    amount: int = Field(default=0, title='已发放积分')

    @classmethod
    @with_read_session
    async def granted_of_day(
        cls,
        session: AsyncSession,
        user_id: str,
        bot_id: str,
        day: str,
        source: str,
    ) -> int:
        stmt = select(cls.amount).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.day) == day,
            col(cls.source) == source,
        )
        result = await session.execute(stmt)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else 0

    @classmethod
    @with_session
    async def grant(
        cls,
        session: AsyncSession,
        user_id: str,
        bot_id: str,
        day: str,
        source: str,
        amount: int,
    ) -> None:
        stmt = select(cls).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.day) == day,
            col(cls.source) == source,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = cls(user_id=user_id, bot_id=bot_id, day=day, source=source, amount=amount)
        else:
            record.amount += amount
        session.add(record)


class XfExchangeRecord(BaseModel, table=True):
    """兑换流水，用于限额与展示。"""

    __table_args__ = {'extend_existing': True}

    group_id: str = Field(default='', title='群号')
    item: str = Field(default='', title='商品', index=True)
    cost: int = Field(default=0, title='花费积分')
    date: str = Field(default='', title='日期', index=True)

    @classmethod
    @with_session
    async def add(
        cls,
        session: AsyncSession,
        *,
        user_id: str,
        bot_id: str,
        group_id: str,
        item: str,
        cost: int,
        date: str,
    ) -> 'XfExchangeRecord':
        record = cls(
            user_id=user_id,
            bot_id=bot_id,
            group_id=group_id,
            item=item,
            cost=cost,
            date=date,
        )
        session.add(record)
        return record

    @classmethod
    @with_read_session
    async def count_today(cls, session: AsyncSession, user_id: str, bot_id: str, item: str, date: str) -> int:
        stmt = select(cls).where(
            col(cls.user_id) == user_id,
            col(cls.bot_id) == bot_id,
            col(cls.item) == item,
            col(cls.date) == date,
        )
        result = await session.execute(stmt)
        return len(list(result.scalars().all()))


@site.register_admin
class XfLuckRecordAdmin(GsAdminModel):
    pk_name = 'id'
    page_schema = PageSchema(label='今日老婆·打卡运势', icon='fa fa-star')
    model = XfLuckRecord


@site.register_admin
class XfCalendarRecordAdmin(GsAdminModel):
    pk_name = 'id'
    page_schema = PageSchema(label='今日老婆·鹿扣日历', icon='fa fa-calendar')
    model = XfCalendarRecord


@site.register_admin
class XfSignRecordAdmin(GsAdminModel):
    pk_name = 'id'
    page_schema = PageSchema(label='今日老婆·签到记录', icon='fa fa-check-square-o')
    model = XfSignRecord


@site.register_admin
class XfPointRecordAdmin(GsAdminModel):
    pk_name = 'id'
    page_schema = PageSchema(label='今日老婆·积分余额', icon='fa fa-diamond')
    model = XfPointRecord


@site.register_admin
class XfExchangeRecordAdmin(GsAdminModel):
    pk_name = 'id'
    page_schema = PageSchema(label='今日老婆·兑换流水', icon='fa fa-exchange')
    model = XfExchangeRecord


@on_core_start
async def ensure_plugin_tables() -> None:
    """热重载不会再跑 core 的建表 Hook，这里补建一次（create_all 幂等）。"""
    await ensure_core_database_tables()
