from pydantic import BaseModel, EmailStr, validator

import re


class Validator(BaseModel):
    @classmethod
    def is_valid(cls, **kwargs) -> bool:
        try:
            cls(**kwargs)
            return True
        except Exception:
            return False


class EmailValidator(Validator):
    email: EmailStr


class IntValidator(Validator):
    number: int


class FloatValidator(Validator):
    number: float


class StringValidator(Validator):
    string: str


class DictValidator(Validator):
    number: dict


class ListValidator(Validator):
    number: list


class PhoneNumberValidator(Validator):
    phone_number: str

    @validator("phone_number")
    def validate_phone_number(cls, v):
        # Define a regex pattern for Indian phone numbers
        phone_regex = re.compile(r"^\+91\d{10}$|^[789]\d{9}$")
        if not phone_regex.match(v):
            raise ValueError(
                """Invalid phone number format. Must be a 10-digit number starting with 7, 8, or 9,
                optionally prefixed with +91"""
            )
        return v
