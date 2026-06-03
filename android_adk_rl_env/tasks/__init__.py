"""Task registry for the runnable Android ADK environment."""

from android_adk_rl_env.tasks.create_note import CreateNoteTask

TASKS = {
    "create_note": CreateNoteTask,
    "CreateNoteTask": CreateNoteTask,
}

__all__ = ["CreateNoteTask", "TASKS"]
