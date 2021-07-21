import inspect
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from warnings import warn

try:  # pragma: no cover
    from typing import get_args, get_origin
except ImportError:  # pragma: no cover
    from typing_inspect import get_args, get_origin  # type: ignore

from .errors import SchemaWarning
from .field import Field


def _type_name(t):
    if isinstance(t, type):
        return t.__name__
    else:
        return type(t).__name__


BUILT_IN_TYPES = {
    object: (
        "object",
        "An arbitrary, flexible type determined at runtime (can be str, int, float, bool, list, object)",
    ),
    str: ("String", "A UTF-8 encoded string"),
    int: ("Integer", "An integer"),
    float: ("Float", "A floating point number"),
    bool: ("Boolean", "A boolean, true or false"),
}


def _get_type_info(t: type, types_by_class: dict, types_by_name: dict) -> dict:
    t, is_optional = check_optional(t)

    if is_optional:
        return {"kind": "NON_NULL", "ofType": _get_type_info(t, types_by_class, types_by_name)}
    elif check_list(t):
        item_type = get_list_type(t) or object
        return {"kind": "LIST", "ofType": _get_type_info(item_type, types_by_class, types_by_name)}
    else:
        introspected = introspect_type(t, types_by_class, types_by_name)
        return {"kind": introspected["kind"], "name": introspected["name"]}


def _parse_arg_docs(doc: Optional[str]) -> dict:
    if not doc:
        return {}

    arg_docs = {}
    found_args = False

    for line in doc.splitlines():
        if line.strip() == "Args:":
            found_args = True
        elif found_args and ":" in line:
            arg_name, arg_doc = line.strip().split(": ", 1)
            arg_docs[arg_name] = arg_doc

    return arg_docs


def _parse_default_args(resolver: Callable) -> Dict[str, Any]:
    arg_spec = inspect.getfullargspec(resolver)
    arg_defaults = arg_spec.kwonlydefaults or {}

    positional_args = reversed(arg_spec.args)
    positional_defaults = reversed(arg_spec.defaults or [])
    arg_defaults.update(zip(positional_args, positional_defaults))

    return arg_defaults


def check_optional(t: type) -> Tuple[type, bool]:
    args = get_args(t)
    if get_origin(t) is Union and len(args) == 2 and isinstance(None, args[1]):
        return args[0], True
    else:
        return t, False


def check_list(t: type) -> bool:
    return t is list or get_origin(t) is list


def get_list_type(t: type) -> Optional[type]:
    args = get_args(t)
    if args:
        return args[0]
    else:
        return None


def _get_args(field: Field, types_by_class: dict, types_by_name: dict) -> List[dict]:
    if not field.args:
        return []

    arg_docs = _parse_arg_docs(field.doc)
    default_values = _parse_default_args(field.resolver)

    introspected_args = []
    for arg, arg_type in field.args.items():
        arg_type, is_optional = check_optional(arg_type)
        type_info = _get_type_info(arg_type, types_by_class, types_by_name)

        if arg in default_values:
            default: Optional[str] = json.dumps(default_values.get(arg))
        else:
            default = None

        if not is_optional and default != "null":
            type_info = {"kind": "NON_NULL", "ofType": type_info}

        introspected_args.append(
            {
                "name": arg,
                "description": arg_docs.get(arg),
                "type": type_info,
                "defaultValue": default,
            }
        )

    return introspected_args


def _get_field_description(doc: Optional[str]) -> Optional[str]:
    if not doc:
        return doc

    description = []
    for line in doc.splitlines():
        line = line.strip()
        if line == "Args:":
            break
        elif line:
            description.append(line)

    return "\n".join(description)


def introspect_type(t, types_by_class: dict, types_by_name: dict, is_operation: bool = False) -> dict:
    if isinstance(t, TypeVar):  # pragma: no cover
        t = object

    try:
        return types_by_class[t]
    except KeyError:
        pass

    try:
        name, doc = BUILT_IN_TYPES[t]
        built_in_info = {"kind": "SCALAR", "name": name, "description": doc}

        types_by_class[t] = built_in_info
        types_by_name[name] = built_in_info
        return built_in_info
    except KeyError:
        pass

    fields = []
    for attr in dir(t):
        field = getattr(t, attr)
        if not isinstance(field, Field):
            continue

        type_info = _get_type_info(field.field_type, types_by_class, types_by_name)
        args = _get_args(field, types_by_class, types_by_name)
        description = _get_field_description(field.doc)

        fields.append({"name": field.name, "description": description, "args": args, "type": type_info})

    if is_operation and not fields:
        return None  # type: ignore

    extra = {}
    if is_operation or fields:
        kind = "OBJECT"
    elif inspect.isclass(t) and issubclass(t, Enum):
        kind = "ENUM"
        extra["enumValues"] = [{"name": e.name} for e in t]
    else:
        kind = "SCALAR"

    name = _type_name(t)
    introspected = {"kind": kind, "name": name, "fields": fields, "description": t.__doc__, **extra}

    if kind == "OBJECT":
        introspected["interfaces"] = []

    types_by_class[t] = introspected

    if name in types_by_name:
        warn(f"Multiple types found with the same name during introspection: {name}", SchemaWarning)
    else:
        types_by_name[name] = introspected

    return introspected
