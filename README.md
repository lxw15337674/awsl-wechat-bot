# AWSL 微信机器人

基于 macOS Vision OCR 的微信群聊机器人，自动检测 "awsl" 关键词并回复随机图片。

## 功能特性

- 使用 macOS 原生 Vision 框架进行 OCR 文字识别
- 自动监控指定微信群聊消息
- 检测到触发关键词后自动发送随机图片
- 支持冷却时间防止刷屏
- SQLite 数据库去重，避免重复响应
- 纯 Python 实现，无需额外 OCR 服务

## 系统要求

- macOS 10.15+ (Catalina 或更高版本)
- Python 3.9+
- 微信 macOS 客户端
- 辅助功能权限（用于模拟键盘操作）

## 安装

1. 克隆项目并进入目录：

```bash
cd awsl-wechat-bot
```

2. 创建虚拟环境并激活：

```bash
python3 -m venv venv
source venv/bin/activate
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.py` 文件：

```python
class Config:
    # 要监控的群聊名称
    GROUP_NAME = "你的群聊名称"

    # 触发关键词
    TRIGGER_KEYWORD = "awsl"

    # 检查消息间隔（秒）
    CHECK_INTERVAL = 3

    # 触发冷却时间（秒）
    TRIGGER_COOLDOWN = 10
```

## 使用方法

1. 先启动微信并登录

2. 授予终端辅助功能权限：
   - 打开「系统设置」→「隐私与安全性」→「辅助功能」
   - 添加并允许「终端」或你使用的终端应用

3. 运行机器人：

```bash
python main.py
```

4. 机器人会自动：
   - 激活微信窗口
   - 切换到配置的群聊
   - 开始监控消息
   - 检测到 "awsl" 时发送随机图片

## 项目结构

```
awsl-wechat-bot/
├── main.py              # 主程序入口和机器人逻辑
├── config.py            # 配置文件
├── utils_ocr.py         # OCR 识别工具
├── utils_screenshot.py  # 截图工具
├── requirements.txt     # Python 依赖
├── messages.db          # 消息去重数据库（自动生成）
└── venv/                # Python 虚拟环境
```

## 工作原理

1. **截图获取**：定期截取微信聊天窗口的消息区域
2. **OCR 识别**：使用 macOS Vision 框架进行中英文文字识别
3. **消息检测**：分析识别结果，检测是否包含触发关键词
4. **图片发送**：从 AWSL API 获取随机图片并通过模拟键盘发送

## 注意事项

- 首次运行需要授予辅助功能权限
- 运行时微信窗口需要保持可见
- 机器人运行期间会自动激活微信窗口
- 建议在不使用电脑时运行，避免影响其他操作

## 许可证

MIT License
