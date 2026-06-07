# Add New Server

## 目录约定

在 `servers/<server_name>/` 下新增：

- `__init__.py`
- `server.py`
- `schemas.py`
- `README.md`

## 实现步骤

1. 在 `schemas.py` 中定义请求与响应模型，统一使用 Pydantic v2。
2. 在 `server.py` 中创建 `FastMCP` 实例并注册工具。
3. 在工具中复用 `shared.settings`、`shared.permissions`、`shared.errors`、`shared.logging`。
4. 在 `scripts/` 下增加运行入口。
5. 在 `tests/` 下增加 schema 或工具测试。
6. 在 `configs/mcp.example.json` 中添加 server 配置样例。

## 设计边界

- 一个 server 只处理一类能力。
- 返回值必须是 Pydantic schema，不返回裸 `dict`。
- 优先保证最小可运行，再考虑缓存、重试、鉴权和更复杂的抽象。
