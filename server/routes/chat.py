import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from server.session import session_manager
from agent.react_agent import ReactAgent
from agent.event_emitter import EventEmitter

router = APIRouter()
_agent = ReactAgent()


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/session")
async def create_session():
    session = session_manager.create()
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    session = session_manager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    emitter = EventEmitter()

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue = await emitter.get_queue()
        session_manager.add_message(req.session_id, "user", req.message)

        full_response = ""

        def run_agent():
            nonlocal full_response
            for text in _agent.execute_stream(req.message, event_emitter=emitter):
                full_response += text + "\n"

        try:
            await loop.run_in_executor(None, run_agent)
            session_manager.add_message(req.session_id, "assistant", full_response)
            emitter.emit_done()
        except Exception as e:
            emitter.emit_error(str(e))

        while True:
            data = await queue.get()
            yield data
            if '"done"' in data.replace(" ", "") or '"error"' in data.replace(" ", ""):
                break

    return EventSourceResponse(event_generator())
