import asyncio
import json
from typing import Any


class EventEmitter:
    """线程安全的事件发射器。dict 格式供 sse_starlette 直接使用。"""

    def __init__(self):
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._loop = asyncio.get_running_loop()

    def push(self, event_type: str, data: dict[str, Any]) -> None:
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait,
            {"event": event_type, "data": json.dumps(data, ensure_ascii=False)}
        )

    def emit_thinking(self, step: int, tool: str, args: dict, reasoning: str) -> None:
        self.push("thinking", {
            "step": step, "tool": tool,
            "args": {k: v for k, v in args.items() if k not in ("config", "type")},
            "reasoning": reasoning,
        })

    def emit_tool_result(self, step: int, tool: str, result: str, duration_ms: int) -> None:
        self.push("tool_result", {
            "step": step, "tool": tool, "result": result, "duration_ms": duration_ms,
        })

    def emit_token(self, content: str) -> None:
        self.push("token", {"content": content})

    def emit_done(self) -> None:
        self.push("done", {})

    def emit_error(self, message: str) -> None:
        self.push("error", {"message": message})

    async def get_queue(self) -> asyncio.Queue[dict]:
        return self._queue
