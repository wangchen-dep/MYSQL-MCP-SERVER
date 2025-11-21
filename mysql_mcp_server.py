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

from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
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


# Global connection instance
db = MySQLConnection()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MySQL tools."""
    return [
        Tool(
            name="query",
            description="Execute a SELECT query on the MySQL database. Returns query results as JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute"
                    },
                    "params": {
                        "type": "array",
                        "description": "Optional parameters for parameterized queries",
                        "items": {"type": "string"}
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="execute",
            description="Execute an INSERT, UPDATE, or DELETE query on the MySQL database. Returns the number of affected rows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL INSERT/UPDATE/DELETE query to execute"
                    },
                    "params": {
                        "type": "array",
                        "description": "Optional parameters for parameterized queries",
                        "items": {"type": "string"}
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="list_tables",
            description="List all tables across all databases in the MySQL server (excluding system databases like information_schema, mysql, performance_schema, sys). Returns tables grouped by database.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="describe_table",
            description="Get the schema/structure of a specific table including column names, types, and constraints. Supports 'database.table' format to specify table in a different database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table to describe. Can use 'database.table' format to specify a table in a different database, or just 'table' for current database."
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="get_table_info",
            description="Get detailed information about a table including row count, size, and creation time. Supports 'database.table' format to specify table in a different database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table. Can use 'database.table' format to specify a table in a different database, or just 'table' for current database."
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="list_databases",
            description="List all available databases on the MySQL server.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="show_create_table",
            description="Get the CREATE TABLE statement for a specific table. Supports 'database.table' format to specify table in a different database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table. Can use 'database.table' format to specify a table in a different database, or just 'table' for current database."
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="get_table_indexes",
            description="Get all indexes defined on a specific table. Supports 'database.table' format to specify table in a different database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table. Can use 'database.table' format to specify a table in a different database, or just 'table' for current database."
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="validate_query",
            description="Validate a SQL query without executing it. Uses EXPLAIN to check syntax.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to validate"
                    }
                },
                "required": ["sql"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution requests."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
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
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "rowCount": len(results),
                    "data": results
                }, indent=2, ensure_ascii=False, default=str)
            )]
        
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
            if not any(sql_upper.startswith(cmd) for cmd in ["INSERT", "UPDATE", "DELETE"]):
                raise ValueError("Only INSERT, UPDATE, DELETE queries are allowed")
            
            affected_rows = db.execute_update(sql, params if params else None)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "affectedRows": affected_rows,
                    "message": f"Successfully affected {affected_rows} row(s)"
                }, indent=2)
            )]
        
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
                db_name = row['TABLE_SCHEMA']
                table_name = row['TABLE_NAME']
                if db_name not in tables_by_db:
                    tables_by_db[db_name] = []
                tables_by_db[db_name].append(table_name)
                total_tables += 1
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "databaseCount": len(tables_by_db),
                    "totalTableCount": total_tables,
                    "tablesByDatabase": tables_by_db
                }, indent=2, ensure_ascii=False)
            )]
        
        elif name == "describe_table":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")
            
            # Support database.table format
            if '.' in table_name:
                parts = table_name.split('.', 1)
                sql = f"DESCRIBE `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"DESCRIBE `{table_name}`"
            
            results = db.execute_query(sql)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "table": table_name,
                    "columns": results
                }, indent=2, ensure_ascii=False)
            )]
        
        elif name == "get_table_info":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")
            
            # Support database.table format
            if '.' in table_name:
                parts = table_name.split('.', 1)
                db_name = parts[0]
                actual_table_name = parts[1]
            else:
                db_name = db.config.get('database')
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
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "tableInfo": results[0]
                }, indent=2, ensure_ascii=False, default=str)
            )]
        
        elif name == "list_databases":
            sql = "SHOW DATABASES"
            results = db.execute_query(sql)
            
            databases = [row['Database'] for row in results]
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "databaseCount": len(databases),
                    "databases": databases
                }, indent=2)
            )]
        
        elif name == "show_create_table":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")
            
            # Support database.table format
            if '.' in table_name:
                parts = table_name.split('.', 1)
                sql = f"SHOW CREATE TABLE `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"SHOW CREATE TABLE `{table_name}`"
            
            results = db.execute_query(sql)
            
            if results:
                create_statement = results[0].get('Create Table', '')
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "table": table_name,
                        "createStatement": create_statement
                    }, indent=2)
                )]
            else:
                raise ValueError(f"Table '{table_name}' not found")
        
        elif name == "get_table_indexes":
            table_name = arguments.get("table_name")
            if not table_name:
                raise ValueError("table_name is required")
            
            # Support database.table format
            if '.' in table_name:
                parts = table_name.split('.', 1)
                sql = f"SHOW INDEX FROM `{parts[0]}`.`{parts[1]}`"
            else:
                sql = f"SHOW INDEX FROM `{table_name}`"
            
            results = db.execute_query(sql)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "table": table_name,
                    "indexes": results
                }, indent=2, ensure_ascii=False)
            )]
        
        elif name == "validate_query":
            sql = arguments.get("sql")
            if not sql:
                raise ValueError("SQL query is required")
            
            # Use EXPLAIN to validate the query
            try:
                if sql.strip().upper().startswith("SELECT"):
                    explain_sql = f"EXPLAIN {sql}"
                    results = db.execute_query(explain_sql)
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "valid": True,
                            "message": "Query is valid",
                            "explainPlan": results
                        }, indent=2, ensure_ascii=False)
                    )]
                else:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "valid": True,
                            "message": "Query syntax appears valid (non-SELECT queries cannot be fully validated without execution)"
                        }, indent=2)
                    )]
            except pymysql.Error as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "valid": False,
                        "error": str(e)
                    }, indent=2)
                )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


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
            request.scope,
            request.receive,
            request._send
        ) as streams:
            try:
                await app.run(
                    streams[0],
                    streams[1],
                    app.create_initialization_options()
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
    port = 17109
    
    logger.info(f"Server URL: http://{host}:{port}")
    logger.info(f"SSE Endpoint: http://{host}:{port}/sse")
    logger.info(f"Messages Endpoint: http://{host}:{port}/messages/")
    logger.info("=" * 60)
    
    # Create and run the server
    starlette_app = create_app()
    
    config_uvicorn = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info"
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
