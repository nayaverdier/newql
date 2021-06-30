from enum import Enum
from functools import partial
from inspect import isclass
from typing import Any, Dict, Optional, TypeVar

from .context import ExecutionContext
from .errors import QueryError
from .field import Field
from .introspection import get_args, get_origin, introspect_type
from .parse import ParsedEnum, ParsedField, ParsedOperation, ParsedVariable, parse_query

SKIP_FIELD = object()


def _validate_variables(variables: Optional[Dict[str, Any]], operation: ParsedOperation) -> Dict[str, Any]:
    all_variables = operation.variable_defaults or {}
    all_variables.update(variables or {})

    operation_variables = set(operation.variables or ())

    unknown_variables = all_variables.keys() - operation_variables
    if unknown_variables:
        raise QueryError(f"Undefined variables provided: {sorted(unknown_variables)}")

    missing_variables = operation_variables - all_variables.keys()
    if missing_variables:
        raise QueryError(f"Required variables not provided: {sorted(missing_variables)}")

    return all_variables


def _resolve_result(context: ExecutionContext, field: type, requested_field: ParsedField, parent: Any):
    result = {}
    for subfield in requested_field.subfields or ():
        sub_value = _resolve_field(context, field, subfield, parent)
        if sub_value is not SKIP_FIELD:
            result[subfield.alias] = sub_value
    return result


def _is_subclass(t, parent: type) -> bool:
    return t and isclass(t) and issubclass(t, parent)


def _resolve_field(
    context: ExecutionContext,
    fields_class: type,
    requested_field: ParsedField,
    parent: Any = None,
):
    context.push(requested_field)
    field = getattr(fields_class, requested_field.name, None)
    if not isinstance(field, Field):
        context.error("Unknown field requested", requested_field)
        return SKIP_FIELD

    kwargs = requested_field.arguments or {}
    for argument, value in kwargs.items():
        if isinstance(value, ParsedVariable):
            kwargs[argument] = context.variables[value.name]
        elif isinstance(value, ParsedEnum):
            argument_type = field.args.get(argument)
            if _is_subclass(argument_type, Enum):
                # default to the stringified enum, if it does not exist as
                # an attribute on the Enum type
                kwargs[argument] = getattr(argument_type, value.name, value.name)

    try:
        resolved = field.resolver(parent, context, **kwargs)
    except Exception as e:
        context.error(e, requested_field)
        return None

    if resolved is None or not requested_field.subfields:
        context.pop(requested_field)
        return resolved

    field_type = field.field_type
    if field_type is list or get_origin(field_type) is list:
        list_args = get_args(field_type)
        if not list_args or isinstance(list_args[0], TypeVar):
            result = resolved
        else:
            item_type = list_args[0]
            item_resolver = partial(_resolve_result, context, item_type, requested_field)
            result = list(map(item_resolver, resolved))
    else:
        result = _resolve_result(context, field_type, requested_field, resolved)

    context.pop(requested_field)
    return result


class Schema:
    def __init__(self, query_class: type = None, mutation_class: type = None):
        self.query = query_class
        self.mutation = mutation_class

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None, operation_name: str = None):
        try:
            operation = parse_query(query, operation_name)
        except Exception as e:
            # The default introspection query in GraphiQL has fragments
            # which NewQL doesn't support, so fallback to check for __schema
            # and just return the introspection if suspected
            if "__schema" in query:
                operation = parse_query("{ __schema }")
            else:
                return {"data": None, "errors": str(e)}

        operation_class = getattr(self, operation.operation)
        if operation_class is None:
            raise QueryError(f"Operation '{operation.operation}' is not defined for this schema")

        fixed_variables = _validate_variables(variables, operation)

        context = ExecutionContext(operation, fixed_variables, None)  # type: ignore
        resolved = {}
        for requested_field in operation.fields:
            # if __schema is present, just return the entire introspection
            # (mostly just used for the GraphiQL intrgration)
            if requested_field.name == "__schema":
                value = self.introspect()
            else:
                value = _resolve_field(context, operation_class, requested_field)
            if value is not SKIP_FIELD:
                resolved[requested_field.alias] = value

        result: dict = {"data": resolved}
        if context.errors:
            result["errors"] = context.errors
        return result

    def _introspect(self, t: Optional[type], types_by_class: dict, types_by_name: dict) -> Optional[dict]:
        if t is None:
            return None

        introspected = introspect_type(t, types_by_class, types_by_name, is_operation=True)
        if not introspected:
            return None

        return {"name": introspected["name"]}

    def introspect(self):
        types_by_class = {}
        types_by_name = {}

        return {
            "queryType": self._introspect(self.query, types_by_class, types_by_name),
            "mutationType": self._introspect(self.mutation, types_by_class, types_by_name),
            "types": list(types_by_name.values()),
        }
