#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块名称：file_exceptions.py
功能描述：文件操作异常类
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

from typing import Any, Dict, Optional


class FileError(Exception):
    """
    基类文件操作异常。

    Attributes:
        message (str): 错误描述信息。
        file_path (Optional[str]): 相关的文件路径，可能为 None。
        context (Dict[str, Any]): 额外的上下文信息。
    """

    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs: Any):
        """
        初始化文件异常。

        Args:
            message: 错误描述信息。
            file_path: 相关的文件路径，可选。
            **kwargs: 其他上下文信息。
        """
        context: Dict[str, Any] = kwargs.copy()
        if file_path:
            context["file_path"] = file_path
        super().__init__(message, context)
        self.message = message
        self.file_path = file_path
        self.context = context

    def __str__(self) -> str:
        """
        返回错误信息的字符串表示。

        Returns:
            格式化的错误信息。
        """
        if self.file_path:
            return f"{self.__class__.__name__}: {self.message} [文件: {self.file_path}]"
        return f"{self.__class__.__name__}: {self.message}"
