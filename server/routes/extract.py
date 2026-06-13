from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from server.session import session_manager
from agent.tools.knowledge_tools import knowledge_extract

router = APIRouter()


class ExtractRequest(BaseModel):
    session_id: str


@router.post("/extract")
async def extract_knowledge(req: ExtractRequest):
    session = session_manager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    conversation = session_manager.get_conversation_text(req.session_id)
    if not conversation.strip():
        raise HTTPException(status_code=400, detail="当前对话无内容可萃取")

    result = knowledge_extract.invoke({"conversation_text": conversation})
    session.extract_result = result
    return {"result": result}


@router.get("/extract/download")
async def download_extract(session_id: str):
    session = session_manager.get(session_id)
    if not session or not session.extract_result:
        raise HTTPException(status_code=404, detail="没有萃取结果，请先执行萃取")

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"knowledge-{date_str}.txt"

    return Response(
        content=session.extract_result,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
