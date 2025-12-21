# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWSL WeChat Bot - 跨平台微信群聊机器人，使用 macOS Accessibility API / Windows UI Automation 读取消息并响应。

## Development Commands

```bash
# Setup
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt  # macOS
./venv/Scripts/python -m pip install -r requirements.txt  # Windows
cp .env.example .env

# Run
./venv/bin/python main.py  # macOS
./venv/Scripts/python main.py  # Windows
```

## Architecture

- **Detector Threads**: 检测新消息，上下文哈希去重
- **Processor Thread**: 串行处理，10s 冷却
- **HTTP Thread**: FastAPI 服务（可选）

**Adapters**: `src/adapters/` - macOS/Windows 平台实现

## Configuration

配置文件: `.env` (基于 `.env.example`)

## Platform Notes

**macOS**: 需要 Accessibility 权限
**Windows**: 建议管理员权限
