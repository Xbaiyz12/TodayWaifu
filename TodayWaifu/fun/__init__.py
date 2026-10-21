# ruff: noqa: E402
"""今日老婆·娱乐功能子包：签到积分 / 打卡运势 / 鹿扣日历 / 塔罗 / GIF / 群聊游戏 / 问候推送。

子模块导入顺序即注册顺序：`models` / `shared` 必须先于业务命令模块（前者提供数据表，
后者提供 SV 实例与主题定义）。所有 SV 由文件路径自动归属到 TodayWaifu 插件，本子包
不再单独声明 Plugins，也不再有独立的插件配置页与帮助注册。
"""

from . import (
    models as models,
    shared as shared,
    scheduled as scheduled,
    commands_gif as commands_gif,
    commands_game as commands_game,
    commands_luck as commands_luck,
    commands_shop as commands_shop,
    commands_sign as commands_sign,
    commands_greet as commands_greet,
    commands_tarot as commands_tarot,
    commands_calendar as commands_calendar,
    commands_transfer as commands_transfer,
)
