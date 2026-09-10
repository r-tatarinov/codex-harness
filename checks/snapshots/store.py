from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from ..analyzers.schema import SourceDocument
from ..storage import AtomicFile
from .parsing import parse_snapshot
from .schema import FileState, Snapshot


class SnapshotStore:
    def read(self, path: Path) -> Snapshot:
        return parse_snapshot(AtomicFile(path).read_json(), Path.cwd())

    def write(self, path: Path, snapshot: Snapshot) -> None:
        AtomicFile(path).write_json(
            {
                "tool_use_id": snapshot.tool_use_id,
                "cwd": str(snapshot.cwd),
                "files": snapshot.files,
            }
        )

    def file_state(self, path: Path) -> FileState:
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return FileState(exists=False, content=None)
        return FileState(exists=True, content=content)

    def capture(self, paths: Sequence[Path], cwd: Path, tool_use_id: str) -> Snapshot:
        return Snapshot(
            cwd, {str(path): self.file_state(path) for path in paths}, tool_use_id
        )

    def retain_changed(self, path: Path, event: dict) -> bool:
        snapshot = self.read(path)
        if snapshot.tool_use_id != event["tool_use_id"]:
            raise ValueError("Snapshot tool_use_id does not match the hook")
        if str(snapshot.cwd) != str(Path(event["cwd"]).resolve()):
            raise ValueError("Snapshot cwd does not match the hook")
        changed = {
            name: before
            for name, before in snapshot.files.items()
            if self.file_state(Path(name)) != before
        }
        if not changed:
            return False
        self.write(path, Snapshot(snapshot.cwd, changed, snapshot.tool_use_id))
        return True

    def documents_after(self, snapshot: Snapshot) -> tuple[SourceDocument, ...]:
        documents = []
        for name in snapshot.files:
            state = self.file_state(Path(name))
            if state["content"] is not None:
                documents.append(
                    SourceDocument(Path(name), state["content"], snapshot.cwd.resolve())
                )
        return tuple(documents)

    @contextmanager
    def consume(self, path: Path) -> Iterator[Path | None]:

        claimed = path.with_suffix(".processing")
        try:
            path.replace(claimed)
        except FileNotFoundError:
            yield None
            return
        try:
            yield claimed
        finally:
            claimed.unlink(missing_ok=True)
