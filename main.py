#!/usr/bin/env python3
"""
AWSL 微信机器人 - 使用 macOS Vision OCR
监控指定群聊，检测到 "awsl" 消息时自动发送随机图片
"""

import os
import sys
import time
import logging
import subprocess
import tempfile
import re
import sqlite3
import requests

from config import Config
from utils_ocr import screenshot_and_ocr

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeChatOCR:
    """使用 OCR 读取微信消息"""

    def __init__(self):
        self.process_name = self._detect_wechat_process()
        if not self.process_name:
            raise RuntimeError("微信未运行，请先启动微信")
        logger.info(f"检测到微信进程: {self.process_name}")

    def _detect_wechat_process(self) -> str:
        """检测微信进程名称"""
        result = subprocess.run(['pgrep', 'WeChat'], capture_output=True)
        if result.returncode == 0:
            return "WeChat"
        result = subprocess.run(['pgrep', '微信'], capture_output=True)
        if result.returncode == 0:
            return "微信"
        return None

    def _run_applescript(self, script: str) -> str:
        """执行 AppleScript"""
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.debug(f"AppleScript 错误: {result.stderr}")
            return None
        return result.stdout.strip()

    def activate_window(self):
        """激活微信窗口"""
        subprocess.run(['open', '-a', self.process_name], check=True)
        time.sleep(0.3)

    def find_chat(self, chat_name: str) -> bool:
        """查找并切换到指定聊天窗口"""
        self.activate_window()
        time.sleep(0.2)

        script = f'''
        set the clipboard to "{chat_name}"
        tell application "System Events"
            tell process "{self.process_name}"
                keystroke "f" using command down
                delay 0.3
                keystroke "v" using command down
                delay 1.0
                key code 36
                delay 0.5
                key code 53
            end tell
        end tell
        '''
        self._run_applescript(script)
        time.sleep(0.5)
        logger.info(f"已切换到聊天: {chat_name}")
        return True

    def get_messages(self) -> list:
        """获取当前聊天窗口的消息"""
        self.activate_window()
        time.sleep(0.2)

        # 使用 utils 获取消息
        ocr_results = screenshot_and_ocr(self.process_name)

        # 过滤噪音
        messages = []
        for r in ocr_results:
            text = r['text'].strip()
            if r['confidence'] < 0.4:
                continue
            if len(text) < 2:
                continue
            if re.match(r'^[\d:]+$', text):  # 纯时间戳
                continue
            if text in ['<', '>', 'S', '...']:  # UI 元素
                continue
            messages.append(text)

        return messages

    def send_text(self, text: str) -> bool:
        """发送文本消息"""
        self.activate_window()
        time.sleep(0.2)

        script = f'''
        set the clipboard to "{text}"
        tell application "System Events"
            tell process "{self.process_name}"
                keystroke "v" using command down
                delay 0.3
                key code 36
            end tell
        end tell
        '''
        self._run_applescript(script)
        time.sleep(0.5)
        return True

    def send_image(self, image_path: str) -> bool:
        """发送图片"""
        # 复制图片到剪贴板
        script = f'''
        set theFile to POSIX file "{image_path}"
        try
            set the clipboard to (read theFile as JPEG picture)
        on error
            set the clipboard to (read theFile as «class PNGf»)
        end try
        '''
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"复制图片失败: {result.stderr}")
            return False

        time.sleep(0.3)
        self.activate_window()
        time.sleep(0.2)

        # 粘贴并发送
        script = f'''
        tell application "System Events"
            tell process "{self.process_name}"
                keystroke "v" using command down
                delay 0.5
                key code 36
            end tell
        end tell
        '''
        self._run_applescript(script)
        time.sleep(1.0)
        logger.info("图片已发送")
        return True


class AWSlBot:
    """AWSL 机器人"""

    def __init__(self, group_name: str):
        self.group_name = group_name
        self.wechat = WeChatOCR()
        self.max_cache = 200
        self.last_trigger_time = 0
        self._init_db()
        logger.info(f"AWSL Bot 初始化完成，监控群聊: {group_name}")

    def _init_db(self):
        """初始化 SQLite 数据库"""
        db_path = os.path.join(os.path.dirname(__file__), 'messages.db')
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS message_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        logger.info(f"数据库初始化完成: {db_path}")

    def _is_processed(self, msg_hash: str) -> bool:
        """检查消息是否已处理"""
        cursor = self.conn.execute(
            'SELECT 1 FROM message_hashes WHERE hash = ?', (msg_hash,)
        )
        return cursor.fetchone() is not None

    def _mark_processed(self, msg_hash: str):
        """标记消息为已处理"""
        try:
            self.conn.execute(
                'INSERT OR IGNORE INTO message_hashes (hash) VALUES (?)', (msg_hash,)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"数据库写入失败: {e}")

    def _cleanup_old_hashes(self):
        """清理旧记录，保留最近的记录"""
        cursor = self.conn.execute('SELECT COUNT(*) FROM message_hashes')
        count = cursor.fetchone()[0]
        if count > self.max_cache:
            self.conn.execute('''
                DELETE FROM message_hashes WHERE id IN (
                    SELECT id FROM message_hashes ORDER BY id ASC LIMIT ?
                )
            ''', (count - self.max_cache // 2,))
            self.conn.commit()
            logger.info(f"清理旧记录，剩余 {self.max_cache // 2} 条")

    def fetch_awsl_image(self) -> str:
        """从 API 获取随机图片 URL"""
        try:
            response = requests.get(
                Config.API_URL,
                headers={'accept': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            pic_info = data.get('pic_info', {})
            url = pic_info.get('large', pic_info.get('original', {})).get('url')
            if url:
                logger.info(f"获取到图片: {url[:50]}...")
                return url
            return None

        except Exception as e:
            logger.error(f"获取图片失败: {e}")
            return None

    def download_image(self, url: str) -> str:
        """下载图片到临时文件"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            suffix = '.png' if 'png' in url.lower() else '.jpg'
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, 'wb') as f:
                f.write(response.content)

            logger.info(f"图片已下载: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return None

    def send_awsl_image(self) -> bool:
        """获取并发送 AWSL 图片"""
        image_url = self.fetch_awsl_image()
        if not image_url:
            return False

        image_path = self.download_image(image_url)
        if not image_path:
            return False

        try:
            return self.wechat.send_image(image_path)
        finally:
            try:
                os.remove(image_path)
            except OSError:
                pass

    def is_trigger(self, text: str) -> bool:
        """检查是否包含触发词"""
        # 提取消息内容（去掉用户名前缀）
        content = text
        for delimiter in [':', '：']:
            if delimiter in text:
                parts = text.split(delimiter, 1)
                if len(parts) > 1:
                    content = parts[1].strip()
                break

        return content.lower() == Config.TRIGGER_KEYWORD.lower()

    def run(self):
        """运行机器人主循环"""
        logger.info("=" * 50)
        logger.info("AWSL Bot 启动 (OCR 模式)")
        logger.info(f"监控群聊: {self.group_name}")
        logger.info(f"触发关键词: {Config.TRIGGER_KEYWORD}")
        logger.info(f"检查间隔: {Config.CHECK_INTERVAL} 秒")
        logger.info("=" * 50)

        # 切换到目标群聊
        self.wechat.find_chat(self.group_name)

        # 初始化：记录当前消息避免重复触发
        initial_messages = self.wechat.get_messages()
        if len(initial_messages) >= 3:
            recent = tuple(initial_messages[-3:])
            self._mark_processed(str(hash(recent)))
        logger.info(f"已记录历史消息状态")

        logger.info("开始监控消息...")

        try:
            while True:
                messages = self.wechat.get_messages()

                logger.info("-" * 40)
                logger.info(f"OCR 识别到 {len(messages)} 条消息")

                if len(messages) >= 3:
                    # 取最后3条消息作为上下文
                    recent = tuple(messages[-3:])
                    msg_hash = str(hash(recent))

                    if not self._is_processed(msg_hash):
                        self._mark_processed(msg_hash)
                        # 检查最后一条是否触发
                        last_msg = messages[-1]
                        logger.info(f"新消息: {last_msg}")

                        if self.is_trigger(last_msg):
                            # 检查冷却时间
                            now = time.time()
                            if now - self.last_trigger_time >= Config.TRIGGER_COOLDOWN:
                                logger.info(">>> 触发 AWSL! 发送图片...")
                                self.send_awsl_image()
                                self.last_trigger_time = now
                                time.sleep(1)
                            else:
                                remaining = Config.TRIGGER_COOLDOWN - (now - self.last_trigger_time)
                                logger.info(f"冷却中，还需 {remaining:.1f} 秒")

                # 清理旧记录
                self._cleanup_old_hashes()

                time.sleep(Config.CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("收到停止信号，退出...")
            self.conn.close()


def main():
    try:
        bot = AWSlBot(Config.GROUP_NAME)
        bot.run()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
