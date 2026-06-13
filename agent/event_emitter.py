import asyncio
import json
from typing import Any


class EventEmitter:
    """线程安全的事件发射器，桥接同步 Agent 与异步 SSE。"""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    def push(self, event_type: str, data: dict[str, Any]) -> None:
        """同步线程安全地将事件推入异步队列。"""
        payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    def emit_thinking(
        self, step: int, tool: str, args: dict, reasoning: str
    ) -> None:
        self.push("thinking", {
            "step": step,
            "tool": tool,
            "args": {k: v for k, v in args.items() if k != "config" and k != "type"},
            "reasoning": reasoning,
        })

    def emit_tool_result(
        self, step: int, tool: str, result: str, duration_ms: int
    ) -> None:
        self.push("tool_result", {
            "step": step,
            "tool": tool,
            "result": result,
            "duration_ms": duration_ms,
        })

    def emit_token(self, content: str) -> None:
        self.push("token", {"content": content})

    def emit_done(self) -> None:
        self.push("done", {})

    def emit_error(self, message: str) -> None:
        self.push("error", {"message": message})

    async def get_queue(self) -> asyncio.Queue[str]:
        return self._queue
