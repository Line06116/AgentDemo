import time
from typing import Callable

from langchain.agents.middleware import wrap_tool_call, before_model
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from utils.logger_handler import logger


_event_emitter = None


def set_event_emitter(emitter):
    global _event_emitter
    _event_emitter = emitter


_step_counter = 0


def _next_step() -> int:
    global _step_counter
    _step_counter += 1
    return _step_counter


def reset_step_counter():
    global _step_counter
    _step_counter = 0


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    tool_name = request.tool_call["name"]
    args = request.tool_call.get("args", {})
    step = _next_step()

    logger.info(f"[tool monitor] 执行工具: {tool_name}, 参数: {args}")

    if _event_emitter and hasattr(_event_emitter, 'emit_thinking'):
        _event_emitter.emit_thinking(
            step=step,
            tool=tool_name,
            args=args,
            reasoning=f"Agent 决定调用 {tool_name} 工具",
        )

    start = time.time()
    try:
        result = handler(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"[tool monitor] 工具 {tool_name} 调用成功 ({duration_ms}ms)")

        result_str = result.content if hasattr(result, 'content') else str(result)
        if _event_emitter and hasattr(_event_emitter, 'emit_tool_result'):
            _event_emitter.emit_tool_result(
                step=step,
                tool=tool_name,
                result=result_str[:2000],
                duration_ms=duration_ms,
            )

        return result
    except Exception as e:
        logger.error(f"[tool monitor] 工具 {tool_name} 调用失败: {e}")
        raise


@before_model
def log_before_model(state, runtime):
    msgs = state.get("messages", [])
    logger.info(f"[log_before_model] 即将调用模型，{len(msgs)} 条消息")
    if msgs:
        logger.debug(f"[log_before_model] 最后一条: {type(msgs[-1]).__name__}")
    return None
