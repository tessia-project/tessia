#!/bin/bash
# Copyright 2024, 2024 IBM Corp.
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

log() {
	local log_level msg_log_level msg_header

	case "${1}" in
	ERROR | error)
		msg_log_level=0
		;;
	WARN | warn)
		msg_log_level=1
		;;
	INFO | info)
		msg_log_level=2
		;;
	DEBUG | debug)
		msg_log_level=3
		;;
	esac

	case "${ASSETS_LOG_LEVEL-INFO}" in
	ERROR | error)
		log_level=0
		;;
	WARN | warn)
		log_level=1
		;;
	INFO | info)
		log_level=2
		;;
	DEBUG | debug)
		log_level=3
		;;
	esac

	if ((msg_log_level <= log_level)); then
		msg_header="$(date "+%Y-%m-%d %H:%M:%S") | $1 | ${0##*/} |"
		case "$1" in
		ERROR | error | WARN | warn | DEBUG | debug)
			shift
			echo "${msg_header} $*" >&2
			;;
		INFO | info)
			shift
			echo "${msg_header} $*"
			;;
		esac
	fi
}

log INFO "Setup test environment"
while IFS=':' read -r system hostname user pass gh_token; do
	if [[ -z "${system}" ]]; then
		log ERROR "System name not set in tela-host inventory file"
		exit 1
	fi
	if [[ -z "${hostname}" ]]; then
		log ERROR "Hostname for system ${system} not set in tela-host inventory file"
		exit 1
	fi
	if [[ -z "${user}" ]]; then
		log ERROR "Username for system ${system} not set in tela-host inventory file"
		exit 1
	fi
	if [[ -z "${pass}" ]]; then
		log ERROR "Password for user ${user} of system ${system} not set in tela-host inventory file"
		exit 1
	fi
	if [[ -z "${gh_token}" ]]; then
		log ERROR "gh_token for system ${system} not set in tela-host inventory file"
		exit 1
	fi

	export SSHPASS="${pass}"

	log INFO "Add hostname ${hostname} of system ${system} to known hosts (this triggers a hostname lookup)"
	if ! ssh-keyscan -H ${hostname} >>~/.ssh/known_hosts 2>/dev/null; then
		log ERROR "Could not add hostname ${hostname} of system ${system} to known hosts"
		exit 1
	fi

	# Resolve test case dependencies to git repositories
	(
		log INFO "Resolve test case dependencies"
		# Input is "oauth2:<github-token>", remove "oauth2:"
		gh_token="${gh_token##*:}"
		pushd ~/test-workspace/${ASSETS_REPO_NAME} &>/dev/null || exit 1
		export GITHUB_TOKEN="${gh_token}"
		make deps-prepare-for-offline || exit 1
		unset -v GITHUB_TOKEN || exit 1
	) || exit 1

	# Execute in docker environment instead of remote system
	if ((ASSETS_TELA_RUN_LOCAL)); then
		log INFO "Execute tela test case"
		(
			# Include environment block if available
			[[ -r ~/test-workspace/.config/environment ]] && source ~/test-workspace/.config/environment
			export TESSIA_RUN_LOCAL="${ASSETS_TELA_RUN_LOCAL}"
			# Use hostname(FQDN) instead of the system name
			# Required because $system does not have to be the network hostname
			# Otherwise it would also require changes to all test cases that
			# already exploit the TESSIA_SYSTEM variable.
			export TESSIA_SYSTEM="${hostname}"
			export TESSIA_SYSTEM_USER="${user}"
			export TESSIA_SYSTEM_PASS="${pass}"
			# Switch directory to repository
			pushd ~/test-workspace/${ASSETS_REPO_NAME} &>/dev/null || exit 1
			# Build test cases that rely on make
			make -j$(nproc) || exit 1
			# Execute tests
			make PRETTY=0 check ${ASSETS_TELA_TESTS:+TESTS="${ASSETS_TELA_TESTS}"} ${ASSETS_TELA_OPTS}
		) || exit 1
	else
		log INFO "Copy test case to remote system ${system} with hostname ${hostname}"
		sshpass -e rsync -az --chown=${user}:${user} ~/test-workspace/${ASSETS_REPO_NAME} ${user}@${hostname}:~/test-workspace ||
			exit 1

		log INFO "Execute tela test case on remote system ${system} with hostname ${hostname}"
		sshpass -e ssh -T ${user}@${hostname} <<-EOF || exit 1
			# Include environment block if available
			$([[ -r ~/test-workspace/.config/environment ]] && cat ~/test-workspace/.config/environment)
			export TESSIA_RUN_LOCAL="${ASSETS_TELA_RUN_LOCAL}"
			# Switch directory to repository
			pushd ~/test-workspace/"${ASSETS_REPO_NAME}" &>/dev/null || exit 1
			# Build test cases that rely on make
			make -j\$(nproc) || exit 1
			# Execute tests
			make PRETTY=0 check ${ASSETS_TELA_TESTS:+TESTS=\"${ASSETS_TELA_TESTS}\"} ${ASSETS_TELA_OPTS}
		EOF
	fi
done <~/test-workspace/.config/tela-hosts
