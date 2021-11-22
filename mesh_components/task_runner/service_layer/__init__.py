# Copyright 2021 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Service layer for communication between API and library code
"""

#
# IMPORTS
#

from secrets import token_urlsafe

from ..lib.task import task_from_dict

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#


class NotFound(ValueError):
    """Task is not present inservice layer"""


class ServiceLayer:
    """Encapsulate API and library interaction"""

    def __init__(self) -> None:
        """Initialize service layer"""
        # running / watched tasks
        self._tasks = {}
    # __init__()

    def add_task(self, task_dict):
        """
        Add a new task

        Result fields:
            id: new task id
        """
        task = task_from_dict(task_dict)
        task_id = token_urlsafe(6)
        self._tasks[task_id] = {
            'id': task_id,
            'input_task': task,
        }
        return {'id': task_id}
    # add_task()

    def get_task_status(self, task_id):
        """
        Retrieve status of a task

        Result fields:
            id: task id
            status: status reported by machine
        """
        task = self._tasks.get(task_id)
        if not task:
            raise NotFound()

        return {
            'id': task['id'],
            'status': 'in progress'
        }
    # get_task_status

    def stop_task(self, task_id):
        """
        Stop a task

        Result fields:
            id: task id
        """
        task = self._tasks.get(task_id)
        if not task:
            raise NotFound()

        return {
            'id': task['id'],
        }
    # stop()


# ServiceLayer
