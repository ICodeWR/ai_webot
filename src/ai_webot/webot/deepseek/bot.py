#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek机器人实现模块。

实现DeepSeek Web机器人的具体功能。

模块名称：bot.py
功能描述：DeepSeek机器人实现
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import asyncio
import logging
import time
from typing import List, Optional

from ai_webot.webot.base.web_bot import WebBot

logger = logging.getLogger(__name__)


class DeepSeekBot(WebBot):
    """DeepSeek机器人。
    DeepSeek平台必须登录后才能使用。
    """

    def __init__(self, config):
        """初始化DeepSeek机器人"""
        super().__init__(config)
        self.last_response_text = ""  # 上一次的完整响应文本（用于增量比对）
        # 反检测脚本
        self.config.browser.init_script = """
            // 覆盖webdriver属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // 覆盖chrome属性
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // 添加plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 添加languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            """

    # ==================== 抽象方法（必须由子类实现） ====================

    def requires_login(self) -> bool:
        """判断是否需要登录。
        DeepSeek必须登录后才能使用。
        Returns:
            bool: 总是返回 True
        """
        return True

    async def login(self) -> bool:
        """执行DeepSeek登录。
        支持自动登录和手动登录两种方式。
        Returns:
            bool: 登录是否成功
        """
        logger.debug(f"\n=== DeepSeek登录 ({self.config.name}) ===")
        current_url = self.browser.page.url
        chat_url = self.config.chat_url

        if current_url.startswith(chat_url):
            logger.debug("已在聊天页面，无需登录")
            self.is_logged_in = True
            return True

        if current_url.startswith(self.config.login_url):
            logger.debug("已在登录页面")
        else:
            logger.debug(f"导航到登录页面: {self.config.login_url}")
            await self.browser.goto(self.config.login_url)
            await self.browser.page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            logger.debug("已到达登录页面")

        current_url = self.browser.page.url
        if current_url.startswith(chat_url):
            logger.debug("已在聊天页面，无需登录")
            self.is_logged_in = True
            return True

        try:
            print("请在浏览器中手动完成登录：")
            print(" 并等待跳转到聊天界面")
            print("\n 登录完成后按回车键继续...")
            input("请在浏览器中完成登录后按回车继续...")

            # 验证登录是否成功
            if await self._verify_login_complete():
                self.is_logged_in = True
                print("DeepSeek登录成功")
                return True

            print("DeepSeek登录失败")
            return False
        except Exception as e:
            logger.error(f"DeepSeek登录过程出错: {e}")
            return False

    async def _verify_login_complete(self) -> bool:
        """验证登录是否完成。
        Returns:
            bool: 登录是否成功
        """
        # 方法1：检查是否跳转到聊天页面
        try:
            await self.browser.wait_for_url(self.config.chat_url, timeout=10000)
            return True
        except Exception:
            pass

        # 方法2：检查消息输入框
        input_selector = self.config.selectors.get("message_input")
        if input_selector:
            try:
                await self.browser.wait_for_selector(input_selector, timeout=5000)
                return True
            except Exception:
                pass

        return False

    async def ensure_ready(self) -> bool:
        """确保DeepSeek机器人就绪。
        Returns:
            bool: 机器人是否就绪
        """
        print("等待DeepSeek机器人就绪...")
        if self.is_ready:
            return True

        chat_url = self.config.chat_url
        current_url = self.browser.page.url
        if current_url.startswith(chat_url) or current_url == chat_url:
            self.is_ready = True
            self.is_logged_in = True
            return True

        # DeepSeek必须先登录
        if not self.is_logged_in:
            success = await self.login()
            if not success:
                return False
            self.is_logged_in = True

        # 验证聊天界面可用
        if await self._check_chat_available():
            self.is_ready = True
            return True
        return False

    # ==================== 重写基类方法 ====================

    async def _wait_for_response(self) -> str:
        """等待新的AI生成响应完成（排除旧的响应）。
        Returns:
            str: 新的响应文本
        """

        max_stable_checks = 2  # 最大稳定检查次数
        last_new_text = ""
        last_new_length = 0
        stable_count = 0
        response_started = False

        logger.debug("等待 DeepSeek 开始回复...")

        # 等待新响应开始（最长20秒）
        wait_start_time = time.time()
        while time.time() - wait_start_time < 20:
            current_text = await self._get_new_response_only()

            # 只要有新内容且不等于上次响应即可
            if current_text and current_text != self.last_response_text:
                if len(current_text.strip()) > 0:  # 只要有内容就认为是开始
                    logger.debug(f"DeepSeek开始回复: {current_text[:80]}...")
                    last_new_text = current_text
                    last_new_length = len(current_text)
                    last_change_time = time.time()
                    response_started = True
                    break
            await asyncio.sleep(0.5)

        if not response_started:
            logger.debug("等待20秒未检测到新响应开始，尝试直接检查...")
            current_text = await self._get_new_response_only()
            if current_text and current_text != self.last_response_text:
                logger.debug("检测到可能已完成的短响应")
                # 更新 last_response_text 并返回响应
                self.last_response_text = current_text
                return current_text

        # 监控新响应进度
        check_count = 0
        max_wait_time = 300  # 最长等待5分钟
        no_change_threshold = 10  # 10秒无变化认为完成

        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            check_count += 1
            try:
                current_text = await self._get_new_response_only()
                if not current_text or current_text == self.last_response_text:
                    if response_started:
                        # 已开始但当前无新内容，可能是短暂停顿
                        if check_count % 5 == 0:
                            print(".", end="", flush=True)
                    await asyncio.sleep(0.5)
                    continue

                current_length = len(current_text)

                if current_length > last_new_length:
                    # 有新内容生成
                    if check_count % 3 == 0:  # 每3次检查打印一次进度
                        print(".", end="", flush=True)

                    last_new_text = current_text
                    last_new_length = current_length
                    last_change_time = time.time()
                    stable_count = 0

                elif current_length == last_new_length and current_length > 0:
                    # 内容长度稳定
                    stable_count += 1
                    no_change_time = time.time() - last_change_time

                    # 策略1：检查明确的结束标志
                    if self._has_clear_end_marker(current_text):
                        logger.debug("检测到明确的结束标志")
                        print("✓", flush=True)
                        # 更新 last_response_text 并返回响应
                        self.last_response_text = current_text
                        return current_text

                    # 策略2：连续稳定检查
                    if stable_count >= max_stable_checks:
                        logger.debug(f"连续稳定 {stable_count} 次，认为完成")
                        print("✓", flush=True)
                        # 更新 last_response_text 并返回响应
                        self.last_response_text = current_text
                        return current_text

                    # 策略3：超时无变化
                    if no_change_time > no_change_threshold:
                        logger.debug(
                            f"长时间 ({no_change_time:.1f} 秒) 无新内容，认为完成"
                        )
                        print("✓", flush=True)
                        # 更新 last_response_text 并返回响应
                        self.last_response_text = current_text
                        return current_text

                elif current_length < last_new_length:
                    # 内容长度减少，可能是页面刷新或重新生成
                    logger.debug(
                        f"内容长度变化: {current_length} < {last_new_length}，重置状态"
                    )
                    last_new_length = current_length
                    last_change_time = time.time()
                    stable_count = 0

                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"等待响应过程中出错: {e}")
                await asyncio.sleep(2)

        # 超时处理
        logger.warning(f"等待回复超时 ({max_wait_time} 秒)")
        if last_new_text and last_new_text != self.last_response_text:
            print("⚠（超时）", flush=True)
            # 更新 last_response_text 并返回响应
            self.last_response_text = last_new_text
            return last_new_text

        final_text = await self._get_new_response_only()
        if final_text and final_text != self.last_response_text:
            print("⚠（超时获取）", flush=True)
            # 更新 last_response_text 并返回响应
            self.last_response_text = final_text
            return final_text

        print("✗（无响应）", flush=True)
        return ""

    async def _get_new_response_only(self) -> str:
        """获取新的响应文本（排除已知的旧响应）。

        Returns:
            str: 新的响应文本，若无新内容则返回空字符串。
        """
        try:
            current_text = await self._get_latest_ai_message()
            if not current_text:
                return ""

            # 如果当前文本与上次完全相同，说明没有新内容
            if current_text == self.last_response_text:
                return ""

            # 其他情况都返回当前文本
            # 包括：流式增量更新、全新回复等情况
            return current_text
        except Exception as e:
            logger.error(f"获取新响应失败: {e}")
            return ""

    def _has_clear_end_marker(self, text: str) -> bool:
        """检查是否有明确的结束标志。
        Args:
            text: 响应文本
        Returns:
            bool: 是否有明确的结束标志
        """
        if not text:
            return False

        clear_end_markers = [
            "本回答由 AI 生成，内容仅供参考，请仔细甄别。",
            "本回答由 AI 生成，仅供参考。",
            "希望能帮到你！",
        ]

        last_part = text[-300:] if len(text) > 300 else text
        for marker in clear_end_markers:
            if marker in last_part:
                return True
        return False

    async def _get_latest_ai_message(self) -> str:
        """获取页面上最新的 AI 消息文本（仅最新一条）。

        Returns:
            str: 最新 AI 消息的文本内容，若无则返回空字符串。
        """
        try:
            message_selector = (
                self.config.selectors.get("response_content")
                or "[class*='message'], [data-testid*='message'], .prose"
            )
            elements = self.browser.page.locator(message_selector)
            count = await elements.count()
            if count == 0:
                return ""
            latest_element = elements.nth(count - 1)
            if await latest_element.is_visible():
                text = await latest_element.text_content()
                return text.strip() if text else ""
            return ""
        except Exception as e:
            logger.error(f"获取最新AI消息失败: {e}")
            return ""

    async def _read_copybutton_response(self) -> str:
        """复制Markdown格式的AI响应到剪贴板。

        点击复制按钮并将响应内容写入系统剪贴板。

        Returns:
            str: 写入剪贴板的内容
        """
        try:
            # 1. 找到最近的AI回复
            ai_reply = self.browser.page.locator("div:has(> .ds-flex)").last
            button_group = ai_reply.locator(".ds-flex").last
            copy_button = button_group.locator(".ds-icon-button__hover-bg").first

            # 2. 滚动并点击复制按钮
            await copy_button.scroll_into_view_if_needed()
            await self.browser.page.wait_for_timeout(300)
            await copy_button.click()

            # 3. 等待短暂时间确保复制完成
            await self.browser.page.wait_for_timeout(500)

            # 4. 尝试从剪贴板读取内容
            clipboard_content = await self._read_clipboard()
            if clipboard_content:
                return clipboard_content
            return ""
        except Exception as e:
            logger.error(f"复制过程出错: {e}")
            return ""
