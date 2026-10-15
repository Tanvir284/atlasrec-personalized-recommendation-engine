"""Request bodies. Every model forbids unknown fields."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MODEL_NAMES = Literal["popularity", "item_cf", "bpr", "two_tower", "two_tower_id", "ranker"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        email = value.strip().lower()
        local, separator, domain = email.partition("@")
        labels = domain.split(".")
        if (not separator or not local or len(local) > 64 or local.startswith(".") or
                local.endswith(".") or ".." in local or
                not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local) or
                len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
            raise ValueError("Provide a valid email")
        return email


class Preferences(Input):
    categories: list[str] = Field(max_length=10)


class Feedback(Input):
    id: uuid.UUID
    item_id: str = Field(max_length=64)
    kind: Literal["view", "impression", "click", "dismiss", "rating"]
    surface: str = Field(min_length=1, max_length=80)
    request_id: uuid.UUID | None = None
    position: int | None = Field(None, ge=0, le=100)
    client_timestamp: datetime | None = None
    rating: float | None = Field(None, ge=1, le=5)

    @model_validator(mode="after")
    def rating_payload(self):
        if (self.kind == "rating") != (self.rating is not None):
            raise ValueError("A rating value is required only for rating events")
        return self


class Training(Input):
    model: MODEL_NAMES = "popularity"
    epochs: int = Field(6, ge=1, le=30)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    include_application_feedback: bool = True


class ProfileUpdate(Input):
    name: str | None = Field(None, min_length=1, max_length=80)
    email: str | None = Field(None, min_length=3, max_length=254)
    admin: bool | None = None
    password: str | None = Field(None, min_length=10, max_length=128)
    preferences: list[str] | None = Field(None, max_length=10)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return None
        return Registration.validate_email(value)


class PasswordChange(Input):
    current_password: str | None = Field(None, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class AdminUserCreate(Registration):
    admin: bool = False


class AdminUserUpdate(ProfileUpdate):
    pass


