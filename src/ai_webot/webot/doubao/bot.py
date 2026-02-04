#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包机器人实现模块，实现豆包Web机器人的交互具体功能。

模块名称：bot.py
功能描述：豆包机器人实现
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

from playwright.async_api import Locator, Page, TimeoutError, expect

from ai_webot.webot.base.web_bot import WebBot

# 获取模块日志器
logger = logging.getLogger(__name__)


class DouBaoBot(WebBot):
    """
    豆包Web机器人实现类，继承自WebBot抽象基类。

    当前采用手动模式登录和验证方式，需要在网页端手动登录、验证后使用对话功能。
    """

    def __init__(self, config):
        """
        初始化豆包机器人实例。

        Args:
            config: 机器人配置对象，包含浏览器、选择器、聊天地址等配置信息
        """
        super().__init__(config)
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
        """
        判断豆包机器人是否需要强制登录。

        豆包支持游客模式直接使用，无需登录即可发送消息，因此始终返回False。

        Returns:
            bool: 强制登录标识，固定返回False
        """
        return False

    async def login(self) -> bool:
        """
        执行豆包机器人登录操作，支持游客模式。

        豆包无需强制登录，游客模式可直接使用；若游客模式不可用，提示用户手动登录。
        游客模式下第一次发送消息可能需要手动完成人机验证。

        Returns:
            bool: 登录/就绪成功返回True，失败返回False

        Raises:
            Exception: 登录过程中出现的未知异常
        """
        # 检查是否已登录

        logger.info(f"=== 豆包登录 ({self.config.name}) ===")

        try:
            # 尝试游客模式
            if await self._check_chat_available():
                logger.info("豆包游客模式可用，游客模式第一次发送消息会需要手动验证")
                print(
                    "豆包支持游客模式，如需登录请在浏览器页面手动登录后再使用该功能。"
                )
                return True
            logger.info("豆包游客模式不可用，请手动登录")
            return False

        except Exception as e:
            logger.error(f"豆包登录过程出错: {e}", exc_info=True)
            return False

    async def ensure_ready(self) -> bool:
        """
        确保豆包机器人处于就绪状态，可执行消息发送操作。

        检查当前页面是否为豆包聊天页面，若非则导航至配置的聊天地址，
        仅检查页面加载状态，未严格校验元素，适配游客模式,登录为手动。

        Returns:
            bool: 机器人就绪返回True，失败返回False

        Raises:
            Exception: 页面导航、元素等待过程中的未知异常
        """
        if self.is_ready:
            return True

        logger.info("等待豆包机器人就绪...")

        try:
            # 首先导航到聊天页面
            current_url = self.browser.page.url
            chat_url = self.config.chat_url

            if not current_url.startswith(chat_url):
                logger.debug(f"当前URL不是聊天页面，导航到: {chat_url}")
                await self.browser.goto(chat_url)
                logger.debug(f"等待 message_input")
                selector = self.config.selectors.get("message_input")
                if selector:
                    await self.browser.wait_for_selector(selector, timeout=5000)
                await asyncio.sleep(1)  # 给页面加载时间

            # 宽松检查：页面已加载即可
            self.is_ready = True
            logger.info("豆包机器人就绪")
            print("豆包机器人就绪：游客模式时，第一次发消息需要手动验证")
            return True

        except Exception as e:
            logger.error(f"豆包机器人就绪检查失败: {e}")
            return False

    # ==================== 可选重写方法（子类可按需重写） ====================

    async def _wait_for_response(self) -> str:
        """
        等待豆包AI生成响应并返回完整稳定的文本。

        Args:
            None

        Returns:
            str: AI生成的完整、稳定的响应文本；若出现异常，返回空字符串

        Raises:
            TimeoutError: 超出MAX_WAIT_TIME未检测到新AI消息
            ValueError: AI消息文本为空，无有效内容
            Exception: 页面操作、节点定位过程中的未知异常
        """

        logger.debug("等待豆包回复...")
        page: Page = self.browser.page
        base_receive_locator: Locator = page.get_by_test_id("receive_message")
        msg_text_locator_suffix = page.get_by_test_id("message_text_content")

        try:
            # 延迟统计，避免页面渲染未完成导致统计失真
            await asyncio.sleep(0.3)
            # 过滤豆包消息容器
            initial_ai_locator: Locator = base_receive_locator.filter(
                has=msg_text_locator_suffix
            )
            initial_ai_elems: List[Locator] = await initial_ai_locator.all()
            # 手动过滤可见元素
            initial_ai_elems = [
                elem for elem in initial_ai_elems if await elem.is_visible(timeout=1000)
            ]
            initial_ai_count: int = len(initial_ai_elems)
            logger.info(
                f"检测到可见豆包消息数：{initial_ai_count}，等待豆包新消息生成..."
            )

            # 发送后强制滚到底部，确保新消息可见
            await page.click("body", delay=50)
            await page.wait_for_timeout(300)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # 初始化可空变量
            new_ai_locator: Optional[Locator] = None
            wait_start: float = time.time()
            max_wait_time: int = 50
            logger.info(f"等待豆包回复（最长{max_wait_time}秒）...")

            while time.time() - wait_start < max_wait_time:
                # 实时获取豆包消息容器，手动过滤可见元素
                current_ai_locator: Locator = base_receive_locator.filter(
                    has=msg_text_locator_suffix
                )
                current_ai_elems: List[Locator] = await current_ai_locator.all()
                current_ai_elems = [
                    elem
                    for elem in current_ai_elems
                    if await elem.is_visible(timeout=1000)
                ]
                current_ai_count: int = len(current_ai_elems)
                logger.debug(f"current_ai_count： {current_ai_count}）")
                # 每5秒打印实时日志，便于排查
                if (
                    int(time.time() - wait_start) % 5 == 0
                    and (time.time() - wait_start) > 0
                ):
                    logger.debug(
                        f"等待中：当前可见AI消息数{current_ai_count}，初始数{initial_ai_count}"
                    )

                # 打印等待进度
                print(".", end="")

                # 检测新消息：数量增加+最后一个节点可见
                if current_ai_count > initial_ai_count:
                    new_ai_locator = current_ai_locator.last
                    if await new_ai_locator.is_visible(timeout=1000):
                        logger.info(f"检测到新消息，当前可见消息数：{current_ai_count}")
                        break
                await asyncio.sleep(0.6)

            # 非空校验，避免None调用
            if not new_ai_locator:
                all_receive_elems: List[Locator] = await base_receive_locator.all()
                all_receive_count: int = len(all_receive_elems)
                raise TimeoutError(
                    f"{max_wait_time}秒内未检测到新AI消息（初始可见AI数{initial_ai_count}，当前可见{current_ai_count}，页面总receive节点{all_receive_count}）"
                )
            # 文本节点可见
            new_msg_text: Locator = new_ai_locator.get_by_test_id(
                "message_text_content"
            )
            await expect(new_msg_text, "新豆包消息文本节点未渲染/不可见").to_be_visible(
                timeout=20000
            )

            # 文本非空、非纯空白
            current_text: str = (await new_msg_text.inner_text(timeout=5000)).strip()
            if not current_text:
                raise ValueError("新豆包消息文本为空白，无有效内容")
            logger.debug(f"新豆包消息初始内容：{current_text[:50]}...")

            # 内容稳定检测（文本+长度双重判定，避免误判）
            last_text: str = current_text
            last_length: int = len(last_text)
            stable_count: int = 0
            stable_threshold: int = 2
            max_stable_wait: int = 60 * 30  # 防止长文本输出超时
            stable_start: float = time.time()
            logger.info("豆包开始生成新消息，等待内容稳定...")

            while time.time() - stable_start < max_stable_wait:
                # 确保新消息在可视区域，避免文本获取失败
                await new_ai_locator.scroll_into_view_if_needed(timeout=5000)
                try:
                    current_text = (await new_msg_text.inner_text(timeout=5000)).strip()
                except Exception:
                    current_text = ""
                current_length: int = len(current_text)

                # 双重稳定判定：文本非空 + 内容+长度连续2次不变
                if (
                    current_text
                    and current_text == last_text
                    and current_length == last_length
                ):
                    stable_count += 1
                    if stable_count >= stable_threshold:
                        logger.info("✅ 新AI消息内容完全稳定，生成完成")
                        print("\n")
                        return current_text
                else:
                    stable_count = 0
                    last_text = current_text
                    last_length = current_length
                    if current_text:
                        logger.debug(f"新消息生成中，当前内容长度：{current_length}")
                        print(".", end="")
                await asyncio.sleep(0.3)

            raise TimeoutError(
                f"新AI消息内容{max_stable_wait}秒内未稳定，最新内容：{last_text[:50]}..."
            )

        except TimeoutError as e:
            logger.error(f"等待响应超时：{str(e)}", exc_info=True)
            print(f"等待响应失败：{e}")
            return ""
        except ValueError as e:
            logger.error(f"AI消息内容校验失败：{str(e)}", exc_info=True)
            print(f"响应内容异常：{e}")
            return ""
        except Exception as e:
            logger.error(f"等待响应异常：{str(e)}", exc_info=True)
            print(f"等待响应异常：{e}")
            return ""

    async def _read_copybutton_response(self) -> str:
        """
        读取复制按钮的响应内容。

        Returns:
            str: 响应文本内容
        """
        logger.debug("豆包开始读取复制按钮响应...")
        page: Page = self.browser.page

        # 复制前强制滚到底部，确保新消息可见
        await page.click("body", delay=50)
        await page.wait_for_timeout(300)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        base_receive_locator: Locator = page.get_by_test_id("receive_message")
        copy_button_locator = page.get_by_test_id("message_action_copy")

        try:
            # 打印等待进度
            await expect(
                copy_button_locator, "复制按钮节点未渲染/不可见"
            ).to_be_visible(timeout=20000)

            # 点击复制按钮
            await copy_button_locator.click(timeout=5000)

            # 等待响应消息可见
            new_msg_text: Locator = base_receive_locator.get_by_test_id(
                "message_text_content"
            )
            await expect(
                new_msg_text, "复制按钮响应消息节点未渲染/不可见"
            ).to_be_visible(timeout=20000)

            # 3. 等待短暂时间确保复制完成
            await self.browser.page.wait_for_timeout(500)

            # 4. 尝试从剪贴板读取内容
            clipboard_content = await self._read_clipboard()
            if clipboard_content:
                return clipboard_content
            return ""
        except TimeoutError as e:
            logger.error(f"等待响应超时：{str(e)}", exc_info=True)
            print(f"等待响应失败：{e}")
            return ""
        except ValueError as e:
            logger.error(f"AI消息内容校验失败：{str(e)}", exc_info=True)
            print(f"响应内容异常：{e}")
            return ""
        except Exception as e:
            logger.error(f"等待响应异常：{str(e)}", exc_info=True)
            print(f"等待响应异常：{e}")
        return ""
