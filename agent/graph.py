"""
The agent (Task 2 - owner: Nour).

Built with LangChain's create_agent: it runs the ReAct loop
(model -> tool calls -> tool results -> model ...) and we customise it with
middleware instead of hand-writing the loop.

Planned middleware stack (order matters - outermost first):

    ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="end")   # stop rule
    ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS)                           # stop rule
    RepeatedCallGuard (custom, @after_model)                                    # loop detector
    WriteCapGuard     (custom, @wrap_tool_call)                                 # MAX_WRITES_PER_RUN
    ToolRetryMiddleware(max_retries=MAX_TOOL_RETRIES)                           # transient errors
    HumanInTheLoopMiddleware(interrupt_on=CHECKPOINT_POLICY)                    # human checkpoint

Plus InMemorySaver() as checkpointer (required for human-in-the-loop interrupts)
and ChatOpenAI(model=OPENAI_MODEL, temperature=0).

The run ends when the model calls `finish`, or when any limit above fires.
"""


def build_agent():
    raise NotImplementedError("Task 2.2")
