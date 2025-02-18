# syntax=docker/dockerfile:1.3
FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

COPY assets /assets

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    apt-get -yq install --no-install-recommends \
    # to manage the system locale
    locales \
    # these are needed to compile and use tela
    build-essential iproute2\
	# required for https certificate verification
	ca-certificates \
    # ssh login with password
    sshpass openssh-client \
	# Copy files to remote
	rsync \
	# python downloader dependencies
	python3-pip python3-dev python3-setuptools python3-requests \
    libssl-dev libffi-dev cargo rustc \
    # clone repositories
    git >/dev/null && \
    # clean the cache to free up space
    apt-get -q clean && \
	# add execution flags to downloader script
    chmod a+rx /assets/downloader.py && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # add the tela user for less privileged playbook execution
    # /home/tela folder is created to have a working directory
    useradd --create-home --shell /bin/bash tela

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# Switch to tela user
WORKDIR /home/tela
USER tela

# Setup user space
RUN --mount=type=secret,id=github-token,uid=1000,gid=1000 \
	# Add github.ibm.com to known_hosts
	mkdir -m 700 .ssh && ssh-keyscan -t ecdsa github.ibm.com 2>/dev/null > .ssh/known_hosts && \
	echo -e "Host *" > ~/.ssh/config && \
	echo -e "\tPreferredAuthentications password" >> ~/.ssh/config && \
	echo -e "\tServerAliveInterval 360" >> ~/.ssh/config && \
	echo -e "\tServerAliveCountMax 3" >> ~/.ssh/config && \
	# Create folder for inventory and config files
	mkdir -p test-workspace/.config

ENTRYPOINT ["/bin/cat"]
