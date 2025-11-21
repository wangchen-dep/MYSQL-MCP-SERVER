# MySQL MCP Server

一个基于 Model Context Protocol (MCP) 的 MySQL 数据库操作服务器，使用 SSE (Server-Sent Events) 提供远程 HTTP 连接支持。

## 📋 目录

- [功能特性](#功能特性)
- [系统要求](#系统要求)
- [安装步骤](#安装步骤)
- [配置说明](#配置说明)
- [使用指南](#使用指南)
- [可用工具](#可用工具)
- [API 端点](#api-端点)
- [开发指南](#开发指南)

## ✨ 功能特性

- 🔍 **查询执行**: 执行 SELECT 查询并返回 JSON 格式结果
- ✏️ **数据修改**: 支持 INSERT、UPDATE、DELETE 操作
- 📊 **数据库管理**: 列出所有数据库和表
- 🔎 **架构检查**: 查看表结构、索引和创建语句
- ✅ **查询验证**: 在执行前验证 SQL 语法
- 🌐 **远程访问**: 通过 HTTP/SSE 提供远程连接
- 🔒 **安全性**: 参数化查询防止 SQL 注入

## 📦 系统要求

- Python 3.11+
- MySQL 5.7+ 或 MariaDB 10.3+
- 网络连接（用于远程访问）

## 🚀 安装步骤

### 1. 克隆仓库

```bash
git clone <repository-url>
cd mysql-mcp-server
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包：
- `mcp` - Model Context Protocol 核心库
- `pymysql` - MySQL 数据库驱动
- `starlette` - ASGI Web 框架
- `uvicorn` - ASGI 服务器

### 3. 配置数据库

创建 `config.py` 文件并配置数据库连接：

```python
class DatabaseConfig:
    @staticmethod
    def get_connection_params():
        return {
            'host': 'localhost',
            'port': 3306,
            'user': 'your_username',
            'password': 'your_password',
            'database': 'your_database',
            'charset': 'utf8mb4',
            'cursorclass': 'DictCursor'
        }
    
    @staticmethod
    def display_config():
        config = DatabaseConfig.get_connection_params()
        return f"{config['user']}@{config['host']}:{config['port']}/{config['database']}"
```

## ⚙️ 配置说明

### 服务器配置

在 `mysql_mcp_server.py` 中可以修改以下配置：

```python
# 服务器监听地址
host = "0.0.0.0"  # 监听所有网络接口
port = 17109      # 服务端口

# 日志级别
logging.basicConfig(level=logging.INFO)
```

### 数据库配置

在 `config.py` 中配置：

- `host`: 数据库主机地址
- `port`: 数据库端口（默认 3306）
- `user`: 数据库用户名
- `password`: 数据库密码
- `database`: 默认数据库名
- `charset`: 字符编码（推荐 utf8mb4）

## 🎯 使用指南

### 启动服务器

```bash
python mysql_mcp_server.py
```

服务器启动后会显示：

```
============================================================
Starting MySQL MCP Server (SSE Mode)
============================================================
Database: user@localhost:3306/database
Server URL: http://0.0.0.0:17109
SSE Endpoint: http://0.0.0.0:17109/sse
Messages Endpoint: http://0.0.0.0:17109/messages/
============================================================
```

### 连接到服务器

客户端可以通过以下端点连接：

- **SSE 连接**: `GET http://localhost:17109/sse`
- **消息发送**: `POST http://localhost:17109/messages/`

## 🛠️ 可用工具

### 1. query - 查询数据

执行 SELECT 查询并返回结果。

**参数**:
- `sql` (必需): SQL SELECT 查询语句
- `params` (可选): 参数化查询的参数数组

**示例**:
```json
{
  "sql": "SELECT * FROM users WHERE age > %s",
  "params": ["18"]
}
```

**返回**:
```json
{
  "success": true,
  "rowCount": 10,
  "data": [...]
}
```

### 2. execute - 执行修改操作

执行 INSERT、UPDATE 或 DELETE 操作。

**参数**:
- `sql` (必需): SQL 修改语句
- `params` (可选): 参数化查询的参数数组

**示例**:
```json
{
  "sql": "INSERT INTO users (name, email) VALUES (%s, %s)",
  "params": ["John Doe", "john@example.com"]
}
```

**返回**:
```json
{
  "success": true,
  "affectedRows": 1,
  "message": "Successfully affected 1 row(s)"
}
```

### 3. list_tables - 列出所有表

列出所有数据库中的表（排除系统数据库）。

**返回**:
```json
{
  "success": true,
  "databaseCount": 3,
  "totalTableCount": 15,
  "tablesByDatabase": {
    "db1": ["users", "orders"],
    "db2": ["products"]
  }
}
```

### 4. describe_table - 查看表结构

获取表的列信息、类型和约束。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**示例**:
```json
{
  "table_name": "users"
}
```
或跨数据库：
```json
{
  "table_name": "other_db.products"
}
```

**返回**:
```json
{
  "success": true,
  "table": "users",
  "columns": [
    {
      "Field": "id",
      "Type": "int(11)",
      "Null": "NO",
      "Key": "PRI",
      "Default": null,
      "Extra": "auto_increment"
    }
  ]
}
```

### 5. get_table_info - 获取表详细信息

获取表的统计信息，包括行数、大小、创建时间等。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**返回**:
```json
{
  "success": true,
  "tableInfo": {
    "TABLE_NAME": "users",
    "ENGINE": "InnoDB",
    "TABLE_ROWS": 1000,
    "DATA_LENGTH": 16384,
    "INDEX_LENGTH": 8192,
    "CREATE_TIME": "2024-01-01 00:00:00",
    "TABLE_COMMENT": "User information table"
  }
}
```

### 6. list_databases - 列出所有数据库

列出 MySQL 服务器上的所有数据库。

**返回**:
```json
{
  "success": true,
  "databaseCount": 5,
  "databases": ["db1", "db2", "db3"]
}
```

### 7. show_create_table - 查看建表语句

获取表的完整 CREATE TABLE 语句。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**返回**:
```json
{
  "success": true,
  "table": "users",
  "createStatement": "CREATE TABLE `users` (\n  `id` int(11) NOT NULL AUTO_INCREMENT,\n  ..."
}
```

### 8. get_table_indexes - 查看表索引

获取表上定义的所有索引信息。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**返回**:
```json
{
  "success": true,
  "table": "users",
  "indexes": [
    {
      "Table": "users",
      "Key_name": "PRIMARY",
      "Column_name": "id",
      "Index_type": "BTREE"
    }
  ]
}
```

### 9. validate_query - 验证查询语法

在不执行的情况下验证 SQL 查询语法。

**参数**:
- `sql` (必需): 要验证的 SQL 语句

**返回**:
```json
{
  "success": true,
  "valid": true,
  "message": "Query is valid",
  "explainPlan": [...]
}
```

## 🔌 API 端点

### GET /sse

建立 Server-Sent Events 连接，用于接收服务器推送的消息。

**响应**: 持续的 SSE 事件流

### POST /messages/

发送 MCP 协议消息到服务器。

**请求头**:
- `Content-Type: application/json`

**请求体**: MCP 协议消息

## 🔒 安全注意事项

1. **参数化查询**: 始终使用参数化查询防止 SQL 注入
   ```json
   {
     "sql": "SELECT * FROM users WHERE id = %s",
     "params": ["123"]
   }
   ```

2. **查询类型限制**: 
   - `query` 工具只接受 SELECT 语句
   - `execute` 工具只接受 INSERT/UPDATE/DELETE 语句

3. **网络安全**:
   - 在生产环境中使用 HTTPS
   - 配置防火墙限制访问
   - 使用强密码和访问控制

4. **数据库权限**: 
   - 为服务器创建专用数据库用户
   - 仅授予必要的权限

## 🐛 错误处理

所有工具在出错时返回统一的错误格式：

```json
{
  "success": false,
  "error": "错误描述信息"
}
```

常见错误：
- 数据库连接失败
- SQL 语法错误
- 权限不足
- 表不存在
- 参数缺失

## 📝 开发指南

### 添加新工具

1. 在 `list_tools()` 中定义工具元数据：
```python
Tool(
    name="my_tool",
    description="工具描述",
    inputSchema={
        "type": "object",
        "properties": {...},
        "required": [...]
    }
)
```

2. 在 `call_tool()` 中实现工具逻辑：
```python
elif name == "my_tool":
    # 实现逻辑
    return [TextContent(type="text", text=json.dumps(result))]
```

### 运行测试

```bash
# 运行单元测试
python -m pytest tests/

# 检查代码风格
python -m flake8 mysql_mcp_server.py
```

### 日志调试

调整日志级别以获取更多信息：

```python
logging.basicConfig(level=logging.DEBUG)
```

## 📄 许可证

[添加您的许可证信息]

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

[添加联系方式]