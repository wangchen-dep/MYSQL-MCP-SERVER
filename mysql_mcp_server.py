#!/usr/bin/env python3
"""
MySQL MCP Server (SSE)

A Model Context Protocol (MCP) server for MySQL database operations.
Provides tools for querying, schema inspection, and database management.
Uses SSE (Server-Sent Events) for remote HTTP connections.
"""

import asyncio
import logging
from typing import Any, Optional
import json

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn

from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource, LoggingLevel
import pymysql
from pymysql.cursors import DictCursor

from config import DatabaseConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mysql-mcp-server")

# Create MCP server instance
app = Server("mysql-mcp-server")


class MySQLConnection:
    """MySQL connection manager with connection pooling."""

    def __init__(self):
        self.config = DatabaseConfig.get_connection_params()
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection."""
        if not self.conn or not self.conn.open:
            try:
                self.conn = pymysql.connect(**self.config)
                self.cursor = self.conn.cursor(DictCursor)
                logger.info("Connected to MySQL database")
            except pymysql.Error as e:
                logger.error(f"Failed to connect to MySQL: {e}")
                raise

    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.conn and self.conn.open:
            self.conn.close()
            self.conn = None
            logger.info("Closed MySQL connection")

    def execute_query(self, sql: str, params: tuple = None) -> list:
        """Execute a SELECT query and return results."""
        self.connect()
        try:
            logger.info(f"Executing query: {sql} with params: {params}")
            self.cursor.execute(sql, params or ())
            results = self.cursor.fetchall()
            return results
        except pymysql.Error as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def execute_update(self, sql: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        self.connect()
        try:
            affected_rows = self.cursor.execute(sql, params or ())
            self.conn.commit()
            return affected_rows
        except pymysql.Error as e:
            self.conn.rollback()
            logger.error(f"Update execution failed: {e}")
            raise

    def execute_procedure(
        self, procedure_sql: str, call_params: list = None, cleanup: bool = True
    ) -> dict:
        """Execute a stored procedure from full CREATE PROCEDURE statement.

        Args:
            procedure_sql: Full CREATE PROCEDURE statement
            call_params: Parameters to pass when calling the procedure (optional)
            cleanup: Whether to drop the procedure after execution (default: True)

        Returns:
            dict with affected_rows, result_sets, and result_count
        """
        self.connect()
        procedure_name = None

        try:
            # Extract procedure name from CREATE PROCEDURE statement
            import re

            match = re.search(
                r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+`?([\w]+)`?\s*\(",
                procedure_sql,
                re.IGNORECASE,
            )
            if not match:
                raise ValueError(
                    "Invalid CREATE PROCEDURE statement: cannot extract procedure name"
                )

            procedure_name = match.group(1)
            logger.info(f"Extracted procedure name: {procedure_name}")

            # Drop procedure if exists
            try:
                drop_sql = f"DROP PROCEDURE IF EXISTS `{procedure_name}`"
                self.cursor.execute(drop_sql)
                logger.info(f"Dropped existing procedure: {procedure_name}")
            except pymysql.Error as e:
                logger.warning(f"Failed to drop procedure: {e}")

            # Create the procedure
            self.cursor.execute(procedure_sql)
            self.conn.commit()
            logger.info(f"Created procedure: {procedure_name}")

            # Call the procedure
            if call_params:
                placeholders = ", ".join(["%s"] * len(call_params))
                call_sql = f"CALL `{procedure_name}`({placeholders})"
                affected_rows = self.cursor.execute(call_sql, tuple(call_params))
            else:
                call_sql = f"CALL `{procedure_name}`()"
                affected_rows = self.cursor.execute(call_sql)

            logger.info(f"Called procedure: {call_sql}")

            # Fetch all result sets
            results = []
            try:
                # Get the first result set
                result_set = self.cursor.fetchall()
                if result_set:
                    results.append(result_set)

                # Get additional result sets if any
                while self.cursor.nextset():
                    result_set = self.cursor.fetchall()
                    if result_set:
                        results.append(result_set)
            except Exception:
                # No result set to fetch
                pass

            self.conn.commit()

            return {
                "affected_rows": affected_rows,
                "result_sets": results,
                "result_count": len(results),
                "procedure_name": procedure_name,
            }

        except pymysql.Error as e:
            self.conn.rollback()
            logger.error(f"Procedure execution failed: {e}")
            raise
        finally:
            # Clean up: drop the procedure if requested
            if cleanup and procedure_name:
                try:
                    drop_sql = f"DROP PROCEDURE IF EXISTS `{procedure_name}`"
                    self.cursor.execute(drop_sql)
                    self.conn.commit()
                    logger.info(f"Cleaned up procedure: {procedure_name}")
                except pymysql.Error as e:
                    logger.warning(f"Failed to cleanup procedure: {e}")


# Global connection instance
db = MySQLConnection()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MySQL tools."""
    return [
        Tool(
            name="query",
            description="执行 MySQL 的 SELECT 查询。返回查询结果的 JSON 数组。支持可选参数化查询。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 SELECT 语句。",
                    },
                    "params": {
                        "type": "array",
                        "description": "SQL 参数列表（用于预处理语句）。",
                        "items": {"type": "string"},
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="execute",
            description="执行 INSERT、UPDATE 或 DELETE 语句（不支持 SELECT）。返回受影响的行数。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 INSERT/UPDATE/DELETE 语句。",
                    },
                    "params": {
                        "type": "array",
                        "description": "SQL 参数列表（用于预处理语句）。",
                        "items": {"type": "string"},
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="list_tables",
            description="列出 MySQL 服务器中所有非系统数据库的所有表，并按数据库进行分组。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="describe_table",
            description="获取指定表的结构信息，包括字段、类型、约束等。支持 'database.table' 格式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "要描述的表名，支持 'database.table' 格式。",
                    }
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="get_table_info",
            description="获取指定表的详细信息，包括行数、大小、创建时间等。支持 'database.table' 格式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名，支持 'database.table' 格式。",
                    }
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="list_databases",
            description="列出 MySQL 服务器中所有可用的数据库（不包含系统库）。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="show_create_table",
            description="返回指定表的 CREATE TABLE 语句。支持 'database.table' 格式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名，支持 'database.table' 格式。",
                    }
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="get_table_indexes",
            description="获取指定表的所有索引定义，包括主键、唯一索引和普通索引等。支持 'database.table' 格式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名，支持 'database.table' 格式。",
                    }
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="validate_query",
            description="使用 EXPLAIN 校验 SQL 语句是否有效（只检查语法，不执行查询）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要校验的 SQL 语句。",
                    }
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="execute_procedure",
            description="执行完整的存储过程。传入完整的 CREATE PROCEDURE 语句，系统会自动创建、执行并清理该存储过程。支持返回多个结果集。",
            inputSchema={
                "type": "object",
                "properties": {
                    "procedure_sql": {
                        "type": "string",
                        "description": "完整的 CREATE PROCEDURE 语句，例如：CREATE PROCEDURE test_proc() BEGIN SELECT * FROM users; END",
                    },
                    "call_params": {
                        "type": "array",
                        "description": "调用存储过程时传入的参数列表（可选）。",
                        "items": {"type": "string"},
                    },
                    "cleanup": {
                        "type": "boolean",
                        "description": "执行后是否删除该存储过程（默认为 true）。",
                        "default": True,
                    },
                },
                "required": ["procedure_sql"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution requests."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    # Extract SQL for error reporting
    sql = arguments.get("sql", "")
    table_name = arguments.get("table_name", "")

    try:
        if name == "query":
            sql = arguments.get("sql")
            params = tuple(arguments.get("params", []))

            if not sql:
                raise ValueError("SQL query is required")

            # Ensure it's a SELECT query
            if not sql.strip().upper().startswith("SELECT"):
                raise ValueError("Only SELECT queries are allowed for 'query' tool")

            results = db.execute_query(sql, params if params else None)

            response_data = {
                "executeSql": sql,
                "success": True,
                "rowCount": len(results),
                "execute_result_data": results,
            }
            response_text = json.dumps(
                response_data, indent=2, ensure_ascii=False, default=str
            )
            logger.info(f"Query tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "execute":
            sql = arguments.get("sql")
            params = tuple(arguments.get("params", []))

            if not sql:
                raise ValueError("SQL query is required")

            # Ensure it's not a SELECT query
            sql_upper = sql.strip().upper()
            if sql_upper.startswith("SELECT"):
                raise ValueError("Use 'query' tool for SELECT statements")

            # Only allow INSERT, UPDATE, DELETE
            if not any(
                sql_upper.startswith(cmd) for cmd in ["INSERT", "UPDATE", "DELETE"]
            ):
                raise ValueError("Only INSERT, UPDATE, DELETE queries are allowed")

            affected_rows = db.execute_update(sql, params if params else None)

            response_data = {
                "executeSql": sql,
                "success": True,
                "execute_result_affectedRows": affected_rows,
                "message": f"Successfully affected {affected_rows} row(s)",
            }
            response_text = json.dumps(response_data, indent=2)
            logger.info(f"Execute tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "list_tables":
            # Query all tables from all databases using information_schema
            sql = """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            results = db.execute_query(sql)

            # Group tables by database
            tables_by_db = {}
            total_tables = 0
            for row in results:
                db_name = row["TABLE_SCHEMA"]
                table_name = row["TABLE_NAME"]
                if db_name not in tables_by_db:
                    tables_by_db[db_name] = []
                tables_by_db[db_name].append(table_name)
                total_tables += 1

            response_data = {
                "executeSql": sql,
                "success": True,
                "databaseCount": len(tables_by_db),
                "totalTableCount": total_tables,
                "execute_result_tablesByDatabase": tables_by_db,
            }
            response_text = json.dumps(response_data, indent=2, ensure_ascii=False)
            logger.info(f"List tables tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "describe_table":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")

            # Support database.table format
            if "." in table_name:
                parts = table_name.split(".", 1)
                sql = f"DESCRIBE `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"DESCRIBE `{table_name}`"

            results = db.execute_query(sql)

            response_data = {
                "executeSql": sql,
                "success": True,
                "table": table_name,
                "execute_result_columns": results,
            }
            response_text = json.dumps(response_data, indent=2, ensure_ascii=False)
            logger.info(f"Describe table tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "get_table_info":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")

            # Support database.table format
            if "." in table_name:
                parts = table_name.split(".", 1)
                db_name = parts[0]
                actual_table_name = parts[1]
            else:
                db_name = db.config.get("database")
                actual_table_name = table_name

            sql = """
                SELECT 
                    TABLE_NAME,
                    ENGINE,
                    TABLE_ROWS,
                    AVG_ROW_LENGTH,
                    DATA_LENGTH,
                    INDEX_LENGTH,
                    CREATE_TIME,
                    UPDATE_TIME,
                    TABLE_COLLATION,
                    TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """
            results = db.execute_query(sql, (db_name, actual_table_name))

            if not results:
                raise ValueError(f"Table '{table_name}' not found")

            response_data = {
                "executeSql": sql,
                "success": True,
                "execute_result_tableInfo": results[0],
            }
            response_text = json.dumps(
                response_data, indent=2, ensure_ascii=False, default=str
            )
            logger.info(f"Get table info tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "list_databases":
            sql = "SHOW DATABASES"
            results = db.execute_query(sql)

            databases = [row["Database"] for row in results]

            response_data = {
                "executeSql": sql,
                "success": True,
                "databaseCount": len(databases),
                "execute_result_databases": databases,
            }
            response_text = json.dumps(response_data, indent=2)
            logger.info(f"List databases tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "show_create_table":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")

            # Support database.table format
            if "." in table_name:
                parts = table_name.split(".", 1)
                sql = f"SHOW CREATE TABLE `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"SHOW CREATE TABLE `{table_name}`"

            results = db.execute_query(sql)

            if results:
                create_statement = results[0].get("Create Table", "")
                response_data = {
                    "executeSql": sql,
                    "success": True,
                    "table": table_name,
                    "execute_result_createStatement": create_statement,
                }
                response_text = json.dumps(response_data, indent=2)
                logger.info(f"Show create table tool response: {response_text}")

                return [TextContent(type="text", text=response_text)]
            else:
                raise ValueError(f"Table '{table_name}' not found")

        elif name == "get_table_indexes":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")

            # Support database.table format
            if "." in table_name:
                parts = table_name.split(".", 1)
                sql = f"SHOW INDEX FROM `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"SHOW INDEX FROM `{table_name}`"

            results = db.execute_query(sql)

            response_data = {
                "executeSql": sql,
                "success": True,
                "table": table_name,
                "execute_result_indexes": results,
            }
            response_text = json.dumps(response_data, indent=2, ensure_ascii=False)
            logger.info(f"Get table indexes tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        elif name == "validate_query":
            sql = arguments.get("sql")
            if not sql:
                raise ValueError("SQL query is required")

            # Use EXPLAIN to validate the query
            try:
                if sql.strip().upper().startswith("SELECT"):
                    explain_sql = f"EXPLAIN {sql}"
                    results = db.execute_query(explain_sql)

                    response_data = {
                        "executeSql": sql,
                        "success": True,
                        "valid": True,
                        "message": "Query is valid",
                        "execute_result_explainPlan": results,
                    }
                    response_text = json.dumps(
                        response_data, indent=2, ensure_ascii=False
                    )
                    logger.info(
                        f"Validate query tool response (SELECT): {response_text}"
                    )

                    return [TextContent(type="text", text=response_text)]
                else:
                    response_data = {
                        "executeSql": sql,
                        "success": True,
                        "valid": True,
                        "execute_result_message": "Query syntax appears valid (non-SELECT queries cannot be fully validated without execution)",
                    }
                    response_text = json.dumps(response_data, indent=2)
                    logger.info(
                        f"Validate query tool response (non-SELECT): {response_text}"
                    )

                    return [TextContent(type="text", text=response_text)]
            except pymysql.Error as e:
                response_data = {
                    "executeSql": sql,
                    "success": False,
                    "valid": False,
                    "execute_result_error": str(e),
                }
                response_text = json.dumps(response_data, indent=2)
                logger.info(f"Validate query tool response (error): {response_text}")

                return [TextContent(type="text", text=response_text)]

        elif name == "execute_procedure":
            procedure_sql = arguments.get("procedure_sql")
            call_params = arguments.get("call_params", [])
            cleanup = arguments.get("cleanup", True)

            if not procedure_sql:
                raise ValueError("procedure_sql is required")

            # Ensure it's a CREATE PROCEDURE statement
            sql_upper = procedure_sql.strip().upper()
            if not sql_upper.startswith("CREATE"):
                raise ValueError(
                    "Only CREATE PROCEDURE statements are allowed for 'execute_procedure' tool"
                )

            result = db.execute_procedure(procedure_sql, call_params, cleanup)

            response_data = {
                "executeSql": procedure_sql,
                "procedureName": result["procedure_name"],
                "success": True,
                "affectedRows": result["affected_rows"],
                "resultSetCount": result["result_count"],
                "execute_result_data": result["result_sets"],
                "cleaned": cleanup,
            }

            # Add a human-readable message
            if result["result_count"] > 0:
                total_rows = sum(len(rs) for rs in result["result_sets"])
                response_data["message"] = (
                    f"Procedure '{result['procedure_name']}' executed successfully. Returned {result['result_count']} result set(s) with {total_rows} total row(s)."
                )
            else:
                response_data["message"] = (
                    f"Procedure '{result['procedure_name']}' executed successfully. Affected {result['affected_rows']} row(s)."
                )

            if cleanup:
                response_data["message"] += " Procedure has been cleaned up."

            response_text = json.dumps(
                response_data, indent=2, ensure_ascii=False, default=str
            )
            logger.info(f"Execute procedure tool response: {response_text}")

            return [TextContent(type="text", text=response_text)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Tool execution error: {e}")

        # Build error response with executeSql if available
        response_data = {"success": False, "error": str(e)}

        # Add executeSql field for tools that use SQL
        if sql:
            response_data["executeSql"] = sql
        elif table_name:
            # For table operations, construct the SQL that would have been executed
            if name == "describe_table":
                if "." in table_name:
                    parts = table_name.split(".", 1)
                    response_data["executeSql"] = f"DESCRIBE `{parts[0]}`.`{parts[1]}`"
                else:
                    response_data["executeSql"] = f"DESCRIBE `{table_name}`"
            elif name == "show_create_table":
                if "." in table_name:
                    parts = table_name.split(".", 1)
                    response_data["executeSql"] = (
                        f"SHOW CREATE TABLE `{parts[0]}`.`{parts[1]}`"
                    )
                else:
                    response_data["executeSql"] = f"SHOW CREATE TABLE `{table_name}`"
            elif name == "get_table_indexes":
                if "." in table_name:
                    parts = table_name.split(".", 1)
                    response_data["executeSql"] = (
                        f"SHOW INDEX FROM `{parts[0]}`.`{parts[1]}`"
                    )
                else:
                    response_data["executeSql"] = f"SHOW INDEX FROM `{table_name}`"

        response_text = json.dumps(response_data, indent=2)
        logger.info(f"Tool error response: {response_text}")

        return [TextContent(type="text", text=response_text)]


def create_app() -> Starlette:
    """Create and configure the Starlette application."""

    # Create SSE transport with the message endpoint (must have trailing slash)
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        """
        Handle SSE connection endpoint.
        This establishes the SSE stream for server-to-client communication.
        """
        logger.info(f"New SSE connection from {request.client.host}")

        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            try:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )
            except Exception as e:
                logger.error(f"Error in SSE connection: {e}")
                raise

        # Must return Response to avoid NoneType error
        return Response()

    # Create Starlette app with routes
    # Note: Mount path must match the endpoint in SseServerTransport
    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    return starlette_app


async def main():
    """Main entry point for the SSE MCP server."""
    logger.info("=" * 60)
    logger.info("Starting MySQL MCP Server (SSE Mode)")
    logger.info("=" * 60)

    # Display configuration
    config = DatabaseConfig.display_config()
    logger.info(f"Database: {config}")

    # Get configuration
    host = "0.0.0.0"
    port = 17110

    logger.info(f"Server URL: http://{host}:{port}")
    logger.info(f"SSE Endpoint: http://{host}:{port}/sse")
    logger.info(f"Messages Endpoint: http://{host}:{port}/messages/")
    logger.info("=" * 60)

    # Create and run the server
    starlette_app = create_app()

    config_uvicorn = uvicorn.Config(
        starlette_app, host=host, port=port, log_level="info"
    )

    server = uvicorn.Server(config_uvicorn)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    finally:
        db.close()
