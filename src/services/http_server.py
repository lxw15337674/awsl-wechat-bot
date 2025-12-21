"""
HTTP API 服务
提供向微信聊天窗口推送消息的 HTTP 接口
"""

import logging
import os
import json
import time
import threading
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from .scheduled_task import ScheduledTaskService

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


class ScheduledTaskCreate(BaseModel):
    """创建定时任务请求模型"""
    name: str
    cron_expression: str
    message: str
    target_groups: List[str] = []


class ScheduledTaskUpdate(BaseModel):
    """更新定时任务请求模型"""
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    message: Optional[str] = None
    target_groups: Optional[List[str]] = None
    enabled: Optional[bool] = None


class ScheduledTaskResponse(BaseModel):
    """定时任务响应模型"""
    id: int
    name: str
    cron_expression: str
    message: str
    target_groups: List[str]
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_run: Optional[str] = None


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

        # 初始化定时任务服务
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scheduled_tasks.db')
        self.task_service = ScheduledTaskService(db_path)

        # 调度器控制
        self.scheduler_running = False
        self.scheduler_thread = None

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

        @self.app.get("/api/tasks", response_model=List[ScheduledTaskResponse])
        async def list_scheduled_tasks():
            """获取所有定时任务"""
            tasks = self.task_service.get_all_tasks()
            return [self._task_to_response(task) for task in tasks]

        @self.app.post("/api/tasks", response_model=ScheduledTaskResponse)
        async def create_scheduled_task(request: ScheduledTaskCreate):
            """创建定时任务"""
            # 将 target_groups 列表转换为 JSON 字符串
            target_groups_json = json.dumps(request.target_groups, ensure_ascii=False)

            task = self.task_service.create_task(
                name=request.name,
                cron_expression=request.cron_expression,
                message=request.message,
                target_groups=target_groups_json,
                enabled=True
            )

            if not task:
                raise HTTPException(
                    status_code=400,
                    detail="创建任务失败，请检查 cron 表达式是否正确"
                )

            logger.info(f"[HTTP API] 创建定时任务: {task.name}")
            return self._task_to_response(task)

        @self.app.get("/api/tasks/{task_id}", response_model=ScheduledTaskResponse)
        async def get_scheduled_task(task_id: int):
            """获取指定定时任务"""
            task = self.task_service.get_task(task_id)
            if not task:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到任务: {task_id}"
                )

            return self._task_to_response(task)

        @self.app.put("/api/tasks/{task_id}", response_model=ScheduledTaskResponse)
        async def update_scheduled_task(task_id: int, request: ScheduledTaskUpdate):
            """更新定时任务"""
            # 检查任务是否存在
            task = self.task_service.get_task(task_id)
            if not task:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到任务: {task_id}"
                )

            # 准备更新参数
            update_params = {}
            if request.name is not None:
                update_params['name'] = request.name
            if request.cron_expression is not None:
                update_params['cron_expression'] = request.cron_expression
            if request.message is not None:
                update_params['message'] = request.message
            if request.target_groups is not None:
                update_params['target_groups'] = json.dumps(request.target_groups, ensure_ascii=False)
            if request.enabled is not None:
                update_params['enabled'] = request.enabled

            # 更新任务
            success = self.task_service.update_task(task_id, **update_params)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="更新任务失败"
                )

            logger.info(f"[HTTP API] 更新定时任务: {task_id}")
            # 返回更新后的任务
            updated_task = self.task_service.get_task(task_id)
            return self._task_to_response(updated_task)

        @self.app.delete("/api/tasks/{task_id}")
        async def delete_scheduled_task(task_id: int):
            """删除定时任务"""
            # 检查任务是否存在
            task = self.task_service.get_task(task_id)
            if not task:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到任务: {task_id}"
                )

            success = self.task_service.delete_task(task_id)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="删除任务失败"
                )

            logger.info(f"[HTTP API] 删除定时任务: {task_id}")
            return {"success": True, "message": "任务已删除"}

    def _task_to_response(self, task) -> ScheduledTaskResponse:
        """将任务对象转换为响应模型"""
        # 解析 target_groups JSON 字符串
        try:
            target_groups = json.loads(task.target_groups) if task.target_groups else []
        except json.JSONDecodeError:
            target_groups = []

        return ScheduledTaskResponse(
            id=task.id,
            name=task.name,
            cron_expression=task.cron_expression,
            message=task.message,
            target_groups=target_groups,
            enabled=task.enabled,
            created_at=task.created_at,
            updated_at=task.updated_at,
            last_run=task.last_run
        )

    def _scheduler_loop(self):
        """定时任务调度循环"""
        logger.info("定时任务调度线程启动")

        while self.scheduler_running:
            try:
                current_time = datetime.now()

                # 获取所有启用的任务
                tasks = self.task_service.get_enabled_tasks()

                for task in tasks:
                    # 检查任务是否应该运行
                    if self.task_service.should_run(task, current_time):
                        logger.info(f"⏰ 执行定时任务: {task.name} - {task.message}")

                        # 解析目标群组
                        try:
                            target_groups = json.loads(task.target_groups) if task.target_groups else []
                        except json.JSONDecodeError:
                            target_groups = []

                        # 如果没有指定目标群组，发送到所有群
                        if not target_groups:
                            groups_to_send = self.bot.groups
                        else:
                            # 只发送到指定的群
                            groups_to_send = [g for g in self.bot.groups if g["name"] in target_groups]

                        # 发送消息到目标群组
                        for group in groups_to_send:
                            # 检查窗口是否存在
                            if not group["window"].Exists(0.5):
                                logger.debug(f"群 [{group['name']}] 窗口已关闭，跳过定时任务")
                                continue

                            try:
                                self.bot.wechat.send_text_to_window(group["window"], task.message)
                                logger.info(f"⏰ 定时任务消息已发送到 [{group['name']}]")
                            except Exception as e:
                                logger.error(f"⏰ 定时任务发送失败 [{group['name']}]: {e}")

                        # 更新最后运行时间
                        self.task_service.update_last_run(task.id)

                # 每秒检查一次
                time.sleep(1)
            except Exception as e:
                logger.error(f"定时任务调度出错: {e}", exc_info=True)
                time.sleep(5)

        logger.info("定时任务调度线程退出")

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        运行 HTTP 服务器

        Args:
            host: 监听地址
            port: 监听端口
        """
        # 启动定时任务调度线程
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("定时任务调度器已启动")

        logger.info(f"启动 HTTP API 服务器: http://{host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
