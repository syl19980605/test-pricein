import json

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from backend.agent.bobby_agent import bobby_agent
from backend.models.schemas import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    async def event_generator():
        try:
            action = req.action.model_dump() if req.action else None
            async for chunk in bobby_agent.chat(req.message, req.conversation_id, action):
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history/{conversation_id}")
async def chat_history(conversation_id: str):
    return await bobby_agent.get_history(conversation_id)
