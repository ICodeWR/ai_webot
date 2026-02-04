# 贡献指南

感谢您考虑为 AI Webot 项目做出贡献！本文档将指导您如何参与项目开发。

## 开发环境设置

### 1. 克隆仓库
```bash
git clone https://gitee.com/ai_webot.git
cd ai-webot
```

### 2. 安装依赖
```bash
# 安装 Poetry（如未安装）
curl -sSL https://install.python-poetry.org | python3 -

# 安装项目依赖
poetry install

# 安装开发依赖
poetry install --with dev

# 安装 Playwright 浏览器
poetry run playwright install chromium
```

### 3. 预提交钩子
```bash
# 安装预提交钩子
poetry run pre-commit install

# 手动运行所有检查
poetry run pre-commit run --all-files
```

## 代码规范

### Python 代码风格
- **格式化**: 使用 Black (`poetry run black .`)
- **导入排序**: 使用 isort (`poetry run isort .`)
- **类型注解**: 所有函数和方法都应有类型注解
- **行长度**: 最大 88 个字符

### 文档要求
- 所有公开的类、方法和函数都应有文档字符串
- 使用 Google 风格文档字符串格式
- 模块开头应有模块级文档字符串

### 测试要求
- 新功能必须包含单元测试
- 测试覆盖率不应降低
- 异步代码使用 `pytest-asyncio`

## 开发流程

### 1. 创建分支
```bash
git checkout -b feature/描述性名称
# 或
git checkout -b fix/问题描述
```

### 2. 实现功能
- 遵循现有代码架构
- 添加类型注解
- 编写文档字符串
- 添加单元测试

### 3. 运行测试
```bash
# 运行所有测试
poetry run pytest

# 运行特定测试
poetry run pytest tests/test_deepseek.py

# 检查代码质量
poetry run black --check .
poetry run isort --check-only .
poetry run flake8 ./src/
poetry run mypy ./src/
```

### 4. 提交更改
```bash
git add .
git commit -m "类型: 描述性提交信息"
```

**提交信息格式**：
- `feat:` 新功能
- `fix:` bug修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建过程或辅助工具

### 5. 创建 Pull Request
1. 推送分支到远程仓库
2. 在 Gitee 上创建 Pull Request
3. 填写 PR 描述模板
4. 等待代码审查

## 项目架构

### 核心模块
- `ai_webot/drivers/`: 浏览器驱动层
- `ai_webot/services/`: 服务层（配置、异常）
- `ai_webot/webot/`: 机器人实现层
- `ai_webot/api.py`: 公共API接口
- `ai_webot/cli.py`: 命令行接口

### 添加新的 AI 平台

1. **创建实现类**
   ```python
   # webot/newplatform/bot.py
   from ai_webot.webot.base.web_bot import WebBot
   
   class NewPlatformBot(WebBot):
       def requires_login(self) -> bool:
           """是否需要登录"""
           pass
       
       async def login(self) -> bool:
           """登录实现"""
           pass
       
       async def ensure_ready(self) -> bool:
           """确保就绪"""
           pass
   ```

2. **创建配置文件模板**
   - 参考现有平台的配置文件
   - 添加 `plugin` 字段指定实现类

3. **测试新平台**
   - 编写单元测试
   - 手动测试交互流程

## 测试指南

### 单元测试结构
```python
# tests/test_newplatform.py
import pytest
from ai_webot.webot.newplatform.bot import NewPlatformBot

@pytest.mark.asyncio
async def test_bot_initialization():
    """测试机器人初始化"""
    bot = NewPlatformBot(config)
    assert bot is not None

@pytest.mark.asyncio  
async def test_bot_login():
    """测试登录功能"""
    bot = NewPlatformBot(config)
    result = await bot.login()
    assert result in [True, False]
```

### 集成测试
```bash
# 运行集成测试（需要实际浏览器）
poetry run pytest tests/integration/ -v
```

## 文档更新

### 更新 README
- 新功能特性
- 使用示例
- API 变更

### 更新配置文档
- 新增配置选项
- 环境变量说明

### 编写教程
- 平台集成指南
- 常见问题解答

## 问题反馈

### Bug 报告
1. 在 Issues 中搜索是否已存在
2. 使用 Bug 报告模板
3. 提供重现步骤和日志

### 功能请求
1. 描述使用场景
2. 提供具体需求
3. 讨论实现方案

## 行为准则

- 尊重所有贡献者
- 建设性讨论技术问题
- 遵守开源协议和法律法规
- 不得提交恶意代码或后门

感谢您的贡献！