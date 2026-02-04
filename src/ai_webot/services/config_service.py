#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置服务模块。

提供BotConfig和ConfigService，支持YAML和JSON格式的配置文件加载和解析。
模块名称：config_service.py
功能描述：配置服务
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_webot import __version__

from .file_exceptions import FileError

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class BrowserConfig:
    """浏览器配置数据类"""

    user_agent: str = field(
        default_factory=lambda: (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    geolocation: Dict[str, float] = field(
        default_factory=lambda: {"latitude": 39.9042, "longitude": 116.4074}
    )
    permissions: List[str] = field(default_factory=lambda: ["geolocation"])
    init_script: str = field(
        default_factory=lambda: (
            "// 覆盖webdriver属性\n"
            "Object.defineProperty(navigator, 'webdriver', {\n"
            "    get: () => false\n"
            "});\n\n"
            "// 覆盖chrome属性\n"
            "window.chrome = {\n"
            "    runtime: {},\n"
            "    loadTimes: function() {},\n"
            "    csi: function() {},\n"
            "    app: {}\n"
            "};\n\n"
            "// 添加plugins\n"
            "Object.defineProperty(navigator, 'plugins', {\n"
            "    get: () => [1, 2, 3, 4, 5]\n"
            "});\n\n"
            "// 添加languages\n"
            "Object.defineProperty(navigator, 'languages', {\n"
            "    get: () => ['zh-CN', 'zh', 'en']\n"
            "});"
        )
    )
    headless: bool = False


@dataclass
class BotConfig:
    """机器人配置数据类"""

    name: str
    login_url: str
    chat_url: str
    selectors: Dict[str, str]
    plugin: Dict[str, str]
    specific: Dict[str, Any]
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    description: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)
    output_dir: Optional[str] = None
    version: Optional[str] = __version__

    def __post_init__(self) -> None:
        """
        初始化后的处理

        确保 features 包含默认值，并且超时设置合理
        """
        # 确保features包含默认值
        default_features = {
            "save_login_state": True,
            "save_conversations": True,
            "use_markdown_copy": True,
            "save_history": True,
        }

        # 合并默认特征和用户定义的特征
        for key, value in default_features.items():
            if key not in self.features:
                self.features[key] = value

        # 设置默认浏览器配置
        if not self.browser:
            self.browser = BrowserConfig()

        if not self.version:
            self.version = __version__

    @property
    def save_login_state(self) -> bool:
        """是否保存登录状态"""
        return self.features.get("save_login_state", True)

    @property
    def save_conversations(self) -> bool:
        """是否保存对话记录"""
        return self.features.get("save_conversations", True)

    @property
    def use_markdown_copy(self) -> bool:
        """是否使用复制按钮获取Markdown"""
        return self.features.get("use_markdown_copy", True)

    @property
    def headless(self) -> bool:
        """是否无头模式"""
        return self.browser.headless

    @property
    def save_history(self) -> bool:
        """是否保存历史记录"""
        return self.features.get("save_history", True)

    @property
    def get_output_dir(self) -> Path:
        """获取输出目录路径"""
        if self.output_dir:
            return Path(self.output_dir)
        return Path("output")


class ConfigService:
    """配置服务 - 支持YAML和JSON格式"""

    def __init__(self, config_dir: str = "configs") -> None:
        """
        初始化配置服务

        Args:
            config_dir: 配置文件目录，默认为"configs"
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        # 检查YAML支持
        if not YAML_AVAILABLE:
            print("警告: PyYAML未安装，将使用JSON格式")
            print("建议安装: pip install pyyaml")

    def _find_config_file(self, bot_name: str) -> Optional[Path]:
        """
        查找配置文件，优先使用YAML格式

        Args:
            bot_name: 机器人名称

        Returns:
            配置文件路径，如果未找到返回None
        """
        # 查找优先级：.yaml > .json
        for ext in [".yaml", ".json"]:
            config_file = self.config_dir / f"{bot_name}{ext}"
            if config_file.exists():
                return config_file

        return None

    @staticmethod
    def load_yaml(file_path: Path) -> Dict[str, Any]:
        """
        加载 YAML 文件，自动替换环境变量。

        Args:
            file_path: YAML 文件路径

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 文件不存在
            ImportError: PyYAML 库未安装
        """

        if not YAML_AVAILABLE:
            raise ImportError("请安装PyYAML库: pip install pyyaml")

        # 读取文件
        if not file_path.exists():
            raise FileError(f"文件不存在：{file_path}")

        content = file_path.read_text(encoding="utf-8")

        # 替换环境变量
        def replace_env_var(match: re.Match) -> str:
            """
            替换环境变量
                例如，${VARIABLE} 或 ${VARIABLE:default_value}
                如果环境变量存在，返回环境变量的值
                如果环境变量不存在且提供了默认值，返回默认值
                否则，保持原样

            Args:
                match: 匹配对象

            Returns:
                环境变量的值
            """
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else None

            env_value = os.getenv(var_name)
            if env_value is not None:
                return env_value
            elif default_value is not None:
                return default_value
            else:
                return match.group(0)  # 保持原样

        # 匹配 ${VAR} 或 ${VAR:default}
        pattern = r"\$\{([A-Za-z0-9_]+)(?::([^}]+))?\}"
        content = re.sub(pattern, replace_env_var, content)

        return yaml.safe_load(content)

    @staticmethod
    def save_yaml(data: Dict[str, Any], file_path: Path) -> None:
        """
        保存YAML文件

        Args:
            data: 配置数据
            file_path: 保存路径

        Raises:
            ImportError: PyYAML 未安装
        """
        # 检查 PyYAML 是否可用
        if not YAML_AVAILABLE:
            raise ImportError("请安装PyYAML库: pip install pyyaml")

        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            # 使用友好的 YAML 格式
            yaml.dump(
                data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                indent=2,
                sort_keys=False,
            )

    @staticmethod
    def load_json(file_path: Path) -> Dict[str, Any]:
        """
        加载JSON文件

        Args:
            file_path: JSON文件路径

        Returns:
            配置字典
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_json(data: Dict[str, Any], file_path: Path) -> None:
        """
        保存JSON文件

        Args:
            data: 配置数据
            file_path: 保存路径
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, bot_name: str) -> BotConfig:
        """
        加载机器人配置

        Args:
            bot_name: 机器人名称

        Returns:
            机器人配置对象

        Raises:
            FileError: 配置文件不存在
            ImportError: PyYAML 库未安装
        """
        config_file = self._find_config_file(bot_name)

        if not config_file:
            available_files = list(self.config_dir.glob("*"))
            raise FileNotFoundError(
                f"配置文件不存在: {bot_name}\n"
                f"配置文件目录: {self.config_dir}\n"
                f"可用文件: {[f.name for f in available_files]}"
            )

        # 根据文件扩展名选择加载器
        if config_file.suffix.lower() in [".yaml", ".yml"]:
            # PyYAML 库未安装时，抛出错误
            if not YAML_AVAILABLE:
                raise ImportError(
                    f"需要PyYAML库来加载YAML文件: {config_file}\n"
                    f"请安装: pip install pyyaml"
                )
            # 使用PyYAML库加载YAML文件
            data = ConfigService.load_yaml(config_file)
        else:
            # 使用JSON库加载JSON文件
            data = ConfigService.load_json(config_file)

        # 转换浏览器配置
        browser_data = data.get("browser", {})
        if browser_data:
            browser_config = BrowserConfig(**browser_data)
            data["browser"] = browser_config

        # 转换为机器人配置对象
        return BotConfig(**data)

    def list_all(self) -> Dict[str, str]:
        """
        列出所有配置

        Returns:
            机器人名称到配置的映射字典
        """
        configs: Dict[str, str] = {}

        # 1. 加载 YAML 配置
        if YAML_AVAILABLE:
            for file in self.config_dir.glob("*.yaml"):
                try:
                    data = ConfigService.load_yaml(file)
                    configs[file.stem] = data.get("name", file.stem)
                except Exception as e:
                    print(f"警告: 加载配置文件 {file} 失败: {e}")
        else:
            print("提示: PyYAML未安装，跳过YAML配置文件")

        # 2. 加载 JSON 配置（避免重复）
        for file in self.config_dir.glob("*.json"):
            if file.stem in configs:  # 如果已有YAML版本，跳过JSON
                continue
            try:
                data = ConfigService.load_json(file)
                configs[file.stem] = data.get("name", file.stem)
            except Exception as e:
                print(f"警告: 加载配置文件 {file} 失败: {e}")

        return configs

    def create_sample_config(self, bot_type: str, format: str = "yaml") -> str:
        """
        创建示例配置文件

        Args:
            bot_type: 机器人类型
            format: 配置文件格式，支持 "yaml" 或 "json"

        Returns:
            配置文件路径

        Raises:
            ValueError: 当机器人类型不支持时
        """
        # 验证格式参数
        format = format.lower()
        if format not in ["yaml", "json"]:
            raise ValueError(f"不支持的格式: {format}，请使用 'yaml' 或 'json'")

        # 获取示例配置数据
        if bot_type == "deepseek":
            sample_data = {
                "name": "DeepSeek",
                "description": "DeepSeek Web聊天机器人\n支持文件上传和代码对话",
                "login_url": "https://chat.deepseek.com/auth/login",
                "chat_url": "https://chat.deepseek.com/",
                "browser": {
                    "user_agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "locale": "zh-CN",
                    "timezone": "Asia/Shanghai",
                    "geolocation": {"latitude": 39.9042, "longitude": 116.4074},
                    "permissions": ["geolocation"],
                    "headless": False,
                },
                "selectors": {
                    "message_input": "textarea",
                    "send_button": "button[type='submit']",
                    "file_upload": "input[type='file']",
                    "copy_button": "button.copy-btn",
                    "response_content": ".message-content",
                },
                "features": {
                    "save_login_state": True,
                    "save_conversations": True,
                    "use_markdown_copy": True,
                    "save_history": True,
                },
                "plugin": {
                    "module": "ai_webot.webot.deepseek.bot",
                    "class": "DeepSeekBot",
                },
                "specific": {
                    "preferred_login": "None",
                    "auto_accept_cookies": True,
                },
                "output_dir": "output/deepseek",
                "version": "1.0.0",
            }
        elif bot_type == "qianwen":
            sample_data = {
                "name": "通义千问",
                "description": "通义千问Web聊天机器人\n支持多种登录方式",
                "login_url": "https://tongyi.aliyun.com/qianwen",
                "chat_url": "https://tongyi.aliyun.com/qianwen/chat",
                "browser": {
                    "user_agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "locale": "zh-CN",
                    "timezone": "Asia/Shanghai",
                    "geolocation": {"latitude": 39.9042, "longitude": 116.4074},
                    "permissions": ["geolocation"],
                    "headless": False,
                },
                "selectors": {
                    "message_input": "textarea[placeholder*='输入' i]",
                    "send_button": "button:has-text('发送'), button[type='submit']",
                    "file_upload": "input[type='file'], .upload-btn",
                    "copy_button": "button.copy-btn, button[aria-label*='复制']",
                    "response_content": ".response-content, .message-content",
                },
                "features": {
                    "save_login_state": True,
                    "save_conversations": True,
                    "use_markdown_copy": True,
                    "save_history": True,
                },
                "plugin": {
                    "module": "ai_webot.webot.qianwen.bot",
                    "class": "QianWenBot",
                },
                "specific": {
                    "qrcode_refresh_interval": 30,
                },
                "output_dir": "output/qianwen",
                "version": "1.0.0",
            }
        elif bot_type == "doubao":
            sample_data = {
                "name": "豆包",
                "description": "豆包Web聊天机器人\n支持手机验证码和二维码登录",
                "login_url": "https://www.doubao.com/chat",
                "chat_url": "https://www.doubao.com/chat",
                "browser": {
                    "user_agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "locale": "zh-CN",
                    "timezone": "Asia/Shanghai",
                    "geolocation": {"latitude": 39.9042, "longitude": 116.4074},
                    "permissions": ["geolocation"],
                    "headless": False,
                },
                "selectors": {
                    "message_input": "div[contenteditable='true'], textarea[placeholder*='聊点什么' i]",
                    "send_button": "button:has-text('发送'), button.send-btn, button[type='submit']",
                    "file_upload": "input[type='file'], .upload-area",
                    "copy_button": "button.copy-btn, button[aria-label*='复制'], button[title*='复制']",
                    "response_content": ".message-text, .bubble-content, .message-content",
                },
                "features": {
                    "save_login_state": True,
                    "save_conversations": True,
                    "use_markdown_copy": True,
                    "save_history": True,
                },
                "plugin": {
                    "module": "ai_webot.webot.doubao.bot",
                    "class": "DouBaoBot",
                },
                "specific": {
                    "debug_screenshot": False,
                },
                "output_dir": "output/doubao",
                "version": "1.0.0",
            }
        else:
            raise ValueError(f"不支持的机器人类型: {bot_type}")

        # 根据格式保存文件
        if format == "yaml":
            if not YAML_AVAILABLE:
                print("警告: PyYAML未安装，将使用JSON格式")
                format = "json"

        if format == "yaml":
            config_file = self.config_dir / f"{bot_type}.yaml"  # 只生成 .yaml 文件
            ConfigService.save_yaml(sample_data, config_file)
        else:
            config_file = self.config_dir / f"{bot_type}.json"
            ConfigService.save_json(sample_data, config_file)

        return str(config_file)
