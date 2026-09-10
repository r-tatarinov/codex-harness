import json
import os
import tempfile
from pathlib import Path
from typing import Any


class AtomicFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read_text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def read_json(self) -> Any:
        return json.loads(self.read_text())

    def write_json(self, value: object) -> None:
        self.write_text(json.dumps(value, ensure_ascii=False))

    def write_text(self, text: str, *, exclusive: bool = False) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as file:
                temporary = Path(file.name)
                file.write(text)
                file.flush()
                os.fsync(file.fileno())
            if exclusive:
                try:
                    os.link(temporary, self.path)
                except FileExistsError:
                    pass
            else:
                temporary.replace(self.path)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:

                    pass

    def backup_to(self, path: Path) -> None:
        try:
            os.link(self.path, path)
        except FileExistsError:
            pass
