"""积分产出规则的纯函数测试：基础分 + 连签加成封顶，以及连打卡天数计算。"""

import ast
import datetime
import unittest
from typing import Protocol, runtime_checkable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'TodayWaifu' / 'fun'
CALENDAR_LOGIC = ROOT / 'utils' / 'calendar_logic.py'
LUCK_COMMANDS = ROOT / 'commands_luck.py'


@runtime_checkable
class SignPoints(Protocol):
    def __call__(self, base: int, bonus: int, streak: int) -> int: ...


@runtime_checkable
class LuckStreak(Protocol):
    def __call__(self, dates: set[str], day: datetime.date) -> int: ...


def _load_function(path: Path, name: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    """只抽取目标函数执行，避免为一个纯函数引入 gsuid_core 运行时依赖。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = dict(extra or {})
    exec(compile(module, str(path), 'exec'), namespace)  # noqa: S102
    return namespace


class SignPointTests(unittest.TestCase):
    def _sign_points(self) -> SignPoints:
        value = _load_function(CALENDAR_LOGIC, 'sign_points')['sign_points']
        assert isinstance(value, SignPoints)
        return value

    def test_first_day_gets_base_only(self) -> None:
        self.assertEqual(self._sign_points()(10, 2, 1), 10)

    def test_streak_adds_bonus_per_extra_day(self) -> None:
        sign_points = self._sign_points()
        self.assertEqual(sign_points(10, 2, 2), 12)
        self.assertEqual(sign_points(10, 2, 5), 18)

    def test_bonus_is_capped_at_three_times_base(self) -> None:
        sign_points = self._sign_points()
        self.assertEqual(sign_points(10, 2, 100), 40)
        self.assertEqual(sign_points(10, 0, 100), 10)

    def test_zero_streak_is_treated_as_first_day(self) -> None:
        self.assertEqual(self._sign_points()(10, 2, 0), 10)


class LuckStreakTests(unittest.TestCase):
    def _luck_streak(self) -> LuckStreak:
        value = _load_function(LUCK_COMMANDS, '_luck_streak', {'datetime': datetime})['_luck_streak']
        assert isinstance(value, LuckStreak)
        return value

    def test_first_checkin_counts_as_one(self) -> None:
        self.assertEqual(self._luck_streak()(set(), datetime.date(2026, 10, 21)), 1)

    def test_yesterday_continues_the_streak(self) -> None:
        dates = {'2026-10-20'}
        self.assertEqual(self._luck_streak()(dates, datetime.date(2026, 10, 21)), 2)

    def test_gap_resets_the_streak(self) -> None:
        dates = {'2026-10-19', '2026-10-20'}
        self.assertEqual(self._luck_streak()(dates, datetime.date(2026, 10, 21)), 3)

    def test_missing_yesterday_breaks_the_streak(self) -> None:
        dates = {'2026-10-18', '2026-10-19'}
        self.assertEqual(self._luck_streak()(dates, datetime.date(2026, 10, 21)), 1)


if __name__ == '__main__':
    unittest.main()
