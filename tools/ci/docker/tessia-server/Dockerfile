FROM ubuntu:18.04 as base

# by default we expect the git repos to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variables
# to point to another location
ARG git_repo=file:///assets/tessia.git

ARG DEBIAN_FRONTEND=noninteractive

# this flag determines whether the entrypoint should try to automatically initialize
# an empty database or perform schema upgrades via tess-dbmanage. Use with care
# as you might lose db data.
ENV TESSIA_DB_AUTOMANAGE false

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    apt-get -yq install --no-install-recommends \
    # to manage the system locale
    locales \
    # used by baselib to check if hosts are up
    iputils-ping \
    # used by baselib for zvm communication
    s3270 \
    # used to install python libraries
    python3-pip \
    # used by setuptools to detect module version numbers
    git \
    # these are needed to build cryptography (dep chain is baselib -> paramiko ->
    # cryptography) and uwsgi
    build-essential libssl-dev libffi-dev python3-dev \
    # build python postgres connector (psycopg2)
    libpq-dev \
    # to use python postgres connector (psycopg2)
    libpq5 \
    # useful for administration tasks
    vim \
    # rust compiler for python cryptography
    cargo rustc \
    # required by ansible when using ssh connection plugin
    sshpass openssh-client \
    # init-like daemon to manage our services' processes
    supervisor > /dev/null && \
    # set up python packaging tools
    pip3 -q install -U "setuptools==49.6.0" pip && \
    # remove pip from distro to avoid conflicts
    apt-get -y remove python3-pip && hash -r && \
    # clean the cache to free up space
    apt-get -q clean && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

COPY assets /assets/

# get the code
RUN cd /assets && \
    git clone $git_repo repo-tessia

### Components builder
FROM base as components-build

RUN \
    # output directory
    mkdir /assets/bin && \
    cd /assets/repo-tessia && \
    # build components
    cd /assets/repo-tessia/components/installer-webhook && \
    cargo test && cargo build --release && \
    mv /assets/repo-tessia/build/release/installer-webhook /assets/bin && \
    rm -rf /assets/repo-tessia/build

### Server image
FROM base as server

ARG user=tessia
ARG group=tessia
ARG uid=1000
ARG gid=1000

RUN groupadd -g ${gid} ${group} && \
    useradd -u ${uid} -g ${gid} -m ${user}

# server installation
RUN cd /assets/repo-tessia && \
    # web server for api service
    pip3 -q install -U uwsgi && \
    # server installation
    pip3 install -U -r requirements.txt -r dev-requirements.txt . && \
    ./setup.py -q install_data && \
    # files settings
    install -m 700 -g ${group} -o ${user} -d /etc/tessia && \
    install -m 600 -g ${group} -o ${user} /usr/local/etc/tessia/* /etc/tessia && \
    rm -rf /usr/local/etc/tessia && \
    install -m 755 -g ${group} -o ${user} -d /var/tessia /var/tessia/jobs /var/tessia/www /var/log/tessia && \
    # used to manage startup of the api and scheduler daemons
    cp /assets/supervisord.conf /etc/supervisor/conf.d/tessia.conf && \
    # tool used to handle yaml files from cmdline
    cp /assets/yamlman /usr/local/bin/ && \
    # by default log files are relative paths for use in virtualenvs, we change it here
    sed -i 's,^\( \+filename:\) log/\(.*\)$,\1 /var/log/\2,g' /etc/tessia/server.yaml && \
    # same for www/jobs dirs
    yamlman update /etc/tessia/server.yaml auto_install.dir /var/tessia/www && \
    yamlman update /etc/tessia/server.yaml scheduler.jobs_dir /var/tessia/jobs && \
    # cleanup section - remove unneeded resources
    cd / && \
    mv /assets/entrypoint /entrypoint && \
    rm -rf /assets && \
    apt-get -yq purge --auto-remove \
    build-essential \
    libssl-dev \
    libffi-dev \
    libpq-dev > /dev/null

# get components
COPY --from=components-build /assets/bin/installer-webhook /usr/local/bin/

EXPOSE 80 5000 7223

VOLUME ["/etc/tessia", "/var/tessia/jobs"]

ENTRYPOINT ["/entrypoint"]
