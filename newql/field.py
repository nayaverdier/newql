import inspect
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union, get_type_hints

from varname import varname  # type: ignore

from .context import ExecutionContext

FIELD_NAME_PATTERN = re.compile("[_a-zA-Z][_a-zA-Z0-9]*")


@dataclass
class Field:
    name: str
    resolver: Callable
    field_type: type
    args: Dict[str, type]
    doc: Optional[str] = None

    # don't lose the ability to call functions wrapped with @field
    def __call__(self, *args, **kwargs):
        return self.resolver(*args, **kwargs)


def default_resolver(field_name: str) -> Callable[[Any, ExecutionContext], Any]:
    def dict_or_attribute_resolver(obj, _):
        if isinstance(obj, Mapping):
            return obj[field_name]
        else:
            return getattr(obj, field_name)

    return dict_or_attribute_resolver


def _extract_field_args(resolver: Callable, explicit_args: Optional[Dict[str, type]]) -> Dict[str, type]:
    E = f"Resolver '{resolver.__name__}' "

    arg_spec = inspect.getfullargspec(resolver)
    if arg_spec.varargs is None and len(arg_spec.args) < 2:
        raise ValueError(E + "must accept at least two positional arguments")

    parameters = set(arg_spec.args[2:] + arg_spec.kwonlyargs)
    field_args = {arg: arg_type for arg, arg_type in arg_spec.annotations.items() if arg in parameters}

    if explicit_args is None:
        all_args = field_args
    else:
        fixed_explicit_args = {arg: arg_type for arg, arg_type in explicit_args.items() if arg_type}
        all_args = field_args.copy()
        all_args.update(fixed_explicit_args)

    missing_hints = parameters - all_args.keys()
    if missing_hints:
        raise ValueError(E + f"missing type hints for {sorted(missing_hints)}")

    if arg_spec.varkw and explicit_args is None:
        raise ValueError(
            f"Must explicitly set 'args' for resolver '{resolver.__name__}' with argument '**{arg_spec.varkw}'"
        )

    # if present, make sure no parameters of the function
    # are missing from the explicit arguments
    if explicit_args is not None:
        extra_explicit = explicit_args.keys() - parameters
        if arg_spec.varkw is None and extra_explicit:
            raise ValueError(E + f"does not have all arguments in 'args': {sorted(extra_explicit)}")

    return all_args


def field(
    _resolver_or_name: Union[str, Callable] = None,
    *,
    name: str = None,
    resolver: Callable = None,
    type: type = None,
    args: Dict[str, type] = None,
    doc: str = None,
) -> Union[Field, Callable[..., Field]]:
    '''
    A decorator to turn a resolver function into a field. Can also be used
    to construct a Field directly, defaulting to a resolver that tries to find
    the field as an attribute (or key in a dictionary)

    When called as a constructor, the first argument must be the field name (not passed
    in as `name="..."`, as that is reserved for higher order decorators:

        class MyType:
            # uses the default resolver
            my_field = field(type=str)

            # uses custom resolver
            my_custom_field = field(type=int, resolver=my_resolver)

            # can pass explicit name
            anything = field("something", type=str)

    Can also be called as a higher order decorator to override field information:

        @field(name="actual_name", type=str, doc="Documentation about the string")
        def _gibberish(parent, context: ExecutionContext):
            return "foo"

        # equivalent to the following
        @field
        def actual_name(parent, context) -> str:
            """Documentation about the field"""
            return "foo"

    These higher order decorators are particularly useful for fields
    that return nested fields, for example:

        class Nested:
            @field
            def first_data_word(parent, _) -> str:
                return parent["some_data"].split()[0]

        class Parent:
            # type=Nested is necessary (at least when using mypy) since the function
            # returns a dict, but the field type is actually Nested
            @field(type=Nested)
            def nested(_, _) -> dict:
                return {"some_data": "goes here"}
    '''

    if _resolver_or_name is None:
        # either called as a higher order decorator `@field(...)`,
        # or as a constructor with implicit name `my_field = field(type=str)`
        if name is None:
            # if called as a field, we will be able to extract varname
            try:
                name = name or varname()  # type: ignore
            except Exception:
                # otherwise, varname() will raise an exception and name will still be None
                pass
            else:
                # only set resolver in the case where we successfully extracted varname
                # (and so field was called as a constructor, missing the name)
                resolver = resolver or default_resolver(name)
    elif isinstance(_resolver_or_name, str):
        # calling `field` as a constructor, use provided resolver or the default one
        if name is not None:
            raise ValueError("Cannot specify field name with both positional and keyword argument")
        name = _resolver_or_name
        resolver = resolver or default_resolver(name)
    else:
        # calling `field` as a flat decorator
        if resolver is not None:
            raise ValueError("Cannot specify resolver with both positional and keyword argument")
        resolver = _resolver_or_name

    def decorator(resolver: Callable) -> Field:
        field_name = name or resolver.__name__
        if not FIELD_NAME_PATTERN.fullmatch(field_name):
            raise ValueError(f"Field name must match {FIELD_NAME_PATTERN.pattern}, found '{field_name}'")

        field_type = type or get_type_hints(resolver).get("return")
        if field_type is None:
            raise ValueError(
                f"No return value type hint on resolver and `type` parameter not present for '{field_name}'"
            )

        field_args = _extract_field_args(resolver, args)
        field_doc = doc or resolver.__doc__

        return Field(field_name, resolver, field_type, field_args, field_doc)

    return decorator if resolver is None else decorator(resolver)
