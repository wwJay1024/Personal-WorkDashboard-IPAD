import json
from pathlib import Path
from typing import TypeVar

import aiofiles
from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class DataService:
    def __init__(self) -> None:
        self.registry: dict[str, tuple[Path, type[BaseModel]]] = {}

    def register(self, data_type: str, file_path: Path, model: type[T]) -> None:
        self.registry[data_type] = (file_path, model)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text("[]\n", encoding="utf-8")
        logger.info("registered data type {} -> {}", data_type, file_path)

    def list_types(self) -> list[str]:
        return sorted(self.registry.keys())

    def _get_entry(self, data_type: str) -> tuple[Path, type[BaseModel]]:
        if data_type not in self.registry:
            raise KeyError(f"unknown data type: {data_type}")
        return self.registry[data_type]

    async def read_all(self, data_type: str) -> list[dict]:
        file_path, model = self._get_entry(data_type)
        if not file_path.exists():
            return []
        async with aiofiles.open(file_path, "r", encoding="utf-8") as handle:
            content = await handle.read()
        if not content.strip():
            return []
        try:
            payload = json.loads(content)
            if not isinstance(payload, list):
                logger.error("{} should contain a JSON list", file_path)
                return []
            return [model.model_validate(item).model_dump(mode="json") for item in payload]
        except Exception as exc:
            logger.error("failed to read {}: {}", file_path, exc)
            return []

    async def write_all(self, data_type: str, records: list[dict]) -> list[dict]:
        file_path, model = self._get_entry(data_type)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        validated = [model.model_validate(record).model_dump(mode="json") for record in records]
        async with aiofiles.open(file_path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(validated, ensure_ascii=False, indent=2))
            await handle.write("\n")
        return validated

    async def add_record(self, data_type: str, record: dict) -> dict:
        records = await self.read_all(data_type)
        _, model = self._get_entry(data_type)
        new_record = model.model_validate(record).model_dump(mode="json")
        records.append(new_record)
        await self.write_all(data_type, records)
        return new_record

    async def update_record(self, data_type: str, record_id: str, updates: dict) -> dict | None:
        records = await self.read_all(data_type)
        _, model = self._get_entry(data_type)
        for index, record in enumerate(records):
            if record.get("id") == record_id:
                merged = {**record, **updates}
                updated = model.model_validate(merged).model_dump(mode="json")
                records[index] = updated
                await self.write_all(data_type, records)
                return updated
        return None

    async def delete_record(self, data_type: str, record_id: str) -> bool:
        records = await self.read_all(data_type)
        filtered = [record for record in records if record.get("id") != record_id]
        if len(filtered) == len(records):
            return False
        await self.write_all(data_type, filtered)
        return True
