# AWSL 微信机器人

基于 macOS Accessibility API 的微信群聊机器人，自动检测 "awsl" 关键词并回复随机图片或使用 AI 回答问题。

## 功能特性

- 使用 macOS Accessibility API 直接读取微信消息（100% 准确）
- 队列模式架构，消息检测与处理分离，防止漏掉回复
- 自动监控指定微信群聊消息
- 检测到 "awsl" 触发关键词后自动发送随机图片
- 检测到 "awsl+问题" 时使用 AI 智能回答问题
- 支持冷却时间防止刷屏（10秒）
- SQLite 数据库去重，避免重复响应
- 使用 Pydantic Settings 管理配置
- 纯 Python 实现，无需额外服务

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

### 方式一：使用环境变量（推荐）

1. 复制配置模板文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入实际配置：
```bash
# 群聊名称
GROUP_NAME=你的群聊名称

# OpenAI API 配置（必填）
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### 方式二：直接修改 config.py

编辑 `config.py` 文件中的默认值：

```python
class Config(BaseSettings):
    # 要监控的群聊名称
    GROUP_NAME: str = "你的群聊名称"

    # 触发关键词
    TRIGGER_KEYWORD: str = "awsl"

    # 检查消息间隔（秒）
    CHECK_INTERVAL: int = 3

    # 触发冷却时间（秒）
    TRIGGER_COOLDOWN: int = 10

    # OpenAI 配置
    OPENAI_API_KEY: str  # 必须通过环境变量设置
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
```

**注意**：`OPENAI_API_KEY` 必须通过环境变量设置，不应该硬编码在代码中。

## 使用方法

### 1. 前置准备

1. 启动微信并登录
2. 授予终端辅助功能权限：
   - 打开「系统设置」→「隐私与安全性」→「辅助功能」
   - 添加并允许「终端」或你使用的终端应用

### 2. 运行机器人

直接运行机器人：

```bash
python main.py
```

机器人会自动：
- 激活微信窗口
- 切换到配置的群聊
- 点击输入框确保焦点
- 开始监控消息（每3秒检测一次）
- 检测到 "awsl" 时发送随机图片
- 检测到 "awsl" 后跟任何文本时使用 AI 回答问题

### 3. 使用示例

**发送随机图片：**
```
用户: awsl
机器人: [发送随机图片]
```

**AI 智能回答（支持多种格式）：**
```
用户: awsl今天天气怎么样？
机器人: [AI 回复天气相关信息]

用户: awsl 1+1等于几？
机器人: 1+1等于2！数学界的经典双人舞，永远默契无间。

用户: awsl帮我写一首诗
机器人: [AI 生成诗歌]
```

## 项目结构

```
awsl-wechat-bot/
├── main.py                      # 主程序入口和机器人逻辑
├── config.py                    # 配置文件（使用 Pydantic Settings）
├── ai_service.py                # AI 服务模块
├── utils_accessibility_api.py   # Accessibility API 工具
├── get_messages.applescript     # 获取消息的 AppleScript
├── test_ai.py                   # AI 服务测试脚本
├── requirements.txt             # Python 依赖
├── .env                         # 环境变量配置（不提交到 Git）
├── .env.example                 # 环境变量配置模板
├── messages.db                  # 消息去重数据库（自动生成）
└── venv/                        # Python 虚拟环境
```

## 工作原理

### 架构设计

机器人使用**双线程队列模式**：

1. **检测线程**：持续监控消息（每3秒一次）
   - 使用 Accessibility API 读取微信聊天消息
   - 检测到触发关键词时将消息加入队列
   - 使用 SQLite 数据库去重，避免重复处理

2. **处理线程**：从队列取出消息并处理
   - 带冷却控制（10秒），防止刷屏
   - 根据触发类型发送图片或 AI 回复
   - 线程安全的数据库和冷却时间管理

### 消息获取

- 使用 macOS Accessibility API 直接访问微信 UI 元素
- 查找 AXList（title="Messages"）获取消息列表
- 提取每条消息的 AXStaticText 内容
- 准确度 100%，无需 OCR

### 输入框焦点

- 使用 Quartz 框架的系统级鼠标事件
- 计算输入框位置（窗口宽度60%，高度92%）
- 模拟真实鼠标点击获得焦点

### 智能响应

- **纯 "awsl"**：从 AWSL API 获取随机图片并发送
- **"awsl+文本"**：调用 OpenAI API 获取 AI 回复并发送

## 注意事项

- 首次运行需要授予辅助功能权限
- 运行时微信窗口需要保持可见
- 机器人运行期间会自动激活微信窗口
- 建议在不使用电脑时运行，避免影响其他操作

## 许可证

MIT License
