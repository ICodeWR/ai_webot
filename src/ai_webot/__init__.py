#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Webot - AI网页版对话机器人框架。

模块名称：__init__.py
功能描述：AI Webot 主模块
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

__version__ = "0.1.0"
__author__ = "码上工坊"
__license__ = "MIT"

# 核心类型导出
from ai_webot.services.config_service import BotConfig

# API模块导出
from .api import (
    BotFactory,
    BotRegistry,
)

__all__ = [
    "BotConfig",
    "BotFactory",
    "BotRegistry",
    "__version__",
    "__author__",
    "__license__",
]
