FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

COPY assets /assets

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    apt-get -yq install --no-install-recommends \
    # to manage the system locale
    locales \
    # used to install python libraries
    python3-pip \
    # these are needed to compile ansible dependencies
    build-essential libssl-dev libffi-dev python3-dev \
    # so that rsync module in ansible works
    rsync \
    # clone repositories
    git > /dev/null && \
    # clean the cache to free up space
    apt-get -q clean && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # set up python packaging tools
    pip3 -q install -U setuptools pip && \
    # remove pip from distro to avoid conflicts
    apt-get -y remove python3-pip && hash -r && \
    # dependencies for entrypoint
    pip3 -q install -U ansible \
    # used by downloader.py
    requests && \
    chmod a+x /assets/downloader.py && \
    # add the ansible user for less privileged playbook execution
    # /home/ansible folder is created to have a working directory
    useradd --create-home --shell /bin/bash ansible && \
    # add empty folder to clone ansible playbook to
    mkdir /home/ansible/playbook && \
    chown ansible:ansible /home/ansible/playbook

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

WORKDIR /home/ansible

ENTRYPOINT ["/bin/cat"]
