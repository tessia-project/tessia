FROM ubuntu:latest

# by default we expect the git repos to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variables
# to point to another location
ARG git_repo=/assets/tessia-engine.git
ARG baselib_repo=/assets/tessia_baselib.git

# whether we are building a container for production use
ARG prod_build=true

# this flag determines whether the entrypoint should try to automatically initialize
# an empty database or perform schema upgrades via tessia-dbmanage. Use with care
# as you might lose db data.
ENV TESSIA_DB_AUTOMANAGE false

# Set the locale for this container to UTF-8 for this session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# Generate en_US.UTF-8 locale and update the default locale, some
# applications use this.
RUN locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    apt-get update -q && \
    DEBIAN_FRONTEND=noninteractive apt-get -yq install --no-install-recommends \
    # used to install python libraries
    python3-pip \
    # used by pbr (in setuptools) to detect module version numbers
    git \
    # these are needed to build cryptography (dep chain is tessia_baselib -> paramiko ->
    # cryptography) and uwsgi
    build-essential libssl-dev libffi-dev python3-dev \
    # init-like daemon to manage our services' processes
    supervisor && \
    # Install the python dependencies.
    # setuptools for installing applications (including tessia) - it must be installed
    # separately first otherwise other packages fail to install
    pip3 install -U setuptools && \
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    pip3 install -U \
    # this is to update the pip version if necessary
    pip \
    # pbr is used by tessia for installation
    pbr \
    # web server for api service
    uwsgi \
    # dependencies used for testing builds
    pylint \
    coverage

COPY assets /assets/

# tessia_baselib installation
RUN cd /assets && \
    git clone $baselib_repo tessia_baselib && \
    cd tessia_baselib && \
    pip3 install -U -r requirements.txt && \
    ./setup.py install && \
    # tessia-engine installation && \
    cd /assets && \
    git clone $git_repo tessia-engine && \
    cd tessia-engine && \
    # it's important not to use -U here to prevent pip from trying to clone
    # tessia_baselib's repository as it might not be accessible from the builder
    # machine
    pip3 install -r requirements.txt && \
    ./setup.py install && \
    # tessia-engine files settings
    useradd -m tessia && \
    install -m 700 -g tessia -o tessia -d /etc/tessia && \
    install -m 600 -g tessia -o tessia /usr/local/etc/tessia/* /etc/tessia && \
    rm -rf /usr/local/etc/tessia && \
    install -m 755 -g tessia -o tessia -d /var/tessia /var/tessia/jobs /var/tessia/www /var/log/tessia && \
    # by default log files are relative paths for use in virtualenvs, we change it here
    sed -i 's,^\( \+filename:\) log/\(.*\)$,\1 /var/log/\2,g' /etc/tessia/engine.yaml && \
    # used to manage startup of the api and scheduler daemons
    cp /assets/supervisord.conf /etc/supervisor/conf.d/supervisord.conf && \
    # remove unneeded dependencies used only for building paramiko and uwsgi
    DEBIAN_FRONTEND=noninteractive apt-get -yq purge --auto-remove \
        build-essential libssl-dev libffi-dev python3-dev

EXPOSE 80 5000

VOLUME ["/etc/tessia", "/var/tessia/jobs"]

CMD ["/assets/entrypoint"]
