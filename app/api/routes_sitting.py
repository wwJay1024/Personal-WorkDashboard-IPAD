from fastapi import APIRouter, Request

from app.models.sitting import SittingReminderResponse

router = APIRouter(prefix="/api/sitting", tags=["sitting"])


def _get_service(request: Request):
    return request.app.state.sitting_service


@router.get("/status")
async def get_status(request: Request):
    return _get_service(request).get_state().model_dump(mode="json")


@router.post("/start")
async def start_sitting(request: Request):
    await _get_service(request).start_sitting()
    return {"status": "ok"}


@router.post("/stop")
async def stop_sitting(request: Request):
    await _get_service(request).stop_sitting()
    return {"status": "ok"}


@router.post("/away")
async def mark_away(request: Request):
    await _get_service(request).mark_away()
    return {"status": "ok"}


@router.post("/back")
async def mark_back(request: Request):
    await _get_service(request).mark_back()
    return {"status": "ok"}


@router.post("/meeting/start")
async def start_meeting(request: Request):
    await _get_service(request).start_meeting()
    return {"status": "ok"}


@router.post("/meeting/stop")
async def stop_meeting(request: Request):
    await _get_service(request).stop_meeting()
    return {"status": "ok"}


@router.post("/reminder-response")
async def reminder_response(body: SittingReminderResponse, request: Request):
    await _get_service(request).handle_reminder_response(body.action)
    return {"status": "ok"}
