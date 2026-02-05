#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web机器人抽象基类模块。

提供Web机器人基础框架，包含浏览器管理、消息发送和响应获取等功能。
具体机器人必须实现抽象方法，包括登录逻辑和登录需求判断。

模块名称：web_bot.py
功能描述：Web机器人抽象基类
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from math import e
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_webot.drivers import BrowserDriver
from ai_webot.services import BotConfig

logger = logging.getLogger(__name__)


class WebBot(ABC):
    """
    Web机器人抽象基类。

    提供Web机器人的基础框架，具体机器人必须实现抽象方法。
    支持浏览器生命周期管理、消息发送、响应获取等功能。

    Attributes:
        config (BotConfig): 机器人配置对象
        browser (BrowserDriver): 浏览器驱动实例
        is_logged_in (bool): 登录状态标识
        is_ready (bool): 机器人就绪状态标识
    """

    def __init__(self, config: BotConfig) -> None:
        """
        初始化Web机器人。

        Args:
            config: 机器人配置对象，包含各种运行参数和选择器配置
        """
        self.config = config
        # 使用配置初始化浏览器驱动
        self.browser = BrowserDriver(config)
        self.is_logged_in = False
        self.is_ready = False
        self._browser_started = False
        self.markdown_content: Optional[str]
        # 创建输出目录
        self.output_dir = self.config.get_output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.exclude_exts = {
            ".pyc",
            ".pyo",
            ".so",
            ".o",
            ".a",
            ".pyclass",
            ".pyd",
            ".pyo",
            ".env",
            ".env.example",
            ".gitignore",
            ".gitattributes",
            ".DS_Store",
            ".gitlab-ci.yml",
            ".travis.yml",
            "pyproject.toml",
            ".lock",
            ".dockerignore",
            ".lib",
            ".dll",
            ".exe",
            ".bak",
            ".python-version",
        }
        self.exclude_dirs = {
            "__pycache__",
            ".git",
            ".idea",
            ".venv",
            "node_modules",
            "venv",
            ".mypy_cache",
            ".pytest_cache",
            ".eggs",
        }

    async def __aenter__(self):
        """
        异步上下文管理器入口。

        启动浏览器驱动，准备机器人使用。

        Returns:
            WebBot: 当前机器人实例
        """
        if not self._browser_started:
            await self.browser.start(self.config.name, self.config.save_login_state)
            self._browser_started = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器出口。

        关闭浏览器驱动，清理资源。

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪信息
        """
        if self._browser_started:
            await self.browser.close(self.config.name, self.config.save_login_state)
            self._browser_started = False

    # ==================== 抽象方法（必须由子类实现） ====================

    @abstractmethod
    def requires_login(self) -> bool:
        """
        判断该机器人是否需要登录。

        子类必须根据平台特性实现此方法。

        Returns:
            bool: 是否需要登录
        """
        pass

    @abstractmethod
    async def login(self) -> bool:
        """
        执行登录操作。

        子类必须实现具体的登录逻辑。

        Returns:
            bool: 登录是否成功
        """
        pass

    @abstractmethod
    async def ensure_ready(self) -> bool:
        """
        确保机器人就绪可用。
        Returns:
            bool: 机器人是否就绪，True表示就绪
        """
        pass

    # ==================== 可选重写方法（子类可按需重写） ====================

    async def initialize(self) -> None:
        """
        初始化机器人。

        子类可重写以执行特定的初始化逻辑。
        """
        pass

    async def cleanup(self) -> None:
        """
        清理机器人资源。

        子类可重写以添加额外的清理逻辑。
        """
        pass

    # ==================== 公共方法（可直接使用） ====================

    async def pre_send_hook(
        self,
        message: str,
        files: Optional[List[str]] = None,
        dirs: Optional[str] = None,
    ) -> None:
        pass

    async def post_send_hook(self) -> None:
        pass

    async def send_message(
        self,
        message: str,
        files: Optional[List[str]] = None,
        dirs: Optional[str] = None,
    ) -> str:
        """
        发送消息到聊天界面。

        Args:
            message: 要发送的文本消息
            files: 要上传的文件路径列表，默认为None

        Returns:
            str: 接收到的响应文本

        Raises:
            ValueError: 机器人未就绪时抛出
        """
        logger.debug(f"Webot发送消息：{message}")
        # 确保机器人就绪
        if not await self.ensure_ready():
            raise ValueError("机器人未就绪，无法发送消息")

        # 由具体AI机器人子类实现
        await self.pre_send_hook(message=message, files=files, dirs=dirs)

        # 导航到聊天页面
        await self._ensure_chat_page()

        # 清除输入框（如果有旧文本，可选）
        input_selector = self.config.selectors.get("message_input")
        if input_selector:
            try:
                await self.browser.fill(input_selector, "")
            except:
                pass

        # 处理文件上传
        if files:
            await self._upload_files(files)
        # 处理目录上传
        if dirs:
            await self._upload_directory(dirs)

        # 输入消息
        input_selector = self.config.selectors.get("message_input")
        if input_selector:
            # await self.browser.fill(input_selector, message)
            await self.browser.type(input_selector, message)

        # print("Webot使用回车键发送...")
        print("Webot发送消息...")
        await self.browser.page.keyboard.press("Enter")

        # 等待并获取响应
        print("Webot等待AI生成响应...")
        response = await self._wait_for_response()
        # print("Webot接收AI已生成的响应")

        # 由具体AI机器人子类实现
        await self.post_send_hook()

        self.markdown_content = await self._read_copybutton_response()
        await self.save_markdown_response(response)
        if self.markdown_content:
            return self.markdown_content

        return response

    # ==================== 历史记录管理 ====================

    async def get_conversation_history(self, limit: int = 10) -> List[str]:
        """
        获取对话历史记录。

        Args:
            limit: 返回的记录数量限制，默认为10

        Returns:
            List[Dict[str, Any]]: 历史记录列表
        """
        history_dir = self.output_dir / "history"
        history_dir.mkdir(exist_ok=True)

        print("Webot查找历史记录...")

        history_selectors = ['a[href*="/chat/"]']

        history = []
        for selector in history_selectors:
            try:
                items = await self.browser.page.query_selector_all(selector)
                print(f"查找到{len(items)}个历史记录")
                for item in items:  # 限制数量
                    if await item.is_visible():
                        text = await item.inner_text()
                        print(f"text: {text}")
                        if text and len(text) > 1:
                            history.append(text)
            except Exception as e:
                print(f"查找历史记录失败，捕获异常{e}")
                continue

        return history

    async def save_markdown_response(self, response: str) -> Optional[str]:
        """保存Markdown格式的AI回复到文件。

        Args:
            response: AI回复的Markdown格式文本

        Returns:
            str: 文件名
        """

        if not response:
            return ""

        content = self.markdown_content or response
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if not self.config.output_dir:
            self.config.output_dir = f"output/{self.config.name}"

        Path(self.config.output_dir).mkdir(exist_ok=True, parents=True)

        # 生成新的文件名
        filename = f"{self.config.name}_response_{timestamp}.md"
        full_name = Path(self.config.output_dir) / filename

        with open(full_name, "w", encoding="utf-8") as f:
            f.write(f"# DeepSeek AI 回复\n\n")
            f.write(f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**长度**: {len(content)} 字符\n\n")
            f.write("---\n\n")
            f.write(content)

        print(f"已保存: {filename}")
        return str(filename)

    # ==================== 辅助方法（内部使用） ====================

    async def _ensure_chat_page(self) -> None:
        """
        确保当前在聊天页面。
        """
        current_url = self.browser.page.url
        chat_url = self.config.chat_url

        if not current_url.startswith(chat_url):
            await self.browser.goto(chat_url)
            await self.browser.page.wait_for_load_state("networkidle")

    async def _check_chat_available(self) -> bool:
        """
        检查聊天界面是否可用。

        Returns:
            bool: 聊天界面是否可用
        """
        try:
            await self._ensure_chat_page()

            # 检查关键元素是否存在
            input_selectors = [
                self.config.selectors.get("message_input"),
                "textarea",
                'input[type="text"]',
            ]

            for selector in input_selectors:
                if selector:
                    try:
                        await self.browser.wait_for_selector(selector, timeout=3000)
                        return True
                    except Exception:
                        continue

            # 页面已加载但未找到输入框
            await asyncio.sleep(1)
            return True

        except Exception:
            return False

    async def _upload_files(self, files: List[str]) -> List[str]:
        """
        上传文件到聊天界面。

        Args:
            files: 文件路径列表

        Returns:
            List[str]: 成功上传的文件列表
        """
        upload_selector = self.config.selectors.get("file_upload")
        if not upload_selector:
            logger.debug("未配置文件上传选择器，跳过文件上传")
            return []

        uploaded_files = []
        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                logger.debug(f"文件不存在: {file_path}")
                continue
            if not path.is_file():
                logger.debug(f"不是有效的文件: {file_path}")
                continue

            try:
                # 上传文件
                await self.browser.upload_single_file(upload_selector, file_path)
                uploaded_files.append(file_path)
                logger.debug(f"已上传文件: {file_path}")

                # 等待文件上传处理
                await asyncio.sleep(2)

                # 检查文件是否出现在页面中(简化)
                file_name = path.name
                try:
                    # 尝试查找包含文件名的元素
                    file_element = await self.browser.page.query_selector(
                        f':has-text("{file_name}")'
                    )
                    if file_element:
                        is_visible = await file_element.is_visible()
                        if is_visible:
                            logger.debug(f"文件 {file_name} 确认已上传")
                    else:
                        # 备选检查：检查上传相关元素
                        upload_elements = [
                            '[class*="file"]',
                            '[class*="attachment"]',
                            '[class*="upload"]',
                        ]

                        for element_selector in upload_elements:
                            element = await self.browser.page.query_selector(
                                element_selector
                            )
                            if element:
                                is_visible = await element.is_visible()
                                if is_visible:
                                    logger.debug(
                                        f"通过 {element_selector} 确认文件已上传"
                                    )
                                    break
                        else:
                            logger.warning(
                                f"无法确认文件 {file_name} 是否上传成功，但已发送上传指令"
                            )
                except Exception as e:
                    logger.warning(f"⚠ 文件确认检查出错: {e}")
                    # 即使确认失败，也认为上传成功，因为上传操作本身成功了

                # 文件间等待
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"上传文件失败 {file_path}: {e}")

        return uploaded_files

    async def _wait_for_response(self) -> str:
        """
        等待AI生成响应完成。
        需要在子类中实现

        Returns:
            str: 响应文本
        """
        logger.debug("Webot - 等待AI生成响应...")
        return ""

    async def _read_copybutton_response(self) -> str:
        """
        读取复制按钮的响应内容。

        Returns:
            str: 响应文本内容
        """
        return ""

    async def _read_clipboard(self) -> str:
        """
        读取剪贴板内容。

        Returns:
            str: 剪贴板内容字符串，读取失败返回空字符串
        """
        try:
            clipboard_content = await self.browser.page.evaluate(
                """
                async () => {
                    try {
                        const text = await navigator.clipboard.readText();
                        return text;
                    } catch (err) {
                        // 如果权限被拒绝，尝试其他方法
                        console.log('剪贴板读取失败:', err);
                        return null;
                    }
                }
            """
            )

            if clipboard_content:
                return clipboard_content
            else:
                logger.debug("无法读取剪贴板内容，返回缓存的响应")
            return ""
        except Exception as e:
            logger.debug(f"读取剪贴板失败: {e}")
        return ""

    def _format_size(self, size_bytes: float) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    async def _create_directory_structure(
        self,
        directory: Path,
        output_file: Optional[str] = None,
        exclude_dirs: Optional[set] = None,  # set = None,
        exclude_exts: Optional[set] = None,  # set = None,
    ) -> str:
        """
        创建目录结构说明文件。

        Args:
            directory: 目录路径
            output_file: 输出文件
            exclude_dirs: 要排除的目录名集合
            exclude_exts: 要排除的文件扩展名集合

        Returns:
            Optional[str]: 生成的文件路径清单
        """

        if output_file is None:
            output_file = "directory_structure.md"

        exclude_dirs = exclude_dirs or self.exclude_dirs
        exclude_exts = exclude_exts or self.exclude_exts

        root = Path(directory).resolve()

        file_list = []

        if not root.exists() or not root.is_dir():
            logger.error(f"错误: 目录不存在或不是目录: {root}")
            return ""

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                # 写入头部
                f.write("=" * 60 + "\n")
                f.write(f"目录结构: {root}\n")
                f.write(f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
                f.write("=" * 60 + "\n\n")

                # 写入目录树
                f.write("目录结构:\n")
                f.write(".\n")

                def write_tree(folder: Path, prefix: str = "", is_last: bool = True):
                    items = sorted(
                        folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
                    )

                    for i, item in enumerate(items):
                        item_is_last = i == len(items) - 1

                        # 排除目录
                        if item.is_dir() and item.name in exclude_dirs:
                            continue

                        connector = "└── " if item_is_last else "├── "

                        if item.is_dir():
                            f.write(f"{prefix}{connector}{item.name}/\n")
                            new_prefix = prefix + ("    " if item_is_last else "│   ")
                            write_tree(item, new_prefix, item_is_last)
                        else:
                            # 排除文件扩展名
                            if item.suffix.lower() in exclude_exts:
                                continue
                            f.write(f"{prefix}{connector}{item.name}\n")

                write_tree(root)

                f.write("\n" + "-" * 60 + "\n\n")

                # 写入文件清单
                f.write("文件绝对路径:\n")
                file_count = 0
                total_size = 0
                for current_dir, dirs, files in os.walk(root):
                    # 排除目录
                    dirs[:] = [d for d in dirs if d not in exclude_dirs]

                    for file in files:
                        file_path = Path(current_dir) / file
                        if file_path.suffix.lower() in exclude_exts:
                            continue

                        f.write(f"{file_path}\n")
                        file_list.append(f"{file_path}")  # 添加文件路径到清单file_path)
                        file_count += 1

                        try:
                            total_size += file_path.stat().st_size
                        except:
                            pass

                # 写入统计信息
                f.write("\n" + "=" * 60 + "\n")
                f.write(f"统计:\n")
                f.write(f"  文件数量: {file_count}\n")
                f.write(f"  总大小: {self._format_size(total_size)}\n")
                f.write("=" * 60 + "\n")

            logger.debug(f"✓ 已保存到: {output_file}")
            logger.debug(
                f"✓ 共 {file_count} 个文件，总大小 {self._format_size(total_size)}"
            )
            return output_file

        except Exception as e:
            logger.error(f"错误: {e}")
            return ""

    async def _upload_directory(self, directory_path: str) -> List[str]:
        """
        上传目录下所有文件。

        Args:
            directory_path: 目录路径

        Returns:
            List[str]: 成功上传的文件列表

        Raises:
            FileNotFoundError: 目录不存在时抛出
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")
        if not directory.is_dir():
            raise ValueError(f"路径不是目录: {directory_path}")

        # 获取目录下所有文件
        files = [
            str(f)
            for f in directory.rglob("*")
            if f.is_file()
            and f.suffix not in self.exclude_exts
            and f.name not in self.exclude_exts
            and not any(excluded in f.parts for excluded in self.exclude_dirs)
        ]

        print(files)

        if not files:
            print(f"目录 {directory_path} 中没有文件")
            return []

        print(f"发现 {len(files)} 个文件，准备上传...")

        # 生成目录结构说明文件
        structure_file = await self._create_directory_structure(directory)
        if structure_file:
            files.insert(0, structure_file)

        # 上传文件
        return await self._upload_files(files)
