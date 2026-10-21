"""今日老婆 配置默认值。

键名统一用 `xf_` 前缀，WebConsole 里按 GsDivider 分组展示。
**每个用户可见功能都有独立的布尔开关**（`xf_*_enable`，标题里带 ①..㉔ 编号），
命令处理函数逐个对照自己的开关判断；数值型配置一律用 GsInt/GsFloat。
"""

from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsDivider,
    GsIntConfig,
    GsStrConfig,
    GsBoolConfig,
    GsFloatConfig,
    GsTimeRConfig,
    GsListStrConfig,
)

CONFIG_DEFAULT: Dict[str, GSC] = {
    # ===== 基础 =====
    'xf_divider_base': GsDivider(
        title='基础设置',
        desc='总开关与使用范围',
        data='基础设置',
    ),
    'xf_enable': GsBoolConfig(
        title='① 总开关',
        desc='关闭后本插件所有功能都不响应',
        data=True,
    ),
    'xf_whitelist_enable': GsBoolConfig(
        title='启用群/用户白名单',
        desc='开启后只有白名单里的群号或用户号可用（白名单为空时谁都不可用）；默认开启且只放行作者自己',
        data=True,
    ),
    'xf_whitelist': GsListStrConfig(
        title='白名单（群号或用户号）',
        desc='一行一个；命中群号则整个群可用，命中用户号则该用户在任何群/私聊都可用',
        data=['2734320958'],
    ),
    'xf_blacklist': GsListStrConfig(
        title='黑名单（群号或用户号）',
        desc='一行一个，禁止使用本插件，优先级高于白名单',
        data=[],
    ),
    # ===== 打卡运势 =====
    'xf_divider_luck': GsDivider(
        title='打卡运势',
        desc='每日幸运值打卡与榜单',
        data='打卡运势',
    ),
    'xf_luck_enable': GsBoolConfig(
        title='② 打卡',
        desc='关闭后【打卡】不再响应',
        data=True,
    ),
    'xf_luck_rank_enable': GsBoolConfig(
        title='③ 幸运值排行榜 / 非酋榜',
        desc='关闭后【幸运值排行榜】【幸运值非酋榜】【幸运排行榜】【非酋榜】不再响应',
        data=True,
    ),
    'xf_extract_enable': GsBoolConfig(
        title='④ 提取背景原图',
        desc='关闭后【提取背景】【提取原图】【获取背景】【提取壁纸】【提取面板图】不再响应',
        data=True,
    ),
    'xf_luck_retry_below': GsIntConfig(
        title='低分重抽阈值',
        desc='幸运值低于该值时先不显示结果，让用户再发一次打卡重抽（0 表示关闭）',
        data=10,
        max_value=100,
    ),
    'xf_luck_bg_dir': GsStrConfig(
        title='打卡面板图目录',
        desc='留空则用 data/XutheringWavesUID/custom_role_pile，可填任意本地图片目录',
        data='',
    ),
    'xf_luck_rank_limit': GsIntConfig(
        title='排行榜展示人数',
        desc='排行榜 / 非酋榜最多展示多少人',
        data=20,
        max_value=50,
    ),
    # ===== GIF 工具 =====
    'xf_divider_gif': GsDivider(
        title='GIF 工具',
        desc='动图加速 / 减速 / 逐帧分解',
        data='GIF 工具',
    ),
    'xf_gif_enable': GsBoolConfig(
        title='⑤ GIF 工具总开关',
        desc='关闭后【加速】【减速】【分解】【gif帮助】全部不再响应',
        data=True,
    ),
    'xf_gif_speed_enable': GsBoolConfig(
        title='⑥ GIF 加速 / 减速',
        desc='关闭后【加速】【减速】不再响应（GIF 总开关仍开着）',
        data=True,
    ),
    'xf_gif_split_enable': GsBoolConfig(
        title='⑦ GIF 分解',
        desc='关闭后【分解】不再响应',
        data=True,
    ),
    'xf_gif_max_mb': GsIntConfig(
        title='GIF 体积上限(MB)',
        desc='超过该体积的动图直接拒绝处理，防止内存被占满',
        data=25,
        max_value=100,
    ),
    'xf_gif_max_frames': GsIntConfig(
        title='GIF 帧数上限',
        desc='最多处理多少帧，超出的帧会被丢弃',
        data=400,
        max_value=2000,
    ),
    'xf_gif_min_speed': GsFloatConfig(
        title='最小倍速',
        desc='允许的最慢倍速',
        data=0.1,
        min_value=0.05,
        max_value=1.0,
    ),
    'xf_gif_max_speed': GsFloatConfig(
        title='最大倍速',
        desc='允许的最快倍速',
        data=5.0,
        min_value=1.0,
        max_value=20.0,
    ),
    # ===== 鹿 / 扣 日历 =====
    'xf_divider_calendar': GsDivider(
        title='鹿 / 扣 日历',
        desc='发 🦌 或 扣 即打卡，生成月度日历',
        data='鹿 / 扣 日历',
    ),
    'xf_deer_enable': GsBoolConfig(
        title='⑧ 鹿日历',
        desc='关闭后 🦌 与【鹿打卡】【鹿日历】等全部鹿指令不再响应',
        data=True,
    ),
    'xf_kou_enable': GsBoolConfig(
        title='⑨ 扣日历',
        desc='关闭后 扣 / 🤏 与【扣打卡】【扣日历】等全部扣指令不再响应',
        data=True,
    ),
    'xf_calendar_rank_enable': GsBoolConfig(
        title='⑩ 日历排行 / 群报',
        desc='关闭后【鹿排行】【鹿群报】【扣排行】【扣群报】不再响应（打卡与日历图不受影响）',
        data=True,
    ),
    'xf_calendar_stats_enable': GsBoolConfig(
        title='⑪ 日历年历 / 生涯 / 报告',
        desc='关闭后【鹿年历】【鹿生涯】【鹿报告】及扣的同类指令不再响应',
        data=True,
    ),
    'xf_calendar_fix_enable': GsBoolConfig(
        title='⑫ 补签 / 撤销 / 清空',
        desc='关闭后【鹿补签】【鹿撤销】【鹿清空】及扣的同类指令不再响应',
        data=True,
    ),
    'xf_calendar_fix_pm': GsIntConfig(
        title='日历更正权限',
        desc='【补签】【撤销】【清空】所需最低权限：0=主人 1=超级用户 2=群主 3=管理员 6=所有人',
        data=3,
        max_value=6,
    ),
    'xf_deer_name': GsStrConfig(
        title='鹿日历显示名',
        desc='日历图与排行榜里显示的活动名',
        data='鹿',
    ),
    'xf_deer_daily_cap': GsIntConfig(
        title='鹿单日计入上限',
        desc='同一天最多计入多少次，超出只记录不计数（0 表示不限制）',
        data=10,
        max_value=999,
    ),
    'xf_kou_name': GsStrConfig(
        title='扣日历显示名',
        desc='日历图与排行榜里显示的活动名',
        data='扣',
    ),
    'xf_kou_daily_cap': GsIntConfig(
        title='扣单日计入上限',
        desc='同一天最多计入多少次，超出只记录不计数（0 表示不限制）',
        data=10,
        max_value=999,
    ),
    # ===== 签到与积分 =====
    'xf_divider_sign': GsDivider(
        title='签到与积分',
        desc='每日签到、连签奖励与积分商城',
        data='签到与积分',
    ),
    'xf_sign_enable': GsBoolConfig(
        title='⑬ 签到',
        desc='关闭后【签到】【签个到】【我的签到】【签到统计】【签到信息】不再响应',
        data=True,
    ),
    'xf_points_enable': GsBoolConfig(
        title='⑭ 积分查询',
        desc='关闭后【查询积分】【我的积分】【积分余额】不再响应',
        data=True,
    ),
    'xf_shop_enable': GsBoolConfig(
        title='⑮ 积分商城 / 兑换',
        desc='关闭后【积分商城】【商城】【兑换】不再响应',
        data=True,
    ),
    'xf_sign_bg_dir': GsStrConfig(
        title='签到横图目录',
        desc='留空则用 data/XutheringWavesUID/custom_mr_bg，仅取横图（宽>高）',
        data='',
    ),
    'xf_sign_points': GsIntConfig(
        title='签到/打卡基础积分',
        desc='每天签到或打卡获得的基础积分，签到与打卡各自独立计算',
        data=10,
        max_value=1000,
    ),
    'xf_sign_streak_bonus': GsIntConfig(
        title='连签额外积分',
        desc='连续签到/打卡每多一天额外获得的积分，最多再加基础积分的 3 倍',
        data=2,
        max_value=100,
    ),
    'xf_shop_items': GsListStrConfig(
        title='商城商品',
        desc='一行一个，格式：名称|价格|说明。例：一张鹿图|50|私聊发你一张鹿图',
        data=[
            '摸摸头|20|群里的大家都可以摸摸你的头',
            '今日免签|30|记录一次签到但当天可以再签一次',
        ],
    ),
    # ===== 塔罗 =====
    'xf_divider_tarot': GsDivider(
        title='塔罗占卜',
        desc='韦特塔罗 78 张牌意，纯本地出图',
        data='塔罗占卜',
    ),
    'xf_tarot_enable': GsBoolConfig(
        title='⑯ 塔罗牌（单张）',
        desc='关闭后【塔罗牌】【彩虹塔罗牌】不再响应',
        data=True,
    ),
    'xf_tarot_three_enable': GsBoolConfig(
        title='⑰ 占卜（三张牌阵）',
        desc='关闭后【占卜】不再响应',
        data=True,
    ),
    'xf_tarot_cooldown': GsIntConfig(
        title='塔罗冷却(秒)',
        desc='同一用户两次占卜之间的最短间隔',
        data=10,
        max_value=600,
    ),
    # ===== 小游戏 =====
    'xf_divider_game': GsDivider(
        title='群聊小游戏',
        desc='骰子 / 猜拳 / 猜数字 / 俄罗斯轮盘',
        data='群聊小游戏',
    ),
    'xf_dice_enable': GsBoolConfig(
        title='⑱ 掷骰子',
        desc='关闭后【掷骰子】【骰子】【roll】不再响应',
        data=True,
    ),
    'xf_rps_enable': GsBoolConfig(
        title='⑲ 石头剪刀布',
        desc='关闭后【石头剪刀布】【猜拳】【rps】不再响应',
        data=True,
    ),
    'xf_guess_enable': GsBoolConfig(
        title='⑳ 猜数字',
        desc='关闭后【猜数字】【开始猜数字】不再响应',
        data=True,
    ),
    'xf_roulette_enable': GsBoolConfig(
        title='㉑ 俄罗斯轮盘',
        desc='关闭后【俄罗斯轮盘】【轮盘】【开一枪】不再响应',
        data=True,
    ),
    'xf_dice_max': GsIntConfig(
        title='骰子面数上限',
        desc='【掷骰子 100】里的最大值上限，防止刷屏',
        data=10000,
        max_value=1000000,
    ),
    'xf_roulette_min': GsIntConfig(
        title='轮盘禁言下限(秒)',
        desc='中枪后被禁言的最短时间',
        data=60,
        max_value=3600,
    ),
    'xf_roulette_max': GsIntConfig(
        title='轮盘禁言上限(秒)',
        desc='中枪后被禁言的最长时间',
        data=600,
        max_value=86400,
    ),
    'xf_roulette_pm': GsIntConfig(
        title='轮盘使用权限',
        desc='0=主人 1=超级用户 2=群主 3=管理员 6=所有人',
        data=6,
        max_value=6,
    ),
    # ===== 问候 =====
    'xf_divider_greet': GsDivider(
        title='早安晚安',
        desc='群内问候与定时推送',
        data='早安晚安',
    ),
    'xf_greet_enable': GsBoolConfig(
        title='㉒ 早安 / 晚安（手动）',
        desc='关闭后【早安】【早上好】【晚安】不再响应',
        data=True,
    ),
    'xf_greet_push_enable': GsBoolConfig(
        title='㉓ 早晚定时推送',
        desc='关闭后【订阅早安】【订阅晚安】与定时推送都不再工作（手动问候不受影响）',
        data=True,
    ),
    'xf_greet_morning': GsTimeRConfig(
        title='早安推送时间',
        desc='每日定时推送早安的时间（需群里先发送【订阅早安】）',
        data=(8, 0),
    ),
    'xf_greet_night': GsTimeRConfig(
        title='晚安推送时间',
        desc='每日定时推送晚安的时间（需群里先发送【订阅晚安】）',
        data=(23, 0),
    ),
}
