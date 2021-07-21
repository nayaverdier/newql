from functools import partial
from typing import Any, Dict, Optional, TypeVar

from .context import ExecutionContext
from .errors import QueryError
from .field import Field
from .introspection import check_list, check_optional, get_list_type, introspect_type
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


def _resolve_arguments(context: ExecutionContext, data, arg_type):
    # TODO: make sure this holds up for deeply nested dict/list/optional argument types

    arg_type, _ = check_optional(arg_type)

    if isinstance(data, dict):
        return {key: _resolve_arguments(context, value, arg_type[key]) for key, value in data.items()}
    elif isinstance(data, list):
        list_type = get_list_type(arg_type)
        return [_resolve_arguments(context, item, list_type) for item in data]
    elif isinstance(data, ParsedVariable):
        return context.variables[data.name]
    elif isinstance(data, ParsedEnum):
        return getattr(arg_type, data.name, data.name)
    else:
        return data


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

    raw_args = requested_field.arguments or {}
    arguments: dict = _resolve_arguments(context, raw_args, field.args)  # type: ignore

    try:
        resolved = field.resolver(parent, context, **arguments)
    except Exception as e:
        context.error(e, requested_field)
        return None

    if resolved is None or not requested_field.subfields:
        context.pop(requested_field)
        return resolved

    field_type = field.field_type
    if check_list(field_type):
        list_type = get_list_type(field_type)
        if not list_type or isinstance(list_type, TypeVar):
            result = resolved
        else:
            item_resolver = partial(_resolve_result, context, list_type, requested_field)
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
