import asyncio
import uuid
from flask import jsonify, current_app
from threading import Thread

class AsyncTaskManager:
    def __init__(self):
        # Dictionary to track task state by job_id
        self.tasks = {}

    def _task_runner(self, app, callback, job_id):
        """
        Background thread function that runs the async task in an event loop
        and stores the result in the tasks dictionary.
        """
        with app.app_context():
            try:
                # Create and bind a new asyncio event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Run the async callback and wait for result
                result = loop.run_until_complete(callback(job_id))

                # Save result if not cancelled
                if self.tasks[job_id]["status"] != "cancelled":
                    self.tasks[job_id]["status"] = "completed"
                    self.tasks[job_id]["result"] = result
                else:
                    self.tasks[job_id]["result"] = ''
            except Exception as e:
                self.tasks[job_id]["status"] = "failed"
                self.tasks[job_id]["result"] = str(e)

    def run_task(self, job_id, callback):
        """
        Launch an async task in a separate thread and track its status.
        Returns a job ID to the client.
        """
        try:
            self.tasks[job_id] = {
                "status": "running",
                "progress": "...",
                "result": ""
            }

            # Start a new thread with app context
            thread = Thread(
                target=self._task_runner,
                args=(current_app._get_current_object(), callback, job_id)
            )
            thread.start()

            return jsonify({"job_id": job_id}), 202

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def set_progress(self, job_id, progress):
        """
        Update the progress of a given task.
        """
        if job_id in self.tasks:
            self.tasks[job_id]["progress"] = progress

    def check_status(self, job_id):
        """
        Return the status, progress, and result of a task by job_id.
        """
        task = self.tasks.get(job_id)
        if not task:
            return jsonify({
                "status": "not_found"
            }), 404

        result = {
            "status": task["status"],
            "progress": task["progress"],
            "result": task["result"]
        }
        return jsonify(result)

    def cancel_task(self, job_id):
        """
        Cancel a running task.
        """
        task = self.tasks.get(job_id)
        if not task:
            return jsonify({"error": "Job not found"}), 404

        if task["status"] == "completed":
            return jsonify({"message": "Job already completed"}), 400

        task["status"] = "cancelled"
        return jsonify({"message": f"Job {job_id} cancelled"})

    def is_cancelled(self, job_id):
        """
        Return True if a task has been cancelled.
        """
        task = self.tasks.get(job_id)
        if not task:
            return jsonify({"error": "Job not found"}), 404

        return task["status"] == "cancelled"
