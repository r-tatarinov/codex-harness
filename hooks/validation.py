def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"Missing or invalid {name}; cannot determine retry scope")
    return value
