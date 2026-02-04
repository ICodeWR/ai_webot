#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通义千问机器人实现模块。

实现通义千问Web机器人的具体功能，支持游客模式和多种登录方式。

模块名称：bot.py
功能描述：通义千问机器人实现
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import List, Optional

from ai_webot.webot.base.web_bot import WebBot

# 获取模块日志器
logger = logging.getLogger(__name__)


class QianWenBot(WebBot):
    """
    通义千问机器人。

    支持游客模式直接使用，也支持密码登录和扫码登录。
    """

    send_msg_str: str = ""
    markdonw_text = None
    dropdown_button_num = 0

    def requires_login(self) -> bool:
        """
        判断是否需要登录。

        通义千问可以游客模式使用，登录不是必须的。

        Returns:
            bool: 总是返回False
        """
        return False

    async def login(self) -> bool:
        """
        执行通义千问登录。

        支持密码登录和扫码登录两种方式。

        Returns:
            bool: 登录是否成功（游客模式也返回True）
        """
        # 检查是否已登录
        logger.debug(f"\n=== 通义千问登录 ({self.config.name}) ===")
        print("通义千问支持游客模式，请手动登录使用")

        try:
            # 尝试游客模式
            if await self._check_chat_available():
                print("通义千问游客模式")
                return True

            # 游客模式不可用，尝试登录
            print("导航到千问登录页面...")

            await self.browser.goto(self.config.login_url)
            await self.browser.page.wait_for_load_state("networkidle")

            return True

        except Exception as e:
            print(f"通义千问登录过程出错: {e}")
            return False

    async def ensure_ready(self) -> bool:
        """
        确保通义千问机器人就绪。

        优先尝试游客模式，失败则尝试登录。

        Returns:
            bool: 机器人是否就绪
        """
        if self.is_ready:
            return True

        # 优先尝试游客模式
        chat_url = self.config.chat_url
        await self.browser.goto(chat_url)
        await asyncio.sleep(1)
        current_url = self.browser.page.url
        if not current_url.startswith(chat_url):
            await self.browser.goto(chat_url)
            await self.browser.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

        try:
            message_input = self.config.selectors.get("message_input")
            if not message_input:
                message_input = 'role=textbox[name="向千问提问"i]'
            await self.browser.wait_for_selector(message_input, timeout=3000)

            self.is_ready = True
            return True
        except Exception:
            logger.error("通义千问机器人就绪失败")
            return False

    async def pre_send_hook(
        self,
        message: str,
        files: Optional[List[str]] = None,
        dirs: Optional[str] = None,
    ) -> None:
        self.send_msg_str = message
        return None

    async def check_has_stop_button(self, page):
        """
        检查页面上是否有停止按钮。

        Returns:
            bool: True表示有停止按钮（AI正在响应），False表示没有停止按钮
        """
        try:
            stop_selectors = [
                'div[class*="stop"]',
            ]

            for selector in stop_selectors:
                elements = await page.locator(selector).all()
                if elements:
                    # 检查是否可见
                    for element in elements:
                        if await element.is_visible():
                            logger.debug(f"找到可见的停止按钮: {selector}")
                            return True
            logger.debug("没有找到可见的停止按钮")
            return False

        except Exception as e:
            logger.debug(f"检查停止按钮时出错: {e}")
            return False

    async def check_has_ai_response_content(self, page, timeout: int = 1000) -> bool:
        """
        检查页面是否有AI响应内容出现。

        Args:
            page: 页面对象
            timeout: 检查超时时间（毫秒）

        Returns:
            bool: 是否有AI响应内容
        """
        try:
            # AI响应内容的常见选择器
            ai_content_selectors = [
                '[class*="answer"]',
                '[class*="response"]',
                '[class*="ai-message"]',
                '[class*="bot-message"]',
                '[class*="markdown"]',
                '[class*="prose"]',
            ]

            for selector in ai_content_selectors:
                try:
                    element = await page.wait_for_selector(
                        selector, timeout=timeout, state="attached"
                    )
                    if element and await element.is_visible():
                        text = await element.text_content()
                        if text and len(text.strip()) > 0:
                            logger.debug(f"检测到AI响应内容: {text[:50]}...")
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.debug(f"检查AI响应内容时出错: {e}")
            return False

    async def _wait_for_response(self) -> str:
        """
        等待千问生成响应完成，并返回成功状态。

        流程：
        1. 发送消息后，等待停止按钮出现（AI开始响应）
        2. AI响应过程中，停止按钮保持存在
        3. AI响应完成后，停止按钮消失
        4. 最后等待下拉按钮出现，获取Markdown格式内容

        Returns:
            str: 响应文本(Markdown格式)
        """

        logger.debug("等待千问生成响应...")

        # 1. 等待用户消息出现
        safe_prefix = re.escape(
            self.send_msg_str[: min(20, len(self.send_msg_str)) or 1]
        )
        user_msg_locator = (
            self.browser.page.locator("div")
            .filter(has_text=re.compile(rf"^{safe_prefix}"))
            .first
        )
        await user_msg_locator.wait_for(state="visible", timeout=10000)

        # 2. 等待AI开始响应（等待停止按钮出现）
        logger.debug("等待AI开始响应（等待停止按钮出现）...")
        start_time = time.time()
        max_start_wait = 30  # 最多等待30秒开始响应

        while time.time() - start_time < max_start_wait:
            has_stop_button = await self.check_has_stop_button(self.browser.page)
            has_ai_content = await self.check_has_ai_response_content(
                self.browser.page, timeout=500
            )

            # 两种情况表示AI开始响应：
            # 1. 有停止按钮（AI正在生成）
            # 2. 有AI响应内容（可能是极短响应，已快速完成）
            if has_stop_button or has_ai_content:
                if has_stop_button:
                    logger.debug("检测到停止按钮，AI开始响应")
                else:
                    logger.debug("检测到AI响应内容（可能是极短响应）")
                break

            await asyncio.sleep(0.5)
        else:
            logger.warning(f"超时：{max_start_wait}秒内未检测到AI开始响应")
            # 即使超时也继续，可能是界面变化或响应异常

        # 3. 等待AI响应完成（等待停止按钮消失）
        logger.debug("等待AI响应完成（等待停止按钮消失）...")
        response_start_time = time.time()
        max_response_wait = 30 * 60  # 最多等待30分钟完成响应

        while time.time() - response_start_time < max_response_wait:
            has_stop_button = await self.check_has_stop_button(self.browser.page)

            if not has_stop_button:
                # 停止按钮消失，表示AI响应可能完成
                # 验证是否有AI响应内容
                if await self.check_has_ai_response_content(
                    self.browser.page, timeout=1000
                ):
                    logger.debug("停止按钮消失且有AI响应内容，AI响应完成")
                    break
                else:
                    logger.debug("停止按钮消失但无AI内容，可能界面异常，继续等待")

            # 显示等待进度
            elapsed = time.time() - response_start_time
            if int(elapsed) % 5 == 0 and elapsed > 0:
                print(".", end="", flush=True)

            await asyncio.sleep(0.5)
        else:
            logger.warning(f"超时：{max_response_wait}秒内AI响应未完成")

        # 4. 下拉按钮选择器
        dropdown_btn = self.browser.page.locator(
            'button:has(span[data-icon-type="qwpcicon-down"])'
        ).last

        # 5. 等待下拉按钮出现
        logger.debug("等待下拉按钮出现...")
        max_wait_minutes = 2
        total_checks = max_wait_minutes * 60

        for i in range(total_checks):
            await self.browser.page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await asyncio.sleep(0.5)

            try:
                if await dropdown_btn.is_visible() and await dropdown_btn.is_enabled():
                    bounding_box = await dropdown_btn.bounding_box()
                    if (
                        bounding_box
                        and bounding_box["width"] > 0
                        and bounding_box["height"] > 0
                    ):
                        logger.debug("下拉按钮已出现")
                        break
            except Exception as e:
                logger.debug(f"检查下拉按钮时出错: {e}")

            if i % 5 == 0:
                print(".", end="", flush=True)

            await asyncio.sleep(1)
        else:
            logger.error(f"超时：{max_wait_minutes} 分钟内未检测到下拉按钮")
            return ""

        # 6. 点击下拉按钮
        try:
            await dropdown_btn.scroll_into_view_if_needed()
            await dropdown_btn.click(timeout=10000)
        except Exception as e:
            logger.error(f"点击下拉按钮失败: {e}")
            return ""

        # 7. 查找并点击复制菜单项
        copy_menu_item = None
        for selector in [
            lambda: self.browser.page.get_by_role(
                "menuitem", name="复制为Markdown"
            ).last,
            lambda: self.browser.page.get_by_role(
                "menuitem", name="复制", exact=True
            ).last,
        ]:
            try:
                candidate = selector()
                await candidate.wait_for(state="visible", timeout=3000)
                copy_menu_item = candidate
                break
            except:
                continue

        if copy_menu_item:
            logger.debug("检测到'复制为Markdown'菜单项")
            await copy_menu_item.click()
            await self.browser.page.wait_for_timeout(500)
            logger.debug("已点击'复制为Markdown'菜单项")

            # 8. 从剪贴板读取内容
            clipboard_content = await self._read_clipboard()
            if clipboard_content:
                self.markdonw_text = clipboard_content
                return clipboard_content
        else:
            logger.warning("未找到'复制为Markdown'菜单项，返回空字符串")

        return ""

    async def _read_copybutton_response(self) -> str:
        """复制Markdown格式的AI响应到剪贴板。

        直接返回self.markdonw_text
        Returns:
            str: 从剪贴板复制的Markdown格式内容
        """
        return self.markdonw_text if self.markdonw_text else ""

    async def _upload_files(self, files: List[str]) -> List[str]:
        """
        上传文件到聊天界面。

        Args:
            files: 文件路径列表

        Returns:
            List[str]: 成功上传的文件列表
        """

        # 定义文档类 and 图片类扩展名
        DOC_EXTENSIONS = {
            "txt",
            "pdf",
            "doc",
            "docx",
            "md",
            "markdown",
            "epub",
            "mobi",
            "xlsx",
            "xls",
            "csv",
            "ppt",
            "pptx",
            "html",
            "htm",
            "json",
            "yaml",
            "yml",
            "ipynb",
            "py",
            "js",
            "ts",
            "java",
            "cpp",
            "c",
            "sql",
            "xml",
            "log",
            "r",
            "jl",
            "toml",
            "env",
            "gitignore",
        }
        IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp"}

        file_input_txt = (
            'input[type="file"][accept*=".txt"], input[type="file"][accept*=".pdf"]'
        )

        print(f"file_input_txt: {file_input_txt}")

        file_input_img = (
            'input[type="file"][accept*=".jpg"], input[type="file"][accept*=".png"]'
        )

        print(f"file_input_img: {file_input_img}")

        if not file_input_txt and not file_input_img:
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
                file_ext = path.suffix.lower().lstrip(".")
                if file_ext in DOC_EXTENSIONS:
                    logger.debug(f"识别为文档文件 ({file_ext})，使用文档上传通道")
                    await self.browser.upload_single_file(file_input_txt, file_path)
                elif file_ext in IMAGE_EXTENSIONS:
                    logger.debug(f"识别为图片文件 ({file_ext})，使用图片上传通道")
                    await self.browser.upload_single_file(file_input_img, file_path)
                else:
                    logger.debug(f"未知文件类型 {file_ext}，使用默认上传通道（文档）")
                    await self.browser.upload_single_file(file_input_txt, file_path)
                uploaded_files.append(file_path)
                logger.debug(f"已上传文件: {file_path}")

                # 等待文件上传处理
                await asyncio.sleep(3)

                # 检查文件是否出现在页面中
                file_name = path.name
                try:
                    file_element = await self.browser.page.query_selector(
                        f':has-text("{file_name}")'
                    )
                    if file_element:
                        is_visible = await file_element.is_visible()
                        if is_visible:
                            logger.debug(f"文件 {file_name} 确认已上传")
                    else:
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
                    logger.warning(f"文件确认检查出错: {e}")

                # 文件间等待
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"上传文件失败 {file_path}: {e}")

        return uploaded_files
