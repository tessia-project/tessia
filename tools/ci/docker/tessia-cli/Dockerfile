FROM ubuntu:latest

# by default we expect the git repo to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variable
# to point to another location
ARG git_repo=/assets/tessia-engine.git

# whether we are building a container for production use
ARG prod_build=true

# Set the locale for this container to UTF-8 for this session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# Generate en_US.UTF-8 locale and update the default locale, some
# applications use this.
RUN locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each on why is it needed.
    apt-get update -q \
    && DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
    # used to install python libraries
    python3-pip \
    # used by pbr (in setuptools) to detect module version numbers
    git && \
    # Install the python dependencies.
    # setuptools for installing applications (including tessia) - it must be installed
    # separately first otherwise other packages fail to install
    pip3 install -U setuptools && \
    pip3 install -U \
    # this is to update the pip version if necessary
    pip \
    # pbr is used in setuptools
    pbr \
    # dependencies used for testing builds - they must come
    # after setuptools installation
    pylint \
    coverage

COPY assets /assets/

RUN cd /assets && \
    git clone $git_repo tessia-engine && \
    cd tessia-engine/cli && \
    pip3 install -U -r requirements.txt && \
    ./setup.py install

EXPOSE 22

# entry point should be ssh daemon
CMD ["/assets/entrypoint"]
