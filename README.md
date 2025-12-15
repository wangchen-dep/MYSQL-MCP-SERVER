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
- 🔄 **存储过程**: 创建、执行和管理存储过程

## 📦 系统要求

- Python 3.7+
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

创建 `.env` 文件并配置数据库连接：

```env
DB_IP=10.1.248.47
DB_PORT=6677
DB_NAME=upc
DB_PASSWD=upcpcm
DB_DATABASE=base
```

或者修改 `config.py` 文件中的默认值：

```python
class DatabaseConfig:
    # Database connection parameters
    DB_IP = os.getenv('DB_IP', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'your_username')
    DB_PASSWD = os.getenv('DB_PASSWD', 'your_password')
    DB_DATABASE = os.getenv('DB_DATABASE', 'your_database')
```

## ⚙️ 配置说明

### 服务器配置

在 `mysql_mcp_server.py` 中可以修改以下配置：

```python
# 服务器监听地址
host = "0.0.0.0"  # 监听所有网络接口
port = 17110      # 服务端口 (注意端口可能与原README不同)

# 日志级别
logging.basicConfig(level=logging.INFO)
```

### 数据库配置

在 `.env` 文件中配置：

- `DB_IP`: 数据库主机地址
- `DB_PORT`: 数据库端口（默认 3306）
- `DB_NAME`: 数据库用户名
- `DB_PASSWD`: 数据库密码
- `DB_DATABASE`: 默认数据库名

## 🎯 使用指南

### 启动服务器

```bash
# 使用启动脚本 (推荐)
./start_mcp.sh

# 或者直接运行
python mysql_mcp_server.py
```

服务器启动后会显示：

```
============================================================
Starting MySQL MCP Server (SSE Mode)
============================================================
Database: {'host': '10.1.248.47', 'port': '6677', 'user': 'upc', 'password': 'up***', 'database': 'base'}
Server URL: http://0.0.0.0:17110
SSE Endpoint: http://0.0.0.0:17110/sse
Messages Endpoint: http://0.0.0.0:17110/messages/
============================================================
```

### 连接到服务器

客户端可以通过以下端点连接：

- **SSE 连接**: `GET http://localhost:17110/sse`
- **消息发送**: `POST http://localhost:17110/messages/`

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
  "params": [18]
}
```

**返回**:
```json
{
  "executeSql": "SELECT * FROM users WHERE age > %s",
  "success": true,
  "rowCount": 10,
  "execute_result_data": [...]
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
  "executeSql": "INSERT INTO users (name, email) VALUES (?, ?)",
  "success": true,
  "execute_result_affectedRows": 1,
  "message": "Successfully affected 1 row(s)"
}
```

### 3. list_tables - 列出所有表

列出所有数据库中的表（排除系统数据库）。

**返回**:
```json
{
  "executeSql": "SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES...",
  "success": true,
  "databaseCount": 3,
  "totalTableCount": 15,
  "execute_result_tablesByDatabase": {
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
  "executeSql": "DESCRIBE `users`",
  "success": true,
  "table": "users",
  "execute_result_columns": [
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
  "executeSql": "SELECT TABLE_NAME, ENGINE, TABLE_ROWS, ...",
  "success": true,
  "execute_result_tableInfo": {
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
  "executeSql": "SHOW DATABASES",
  "success": true,
  "databaseCount": 5,
  "execute_result_databases": ["db1", "db2", "db3"]
}
```

### 7. show_create_table - 查看建表语句

获取表的完整 CREATE TABLE 语句。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**返回**:
```json
{
  "executeSql": "SHOW CREATE TABLE `users`",
  "success": true,
  "table": "users",
  "execute_result_createStatement": "CREATE TABLE `users` (\n  `id` int(11) NOT NULL AUTO_INCREMENT,\n  ..."
}
```

### 8. get_table_indexes - 查看表索引

获取表上定义的所有索引信息。

**参数**:
- `table_name` (必需): 表名，支持 `database.table` 格式

**返回**:
```json
{
  "executeSql": "SHOW INDEX FROM `users`",
  "success": true,
  "table": "users",
  "execute_result_indexes": [
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
  "executeSql": "SELECT * FROM users",
  "success": true,
  "valid": true,
  "message": "Query is valid",
  "execute_result_explainPlan": [...]
}
```

### 10. execute_procedure - 执行存储过程

创建、执行并清理存储过程。这是本服务器的一个特色功能。

**参数**:
- `procedure_sql` (必需): 完整的 CREATE PROCEDURE 语句
- `call_params` (可选): 调用存储过程时的参数列表
- `cleanup` (可选): 执行后是否删除存储过程（默认 true）

**示例**:
```json
{
  "procedure_sql": "CREATE PROCEDURE GetUserById(IN userId INT) BEGIN SELECT * FROM users WHERE id = userId; END",
  "call_params": [123],
  "cleanup": true
}
```

**返回**:
```json
{
  "executeSql": "CREATE PROCEDURE GetUserById(IN userId INT) BEGIN SELECT * FROM users WHERE id = userId; END",
  "procedureName": "GetUserById",
  "success": true,
  "affectedRows": -1,
  "resultSetCount": 1,
  "execute_result_data": [[{"id": 123, "name": "John", "email": "john@example.com"}]],
  "cleaned": true,
  "message": "Procedure 'GetUserById' executed successfully. Returned 1 result set(s) with 1 total row(s). Procedure has been cleaned up."
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
     "params": [123]
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

## 🔄 存储过程功能详解

MySQL MCP Server 提供了独特的存储过程执行功能，无需预先在数据库中创建存储过程即可执行。

### 工作原理

1. 接收完整的 CREATE PROCEDURE 语句
2. 自动创建临时存储过程
3. 执行存储过程
4. 获取所有结果集
5. 根据配置自动清理存储过程

### 特色功能

- **零污染**: 自动清理机制确保不会在数据库中留下临时对象
- **多结果集**: 完整支持存储过程返回的多个结果集
- **参数化调用**: 支持带参数的存储过程调用
- **灵活控制**: 可选择是否清理存储过程

### 使用场景

1. 复杂的数据处理任务
2. 需要事务控制的操作
3. 批量数据导入导出
4. 复杂业务逻辑封装

### 示例

```json
{
  "name": "execute_procedure",
  "arguments": {
    "procedure_sql": "CREATE PROCEDURE UpdateUserStatus(IN userId INT, IN newStatus VARCHAR(50)) BEGIN UPDATE users SET status = newStatus WHERE id = userId; SELECT ROW_COUNT() as affected_rows; END",
    "call_params": [123, "active"]
  }
}
```

[添加联系方式] wx: ChenChen_Maerjing
