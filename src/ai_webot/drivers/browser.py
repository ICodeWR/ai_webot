#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器驱动封装模块。

提供Playwright浏览器的驱动封装，包括浏览器启动、状态管理、
元素操作和文件上传等功能。

模块名称：browser.py
功能描述：Playwright浏览器驱动封装G
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from ai_webot.services import BotConfig, FileError

# 创建日志器
logger = logging.getLogger(__name__)


class BrowserError(Exception):
    """
    浏览器基础异常类。

    Attributes:
        message (str): 错误描述信息。
        context (dict): 错误发生的上下文信息。
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化浏览器异常。

        Args:
            message: 错误描述信息。
            context: 错误发生的上下文信息。
        """
        self.message = message
        self.context: Dict[str, Any] = context or {}
        super().__init__(self.message)
        logger.error(f"浏览器异常: {message} - Context: {context}")

    def __str__(self) -> str:
        """
        返回错误信息的字符串表示。

        Returns:
            错误描述字符串。
        """
        if self.context:
            details = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.__class__.__name__}: {self.message} [{details}]"
        return f"{self.__class__.__name__}: {self.message}"


class BrowserDriver:
    """
    浏览器驱动类。

    封装了Playwright浏览器的基本操作，包括启动、关闭、
    页面导航、元素操作和文件上传等功能。

    Attributes:
        config (BotConfig): 机器人配置对象。
        headless (bool): 是否以无头模式运行浏览器。
        _playwright (Optional[Playwright]): Playwright实例。
        _browser (Optional[Browser]): 浏览器实例。
        _context (Optional[BrowserContext]): 浏览器上下文。
        _page (Optional[Page]): 当前页面对象。
    """

    # 默认User-Agent字符串
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, config: BotConfig) -> None:
        """
        初始化浏览器驱动。

        Args:
            config: 机器人配置对象，包含浏览器设置。
        """
        self.config = config
        self.headless = config.headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        logger.info(f"浏览器初始化：{config.name}")

    async def start(self, bot_name: str, save_login_state: bool = True) -> None:
        """
        启动浏览器。

        Args:
            bot_name: 机器人名称，用于状态文件管理。
            save_login_state: 是否保存登录状态，默认为True。

        Raises:
            BrowserError: 启动浏览器失败时抛出。
        """
        try:
            # 1. 启动 Playwright
            logger.debug("启动 Playwright")
            self._playwright = await async_playwright().start()

            # 2. 启动浏览器
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--disable-popup-blocking",
                "--disable-notifications",
            ]

            logger.debug(
                f"启动浏览器，加载参数: headless={self.headless}, args={launch_args}"
            )
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
            )

            # 3. 验证浏览器是否成功启动
            if self._browser is None:
                logger.error("浏览器加载出错: 返回值为 None")
                raise BrowserError("浏览器启动失败：返回值为 None")

            logger.debug("浏览器启动完成，加载浏览器上下文")

            # 4. 加载或创建浏览器上下文
            self._context = await self._load_or_create_context(
                bot_name, save_login_state
            )

            # 5. 创建页面并添加初始化脚本
            self._page = await self._context.new_page()

            init_script = self.config.browser.init_script
            if init_script:
                await self._page.add_init_script(init_script)
                logger.debug("初始化脚本加载结束")

            logger.info("浏览器启动成功")

        except Exception as e:
            # 启动失败时清理已分配的资源
            await self._cleanup_on_error()
            logger.exception(f"启动浏览器失败: {e}")
            # 重新抛出异常，让调用者处理
            raise BrowserError(f"启动浏览器失败: {e}") from e

    async def _load_or_create_context(
        self, bot_name: str, save_login_state: bool
    ) -> BrowserContext:
        """
        加载现有状态或创建新的浏览器上下文。

        此方法处理状态文件的加载逻辑，如果状态文件加载失败，会创建新上下文。
        但如果浏览器本身有问题，会直接抛出异常。

        Args:
            bot_name: 机器人名称，用于构建状态文件路径。
            save_login_state: 是否保存登录状态。

        Returns:
            BrowserContext: 浏览器上下文对象。

        Raises:
            BrowserError: 如果浏览器未启动或已断开连接。
            FileError: 如果状态文件存在但无法读取（权限问题等）。
            Exception: 其他未预期的异常。
        """
        state_path = Path("browser_states") / f"{bot_name}_state.json"

        # 配置为不保存登录状态，则直接创建新的上下文
        if not save_login_state:
            logger.info("不保存登录状态，创建新的浏览器上下文")
            return await self._create_context()

        # 状态文件不存在，则直接创建新的上下文
        if not state_path.exists():
            logger.info("状态文件不存在，创建新的浏览器上下文")
            return await self._create_context()

        # 在读取文件前，快速检查浏览器状态，避免在浏览器异常时还尝试读取文件
        if self._browser is None:
            logger.error("浏览器未启动，无法加载状态")
            raise BrowserError("浏览器未启动，无法加载状态")

        try:
            if not self._browser.is_connected():
                logger.error("浏览器已断开连接，无法加载状态")
                raise BrowserError("浏览器已断开连接，无法加载状态")
        except Exception as e:
            logger.error(f"浏览器状态异常: {e}")
            raise BrowserError(f"浏览器状态异常: {e}")

        # 浏览器正常，尝试加载状态文件
        try:
            content = state_path.read_text(encoding="utf-8")
            storage_state = json.loads(content)

            if not isinstance(storage_state, dict):
                logger.warning("状态文件无效，创建新的上下文")
                return await self._create_context()

            logger.info("状态文件加载成功，创建上下文中...")
            return await self._create_context(storage_state)

        except (json.JSONDecodeError, FileNotFoundError) as e:
            # JSON错误：不影响浏览器，可以创建新上下文
            logger.warning(f"无法解析状态文件，创建新的上下文: {e}")
            return await self._create_context()

        except PermissionError as e:
            # 权限错误：提示，然后继续创建新的上下文
            logger.warning(f"无法读取状态文件，创建新的上下文: {e}")
            return await self._create_context()

        except UnicodeDecodeError as e:
            # 编码错误：文件损坏或格式不对，提示，然后继续创建新的上下文
            logger.warning(f"无法读取状态文件，创建新的上下文: {e}")
            return await self._create_context()

        # 不捕获其他异常，包括可能的浏览器异常，调用者需自己处理

    async def _create_context(
        self, storage_state: Optional[Dict[str, Any]] = None
    ) -> BrowserContext:
        """
        创建浏览器上下文（使用配置中的浏览器设置）。

        如果浏览器未启动或已断开连接，此方法会抛出 BrowserError。

        Args:
            storage_state: 存储状态，用于恢复登录状态。如果为 None，则创建新上下文。

        Returns:
            BrowserContext: 浏览器上下文对象。

        Raises:
            BrowserError: 如果浏览器未启动、已断开连接或创建上下文失败。
        """
        # === 浏览器状态验证===
        if self._browser is None:
            logger.error("浏览器未启动，无法创建上下文")
            raise BrowserError("浏览器未启动，无法创建上下文")

        try:
            if not self._browser.is_connected():
                logger.error("浏览器已断开连接，无法创建上下文")
                raise BrowserError("浏览器已断开连接，无法创建上下文")
        except Exception as e:
            # 如果 is_connected() 抛出异常，说明浏览器状态异常
            logger.error(f"浏览器状态异常: {e}")
            raise BrowserError(f"浏览器状态异常: {e}")

        # 验证浏览器配置
        if not self.config.browser:
            logger.error("浏览器配置不存在")
            raise BrowserError("浏览器配置不存在")

        # 处理 User-Agent
        user_agent = self.config.browser.user_agent
        if user_agent:
            # 清理多余的空白字符
            user_agent = re.sub(r"\s+", " ", user_agent).strip()
            if not user_agent:
                # 清理后为空字符串，使用默认值
                user_agent = self.DEFAULT_USER_AGENT
                logger.warning("Browser User-Agent为空，使用默认值")
        else:
            # 未设置 User-Agent，使用默认值
            user_agent = self.DEFAULT_USER_AGENT
            logger.warning("Browser User-Agent未设置，使用默认值")

        logger.debug(f"Using User-Agent: {user_agent[:50]}...")

        # 构建上下文参数
        context_args: Dict[str, Any] = {
            "user_agent": user_agent,
            "locale": self.config.browser.locale or "en-US",
            "timezone_id": self.config.browser.timezone or "UTC",
            "no_viewport": True,  # 使用无 viewport 模式，允许自适应
            "permissions": ["clipboard-read", "clipboard-write"],
        }

        # 添加地理位置信息
        if self.config.browser.geolocation:
            context_args["geolocation"] = self.config.browser.geolocation
            logger.debug(f"geolocation: {self.config.browser.geolocation}")

        # 添加权限
        if self.config.browser.permissions:
            context_args["permissions"] = self.config.browser.permissions
            logger.debug(f"permissions: {self.config.browser.permissions}")

        # 添加存储状态
        if storage_state:
            context_args["storage_state"] = storage_state
            logger.debug(f"从状态文件中恢复登录状态： ({len(storage_state)} keys)")

        # 创建上下文
        try:
            return await self._browser.new_context(**context_args)
        except Exception as e:
            # 捕获创建上下文时的所有异常
            error_context = {
                "has_storage_state": storage_state is not None,
                "user_agent_set": bool(self.config.browser.user_agent),
                "locale": self.config.browser.locale,
                "timezone": self.config.browser.timezone,
            }
            raise BrowserError(f"创建浏览器上下文失败: {e}", error_context)

    async def _cleanup_on_error(self) -> None:
        """
        在启动失败时清理已分配的资源。

        此方法在start()方法发生异常时调用，确保不会泄露资源。
        """
        try:
            if self._context:
                await self._context.close()
                self._context = None
        except Exception:
            pass  # 忽略清理时的错误

        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception:
            pass

    async def save_state(self, bot_name: str) -> None:
        """
        保存浏览器状态。

        Args:
            bot_name: 机器人名称，用于生成状态文件名。

        Raises:
            BrowserError: 保存状态失败时抛出。
        """
        if not self._context:
            print("警告：浏览器上下文不存在，无法保存状态")
            return

        try:
            storage_state = await self._context.storage_state()
            state_path = Path("browser_states") / f"{bot_name}_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(storage_state, indent=2), encoding="utf-8")
            print(f"浏览器状态已保存到: {state_path}")
        except Exception as e:
            raise BrowserError(f"保存浏览器状态失败: {e}")

    async def close(self, bot_name: str, save_login_state: bool = True) -> None:
        """
        关闭浏览器。

        Args:
            bot_name: 机器人名称。
            save_login_state: 是否保存登录状态，默认为True。
        """
        try:
            if save_login_state and self._context:
                await self.save_state(bot_name)
        except Exception as e:
            logger.warning(f"保存浏览器状态错误: {e}")

        try:
            if self._context:
                await self._context.close()
                self._context = None
        except Exception as e:
            logger.warning(f"关闭浏览器上下文错误: {e}")

        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception as e:
            logger.warning(f"关闭浏览器错误: {e}")

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            print(f"警告: 停止Playwright时出错: {e}")

    @property
    def page(self) -> Page:
        """
        获取当前页面对象。

        Returns:
            当前页面对象。

        Raises:
            BrowserError: 浏览器未启动时抛出。
        """
        if self._page is None:
            raise BrowserError("浏览器未启动")
        return self._page

    # ================ 基本操作方法 ================

    async def goto(self, url: str) -> None:
        """
        导航到指定URL。

        Args:
            url: 目标URL。
        """
        await self.page.goto(url)

    async def fill(self, selector: str, text: str) -> None:
        """
        在指定元素中输入文本。

        Args:
            selector: CSS选择器。
            text: 要输入的文本。
        """
        await self.page.fill(selector, text)

    async def type(self, selector: str, text: str, delay: int = 0) -> None:
        """
        在指定元素中输入文本（模拟键盘输入）。

        Args:
            selector: CSS选择器。
            text: 要输入的文本。
        """
        await self.page.type(selector, text, delay=delay)

    async def click(self, selector: str) -> None:
        """
        点击指定元素。

        Args:
            selector: CSS选择器。
        """
        await self.page.click(selector)

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        """
        等待元素出现。

        Args:
            selector: CSS选择器。
            timeout: 超时时间（毫秒），默认5000ms。

        Raises:
            BrowserTimeoutError: 等待超时时抛出。
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            raise BrowserError(
                f"等待元素超时: {selector}", {"selector": selector, "timeout": timeout}
            )

    async def wait_for_url(self, url: str, timeout: int = 30000) -> None:
        """
        等待URL变为指定值。

        Args:
            url: 目标URL。
            timeout: 超时时间（毫秒），默认30000ms。

        Raises:
            BrowserTimeoutError: 等待超时时抛出。
        """
        try:
            await self.page.wait_for_url(url, timeout=timeout)
        except Exception as e:
            raise BrowserError(f"等待URL超时: {url}", {"url": url, "timeout": timeout})

    # ================ 文件上传方法 ================

    async def upload_files(self, selector: str, files: List[str]) -> bool:
        """
        上传文件到指定文件输入框。

        Args:
            selector: 文件上传输入框的CSS选择器。
            files: 文件路径列表。

        Returns:
            bool: 上传是否成功

        Raises:
            FileError: 文件不存在或无效时抛出。
            UploadError: 上传文件失败时抛出。
        """
        if not files:
            return True

        # 验证文件是否存在
        file_paths: List[str] = []
        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                raise FileError(f"文件不存在: {file_path}")
            if not path.is_file():
                raise FileError(f"不是有效的文件: {file_path}")
            file_paths.append(str(path))

        try:
            # 使用locator确保选择器存在
            file_input = self.page.locator(selector)
            await file_input.wait_for(state="attached", timeout=5000)

            # 设置文件
            logger.debug(f"添加文件: {file_paths}")
            await file_input.set_input_files(file_paths)

            # 等待文件上传完成
            await self.page.wait_for_timeout(1000)
            logger.info(f"上传 {len(files)} 文件")
            return True

        except Exception as e:
            logger.exception(f"上传文件失败: {e}")
            raise FileError(f"上传文件失败: {e}", selector=selector)

    async def upload_single_file(self, selector: str, file_path: str) -> bool:
        """
        上传单个文件。

        Args:
            selector: 文件上传输入框的CSS选择器。
            file_path: 文件路径。

        Returns:
            bool: 上传是否成功
        """
        try:
            await self.upload_files(selector, [file_path])
            return True
        except Exception as e:
            logger.error(f"上传单个文件失败: {e}")
            return False
