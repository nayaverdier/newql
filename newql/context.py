from dataclasses import dataclass
from typing import Any, Dict, List, Union

from .parse import ParsedField, ParsedOperation


@dataclass
class ExecutionContext:
    operation: ParsedOperation
    variables: Dict[str, Any]
    current_field: ParsedField

    def __post_init__(self):
        self.errors: Dict[str, Any] = {}
        self.path: List[str] = []

    def push(self, field: ParsedField):
        self.current_field = field
        self.path.append(field.alias)

    def pop(self, field: ParsedField):
        assert field.alias == self.path.pop()

    def error(self, error: Union[str, Exception], field: ParsedField):
        location = self.errors
        for p in self.path[:-1]:
            location = location.setdefault(p, {})
        location[self.path[-1]] = str(error)

        self.pop(field)
