#!/bin/bash
# Description: Autocomplete for option values in addition to the click provided subcommand and option autocomplete feature
# Author:      André Wild <andre.wild1@ibm.com>
# Date:        2022-06-10

# Use generated functions but remove setup call
eval "$(_TESS_COMPLETE=source_bash tess | head -n -1)"

__TESS_COMPLETION_CACHE_PATH=~/".tessia-cli/bash-completion"

# Override generated function
# Will be used by the auto generated setup function
_tess_completion() {
	local cur comps system i
	# Create directory for cache files
	test -d "${__TESS_COMPLETION_CACHE_PATH}" || mkdir -p "${__TESS_COMPLETION_CACHE_PATH}"

	cur="${COMP_WORDS[COMP_CWORD]}"
	if ((${#COMP_WORDS[@]} >= 2)); then
		case "${COMP_WORDS[1]}" in
		autotemplate)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--name | --template)
				(__tess_get_information "autotemplates" update &)
				comps="$(__tess_get_information "autotemplates")"
				;;
			--owner)
				(__tess_get_information "users" update &)
				comps="$(__tess_get_information "users")"
				;;
			--project)
				(__tess_get_information "projects" update &)
				comps="$(__tess_get_information "projects")"
				;;
			esac
			;;
		job)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--id)
				(__tess_get_information "jobs-own-running" update &)
				comps="$(__tess_get_information "jobs-own-running")"
				;;
			--owner)
				(__tess_get_information "users" update &)
				comps="$(__tess_get_information "users")"
				;;
			--parmfile)
				local copy
				__tess_filedir
				# Filter files that are not yaml files
				for ((i = ${#COMPREPLY[@]}; i >= 0; i--)); do
					if [[ -d "${COMPREPLY[$i]}" || "${COMPREPLY[$i]}" =~ .yml$|.yaml$|.parmfile$ ]]; then
						copy+=("${COMPREPLY[$i]}")
					fi
				done
				COMPREPLY=("${copy[@]}")
				return 0
				;;
			--state)
				comps="$(__tess_get_job_states)"
				;;
			--type)
				comps="$(__tess_get_job_types)"
				;;
			esac
			;;
		net)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--owner)
				(__tess_get_information "users" update &)
				comps="$(__tess_get_information "users")"
				;;
			--project)
				(__tess_get_information "projects" update &)
				comps="$(__tess_get_information "projects")"
				;;
			--system)
				(__tess_get_information "systems-all" update &)
				comps="$(__tess_get_information "systems-all")"
				;;
			esac
			;;
		perm)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--login)
				(__tess_get_information "users" update &)
				comps="$(__tess_get_information "users")"
				;;
			--project)
				(__tess_get_information "projects" update &)
				comps="$(__tess_get_information "projects")"
				;;
			--role)
				(__tess_get_information "user-roles" update &)
				comps="$(__tess_get_information "user-roles")"
				;;
			esac
			;;
		os)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--name | --os)
				(__tess_get_information "os-list" update &)
				comps="$(__tess_get_information "os-list")"
				;;
			--template)
				(__tess_get_information "autotemplates" update &)
				comps="$(__tess_get_information "autotemplates")"
				;;
			--type)
				(__tess_get_information "os-types" update &)
				comps="$(__tess_get_information "os-types")"
				;;
			esac
			;;
		storage)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--server)
				(__tess_get_information "storage-servers" update &)
				comps="$(__tess_get_information "storage-servers")"
				;;
			esac
			;;
		system)
			case "${COMP_WORDS[$((COMP_CWORD - 1))]}" in
			--model)
				(__tess_get_information "systems-models" update &)
				comps="$(__tess_get_information "systems-models")"
				;;
			--os)
				(__tess_get_information "os-list" update &)
				comps="$(__tess_get_information "os-list")"
				;;
			--owner)
				(__tess_get_information "users" update &)
				comps="$(__tess_get_information "users")"
				;;
			--profile)
				system="$(__tess_get_system_option "${COMP_WORDS[@]}")"
				#shellcheck disable=SC2181
				if (($? != 0)); then
					return 1
				fi
				(__tess_get_system_profiles "${system}" update &)
				comps="$(__tess_get_system_profiles "${system}")"
				;;
			--system)
				(__tess_get_information "systems-assigned" update &)
				comps="$(__tess_get_information "systems-assigned")"
				;;
			--template)
				(__tess_get_information "autotemplates" update &)
				comps="$(__tess_get_information "autotemplates")"
				;;
			--type)
				(__tess_get_information "systems-types" update &)
				comps="$(__tess_get_information "systems-types")"
				;;
			esac
			;;
		esac
		if [ -n "${comps}" ]; then
			# Generate possible completions
			# shellcheck disable=SC2207
			COMPREPLY=($(compgen -W "${comps}" -- "${cur}"))
			return 0
		fi
	fi

	IFS=$'\n'
	# shellcheck disable=SC2207
	COMPREPLY=($(env COMP_WORDS="${COMP_WORDS[*]}" \
		COMP_CWORD="$COMP_CWORD" \
		_TESS_COMPLETE=complete "$1"))
	return 0
}

__tess_get_system_profiles() {
	local lock file tmp name system

	system="$1"
	name="system-profiles-${system}"
	lock="${__TESS_COMPLETION_CACHE_PATH}/${name}.lock"
	tmp="${__TESS_COMPLETION_CACHE_PATH}/${name}.tmp"
	file="${__TESS_COMPLETION_CACHE_PATH}/${name}"

	case "$2" in
	update)
		if mkdir "${lock}" &>/dev/null; then
			trap '[[ -e "${lock}" ]] && rm -rf -- "${lock}"' RETURN EXIT SIGHUP SIGINT SIGTERM
			tess system prof-list --system "${system}" 2>/dev/null | awk 'NR > 3 { print $1 }' |
				sort >"${tmp}"
			if __tess_verify_pipestatus "${PIPESTATUS[@]}" && [[ -f "${tmp}" ]]; then
				if mv -f "${tmp}" "${file}"; then
					return 0
				fi
			fi
		fi
		return 1
		;;
	*)

		if [ -f "${file}" ]; then
			cat "${file}" &&
				return 0
		fi
		;;
	esac
	return 1
}

__tess_get_information() {
	local lock file tmp name

	if [[ -z "$1" ]]; then
		return 1
	fi

	name="$1"
	lock="${__TESS_COMPLETION_CACHE_PATH}/${name}.lock"
	tmp="${__TESS_COMPLETION_CACHE_PATH}/${name}.tmp"
	file="${__TESS_COMPLETION_CACHE_PATH}/${name}"

	case "$2" in
	update)
		if mkdir "${lock}" &>/dev/null; then
			trap '[[ -e "${lock}" ]] && rm -rf -- "${lock}"' RETURN EXIT SIGHUP SIGINT SIGTERM
			case "${name}" in
			autotemplates)
				tess autotemplate list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			jobs-own-running)
				tess job list --my --state "RUNNING" 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			os-list)
				tess os list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			os-types)
				tess os list 2>/dev/null | awk 'NR > 3 { print $3 }' | sort | uniq >"${tmp}"
				;;
			projects)
				tess perm project-list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			storage-servers)
				tess storage server-list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			systems-all)
				tess system list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			systems-assigned)
				tess system list --my 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			systems-models)
				tess system list | awk ' NR > 3 { print $7 }' | sort | uniq >"${tmp}"
				;;
			systems-types)
				tess system list | awk ' NR > 3 { print $5 }' | sort | uniq >"${tmp}"
				;;
			user-roles)
				tess perm role-list 2>/dev/null | awk '/^Role +:/ { print $3}' | sort >"${tmp}"
				;;
			users)
				tess perm user-list 2>/dev/null | awk 'NR > 3 { print $1 }' | sort >"${tmp}"
				;;
			esac
			if __tess_verify_pipestatus "${PIPESTATUS[@]}" && [[ -f "${tmp}" ]]; then
				if mv -f "${tmp}" "${file}"; then
					return 0
				fi
			fi
		fi
		return 1
		;;
	*)

		if [ -f "${file}" ]; then
			cat "${file}" &&
				return 0
		fi
		;;
	esac
	return 1
}

__tess_get_job_states() {
	local states
	states=("COMPLETED" "FAILED" "CANCELED" "RUNNING" "WAITING" "EXECUTE")
	echo "${states[*]}"
	command -v tr &>/dev/null &&
		echo "${states[*]}" | tr "[:upper:]" "[:lower:]"
	return 0
}

__tess_get_job_types() {
	local types
	types=("ansible" "autoinstall" "tela" "powerman")
	echo "${types[*]}"
	return 0
}

__tess_verify_pipestatus() {
	local i
	if (($# > 0)); then
		for ((i = 1; i <= $#; i++)); do
			if ((${!i} != 0)); then
				return 1
			fi
		done
		return 0
	fi
	return 1
}

__tess_get_system_option() {
	while (($# >= 0)); do
		if [[ "$1" == "--system" ]]; then
			echo "${2}"
			return 0
		fi
		shift
	done
	return 1
}

__tess_filedir() {
	#Check if default implementation is available
	if type -t _filedir &>/dev/null; then
		_filedir "$@"
		return $?
	fi

	local -a tokens
	local tmp x

	if [ -z "$1" ]; then
		# read all files
		x=$(compgen -f -- "$cur") || return 1
		while read -r tmp; do
			tokens+=("$tmp")
		done <<<"$x"
	elif [[ "$1" == "-d" ]]; then
		# read all directories
		x=$(compgen -d -- "$cur") || return 1
		while read -r tmp; do
			tokens+=("$tmp")
		done <<<"$x"
	fi

	if [[ ${#tokens[@]} -ne 0 ]]; then
		COMPREPLY+=("${tokens[@]}")
	fi
	return 0
}

# Python click: Bug in auto generated function names
if type _tess_completionetup &>/dev/null; then
	_tess_completionetup
elif type _tess_completionsetup &>/dev/null; then
	_tess_completionsetup
fi

# Only execute if not sourced
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	if [[ "$#" != 1 || -z "$1" ]]; then
		echo "[Error] This script requires the destination hostname or ip" >&2
		exit 1
	fi
	echo "[Setup] Copy completion file to: '${1}:~/.tessia-bash-completion.sh'"
	if ! scp "$(readlink -f "$0")" "${1}":~/.tessia-bash-completion.sh; then
		echo "[Error] Could not copy files to '$1'" >&2
		exit 1
	fi
	echo "[Setup] Source file .bashrc on remote system '$1'" >&2
	if ! ssh "$1" -- "echo 'source ~/.tessia-bash-completion.sh' >> ~/.bashrc"; then
		echo "[Error] Could not add file to .bashrc on '$1'" >&2
		exit 1
	fi
	echo "[Setup] Successfull"
	exit 0
fi
