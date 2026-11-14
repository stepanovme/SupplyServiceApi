from typing import Literal

from pydantic import BaseModel


class ObjectRef(BaseModel):
    """An object attached to a document: a whole object or one of its levels."""

    object_id: str
    object_type: Literal["object", "object_levels_id"] = "object"
