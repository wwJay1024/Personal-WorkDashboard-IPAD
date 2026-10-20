from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/data", tags=["data"])


class RecordUpdate(BaseModel):
    updates: dict


def get_data_service(request: Request):
    return request.app.state.data_service


@router.get("/types")
async def list_data_types(request: Request):
    return {"types": get_data_service(request).list_types()}


@router.get("/{data_type}")
async def get_all_records(data_type: str, request: Request):
    data_service = get_data_service(request)
    if data_type not in data_service.registry:
        raise HTTPException(status_code=404, detail=f"unknown data type: {data_type}")
    return await data_service.read_all(data_type)


@router.post("/{data_type}")
async def add_record(data_type: str, record: dict, request: Request):
    data_service = get_data_service(request)
    if data_type not in data_service.registry:
        raise HTTPException(status_code=404, detail=f"unknown data type: {data_type}")
    created = await data_service.add_record(data_type, record)
    await request.app.state.push_data_update(data_type)
    return created


@router.put("/{data_type}/{record_id}")
async def update_record(data_type: str, record_id: str, update: RecordUpdate, request: Request):
    data_service = get_data_service(request)
    if data_type not in data_service.registry:
        raise HTTPException(status_code=404, detail=f"unknown data type: {data_type}")
    result = await data_service.update_record(data_type, record_id, update.updates)
    if result is None:
        raise HTTPException(status_code=404, detail="record not found")
    await request.app.state.push_data_update(data_type)
    return result


@router.delete("/{data_type}/{record_id}")
async def delete_record(data_type: str, record_id: str, request: Request):
    data_service = get_data_service(request)
    if data_type not in data_service.registry:
        raise HTTPException(status_code=404, detail=f"unknown data type: {data_type}")
    deleted = await data_service.delete_record(data_type, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="record not found")
    await request.app.state.push_data_update(data_type)
    return {"status": "deleted"}
