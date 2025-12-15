"""
MySQL MCP Server Configuration

Manages database connection settings for the MCP server.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


class DatabaseConfig:
    """Database configuration class with environment variable support."""
    
    # Database connection parameters
    DB_IP = os.getenv('DB_IP', '******')
    DB_PORT = os.getenv('DB_PORT', '****')
    DB_NAME = os.getenv('DB_NAME', '*******')
    DB_PASSWD = os.getenv('DB_PASSWD', '*******')
    DB_DATABASE = os.getenv('DB_DATABASE', '*****')
        
    @classmethod
    def get_connection_params(cls):
        """
        Get connection parameters as a dictionary for PyMySQL.
        
        Returns:
            Dictionary with connection parameters
        """
        from pymysql.cursors import DictCursor
        return {
            'host': cls.DB_IP,
            'port': int(cls.DB_PORT),
            'user': cls.DB_NAME,
            'password': cls.DB_PASSWD,
            'database': cls.DB_DATABASE,
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': False
        }
    
    @classmethod
    def display_config(cls):
        """Display current configuration (with masked password)."""
        masked_password = cls.DB_PASSWD[:2] + '*' * (len(cls.DB_PASSWD) - 2) if cls.DB_PASSWD else '***'
        return {
            'host': cls.DB_IP,
            'port': cls.DB_PORT,
            'user': cls.DB_NAME,
            'password': masked_password,
            'database': cls.DB_DATABASE
        }
