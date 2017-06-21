FROM ubuntu:latest

# by default we expect the git repo to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variable
# to point to another location
ARG git_repo=/assets/tessia-engine.git

# whether we are building a container for production use
ARG prod_build=true

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each on why is it needed.
    apt-get -yq install --no-install-recommends \
    # to manage the system locale
    locales \
    # used to install python libraries
    python3-pip \
    # used by pbr (in setuptools) to detect module version numbers
    git \
    # for wrapt (from pylint)
    build-essential \
    python3-dev > /dev/null && \
    # clean the cache to free up space
    apt-get -q clean && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # Install the python dependencies.
    # setuptools for installing applications (including tessia) - it must be installed
    # separately first otherwise other packages fail to install
    pip3 -q install -U setuptools && \
    pip3 -q install -U \
    # this is to update the pip version if necessary
    pip \
    # pbr is used in setuptools
    pbr && \
    # add the admin user for administrative work
    useradd -ms /bin/bash admin

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

COPY assets /assets/

RUN cd /assets && \
    git clone $git_repo tessia-engine && \
    cd tessia-engine/cli && \
    pip3 -q install -U -r requirements.txt && \
    ./setup.py -q install && \
    # remove unneeded dependencies used only for building
    apt-get -yq purge --auto-remove \
    build-essential \
    python3-dev > /dev/null && \
    mv /assets/entrypoint /entrypoint && \
    rm -rf /assets

CMD ["/entrypoint"]
