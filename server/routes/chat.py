import asyncio
import json
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


@router.get("/sessions")
async def list_sessions():
    return session_manager.list_all()


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "title": session.title,
        "messages": session.messages,
        "extract_result": session.extract_result,
        "created_at": session.created_at,
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if not session_manager.delete(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.post("/chat")
async def chat(req: ChatRequest):
    session = session_manager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    emitter = EventEmitter()

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue = await emitter.get_queue()
        session_manager.add_message(req.session_id, "user", req.message)

        full_response = ""
        finished = False

        def run_agent():
            nonlocal full_response, finished
            try:
                for text in _agent.execute_stream(req.message, event_emitter=emitter):
                    full_response += text
            except Exception as e:
                emitter.emit_error(str(e))
            finally:
                finished = True
                emitter.emit_done()

        loop.run_in_executor(None, run_agent)

        while not finished or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue

        session_manager.add_message(req.session_id, "assistant", full_response)

    return EventSourceResponse(event_generator())
