"""
HTTP API 服务
提供向微信聊天窗口推送消息的 HTTP 接口
"""

import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)


class SendMessageRequest(BaseModel):
    """发送消息请求模型"""
    group_name: str
    message: str


class SendMessageResponse(BaseModel):
    """发送消息响应模型"""
    success: bool
    message: str


class GroupInfo(BaseModel):
    """群组信息模型"""
    name: str
    active: bool


class HTTPServer:
    """HTTP API 服务器"""

    def __init__(self, bot_instance):
        """
        初始化 HTTP 服务器

        Args:
            bot_instance: AWSlBot 实例
        """
        self.bot = bot_instance
        self.app = FastAPI(
            title="AWSL WeChat Bot API",
            description="微信机器人 HTTP API 服务",
            version="1.0.0"
        )
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """根路径 - Web UI"""
            # 读取 HTML 模板文件
            template_path = os.path.join(
                os.path.dirname(__file__),
                'templates',
                'index.html'
            )
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                return "<h1>模板文件未找到</h1>"

        @self.app.get("/api/health")
        async def health():
            """健康检查"""
            return {
                "status": "healthy",
                "groups_count": len(self.bot.groups)
            }

        @self.app.get("/api/groups", response_model=list[GroupInfo])
        async def list_groups():
            """列出所有聊天窗口"""
            groups = []
            for group in self.bot.groups:
                try:
                    # 检查窗口是否仍然存在
                    is_active = group["window"].Exists(0.5)
                    groups.append(GroupInfo(
                        name=group["name"],
                        active=is_active
                    ))
                except Exception as e:
                    logger.error(f"检查群组 {group['name']} 状态失败: {e}")
                    groups.append(GroupInfo(
                        name=group["name"],
                        active=False
                    ))
            return groups

        @self.app.post("/api/send", response_model=SendMessageResponse)
        async def send_message(request: SendMessageRequest):
            """
            向指定聊天窗口发送消息

            Args:
                request: 包含 group_name 和 message 的请求体

            Returns:
                发送结果
            """
            # 查找目标群组
            target_group = None
            for group in self.bot.groups:
                if group["name"] == request.group_name:
                    target_group = group
                    break

            if not target_group:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到群组: {request.group_name}"
                )

            # 检查窗口是否存在
            if not target_group["window"].Exists(0.5):
                raise HTTPException(
                    status_code=400,
                    detail=f"群组窗口已关闭: {request.group_name}"
                )

            # 发送消息
            try:
                success = self.bot.wechat.send_text_to_window(
                    target_group["window"],
                    request.message
                )

                if success:
                    logger.info(f"[HTTP API] 成功发送消息到 [{request.group_name}]")
                    return SendMessageResponse(
                        success=True,
                        message="消息发送成功"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="消息发送失败"
                    )
            except Exception as e:
                logger.error(f"[HTTP API] 发送消息失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"发送消息时出错: {str(e)}"
                )

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        运行 HTTP 服务器

        Args:
            host: 监听地址
            port: 监听端口
        """
        logger.info(f"启动 HTTP API 服务器: http://{host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
