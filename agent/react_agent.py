from langchain.agents import create_agent

from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import (
    rag_search, knowledge_extract, get_knowledge_stats,
    get_current_time, web_search,
)
from agent.tools.middleware import (
    monitor_tool, log_before_model, set_event_emitter, reset_step_counter,
)


class ReactAgent:
    def __init__(self):
        tools = [
            rag_search,
            knowledge_extract,
            get_knowledge_stats,
            get_current_time,
            web_search,
        ]
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=tools,
            middleware=[monitor_tool, log_before_model],
        )

    def execute_stream(self, query: str, event_emitter=None):
        if event_emitter:
            set_event_emitter(event_emitter)
        reset_step_counter()

        input_dict = {"messages": [{"role": "user", "content": query}]}
        for chunk in self.agent.stream(
            input_dict, stream_mode="values", context={}
        ):
            latest = chunk["messages"][-1]
            content = latest.content
            if content:
                text = content.strip()
                if text and event_emitter:
                    event_emitter.emit_token(text)
                if text:
                    yield text
