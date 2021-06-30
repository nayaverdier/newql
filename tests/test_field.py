import pytest

from newql import Field, field


def _field_error(error: str, *args, error_class: type = ValueError, **kwargs):
    with pytest.raises(error_class) as info:
        field(*args, **kwargs)
    assert isinstance(info.value, error_class)
    assert str(info.value) == error


def test_field_invalid():
    _field_error("field() takes from 0 to 1 positional arguments but 2 were given", "a", "b", error_class=TypeError)
    _field_error("Field name must match [_a-zA-Z][_a-zA-Z0-9]*, found 'test-foo'", "test-foo", type=str)
    _field_error("Cannot specify field name with both positional and keyword argument", "field_name", name="field_name")
    _field_error(
        "Cannot specify resolver with both positional and keyword argument",
        lambda *_: None,
        resolver=lambda *_: None,
    )
    _field_error("No return value type hint on resolver and `type` parameter not present for 'my_field'", "my_field")


def test_field_missing_positional_arguments():
    def missing_positional_args() -> str:
        return "test"

    def only_one_positional_arg(parent) -> str:
        return "test"

    def only_kwargs(*, foo, bar, baz=None) -> str:
        return "test"

    def one_with_kwargs(parent, *, foo, bar=None) -> str:
        return "test"

    for f in (missing_positional_args, only_one_positional_arg, only_kwargs, one_with_kwargs):
        _field_error(f"Resolver '{f.__name__}' must accept at least two positional arguments", f)


def test_field_missing_argument_type():
    def pos_arg_missing_type(parent, context, arg) -> str:
        return "test"

    def default_pos_arg_missing_type(parent, context, arg=None) -> str:
        return "test"

    def kwarg_missing_type(parent, context, *, arg) -> str:
        return "test"

    def default_kwarg_missing_type(parent, context, *, arg=None) -> str:
        return "test"

    for f in (pos_arg_missing_type, default_pos_arg_missing_type, kwarg_missing_type, default_kwarg_missing_type):
        _field_error(f"Resolver '{f.__name__}' missing type hints for ['arg']", f)
        assert field(f, args={"arg": str}) == Field(f.__name__, f, str, {"arg": str})


def test_field_kwargs():
    def field_with_kwargs(parent, context, **kw) -> str:
        return "test"

    def field_with_kwarg_kwargs(parent, context, *, foo: bool, **kw) -> str:
        return "test"

    def field_with_arg_kwargs(parent, context, arg: int, **kw) -> str:
        return "test"

    def field_with_arg_kwarg_kwargs(parent, context, arg: int, *, arg2: bool, **kw) -> str:
        return "test"

    for f in (field_with_kwargs, field_with_kwarg_kwargs, field_with_arg_kwargs, field_with_arg_kwarg_kwargs):
        _field_error(f"Must explicitly set 'args' for resolver '{f.__name__}' with argument '**kw'", f)
        args = {"arg": int, "arg2": bool, "foo": bool, "additional": str}
        assert field(f, args=args) == Field(f.__name__, f, str, args)


def test_undefined_explicit_args():
    def my_field(parent, context, arg1: str, *, arg2: int, arg3: bool = False) -> str:
        return "test"

    args = {"arg1": str, "arg2": int, "arg3": bool}
    _field_error(
        "Resolver 'my_field' does not have all arguments in 'args': ['arg4']", my_field, args={**args, "arg4": int}
    )

    assert field(my_field, args={}) == Field("my_field", my_field, str, args)
    assert field(my_field, args=args) == Field("my_field", my_field, str, args)


def test_field_default_resolver():
    def my_field(parent, context) -> str:
        return "test"

    default = field("my_field", type=str)
    assert default.name == "my_field"
    assert default.field_type == str
    assert default.resolver.__module__ == "newql.field"
    assert default.resolver.__name__ == "dict_or_attribute_resolver"


def test_field_constructor():
    def my_field(parent, context) -> str:
        return "test"

    assert field(resolver=my_field) == Field("my_field", my_field, str, {})

    random_var = field(name="yet_another_field", resolver=lambda parent, context: 1, type=int)
    assert random_var.name == "yet_another_field"
    assert random_var.field_type == int
    assert "<lambda>" in random_var.resolver.__name__


def test_varname_default():
    my_field = field(type=str)
    assert my_field.name == "my_field"
    assert my_field.field_type == str
    assert my_field.resolver.__name__ == "dict_or_attribute_resolver"

    def random_resolver(parent, context) -> int:
        return 1

    another_field = field(resolver=random_resolver)
    assert another_field == Field("another_field", random_resolver, int, {})


def test_constructor_override():
    def my_field(parent, context) -> str:
        """Docstring here"""
        return "test"

    assert field(my_field) == Field("my_field", my_field, str, {}, "Docstring here")

    assert field(my_field, name="custom_name") == Field("custom_name", my_field, str, {}, "Docstring here")
    assert field(name="custom_name")(my_field) == Field("custom_name", my_field, str, {}, "Docstring here")

    assert field(my_field, type=int) == Field("my_field", my_field, int, {}, "Docstring here")
    assert field(type=int)(my_field) == Field("my_field", my_field, int, {}, "Docstring here")

    assert field(my_field, doc="New docstring") == Field("my_field", my_field, str, {}, "New docstring")
    assert field(doc="New docstring")(my_field) == Field("my_field", my_field, str, {}, "New docstring")

    def no_type(parent, context):
        return "test"

    assert field(no_type, type=str) == Field("no_type", no_type, str, {})
    assert field(type=str)(no_type) == Field("no_type", no_type, str, {})

    def no_doc(parent, context) -> str:
        return "test"

    assert field(no_doc, doc="docstring") == Field("no_doc", no_doc, str, {}, "docstring")
    assert field(doc="docstring")(no_doc) == Field("no_doc", no_doc, str, {}, "docstring")


def test_field_decorator_vararg_only():
    def my_field(*_) -> str:
        """docstring"""
        return "static"

    assert field(my_field) == Field("my_field", my_field, str, {}, "docstring")


def test_field_resolver_still_callable():
    class Query:
        @field
        def my_field(parent, context) -> int:
            return 100

    # essentially the same behavior as @staticmethod
    assert Query().my_field(None, None) == 100
    assert Query.my_field(None, None) == 100
