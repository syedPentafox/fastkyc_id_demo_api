from pydantic import BaseModel, EmailStr


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
