"""
AWSL 微信机器人配置
"""


class Config:
    # 群聊名称
    GROUP_NAME = "无限进步·搞钱"

    # 触发关键词
    TRIGGER_KEYWORD = "awsl"

    # OCR 自定义词汇表
    OCR_CUSTOM_WORDS = ["awsl"]

    # API 地址
    API_URL = "https://awsl.api.awsl.icu/v2/random_json"

    # 检查消息间隔（秒）
    CHECK_INTERVAL = 3

    # 触发冷却时间（秒）
    TRIGGER_COOLDOWN = 10

    # 截图区域参数（相对于微信窗口的比例）
    SCREENSHOT_LEFT_RATIO = 0.30    # 左边距（跳过聊天列表）
    SCREENSHOT_TOP_RATIO = 0.06     # 上边距（跳过标题栏）
    SCREENSHOT_WIDTH_RATIO = 0.65   # 宽度
    SCREENSHOT_HEIGHT_RATIO = 0.75  # 高度
