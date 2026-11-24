"""Offline-testable stop-policy enforcement for tool requests and model steps."""
from dataclasses import dataclass, field
import json
from agent.config import MAX_MODEL_CALLS, MAX_TOOL_CALLS, MAX_WRITES_PER_RUN, MAX_REPEATED_CALL, MAX_COST_USD
from agent.schemas import WRITE_TOOLS

class StopRun(RuntimeError):
    pass

@dataclass
class StopRule:
    models: int = 0
    tools: int = 0
    writes: int = 0
    cost_usd: float = 0.0
    finished: bool = False
    max_cost_usd: float = MAX_COST_USD
    repetitions: dict[str, int] = field(default_factory=dict)

    def before_model(self):
        if self.finished or self.models >= MAX_MODEL_CALLS or self.cost_usd >= self.max_cost_usd:
            raise StopRun('Model-call, cost or finish stop reached')
        self.models += 1

    def before_tool(self, name: str, args: dict):
        if self.finished: raise StopRun('finish already called')
        if self.tools >= MAX_TOOL_CALLS: raise StopRun('tool-call cap reached')
        key = json.dumps([name,args], sort_keys=True)
        if self.repetitions.get(key, 0) >= MAX_REPEATED_CALL: raise StopRun('identical tool-call loop detected')
        if name in WRITE_TOOLS and self.writes >= MAX_WRITES_PER_RUN: raise StopRun('write cap reached')
        self.tools += 1
        self.repetitions[key] = self.repetitions.get(key, 0) + 1
        if name in WRITE_TOOLS: self.writes += 1
        if name == 'finish': self.finished = True

    def before_retry(self, name: str):
        if self.finished or self.tools >= MAX_TOOL_CALLS:
            raise StopRun('tool-call cap reached before retry')
        if name in WRITE_TOOLS and self.writes >= MAX_WRITES_PER_RUN:
            raise StopRun('write cap reached before retry')
        self.tools += 1
        if name in WRITE_TOOLS:
            self.writes += 1

    def add_usage(self, input_tokens: int, output_tokens: int):
        # Published pricing must be checked at evaluation time; configurable approximation.
        import os
        self.cost_usd += (input_tokens * float(os.getenv('OPENAI_INPUT_USD_PER_1M', '0.40')) + output_tokens * float(os.getenv('OPENAI_OUTPUT_USD_PER_1M', '1.60'))) / 1_000_000
