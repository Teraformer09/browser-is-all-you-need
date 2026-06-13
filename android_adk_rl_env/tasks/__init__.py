"""Task registry for the runnable Android ADK environment."""

from android_adk_rl_env.tasks.create_note import CreateNoteTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask

TASKS = {
    "create_note": CreateNoteTask,
    "CreateNoteTask": CreateNoteTask,
    "ride_booking": RideBookingTask,
    "RideBookingTask": RideBookingTask,
}

__all__ = ["CreateNoteTask", "RideBookingTask", "TASKS"]
