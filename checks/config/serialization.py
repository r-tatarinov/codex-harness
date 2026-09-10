from .errors import ConfigurationError


def toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise ConfigurationError(f"cannot migrate TOML value {value!r}")


def dump_config(config: dict) -> str:
    lines = [f"schema_version = {config['schema_version']}", ""]
    sections = [("verification", config["verification"])]
    for name, tool in config["tools"].items():
        direct = {
            key: value for key, value in tool.items() if not isinstance(value, dict)
        }
        sections.append((f"tools.{name}", direct))
        sections.extend(
            (f"tools.{name}.{key}", value)
            for key, value in tool.items()
            if isinstance(value, dict)
        )
    for section, values in sections:
        lines.append(f"[{section}]")
        lines.extend(f"{key} = {toml_value(value)}" for key, value in values.items())
        lines.append("")
    return "\n".join(lines)
