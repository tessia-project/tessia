#!/usr/bin/env python3
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

"""
Utility for downloading repositories via git/http/https
"""

#
# IMPORTS
#
from logging import INFO as logging_INFO
from logging import getLogger
from logging.config import dictConfig
from urllib.parse import urlsplit, urlunsplit

import os
import requests
import subprocess

#
# CONSTANTS AND DEFINITIONS
#
LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)s | %(levelname)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'DEBUG',
            'stream': 'ext://sys.stdout'
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    }
}

# max allowed size for source repositories
MAX_REPO_MB_SIZE = 100
# max number of commits for cloning
MAX_GIT_CLONE_DEPTH = '10'

#
# CODE
#


class RepoDownloader:
    """
    Download repositories from git, web or as a tarball.
    The URL is read from an environment variable.
    """

    def __init__(self, repo_url):
        """
        Args:
            repo_url (str): The repository url (git or web tarball)
        """
        self._logger = getLogger(__name__)

        self._repo_info = self._parse_source(repo_url)
    # __init__()

    @staticmethod
    def _get_url_type(parsed_url):
        """
        Return a string representing the type of the url provided.

        Args:
            parsed_url (urllib.parse.SplitResult): result of urlsplit

        Returns:
            str: web, git or unknown
        """
        http_protocols = ['http', 'https']

        if parsed_url.scheme == 'git' or (
                parsed_url.scheme in http_protocols and
                (parsed_url.path.endswith('.git') or
                 '.git@' in parsed_url.path)):
            return 'git'

        if parsed_url.scheme in http_protocols:
            return 'web'

        return 'unknown'
    # _get_url_type()

    @classmethod
    def _parse_source(cls, source_url):
        """
        Parse and validate the passed repository url.

        Args:
            source_url (str): repository network url

        Raises:
            ValueError: if validation of parameters fails
            RuntimeError: if subprocess execution fails

        Returns:
            dict: a dictionary containing the parsed information
        """
        # parse url into components
        parsed_url = urlsplit(source_url)
        if not parsed_url.netloc:
            raise ValueError("Invalid URL '{}'".format(source_url))

        repo = {
            'url': source_url,
            'git_branch': None,
            'git_commit': 'HEAD',
            'type': cls._get_url_type(parsed_url),
            'url_obs': cls._url_obfuscate(parsed_url),
            'url_parsed': parsed_url,
        }

        # git source: use git command to verify it
        if repo['type'] == 'git':
            # parse git revision info (branch, commit/tag)
            try:
                _, git_rev = parsed_url.path.rsplit('@', 1)
                repo['url'] = parsed_url.geturl().replace('@' + git_rev, '')
                repo['git_branch'] = git_rev
                repo['git_branch'], repo['git_commit'] = git_rev.rsplit(':', 1)
            except ValueError:
                # user did not specify additional git revision info,
                # use default values
                pass

            # if no branch has been specified look for main and master branches
            if not repo['git_branch']:
                git_branch = ['main', 'master']
            else:
                git_branch = [repo['git_branch']]

            process_env = os.environ.copy()
            process_env['GIT_SSL_NO_VERIFY'] = 'true'
            try:
                git_output = subprocess.run(
                    ['git', 'ls-remote', '--heads',
                     repo['url']] + git_branch,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=process_env,
                    check=True,
                    universal_newlines=True
                )
            except subprocess.CalledProcessError as exc:
                # re-raise and suppress context, which has unscreened repo url
                raise ValueError('Source url is not accessible: {} {}'.format(
                    str(exc).replace(repo['url'], repo['url_obs']),
                    exc.stderr.replace(repo['url'],
                                       repo['url_obs']))) from None
            except OSError as exc:
                # re-raise and suppress context, which has unscreened repo url
                raise RuntimeError('Failed to execute git: {}'.format(
                    str(exc).replace(repo['url'], repo['url_obs']))) from None

            reflist = git_output.stdout.splitlines()
            if not reflist:
                raise ValueError('Branch not found in reflist: {}'.format(
                    str(repo['git_branch'])))
            # reflist looks like "hash<TAB>ref", we display both;
            # see https://git-scm.com/docs/git-ls-remote.html#_examples
            # Note that the same hash can be referred by multiple refs,
            # so reflist may contain several elements
            # If reflist contains two results we have main and master
            # In this case we can't decide which branch is the default branch
            if not repo['git_branch'] and len(reflist) == 2:
                raise ValueError('Repository has main and master branch!')
            if not repo['git_branch'] and len(reflist) == 1:
                ref_branch = reflist[0].split("\t")[1]
                if 'master' in ref_branch:
                    repo['git_branch'] = 'master'
                else:
                    repo['git_branch'] = 'main'
                repo['git_refhead'] = reflist[0].split("\t")[0]
            else:
                repo['git_refhead'] = reflist[0].split("\t")[0]

        # http source: use the requests lib to verify it
        elif repo['type'] == 'web':
            file_name = os.path.basename(parsed_url.path)
            # file to download is not in supported format: report error
            if not (file_name.endswith('tgz') or file_name.endswith('.tar.gz')
                    or file_name.endswith('.tar.bz2')):
                raise ValueError(
                    "Unsupported file format '{}'".format(file_name))

            # verify if url is accessible
            try:
                # set a reasonable timeout, let's not wait too long as the
                # scheduler is possibly waiting
                resp = requests.get(
                    source_url, stream=True, verify=False, timeout=5)
                resp.raise_for_status()
                resp.close()
            except requests.exceptions.HTTPError as exc:
                raise ValueError(
                    "Source url is not accessible: {} {}".format(
                        exc.response.status_code, exc.response.reason))
            except requests.exceptions.RequestException as exc:
                raise ValueError(
                    "Source url is not accessible: {}".format(str(exc)))

        else:
            raise ValueError('Unsupported source url specified')

        return repo
    # _parse_source()

    def _download_git(self):
        """
        Download a repository from a git url
        """
        repo = self._repo_info
        repo_name = repo['url_parsed'].path.split('/')[-1]
        self._logger.info('cloning git repo %s from %s branch %s/%s commit %s',
                          repo_name, repo['url_obs'], repo['git_branch'],
                          repo['git_refhead'], repo['git_commit'])

        # Since git doesn't allow to clone specific commit and for
        # optimal resources usage, we set the depth of cloning.
        # So by default we take only the last commit. But if an user specifies
        # a target commit, then we set the predefined depth value.
        if repo['git_commit'] == 'HEAD':
            depth = '1'
        else:
            depth = MAX_GIT_CLONE_DEPTH

        cmd = ['git', 'clone', '-n', '--depth', depth,
               '-b', repo['git_branch'], repo['url'], '.']
        self._logger.debug('cloning git repo with: %s',
                           ' '.join(cmd).replace(repo['url'], repo['url_obs']))
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env={'GIT_SSL_NO_VERIFY': 'true'},
                check=True,
                universal_newlines=True
            )
        except subprocess.CalledProcessError as exc:
            # re-raise and suppress context, which has unscreened repo url
            raise ValueError('Failed to git clone: {} {}'.format(
                str(exc).replace(repo['url'], repo['url_obs']),
                exc.stderr.replace(repo['url'], repo['url_obs']))) from None
        except OSError as exc:
            # re-raise and suppress context, which has unscreened repo url
            raise RuntimeError('Failed to execute git: {}'.format(
                str(exc).replace(repo['url'], repo['url_obs']))) from None

        cmd = ['git', 'reset', '--hard', repo['git_commit']]
        self._logger.debug('setting git HEAD with: %s', ' '.join(cmd))
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
                universal_newlines=True
            )
        except subprocess.CalledProcessError as exc:
            # re-raise and suppress context, which may have unscreened repo url
            raise ValueError(
                'Failed to checkout to {}, make sure it is not older than {} '
                'commits. Received error: {}'.format(
                    repo['git_commit'],
                    MAX_GIT_CLONE_DEPTH,
                    exc.stderr.replace(
                        repo['url'], repo['url_obs']))) from None
        except OSError as exc:
            # re-raise and suppress context, which may have unscreened repo url
            raise RuntimeError('Failed to execute git: {}'.format(
                str(exc).replace(repo['url'], repo['url_obs']))) from None

        cmd = ['rm', '-rf', '.git']
        self._logger.debug('Remove .git directory: %s', ' '.join(cmd))
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
                universal_newlines=True
            )
        except OSError as exc:
            # re-raise and suppress context, which may have unscreened repo url
            raise RuntimeError('Failed to remove .git directory: {}'.format(
                str(exc).replace(repo['url'], repo['url_obs']))) from None
    # _download_git()

    def _download_web(self):
        """
        Download a repository from a web url
        """
        repo = self._repo_info
        file_name = repo['url_parsed'].path.split('/')[-1]

        # determine how to extract the source file
        tar_flags = ''
        if file_name.endswith('tgz') or file_name.endswith('.tar.gz'):
            tar_flags = 'zxf'
        elif file_name.endswith('.tar.bz2'):
            tar_flags = 'jxf'
        # should never happen as it was validated by parse before
        if not tar_flags:
            raise RuntimeError('Unsupported source file format')

        self._logger.info(
            'downloading compressed file from %s', repo['url_obs'])

        try:
            resp = requests.get(
                self._repo_info['url'], stream=True, verify=False,
                timeout=5)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ValueError(
                "Source url is not accessible: {} {}".format(
                    exc.response.status_code, exc.response.reason))

        # define a sane maximum size to avoid consuming all space from the
        # filesystem
        if (int(resp.headers['content-length']) >
                MAX_REPO_MB_SIZE * 1024 * 1024):
            raise RuntimeError('Source file exceeds max allowed size '
                               '({}MB)'.format(MAX_REPO_MB_SIZE))

        # download the file
        chunk_size = 10 * 1024
        with open(file_name, 'wb') as file_fd:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                file_fd.write(chunk)

        # extract file
        try:
            subprocess.run(
                ['tar', tar_flags, file_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError('Failed to extract file: {}'.format(
                exc.stderr.decode('utf8')))
        except OSError as exc:
            raise RuntimeError('Failed to execute tar: {}'.format(
                str(exc)))

        # source file not needed anymore, free up disk space
        os.remove(file_name)
    # _download_web()

    def download(self):
        """
        Download the repository from the network
        """
        if self._repo_info['type'] == 'git':
            self._download_git()
        elif self._repo_info['type'] == 'web':
            self._download_web()
        # should never happen as it was validated by parse before
        else:
            raise RuntimeError('Unsupported source url')
    # download()

    @staticmethod
    def _url_obfuscate(parsed_url):
        """
        Obfuscate sensitive information (i.e. user and password) from the
        repository URL.

        Args:
            parsed_url (urllib.parse.SplitResult): result of urlsplit

        Returns:
            str: url with obfuscated user credentials
        """
        try:
            _, host_name = parsed_url.netloc.rsplit('@', 1)
        except ValueError:
            return parsed_url.geturl()
        repo_parts = [*parsed_url]
        repo_parts[1] = '{}@{}'.format('****', host_name)

        return urlunsplit(repo_parts)
    # _url_obfuscate()
# RepoDownloader


def main():
    """
    Entry point
    """
    try:
        log_level = int(os.environ.get(
            'ASSETS_LOG_LEVEL', logging_INFO))
    except (TypeError, ValueError):
        log_level = logging_INFO
    dictConfig(LOG_CONFIG)
    getLogger().setLevel(log_level)

    repo_url = os.environ.get('ASSETS_REPO_URL')
    if not repo_url:
        raise RuntimeError(
            'Env variable ASSETS_REPO_URL not set')

    downloader = RepoDownloader(repo_url)
    downloader.download()
# main()


if __name__ == '__main__':
    main()
