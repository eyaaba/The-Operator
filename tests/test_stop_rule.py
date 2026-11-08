"""
Stop-rule proofs (Task 2.1). The brief: "Write the stopping condition first."

These are placeholders until the agent exists. Each one must use a FAKE model
that never calls `finish` (a model that loops forever) and prove the run still ends.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Task 2.1 - implement the stop rule first")


def test_stops_at_max_model_calls():
    """Fake model always calls list_emails -> run ends after MAX_MODEL_CALLS."""


def test_stops_at_max_tool_calls():
    """Fake model asks for 5 tools per turn -> run ends at MAX_TOOL_CALLS."""


def test_stops_on_repeated_identical_call():
    """Fake model calls read_email(em_001) forever -> stopped after MAX_REPEATED_CALL."""


def test_stops_at_write_cap():
    """Fake model archives every email -> blocked after MAX_WRITES_PER_RUN writes."""


def test_finish_ends_the_run():
    """Fake model calls finish on step 2 -> exactly 2 model calls."""
