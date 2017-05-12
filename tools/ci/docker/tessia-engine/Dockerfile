FROM ubuntu:latest

# by default we expect the git repos to be placed by the ci process under /assets
# but it is also possible to use this dockerfile directly and override the variables
# to point to another location
ARG git_repo=file:///assets/tessia-engine.git
ARG baselib_repo=file:///assets/tessia_baselib.git

# whether we are building a container for production use
ARG prod_build=true

ARG DEBIAN_FRONTEND=noninteractive

# this flag determines whether the entrypoint should try to automatically initialize
# an empty database or perform schema upgrades via tessia-dbmanage. Use with care
# as you might lose db data.
ENV TESSIA_DB_AUTOMANAGE false

RUN apt-get -q update > /dev/null && \
    # Install the distro dependencies.
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    apt-get -yq install --no-install-recommends \
    # to manage the system locale
    locales \
    # used to install python libraries
    python3-pip \
    # used by pbr (in setuptools) to detect module version numbers
    git \
    # these are needed to build cryptography (dep chain is tessia_baselib -> paramiko ->
    # cryptography) and uwsgi
    build-essential libssl-dev libffi-dev python3-dev \
    # build python postgres connector (psycopg2)
    libpq-dev \
    # to use python postgres connector (psycopg2)
    libpq5 \
    # init-like daemon to manage our services' processes
    supervisor > /dev/null && \
    # clean the cache to free up space
    apt-get -q clean && \
    # generate the locale/encoding and set it as default
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    # Install the python dependencies.
    # setuptools for installing applications (including tessia) - it must be installed
    # separately first otherwise other packages fail to install
    pip3 -q install -U setuptools && \
    # ATTENTION: make sure to keep a comment for each explaining why is it needed.
    pip3 -q install -U \
    # this is to update the pip version if necessary
    pip \
    # pbr is used by tessia for installation
    pbr \
    # web server for api service
    uwsgi \
    # dependencies used for testing builds
    pylint \
    coverage

# set the locale/encoding for the session
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

COPY assets /assets/

# tessia-engine installation
RUN cd /assets && \
    git clone $git_repo tessia-engine && \
    cd tessia-engine && \
    # use the custom url as the tessia_baselib's repository might not be accessible
    # from the builder
    sed -i "/egg=tessia_baselib/ s,^.*\(@.*$\),git\+${baselib_repo}\1,g" requirements.txt && \
    pip3 -q install -U -r requirements.txt && \
    # linting and unit testing
    tools/run_pylint.py && \
    tools/run_tests.py && \
    # installation
    ./setup.py -q install && \
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
    # cleanup section
    cd / && \
    # remove source repository
    rm -rf /assets/tessia-engine.git /assets/tessia-engine && \
    # remove unneeded packages
    apt-get -yq purge --auto-remove \
    build-essential \
    libssl-dev \
    libffi-dev \
    libpq-dev > /dev/null && \
    # remove unneeded python libs
    pip3 -q uninstall -y \
    pylint \
    coverage

EXPOSE 80 5000

VOLUME ["/etc/tessia", "/var/tessia/jobs"]

CMD ["/assets/entrypoint"]
