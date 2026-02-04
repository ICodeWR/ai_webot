#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Webot命令行接口模块。

提供命令行交互和机器人管理功能，使用命令模式优化代码结构。

模块名称：cli.py
功能描述：命令行接口
版权声明：Copyright (c) 2026 码上工坊
开源协议：MIT License
免责声明：本软件按"原样"提供，不作任何明示或暗示的担保
作者：码上工坊
修改记录：
版本：0.1.0 2026-01-29 - 码上工坊 - 创建文件
"""

import argparse
import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_webot import BotFactory
from ai_webot.services import ConfigService

# 获取模块日志器
logger = logging.getLogger(__name__)


class Command(ABC):
    """命令抽象基类。"""

    def __init__(self, name: str, description: str, help_text: str = "") -> None:
        """
        初始化命令。

        Args:
            name: 命令名称
            description: 命令描述
            help_text: 帮助文本
        """
        self.name = name
        self.description = description
        self.help_text = help_text

    @abstractmethod
    async def execute(self, args: List[str], cli: Any) -> int:
        """
        执行命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，非0表示错误）
        """
        pass

    def print_help(self) -> None:
        """打印命令帮助信息。"""
        if self.help_text:
            print(self.help_text)
        else:
            print(f"命令: {self.name}")
            print(f"描述: {self.description}")


class CommandRegistry:
    """命令注册器，管理所有可用的命令。"""

    def __init__(self) -> None:
        """初始化命令注册器。"""
        self._commands: Dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """
        注册命令。

        Args:
            command: 要注册的命令对象
        """
        self._commands[command.name] = command

    def get_command(self, name: str) -> Optional[Command]:
        """
        获取命令。

        Args:
            name: 命令名称

        Returns:
            Command: 命令对象，如果不存在返回None
        """
        return self._commands.get(name)

    def get_all_commands(self) -> List[Command]:
        """
        获取所有命令。

        Returns:
            List[Command]: 命令对象列表
        """
        return list(self._commands.values())

    def get_command_names(self) -> List[str]:
        """
        获取所有命令名称。

        Returns:
            List[str]: 命令名称列表
        """
        return list(self._commands.keys())


# ==================== 具体命令实现 ====================


class HelpCommand(Command):
    """帮助命令，显示所有可用命令的帮助信息。"""

    def __init__(self):
        """初始化帮助命令。"""
        help_text = """
AI Webot 命令行工具

用法:
  ai-webot                      # 启动交互式对话
  ai-webot list                 # 列出可用机器人
  ai-webot ask <bot> <question> # 直接提问（一次性）
  ai-webot chat <bot>           # 启动对话模式（复用会话）
  ai-webot config show <bot>    # 显示配置
  ai-webot history <subcommand> # 历史记录管理

选项:
  -h, --help     显示帮助信息
  -l, --log-level <level> 设置日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  --log-file <file>       将日志输出到文件

示例:
  ai-webot ask deepseek "你好"          # 单次提问
  ai-webot chat deepseek               # 进入对话模式
  ai-webot config show deepseek        # 查看配置
  ai-webot --log-level DEBUG           # 调试模式
  ai-webot --log-file app.log          # 日志保存到文件
        """
        super().__init__("help", "显示帮助信息", help_text.strip())

    async def execute(self, args: List[str], cli) -> int:
        """
        执行帮助命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功）
        """
        self.print_help()

        # 如果指定了具体命令，显示该命令的帮助
        if args:
            command_name = args[0]
            command = cli.command_registry.get_command(command_name)
            if command:
                command.print_help()
            else:
                print(f"未知命令: {command_name}")
                print("可用命令:", ", ".join(cli.command_registry.get_command_names()))

        return 0


class ListCommand(Command):
    """列出所有可用的机器人。"""

    def __init__(self):
        """初始化列表命令。"""
        super().__init__("list", "列出所有可用的机器人")

    async def execute(self, args: List[str], cli) -> int:
        """
        执行列表命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功）
        """
        print("可用机器人:")
        for bot in cli.available_bots:
            if bot in cli.configs:
                print(f"  ✓ {bot} - {cli.configs[bot]} (已配置)")
            else:
                print(f"  ○ {bot} (未配置)")
        return 0


class AskCommand(Command):
    """执行提问命令（单次提问）。"""

    def __init__(self):
        """初始化提问命令。"""
        help_text = """
用法: ai-webot ask <机器人> <问题>

示例:
  ai-webot ask deepseek "Python是什么？"
  ai-webot ask doubao "你好，豆包！"
  ai-webot ask qianwen "请解释机器学习"
        """
        super().__init__("ask", "直接提问（一次性）", help_text.strip())

    async def execute(self, args: List[str], cli) -> int:
        """
        执行提问命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        if len(args) < 2:
            print("用法: ai-webot ask <机器人> <问题>")
            print("示例: ai-webot ask deepseek '你好'")
            return 1

        bot_type = args[0]
        question = " ".join(args[1:])

        try:
            print(f"向 {bot_type} 提问: {question}")

            # 使用工厂创建机器人
            bot = cli.factory.create(bot_type)
            async with bot as bot_instance:
                response = await bot_instance.send_message(question)

            print(f"\n{bot_type}:")
            print("-" * 40)
            print(response)
            return 0

        except Exception as e:
            print(f"错误: {e}")
            return 1


class ChatCommand(Command):
    """执行聊天命令（进入对话模式）。"""

    def __init__(self):
        """初始化聊天命令。"""
        help_text = """
用法: ai-webot chat <机器人>

进入交互式对话模式，可以连续与机器人对话。

示例:
  ai-webot chat deepseek
  ai-webot chat doubao

对话中可用命令:
  quit, exit, q - 退出对话
  file:路径 - 上传文件，如: file:/path/to/file.txt
  file:路径1,路径2 - 上传多个文件
        """
        super().__init__("chat", "启动对话模式（复用会话）", help_text.strip())

    async def execute(self, args: List[str], cli) -> int:
        """
        执行聊天命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        if len(args) < 1:
            print("用法: ai-webot chat <机器人>")
            return 1

        bot_type = args[0]
        display_name = cli.configs.get(bot_type, bot_type)

        print(f"正在连接 {display_name}...")

        try:
            # 使用工厂创建机器人
            bot = cli.factory.create(bot_type)
            async with bot as bot_instance:
                # 确保机器人就绪（这会触发登录和导航）
                await bot_instance.ensure_ready()
                print(f"连接 {display_name} 成功！开始对话")
                print("输入 'quit' 退出，'file:路径' 上传文件")
                print("-" * 50)
                await cli._conversation_loop(bot_instance, display_name)
            return 0

        except Exception as e:
            print(f"连接失败: {e}")
            return 1


class ConfigCommand(Command):
    """配置相关命令。"""

    def __init__(self):
        """初始化配置命令。"""
        help_text = """
用法: ai-webot config <子命令> <机器人>

子命令:
  show - 显示机器人配置

示例:
  ai-webot config show deepseek
  ai-webot config show doubao
        """
        super().__init__("config", "配置管理", help_text.strip())

    async def execute(self, args: List[str], cli) -> int:
        """
        执行配置命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        if len(args) < 2:
            print("用法: ai-webot config <子命令> <机器人>")
            print("子命令: show")
            return 1

        subcommand = args[0]
        bot_type = args[1]

        if subcommand == "show":
            return await self._show_config(bot_type, cli)
        else:
            print(f"未知子命令: {subcommand}")
            return 1

    async def _show_config(self, bot_type: str, cli) -> int:
        """
        显示机器人配置。

        Args:
            bot_type: 机器人类型
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        try:
            # 使用工厂获取配置
            config = cli.factory.get_config(bot_type)
            config_summary = {
                "name": config.name,
                "login_url": config.login_url,
                "chat_url": config.chat_url,
                "requires_login": config.features.get("requires_login", False),
                "selectors": config.selectors,
                "output_dir": config.output_dir,
            }
            print(f"\n{bot_type} 配置:")
            print(json.dumps(config_summary, indent=2, ensure_ascii=False))
            return 0
        except Exception as e:
            print(f"错误: {e}")
            return 1


class HistoryCommand(Command):
    """历史记录管理命令。"""

    def __init__(self):
        """初始化历史记录命令。"""
        help_text = """
用法: ai-webot history <子命令> [参数]

子命令:
  list [数量] - 列出历史记录，可选指定数量（默认10）

示例:
  ai-webot history list deepseek
  ai-webot history list deepseek 20
        """
        super().__init__("history", "历史记录管理", help_text.strip())

    async def execute(self, args: List[str], cli) -> int:
        """
        执行历史记录命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        if len(args) < 2:
            print("用法: ai-webot history <子命令> <机器人> [参数]")
            print("子命令: list")
            return 1

        subcommand = args[0]
        bot_type = args[1]
        sub_args = args[2:]

        if subcommand == "list":
            return await self._history_list(bot_type, sub_args, cli)
        else:
            print(f"未知子命令: {subcommand}")
            return 1

    async def _history_list(self, bot_type: str, args: List[str], cli) -> int:
        """
        列出历史记录。

        Args:
            bot_type: 机器人类型
            args: 额外参数
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        limit = 10
        if args and args[0].isdigit():
            limit = int(args[0])

        try:
            # 使用工厂创建机器人
            bot = cli.factory.create(bot_type)
            async with bot as bot_instance:
                await bot_instance.ensure_ready()
                history = await bot_instance.get_conversation_history(limit=limit)
                if not history:
                    print("没有历史记录")
                    return 0

                print(f"最近 {len(history)} 条对话记录:")
                print("=" * 60)
                return 0

        except Exception as e:
            print(f"错误: {e}")
            return 1


class InteractiveCommand(Command):
    """交互式对话命令。"""

    def __init__(self):
        """初始化交互式命令。"""
        super().__init__("", "启动交互式对话", "")

    async def execute(self, args: List[str], cli) -> int:
        """
        执行交互式命令。

        Args:
            args: 命令参数列表
            cli: CLI实例

        Returns:
            int: 退出代码（0表示成功，1表示失败）
        """
        await cli.run_interactive()
        return 0


class CLI:
    """命令行接口类，提供与AI机器人的交互功能。"""

    def __init__(self, log_level: str = "INFO"):
        """
        初始化CLI。

        Args:
            log_level: 日志级别字符串（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        # 创建唯一的工厂实例
        self.factory = BotFactory()

        # 从工厂获取可用机器人列表
        self.available_bots = self.factory.list_all()

        # 加载配置
        self.configs = self._load_configs()
        self._setup_logging(log_level)
        self.command_registry = self._init_commands()

        logger.info(f"CLI初始化完成，发现 {len(self.available_bots)} 个机器人")

    def _setup_logging(self, level_str: str) -> None:
        """
        设置日志级别。

        Args:
            level_str: 日志级别字符串
        """
        level = getattr(logging, level_str.upper(), logging.INFO)
        logger.setLevel(level)

        # 设置playwright等第三方库的日志级别
        logging.getLogger("playwright").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    def _load_configs(self) -> Dict[str, str]:
        """加载所有配置。"""
        try:
            config_service = ConfigService()
            return config_service.list_all()
        except Exception as e:
            logger.error("加载配置失败: %s", e, exc_info=True)
            return {}

    def _init_commands(self) -> CommandRegistry:
        """
        初始化命令注册器。

        Returns:
            CommandRegistry: 命令注册器实例
        """
        registry = CommandRegistry()

        # 注册所有命令
        registry.register(HelpCommand())
        registry.register(ListCommand())
        registry.register(AskCommand())
        registry.register(ChatCommand())
        registry.register(ConfigCommand())
        registry.register(HistoryCommand())
        # 交互式命令不注册到registry，作为默认命令

        return registry

    async def run_interactive(self):
        """
        运行交互模式，提供用户与AI机器人的对话界面。
        """
        self._print_banner()

        # 使用初始化时获取的机器人列表
        if not self.available_bots:
            print("未找到可用的机器人配置")
            print("请先在 configs/ 目录下创建配置文件")
            return

        # 显示机器人列表
        print("可用机器人:")
        for i, bot_type in enumerate(self.available_bots, 1):
            display_name = self.configs.get(bot_type, bot_type)
            print(f"  {i}. {display_name} ({bot_type})")
        print(f"  {len(self.available_bots) + 1}. 退出")

        # 选择机器人
        bot_type = self._select_bot(self.available_bots)
        if not bot_type:
            return

        # 使用工厂创建机器人
        display_name = self.configs.get(bot_type, bot_type)
        print(f"\n正在连接 {display_name}...")

        try:
            bot = self.factory.create(bot_type)
            async with bot as bot_instance:
                await bot_instance.ensure_ready()
                print(f"连接 {display_name} 成功！开始对话")
                print("输入 'quit' 或 'exit' 退出对话")
                print("-" * 50)
                await self._conversation_loop(bot_instance, display_name)

        except Exception as e:
            print(f"连接失败: {e}")
            return

    def _print_banner(self):
        """打印程序横幅。"""
        print("=" * 50)
        print("AI Webot - AI对话机器人")
        print("=" * 50)

    def _select_bot(self, available_bots: List[str]) -> str:
        """选择机器人。"""
        while True:
            try:
                choice = input(f"\n选择机器人 (1-{len(available_bots) + 1}): ").strip()
                if not choice:
                    continue

                idx = int(choice) - 1
                if 0 <= idx < len(available_bots):
                    return available_bots[idx]
                elif idx == len(available_bots):
                    return ""
                else:
                    print(f"请输入 1-{len(available_bots) + 1}")
            except (ValueError, KeyboardInterrupt):
                return ""

    async def _conversation_loop(self, bot, bot_display_name: str) -> None:
        """
        对话循环，处理用户输入和机器人响应。

        Args:
            bot: 机器人实例
            bot_display_name: 机器人显示名称
        """
        while True:
            try:
                user_input = input("\n我: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("退出对话")
                    break

                if not user_input:
                    continue

                # 处理文件上传
                files = []
                if user_input.startswith("file:"):
                    file_paths = user_input[5:].strip().split(",")
                    for file_path in file_paths:
                        file_path = file_path.strip()

                        path = Path(file_path)
                        if path.exists() and path.is_file():
                            files.append(file_path)
                            print(f"已添加文件: {file_path}")
                        else:
                            print(f"文件不存在或无效: {file_path}")

                    if files:
                        user_input = input("请输入消息内容: ").strip()
                    else:
                        continue
                dir_name = ""
                if user_input.startswith("dir:"):
                    dir_name = user_input[4:].strip()
                    if not Path(dir_name).exists() or not Path(dir_name).is_dir():
                        print(f"目录不存在或无效: {dir_name}")
                        continue
                    user_input = input("请输入消息内容: ").strip()

                # 发送消息
                answer = await bot.send_message(user_input, files, dir_name)
                # 显示响应
                print(f"\n{bot_display_name}:")
                print("-" * 40)
                print(answer)
                print("-" * 40)

            except KeyboardInterrupt:
                print("\n中断对话")
                break
            except Exception as e:
                print(f"错误: {e}")

    async def execute_command(self, command_name: str, args: List[str]) -> int:
        """
        执行指定命令。

        Args:
            command_name: 命令名称
            args: 命令参数

        Returns:
            int: 退出代码
        """
        command: Optional[Command] = None

        # 空命令或"interactive"使用交互模式
        if not command_name or command_name == "interactive":
            command = InteractiveCommand()
        else:
            command = self.command_registry.get_command(command_name)

        if not command:
            print(f"未知命令: {command_name}")
            print("可用命令:", ", ".join(self.command_registry.get_command_names()))
            return 1

        return await command.execute(args, self)

    def run(self, args: List[str]) -> int:
        """
        运行命令行命令。

        Args:
            args: 命令行参数列表

        Returns:
            int: 退出代码
        """
        if not args:
            # 无参数时运行交互模式
            return asyncio.run(self.execute_command("", []))

        command_name = args[0]
        command_args = args[1:] if len(args) > 1 else []

        return asyncio.run(self.execute_command(command_name, command_args))


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。

    Returns:
        argparse.Namespace: 解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="AI Webot - AI对话机器人命令行工具",
        add_help=False,
    )

    # 添加帮助选项
    parser.add_argument("-h", "--help", action="store_true", help="显示帮助信息")

    # 日志选项
    parser.add_argument(
        "-l",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
        help="设置日志级别 (默认: WARNING)",
    )

    parser.add_argument("--log-file", help="将日志输出到文件")

    # 剩余参数（命令）
    parser.add_argument("command", nargs="*", help="命令和参数")

    return parser.parse_args()


def setup_user_logging(level: str, log_file: Optional[str] = None) -> None:
    """
    为用户配置日志。

    Args:
        level: 日志级别
        log_file: 日志文件路径
    """
    level_num = getattr(logging, level.upper(), logging.WARNING)

    if log_file:
        logging.basicConfig(
            level=level_num,
            format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s",
            filename=log_file,
            filemode="a",
        )
    else:
        logging.basicConfig(
            level=level_num,
            format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s",
        )

    # 设置第三方库的日志级别
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def main():
    """命令行主函数。"""
    # 解析参数
    args = parse_args()

    # 处理帮助
    if args.help:
        cli = CLI()
        cli.command_registry.get_command("help").print_help()
        return

    # 用户决定是否配置日志
    if args.log_level != "WARNING" or args.log_file:
        setup_user_logging(args.log_level, args.log_file)

    logger.debug("命令行参数: %s", args)

    # 创建CLI实例并执行命令
    cli = CLI(log_level=args.log_level)

    try:
        exit_code = cli.run(args.command)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        print("\n再见!")
        sys.exit(0)
    except Exception as e:
        logger.critical("程序异常退出: %s", e, exc_info=True)
        print(f"程序异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
