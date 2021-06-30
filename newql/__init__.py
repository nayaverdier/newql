from importlib import resources

from .context import ExecutionContext
from .errors import NewQLError, QueryError
from .field import Field, field
from .parse import ParsedEnum, ParsedField, ParsedOperation, ParsedVariable, parse_document, parse_query
from .schema import Schema

VERSION = resources.read_text("newql", "VERSION").strip()

__all__ = [
    "ExecutionContext",
    "Field",
    "NewQLError",
    "ParsedOperation",
    "ParsedEnum",
    "ParsedField",
    "ParsedVariable",
    "QueryError",
    "Schema",
    "VERSION",
    "field",
    "parse_document",
    "parse_query",
]
