#!/bin/sh
# Copyright 2016, 2017 IBM Corp.
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

# determine the dir containing the git hooks to be installed
mydir=$(dirname `readlink -f $0`)
hookdir=".git/hooks"
targetdir="$mydir/../$hookdir"

if [ ! -d "$targetdir" ]; then
    echo "FATAL: no $hookdir directory found" >&2
    exit 1
fi

# change to the hooks dir and copy each hook from source dir
pushd "${mydir}/git-hooks" &>/dev/null
for file in *; do
    echo "INFO: applying hook $file"
    # hook already exists: make a backup before copying
    if [ -e "$targetdir/$file" ]; then
        echo "WARN: $file exists; saving as ${file}.local"
        cp "$targetdir/$file" "$targetdir/${file}.local"
    fi
    cp "$file" "${targetdir}/"
done

popd &>/dev/null
echo "done"
