# Copyright 2021 IBM Corp.
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
Tessia instance configurator
"""

#
# IMPORTS
#
import argparse
import json
import logging
import signal
import time

from .control_node.errors import StartInstanceError
from .control_node.detached import DetachedInstance
from .control_node.factory import InstanceFactory

#
# CONSTANTS AND DEFINITIONS
#
DESCRIPTION = """Tessia instance configurator

Use this program to deploy an instance of Tessia.
"""

# Status update interval, seconds
MONITOR_INTERVAL = 5.0

#
# CODE
#


def supervise(instance: DetachedInstance):
    """Monitor tessia instance and close when needed"""
    # Preventively set default signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal.default_int_handler)
    logging.info("Monitoring Tessia instance")
    try:
        # wait until termination
        while all(instance.verify().values()):
            time.sleep(MONITOR_INTERVAL)
        logging.info("Shutting down tessia instance")

    except KeyboardInterrupt:
        logging.info("Ctrl+C received, exiting")
        instance.stop()
    finally:
        instance.cleanup()
# supervise()


def main():
    """
    Command-line entrypoint
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)-15s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='./conf/default.json',
                        help="Path to configuration file")
    parser.add_argument('--make-cli-cert', action='store_true',
                        help="Generate additional client certificate "
                             "to communicate with components")

    args = parser.parse_args()
    logging.info('Loading configuration from %s', args.config)

    with open(args.config, 'r', encoding='utf-8') as conf_file:
        configuration = json.load(conf_file)

    factory = InstanceFactory()
    logging.info('Creating Tessia instance')
    instance = factory.create_instance(configuration)
    logging.info('Writing Tessia instance configuration')
    instance.setup()

    if args.make_cli_cert:
        # write additional client certificates
        key, crt = instance.ca_root.create_component_client_certificate(
            'external')
        instance.ca_root.export_key_cert_to_directory('./', key, crt)

    logging.info('Starting Tessia instance')
    try:
        instance.run()
    except StartInstanceError:
        instance.cleanup()
        raise

    if isinstance(instance, DetachedInstance):
        supervise(instance)
# main()


if __name__ == "__main__":
    main()
