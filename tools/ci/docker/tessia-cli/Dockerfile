FROM public.ecr.aws/ubuntu/ubuntu:20.04

# by default we expect the git repo to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variable
# to point to another location
ARG git_repo=/assets/tessia.git

ARG DEBIAN_FRONTEND=noninteractive

ARG user=tessia
ARG group=tessia
ARG uid=1000
ARG gid=1000

RUN groupadd -g ${gid} ${group} && \
    useradd -u ${uid} -g ${gid} -m ${user}

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each on why is it needed.
    apt-get -yq install --no-install-recommends \
    # required for autocompletion feature of the tessia cli client
    bash-completion \
    # to manage the system locale
    locales \
    # used to install python libraries
    python3-pip \
    # used by setuptools to detect module version numbers
    git \
    # for wrapt (from pylint)
    build-essential \
    python3-dev > /dev/null && \
    # clean the cache to free up space
    apt-get -q clean && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # set up python packaging tools
    pip3 -q install -U "setuptools==49.6.0" pip && \
    # remove pip from distro to avoid conflicts
    apt-get -y remove python3-pip && hash -r && \
    # add the admin user for administrative work
    useradd --create-home --shell /bin/bash admin

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

COPY assets /assets/

RUN cd /assets && \
    git clone $git_repo repo-tessia && \
    cd repo-tessia/cli && \
    # call pip through the wrapper so that versioning works
    ./pip-install -U -r dev-requirements.txt . && \
    # remove unneeded dependencies used only for building
    apt-mark hold python3 && \
    apt-get -yq purge --auto-remove \
    build-essential \
    python3-dev > /dev/null && \
    mv /assets/entrypoint /entrypoint && \
    cp ./bash/tessia-bash-completion.sh /etc/bash_completion.d/tessia-bash-completion.sh && \
    chmod 644 /etc/bash_completion.d/tessia-bash-completion.sh && \
    rm -rf /assets

RUN mkdir -p /etc/tessia-cli && \
    chown -R ${user}:${group} /etc/tessia-cli

VOLUME ["/etc/tessia-cli"]

USER ${user}

ENTRYPOINT ["/entrypoint"]
