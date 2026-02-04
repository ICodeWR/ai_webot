#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Webot公共API模块。

提供机器人注册表和工厂类，统一管理机器人实例。

模块名称：api.py
功能描述：公共API - 机器人注册表和工厂
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

# from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

# 直接导入核心模块
from ai_webot.services import BotConfig, ConfigService
from ai_webot.webot.base.web_bot import WebBot


class BotRegistry:
    """机器人注册表，自动扫描配置文件目录，发现所有可用的机器人类型"""

    def __init__(self, config_dir: str = "configs"):
        """
        初始化机器人注册表。

        Args:
            config_dir: 配置文件目录，注册表会扫描此目录发现可用的机器人
        """
        self.config_dir = Path(config_dir)
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._config_service = ConfigService(config_dir)
        self._scan_configs()

    def _scan_configs(self) -> None:
        """扫描配置文件目录，发现所有可用的机器人配置。"""
        if not self.config_dir.exists():
            print(f"警告: 配置文件目录 {self.config_dir} 不存在")
            return

        config_files_info = self._get_config_files_info()
        if not config_files_info:
            print(f"未在 {self.config_dir} 中找到任何配置文件")
            return

        print(f"发现 {len(config_files_info)} 个配置文件")

        # 按机器人类型和文件类型分组，优先使用YAML
        bot_files: Dict[str, Dict[str, Any]] = {}

        for file_info in config_files_info:
            bot_type = file_info["stem"]
            ext = file_info["suffix"].lower()

            if bot_type not in bot_files:
                bot_files[bot_type] = file_info
            else:
                ext_priority = {".yaml": 2, ".json": 1}
                current_ext = bot_files[bot_type]["suffix"].lower()
                if ext_priority.get(ext, 0) > ext_priority.get(current_ext, 0):
                    bot_files[bot_type] = file_info

        registered_count = 0
        for bot_type, file_info in bot_files.items():
            config_file = file_info["path"]

            try:
                config_data = self._read_config_file(config_file)
                if not config_data:
                    continue

                plugin_info = config_data.get("plugin")
                if not plugin_info:
                    print(f"警告: 配置文件 {config_file.name} 缺少plugin字段，跳过")
                    continue

                module = plugin_info.get("module")
                class_name = plugin_info.get("class")

                if not module or not class_name:
                    print(f"警告: 配置文件 {config_file.name} 的plugin字段不完整，跳过")
                    continue

                config = self._config_service.load(bot_type)

                self._registry[bot_type] = {
                    "config": config,
                    "display_name": config.name,
                    "module": module,
                    "class": class_name,
                    "config_file": str(config_file),
                    "enabled": True,
                    "plugin_info": plugin_info,
                    "specific_config": config_data.get("specific", {}),
                }

                print(f"✓ 注册机器人: {bot_type} ({config.name})")
                registered_count += 1

            except Exception as e:
                print(f"✗ 跳过无效配置文件 {config_file.name}: {e}")

    def _get_config_files_info(self) -> List[Dict[str, Any]]:
        """获取配置文件目录中的所有配置文件信息。"""
        config_files_info: List[Dict[str, Any]] = []

        if not self.config_dir.exists():
            return config_files_info

        supported_extensions = [".yaml", ".json"]

        for ext in supported_extensions:
            for config_file in self.config_dir.glob(f"*{ext}"):
                try:
                    if not config_file.is_file():
                        continue

                    config_files_info.append(
                        {
                            "path": config_file,
                            "stem": config_file.stem,
                            "name": config_file.name,
                            "suffix": config_file.suffix,
                            "size": config_file.stat().st_size,
                            "modified": config_file.stat().st_mtime,
                        }
                    )
                except Exception as e:
                    print(f"获取文件信息失败 {config_file}: {e}")

        return config_files_info

    def _read_config_file(self, config_file: Path) -> Optional[Dict[str, Any]]:
        """读取配置文件原始数据。"""
        try:
            if config_file.suffix.lower() == ".yaml":
                return ConfigService.load_yaml(config_file)
            else:
                return ConfigService.load_json(config_file)
        except Exception as e:
            print(f"读取配置文件 {config_file} 失败: {e}")
            return None

    def get_bot_info(self, bot_type: str) -> Optional[Dict[str, Any]]:
        """获取机器人注册信息。"""
        info = self._registry.get(bot_type.lower())
        if not info:
            return None

        enabled = info.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ["true", "yes", "1", "on"]

        if not enabled:
            return None
        return info

    def get_bot_config(self, bot_type: str) -> Optional[BotConfig]:
        """获取机器人的配置对象。"""
        info = self.get_bot_info(bot_type)
        if info and "config" in info:
            return info["config"]

        try:
            return self._config_service.load(bot_type)
        except Exception:
            return None

    def get_bot_class_path(self, bot_type: str) -> Optional[str]:
        """获取机器人类路径。"""
        info = self.get_bot_info(bot_type)
        if not info:
            return None

        module = info.get("module")
        class_name = info.get("class")

        if not module or not class_name:
            return None

        return f"{module}.{class_name}"

    def get_plugin_info(self, bot_type: str) -> Optional[Dict[str, str]]:
        """
        获取机器人的plugin信息。

        Args:
            bot_type: 机器人类型

        Returns:
            plugin信息字典
        """
        info = self.get_bot_info(bot_type)
        if info and "plugin_info" in info:
            return info["plugin_info"]
        return None

    def get_all_bots(self, enabled_only: bool = True) -> List[str]:
        """获取所有已注册的机器人类型。"""
        if enabled_only:
            result = []
            for bot_type, info in self._registry.items():
                enabled = info.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.lower() in ["true", "yes", "1", "on"]
                if enabled:
                    result.append(bot_type)
            return result
        return list(self._registry.keys())

    def is_bot_registered(self, bot_type: str) -> bool:
        """
        检查机器人是否已注册。

        Args:
            bot_type: 机器人类型

        Returns:
            bool: 是否已注册
        """
        return bot_type.lower() in self._registry

    def get_display_name(self, bot_type: str) -> str:
        """
        获取机器人的显示名称。

        Args:
            bot_type: 机器人类型

        Returns:
            显示名称
        """
        info = self.get_bot_info(bot_type)
        if info and "display_name" in info:
            return info["display_name"]

        # 尝试从配置中获取
        config = self.get_bot_config(bot_type)
        if config:
            return config.name

        return bot_type.capitalize()

    def get_config_file_path(self, bot_type: str) -> Optional[str]:
        """
        获取机器人的配置文件路径。

        Args:
            bot_type: 机器人类型

        Returns:
            配置文件路径，如果不存在则返回None
        """
        info = self.get_bot_info(bot_type)
        if info and "config_file" in info:
            return info["config_file"]
        return None

    def refresh(self) -> None:
        """刷新注册表，重新扫描配置文件目录。"""
        print("刷新机器人注册表...")
        self._registry.clear()
        self._scan_configs()
        print(f"刷新完成，当前注册 {len(self._registry)} 个机器人")

    def get_all_bots_info(self) -> List[Dict[str, Any]]:
        """
        获取所有机器人的详细信息。

        Returns:
            机器人信息列表
        """
        result = []
        for bot_type, info in self._registry.items():
            result.append(
                {
                    "type": bot_type,
                    "display_name": info.get("display_name", ""),
                    "config_file": info.get("config_file", ""),
                    "enabled": info.get("enabled", True),
                    "plugin_info": info.get("plugin_info", {}),
                }
            )
        return result


class BotFactory:
    """机器人工厂类，负责创建和管理不同类型的AI机器人实例。"""

    def __init__(self, config_dir: str = "configs"):
        """
        初始化机器人工厂。

        Args:
            config_dir: 配置文件目录，工厂会从此目录发现可用的机器人
        """
        self.registry = BotRegistry(config_dir)
        self._bot_classes: Dict[str, type] = {}

    def _load_bot_class(self, bot_type: str) -> Optional[type]:
        """
        延迟加载机器人类。

        Args:
            bot_type: 机器人类型

        Returns:
            机器人对应的类，如果加载失败则返回None
        """
        if bot_type in self._bot_classes:
            return self._bot_classes[bot_type]

        class_path = self.registry.get_bot_class_path(bot_type)
        if not class_path:
            return None

        try:
            import importlib

            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            bot_class = getattr(module, class_name)

            # 验证是否是WebBot的子类
            if not issubclass(bot_class, WebBot):
                raise TypeError(f"机器人类 {class_name} 必须继承自 WebBot")

            # 验证是否实现了所有抽象方法
            self._validate_abstract_methods(bot_class)

            self._bot_classes[bot_type] = bot_class
            return bot_class

        except ImportError as e:
            print(f"加载机器人类失败 {bot_type}: 模块不存在")
            print(f"请确保已安装相关实现: pip install ai-webot-{bot_type}")
            return None
        except AttributeError as e:
            print(f"加载机器人类失败 {bot_type}: 类不存在")
            return None
        except Exception as e:
            print(f"加载机器人类失败 {bot_type}: {e}")
            return None

    def _validate_abstract_methods(self, bot_class: type) -> None:
        """
        验证机器人类是否实现了所有抽象方法。

        Args:
            bot_class: 要验证的机器人类

        Raises:
            TypeError: 如果缺少抽象方法实现
        """
        # 获取WebBot的所有抽象方法
        abstract_methods = []
        for name in dir(WebBot):
            attr = getattr(WebBot, name)
            if hasattr(attr, "__isabstractmethod__") and attr.__isabstractmethod__:
                abstract_methods.append(name)

        # 检查是否都实现了
        missing_methods = []
        for method_name in abstract_methods:
            if getattr(bot_class, method_name, None) is getattr(
                WebBot, method_name, None
            ):
                missing_methods.append(method_name)

        if missing_methods:
            raise TypeError(
                f"机器人类 {bot_class.__name__} 缺少必须实现的方法: {missing_methods}"
            )

    def create(self, bot_type: str, config: Optional[BotConfig] = None):
        """
        创建机器人实例。

        Args:
            bot_type: 机器人类型
            config: 机器人配置，如果为None则从注册表中获取

        Returns:
            创建的机器人实例

        Raises:
            ValueError: 当机器人类型不支持或未启用时
            TypeError: 当机器人类未正确实现抽象方法时
        """
        # 首先检查机器人是否已注册
        if not self.registry.is_bot_registered(bot_type):
            available_bots = self.list_all()
            raise ValueError(
                f"机器人类型 '{bot_type}' 未找到配置文件\n"
                f"可用机器人: {available_bots}\n"
                f"请在 configs/ 目录下创建 {bot_type}.yaml 文件"
            )

        # 如果未提供配置，从注册表中获取
        if config is None:
            config = self.registry.get_bot_config(bot_type)
            if config is None:
                raise ValueError(f"无法获取机器人 '{bot_type}' 的配置")

        bot_class = self._load_bot_class(bot_type.lower())
        if not bot_class:
            plugin_info = self.registry.get_plugin_info(bot_type)
            if plugin_info:
                raise ValueError(
                    f"无法加载机器人 '{bot_type}' 的实现类\n"
                    f"请确保已安装相关模块: {plugin_info.get('module')}"
                )
            else:
                raise ValueError(f"无法加载机器人 '{bot_type}' 的实现类")

        # 创建实例
        try:
            bot_instance = bot_class(config)
            return bot_instance
        except Exception as e:
            raise ValueError(f"创建机器人实例失败 {bot_type}: {e}")

    def list_all(self, enabled_only: bool = True) -> List[str]:
        """列出所有可用的机器人类型。"""
        return self.registry.get_all_bots(enabled_only)

    def get_display_name(self, bot_type: str) -> str:
        """获取机器人的显示名称。"""
        return self.registry.get_display_name(bot_type)

    def get_config(self, bot_type: str) -> Optional[BotConfig]:
        """获取机器人的配置。"""
        return self.registry.get_bot_config(bot_type)

    def get_plugin_info(self, bot_type: str) -> Optional[Dict[str, str]]:
        """获取机器人的plugin信息。"""
        return self.registry.get_plugin_info(bot_type)

    def refresh_registry(self) -> None:
        """刷新注册表。"""
        self.registry.refresh()

    def get_all_bots_info(self) -> List[Dict[str, Any]]:
        """获取所有机器人的详细信息。"""
        return self.registry.get_all_bots_info()

    def is_bot_registered(self, bot_type: str) -> bool:
        """检查机器人是否已注册。"""
        return self.registry.is_bot_registered(bot_type)
