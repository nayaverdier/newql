from enum import Enum
from typing import List, Optional

from newql import ExecutionContext, Schema, field


class UserType(Enum):
    ADMIN = "admin"
    USER = "user"


class User:
    name = field(type=str, doc="The full name of the user")
    email = field(type=str, doc="The users contact email")
    age = field(type=int, doc="The current age of the user")

    @field
    def user_type(user: dict, _context) -> str:  # type: ignore
        return user["type"].value

    @field
    def phone(user: dict, context, area_code: bool = True) -> str:  # type: ignore
        """The user's contact phone number

        Args:
            area_code: Whether or not to include the area code
        """
        if area_code:
            return user["area_code"] + "-" + user["phone"]
        else:
            return user["phone"]

    @field
    def custom_arg(user, context, argument: str) -> Optional[str]:
        return argument


USERS = {
    "U1": {
        "name": "John Smith",
        "email": "johnsmith@example.com",
        "age": 34,
        "area_code": "555",
        "phone": "555-1234",
        "type": UserType.ADMIN,
    },
    "U2": {
        "name": "Jane Doe",
        "email": "janedoe@example.com",
        "age": 31,
        "area_code": "555",
        "phone": "555-9876",
        "type": UserType.USER,
    },
    "U-buggy-phone": {
        "name": "Adam Appleseed",
        "email": "adamappleseed@example.com",
        "age": 28,
        "area_code": None,
        "phone": "555-0000",
        "type": UserType.USER,
    },
}


class UserQuery:
    @field(type=User)
    def user(_, context, user_id: str) -> dict:
        if user_id in USERS:
            return USERS[user_id]
        else:
            raise ValueError(f"User '{user_id}' not found")

    @field(type=List[User])
    def users(_, context, user_ids: List[str] = None, user_type: UserType = None) -> List[dict]:
        return [
            user
            for user_id, user in USERS.items()
            if (user_ids is None or user_id in user_ids) and (not user_type or user["type"] == user_type)
        ]


user_schema = Schema(UserQuery)


class Product:
    """Represents a product in stock"""

    product_id = field(type=int)
    product_name = field(type=str)
    price = field(type=float)


class ProductQuery:
    # pass 'type' here since the function returns a dictionary,
    # but we want to actually resolve to a Product
    @field(type=Product)
    def product(_, context: ExecutionContext, product_id: int) -> dict:
        # The "Args" section of the docstring is parsed out to add
        # docs to the arguments (can be seen in GraphiQL)
        """Find a specific product by id

        Args:
            product_id: The ID of the product to find
        """

        products = {1: ("Product1", 49.99), 2: ("Product2", 94.49)}
        if product_id in products:
            name, price = products[product_id]
            return {"product_id": product_id, "product_name": name, "price": price}
        else:
            raise ValueError(f"Product not found: {product_id}")


product_schema = Schema(ProductQuery)
