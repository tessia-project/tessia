#!/bin/bash
# Patch scheduler sources for fork-based execution (no Docker-in-Docker).
# This script is called from the change-server-dockerfile Tekton task and
# injects a RUN block into the server Dockerfile immediately after the
# git clone step.
#
# Usage: scheduler-patch.sh <DOCKERFILE>
set -e

DOCKERFILE="$1"
SCHED=/assets/repo-tessia/tessia/server/scheduler
WRAPPER=$SCHED/wrapper.py

PATCH_FILE="$(mktemp)"
cat > "$PATCH_FILE" << 'EOF'

# Patch scheduler sources for fork-based execution (no Docker-in-Docker).
RUN SCHED=/assets/repo-tessia/tessia/server/scheduler && \
    WRAPPER=$SCHED/wrapper.py && \
    \
    sed -i 's/self._spawner = spawner.ContainerSpawner()/self._spawner = spawner.ForkSpawner()/' $SCHED/looper.py && \
    sed -i "s/set_start_method('forkserver')/set_start_method('fork')/g" $SCHED/looper.py && \
    sed -i "s/start_method != 'forkserver'/start_method != 'fork'/g" $SCHED/looper.py && \
    sed -i 's/Multiprocessing mode must be forkserver/Multiprocessing mode must be fork/g' $SCHED/looper.py && \
    \
    sed -i '/Process did not start with looper cwd/{n;s/return PROCESS_DEAD/return PROCESS_UNKNOWN/}' $SCHED/spawner.py && \
    \
    sed -i 's/^from tessia\.server\.state_machines import MACHINES$/from tessia.server.db.connection import MANAGER as _db_mgr  # pylint: disable=reimported\nfrom tessia.server.state_machines import MACHINES/' $WRAPPER && \
    sed -i '/^        self\._machine = MACHINES\.classes\[self\._job_type\]($/{ N; s/        self\._machine = MACHINES\.classes\[self\._job_type\](\n            self\._job_params)/        # Dispose the inherited SQLAlchemy pool after fork() so each job\n        # process opens its own fresh DB connections.\n        try:\n            conn = _db_mgr._conn\n            if conn is not None:\n                conn[0].dispose()\n                _db_mgr._conn = None\n        except Exception:  # pylint: disable=broad-except\n            pass\n\n        # Write the result file on construction failure so the looper can\n        # mark the job correctly instead of leaving it in an unknown state.\n        try:\n            self._machine = MACHINES.classes[self._job_type](\n                self._job_params)\n        except Exception:\n            sys.excepthook(*sys.exc_info())\n            sys.stderr.flush()\n            sys.stdout.flush()\n            self._write_result(RESULT_EXCEPTION)\n            return/; }' $WRAPPER && \
    sed -i 's/^                    ret_code = RESULT_EXCEPTION$/                    sys.stderr.flush()\n                    sys.stdout.flush()\n                    ret_code = RESULT_EXCEPTION/' $WRAPPER && \
    sed -i 's/^        # The state machine was not yet cleaning up, do it in$/        # Flush output before handing off to the cleanup interpreter so\n        # that nothing in Python'"'"'s buffers is lost across os.execv().\n        sys.stderr.flush()\n        sys.stdout.flush()\n\n        # The state machine was not yet cleaning up, do it in/' $WRAPPER && \
    sed -i '/^        machine = MACHINES\.classes\[self\._job_type\]($/{ N; N; N; s/        machine = MACHINES\.classes\[self\._job_type\](\n            self\._job_params)\n\n        try:/        # Write result file even if the machine cannot be instantiated.\n        try:\n            machine = MACHINES.classes[self._job_type](\n                self._job_params)\n        except Exception:\n            sys.excepthook(*sys.exc_info())\n            sys.stderr.flush()\n            sys.stdout.flush()\n            self._write_result(ret_code, RESULT_EXCEPTION)\n            return\n\n        try:/; }' $WRAPPER
EOF

# Insert the patch block after the "git clone $git_repo repo-tessia" line.
sed -i "/git clone \$git_repo repo-tessia/r $PATCH_FILE" "$DOCKERFILE"

rm -f "$PATCH_FILE"
echo "Scheduler fork-patch RUN block injected into Dockerfile."
