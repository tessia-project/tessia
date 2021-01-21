# Copyright 2017 IBM Corp.
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
Unit test for the powerman machine.
"""

from contextlib import contextmanager
from tessia.server.state_machines import base
from tessia.server.state_machines.powerman import machine
from tessia.server.db.models import System, SystemProfile
from tests.unit.db.models import DbUnit
from unittest import TestCase
from unittest.mock import call, patch, Mock

import json
import os

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class TestPowerManagerMachine(TestCase):
    """
    Unit testing for the PowerManagerMachine class.
    """
    @classmethod
    def setUpClass(cls):
        """
        Called once to create the db content for this test.
        """
        DbUnit.create_db()
        sample_file = '{}/data.json'.format(
            os.path.dirname(os.path.abspath(__file__)))
        with open(sample_file, 'r') as sample_fd:
            data = sample_fd.read()
        DbUnit.create_entry(json.loads(data))
        cls.db = DbUnit
    # setUpClass()

    def setUp(self):
        """
        Called before each test to set up the necessary mocks.
        """
        patcher = patch.object(machine, 'logging')
        mock_logging = patcher.start()
        self.addCleanup(patcher.stop)
        mock_logging.getLogger.return_value = Mock(
            spec=['warning', 'error', 'debug', 'info'])

        # mock config object
        patcher = patch.object(base, 'CONF', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # mock sys module
        patcher = patch.object(base, 'sys', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # mock sleep
        patcher = patch.object(machine.time, 'sleep', autospec=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        # mocks for baselib objects
        patcher = patch.object(machine, 'Guest')
        self._mock_guest_cls = patcher.start()
        self._mock_guest_obj = self._mock_guest_cls.return_value
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'Terminal')
        self._mock_term_cls = patcher.start()
        self._mock_term_obj = self._mock_term_cls.return_value
        self.addCleanup(patcher.stop)

        patcher = patch.object(machine, 'Hypervisor')
        self._mock_hyp_cls = patcher.start()
        self._mock_hyp_obj = self._mock_hyp_cls.return_value
        self.addCleanup(patcher.stop)

        # mock for post_install module
        patcher = patch.object(
            machine.post_install, 'PostInstallChecker', autospec=True)
        self._mock_post_cls = patcher.start()
        self._mock_post_obj = self._mock_post_cls.return_value
        self._mock_post_obj.verify.return_value = []
        self.addCleanup(patcher.stop)
    # setUp()

    def _assert_poweroff_action(self, hyp_type, hyp_prof_obj, guest_obj,
                                hyp_index, stop_index, guest_prof=None):
        """
        Helper to assert if the routine to check if system was powered
        off occurred.

        Args:
            hyp_type (str): hypervisor type (kvm, hmc, zvm)
            hyp_prof_obj (SystemProfile): hypervisor profile db object
            guest_obj (System): target system db object
            hyp_index (int): index to verify in list of calls of mock for
                             Hypervisor class
            stop_index (int): index to verify in list of calls for mock of
                             Hypervisor.stop method
            guest_prof (SystemProfile): guest profile db object, only used when
                                        hyp_type is zvm
        """
        if hyp_type == 'zvm':
            byuser = guest_prof.credentials.get('zvm-logonby')
            init_params = {}
            if byuser:
                init_params['byuser'] = byuser
            hyp_args = (
                hyp_type, hyp_prof_obj.system_rel.name,
                hyp_prof_obj.system_rel.hostname,
                guest_obj.name,
                guest_prof.credentials['zvm-password'],
                init_params)
        else:
            hyp_args = (
                hyp_type, hyp_prof_obj.system_rel.name,
                hyp_prof_obj.system_rel.hostname,
                hyp_prof_obj.credentials['admin-user'],
                hyp_prof_obj.credentials['admin-password'], None)
        self.assertEqual(
            self._mock_hyp_cls.call_args_list[hyp_index], call(*hyp_args))
        self.assertEqual(
            self._mock_hyp_obj.login.call_args_list[hyp_index], call())
        self.assertEqual(self._mock_hyp_obj.stop.call_args_list[stop_index],
                         call(guest_obj.name, {}))

    # _assert_poweroff_action()

    def _assert_poweron_action(self, hyp_type, hyp_prof_obj, guest_prof_obj,
                               mock_index, custom_cpu=None, custom_mem=None):
        """
        Helper to assert if the routine to check if system was powered
        on occurred.

        Args:
            hyp_type (str): hypervisor type (kvm, hmc)
            hyp_prof_obj (SystemProfile): hypervisor profile db object
            guest_prof_obj (SystemProfile): target system profile db object
            mock_index (int): index to verify in list of calls of mock for
                             Hypervisor class
            custom_cpu (int): for testing override cpu option
            custom_mem (int): for testing override memory option

        Raises:
            RuntimeError: in case developer pass an unknown guest profile
        """
        os_obj = hyp_prof_obj.operating_system_rel
        if (hyp_type != 'hmc' and os_obj and
                os_obj.type.lower() in ('cms', 'zcms')):
            params = None
            byuser = guest_prof_obj.credentials.get('zvm-logonby')
            if byuser:
                params = {'byuser': byuser}
            hyp_args = (
                'zvm', hyp_prof_obj.system_rel.name,
                hyp_prof_obj.system_rel.hostname,
                guest_prof_obj.system_rel.name,
                guest_prof_obj.credentials['zvm-password'],
                params)
        else:
            hyp_args = (
                hyp_type, hyp_prof_obj.system_rel.name,
                hyp_prof_obj.system_rel.hostname,
                hyp_prof_obj.credentials['admin-user'],
                hyp_prof_obj.credentials['admin-password'], None)

        self.assertEqual(self._mock_hyp_cls.call_args_list[mock_index],
                         call(*hyp_args))
        self.assertEqual(
            self._mock_hyp_obj.login.call_args_list[mock_index], call())

        # build params
        params = {}
        if hyp_type == 'hmc':
            # these attributes are from the data.json file
            if guest_prof_obj.name == 'fcp1':
                params['boot_params'] = {
                    'boot_method': 'scsi',
                    'devicenr': '0.0.1800',
                    'wwpn': '100207630503c1ae',
                    'lun': '1022400000000000',
                    'uuid': '11002076305aac1a0000000000002200'[1:],
                }
            elif guest_prof_obj.name == 'dasd1':
                params['boot_params'] = {
                    'boot_method': 'dasd',
                    'devicenr': '3956',
                }
        elif hyp_type == 'kvm':
            params['parameters'] = {'boot_method': 'disk'}
            ifaces = []
            for iface_obj in guest_prof_obj.system_ifaces_rel:
                ifaces.append({
                    'mac_address': iface_obj.mac_address,
                    'attributes': iface_obj.attributes,
                    'type': iface_obj.type
                })
            params['ifaces'] = ifaces
            svols = []
            for vol_obj in guest_prof_obj.storage_volumes_rel:
                svols.append({
                    'type': vol_obj.type,
                    'specs': vol_obj.specs,
                    'system_attributes': vol_obj.system_attributes,
                    'volume_id': vol_obj.volume_id,
                })
            params['storage_volumes'] = svols
        elif hyp_type == 'zvm':
            params = {'boot_method': 'disk'}
            ifaces = []
            result = None
            for iface_obj in guest_prof_obj.system_ifaces_rel:
                if iface_obj.type.lower() == 'osa':
                    ccw_base = [
                        channel.split('.')[-1]
                        for channel in
                        iface_obj.attributes['ccwgroup'].split(',')
                    ]
                    result = {
                        'type': iface_obj.type.lower(),
                        'id': ','.join(ccw_base)
                    }
                elif iface_obj.type.lower() == 'roce':
                    result = {
                        'id': iface_obj.attributes['fid'],
                        'type': 'pci',
                    }
                ifaces.append(result)

            params['ifaces'] = ifaces
            svols = []
            for vol_obj in guest_prof_obj.storage_volumes_rel:
                result = {'type': vol_obj.type_rel.name.lower()}
                if result['type'] != 'fcp':
                    result['devno'] = vol_obj.volume_id.split('.')[-1]
                else:
                    result['adapters'] = vol_obj.specs['adapters']
                    result['lun'] = vol_obj.volume_id
                if guest_prof_obj.root_vol is vol_obj:
                    result['boot_device'] = True
                svols.append(result)
            params['storage_volumes'] = svols

        # sanity check
        if not params:
            raise RuntimeError('Unknown parameters provided')

        check_cpu = guest_prof_obj.cpu
        if custom_cpu:
            check_cpu = custom_cpu
        check_mem = guest_prof_obj.memory
        if custom_mem:
            check_mem = custom_mem
        self._mock_hyp_obj.start.assert_called_with(
            guest_prof_obj.system_rel.name, check_cpu, check_mem, params)
    # _assert_poweron_action()

    def _assert_system_up_action(self, system_prof, mock_index,
                                 guest_prof=None):
        """
        Helper to assert if the routine to check if system was up occurred.

        Args:
            system_prof (System): target system's db object
            mock_index (int): index to verify in list of calls for mock of
                              Guest class and Guest.login method
            guest_prof (System): when target system is cms, this is the guest
                profile containing zvm credentials for login
        """
        os_obj = system_prof.operating_system_rel
        if os_obj and os_obj.type.lower() in ('cms', 'zcms'):
            self.assertEqual(
                self._mock_term_cls.call_args_list[mock_index],
                call()
            )
            params = {'noipl': True, 'here': True}
            byuser = guest_prof.credentials.get('zvm-logonby')
            if byuser:
                params['byuser'] = byuser
            self.assertEqual(
                self._mock_term_obj.login.call_args_list[mock_index],
                call(system_prof.system_rel.hostname,
                     guest_prof.system_rel.name,
                     guest_prof.credentials['zvm-password'],
                     params, timeout=15)
            )
            return

        init_args = (
            'linux',
            system_prof.system_rel.name, system_prof.system_rel.hostname,
            system_prof.credentials['admin-user'],
            system_prof.credentials['admin-password'], None)
        self.assertEqual(
            self._mock_guest_cls.call_args_list[mock_index],
            call(*init_args)
        )
        self.assertEqual(
            self._mock_guest_obj.login.call_args_list[mock_index],
            call(timeout=15)
        )
    # _assert_system_up_action()

    @staticmethod
    def _get_profile(system, profile=None):
        """
        Helper function to query the db for a given profile
        """
        query = SystemProfile.query.join(
            'system_rel').filter(System.name == system)
        # profile specified: add name filter to query
        if profile:
            query = query.filter(SystemProfile.name == profile)
        # profile not specified: use filter for default
        else:
            query = query.filter(SystemProfile.default == bool(True))

        # retrieve the system profile object
        return query.one()
    # _get_profile()

    @contextmanager
    def _mock_db_obj(self, target_obj, target_field, temp_value):
        """
        Act as a context manager to temporarily change a value in a db row and
        restore it on exit.

        Args:
            target_obj (SAobject): sqlsa model object
            target_field (str): name of field in object
            temp_value (any): value to be temporarily assigned

        Yields:
            None: nothing is returned
        """
        orig_value = getattr(target_obj, target_field)
        setattr(target_obj, target_field, temp_value)
        self.db.session.add(target_obj)
        self.db.session.commit()
        yield
        setattr(target_obj, target_field, orig_value)
        self.db.session.add(target_obj)
        self.db.session.commit()
    # _mock_db_obj()

    @staticmethod
    def test_cleanup():
        """
        Exercise the machine cleanup in case the scheduler wants to cancel it.
        """
        request = str({
            'systems': [
                {
                    'action': 'poweron-exclusive',
                    'name': 'kvm054',
                },
            ]
        })
        # currently the method does nothing
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.cleanup()
    # test_cleanup()

    def test_multiple_actions(self):
        """
        Test a request to perform multiple actions. This test also covers
        the poweron exclusive action.
        """
        # prepare mocks, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # before poweron
            ConnectionError('offline'),
            # after poweron
            None
        ]

        # collect necessary db objects
        exclusive_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=exclusive_system).one()
        prof_obj = self._get_profile(system_obj.name, 'dasd1')

        # run machine
        request = str({
            'systems': [
                {
                    'action': 'poweron-exclusive',
                    'name': exclusive_system,
                    'profile': 'dasd1'
                },
                {
                    'action': 'poweroff',
                    'name': 'kvm054'
                },
            ]
        })

        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to poweroff siblings
        # get the siblings' objects
        sibling_systems = list(System.query.filter(
            System.hypervisor_id == system_obj.hypervisor_id
        ).filter(
            System.name != exclusive_system
        ).all())
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)
        for index, entry in enumerate(sibling_systems):
            self._assert_poweroff_action('hmc', hyp_prof, entry, 0, index)

        # validate call to verify if system is up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('hmc', hyp_prof, prof_obj, 1)

        # validate call to poweroff kvm guest
        kvm_obj = System.query.filter_by(name='kvm054').one()
        hyp_prof = self._get_profile(kvm_obj.hypervisor_rel.name)
        self._assert_poweroff_action('kvm', hyp_prof, kvm_obj, 2, -1)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 1)
        self._mock_post_cls.assert_called_with(prof_obj, permissive=True)
        self._mock_post_obj.verify.assert_called_with()

    # test_multiple_actions()

    def test_invalid_profile_no_root(self):
        """
        Verify that the machine perform sanity check and fails in case a
        profile without a root volume is used.
        """
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        prof_obj = self._get_profile(system_obj.name)
        vol_obj = prof_obj.storage_volumes_rel[0]
        error_msg = ('Profile {} has no volume containing a root partition'
                     .format(prof_obj.name))
        with self._mock_db_obj(vol_obj, 'part_table', None):
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.PowerManagerMachine(request)
    # test_invalid_profile_no_root()

    def test_invalid_request_format(self):
        """
        Exercise submitting a request in invalid format
        """
        error_msg = '^Invalid request parameters:'

        request = str({
            'systems': [
                {
                    'invalid_key': 'something',
                    'action': 'poweroff',
                    'name': 'kvm054'
                },
            ]
        })
        # test both with parse as well as class constructor
        with self.assertRaisesRegex(SyntaxError, error_msg):
            machine.PowerManagerMachine.parse(request)
        with self.assertRaisesRegex(SyntaxError, error_msg):
            machine.PowerManagerMachine(request)

        request = str({
            'systems': [
                {
                    'action': 'invalid_action',
                    'name': 'kvm054'
                },
            ]
        })
        error_msg = '^Invalid request parameters:'
        # test both with parse as well as class constructor
        with self.assertRaisesRegex(SyntaxError, error_msg):
            machine.PowerManagerMachine.parse(request)
        with self.assertRaisesRegex(SyntaxError, error_msg):
            machine.PowerManagerMachine(request)
    # test_invalid_request_format()

    def test_invalid_system(self):
        """
        Try different combinations of invalid systems.
        """
        # try to poweroff a CPC system which is not supported
        request = str({
            'systems': [
                {
                    'action': 'poweroff',
                    'name': 'cpc3'
                },
            ]
        })
        error_msg = ('System {} cannot be managed because it has no '
                     'hypervisor defined'.format('cpc3'))
        # test both with parse as well as class constructor
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine.parse(request)
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine(request)

        # try to poweron a system which does not exist
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': 'foo_system'
                },
            ]
        })
        error_msg = "System '{}' does not exist".format('foo_system')
        # test both with parse as well as class constructor
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine.parse(request)
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine(request)

        # try to poweron a system with a profile which does not exist
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': 'cpc3lp52',
                    'profile': 'foo_profile',
                },
            ]
        })
        error_msg = (
            "Specified profile {} for system {} does not exist".format(
                'foo_profile', 'cpc3lp52'))
        # test both with parse as well as class constructor
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine.parse(request)
        with self.assertRaisesRegex(ValueError, error_msg):
            machine.PowerManagerMachine(request)

        # try to poweron a system without specifying a profile and the system
        # has no default profile
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name
                },
            ]
        })
        error_msg = "Default profile for system {} does not exist.".format(
            system_obj.name)
        with self._mock_db_obj(prof_obj, 'default', False):
            # test both with parse as well as class constructor
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.PowerManagerMachine.parse(request)
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.PowerManagerMachine(request)

        # try to poweron a system whose profile does not specify a hypervisor
        # profile and the hypervisor system has no default profile defined
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        hyp_obj = System.query.filter_by(id=system_obj.hypervisor_id).one()
        hyp_prof = self._get_profile(hyp_obj.name)
        cpc_prof = self._get_profile(hyp_obj.hypervisor_rel.name)
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                    'force': True
                },
            ]
        })
        error_msg = 'System {} has no default profile defined'.format(
            cpc_prof.system_rel.name)
        with self._mock_db_obj(hyp_prof, 'hypervisor_profile_id', None):
            with self._mock_db_obj(cpc_prof, 'default', False):
                with self.assertRaisesRegex(ValueError, error_msg):
                    machine.PowerManagerMachine(request)

    # test_invalid_system()

    def test_invalid_kvm_volume(self):
        """
        Test that a kvm guest system containing a volume without libvirt
        definition will fail
        """
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                    'force': True
                },
            ],
            'verify': True,
        })
        prof_obj = self._get_profile(system_obj.name)
        vol_obj = prof_obj.storage_volumes_rel[0]
        error_msg = (
            'Volume {} has a libvirt definition missing, '
            'perform a system installation to create a valid entry'.format(
                vol_obj.volume_id))
        with self._mock_db_obj(vol_obj, 'system_attributes', {}):
            machine_obj = machine.PowerManagerMachine(request)
            with self.assertRaisesRegex(ValueError, error_msg):
                machine_obj.start()
    # test_invalid_kvm_volume()

    def test_parse_resources(self):
        """
        Verify if the machine correctly allocate all resources expected.
        """
        system_exc = 'cpc3lp52'
        request = str({
            'systems': [
                {
                    'action': 'poweron-exclusive',
                    'name': system_exc,
                },
                {
                    'action': 'poweroff',
                    'name': 'kvm054'
                },
            ]
        })

        # collect necessary db objects
        system_obj = System.query.filter_by(name=system_exc).one()
        exclusive_objs = System.query.filter(
            System.hypervisor_id == system_obj.hypervisor_id).all()
        hyp_obj = System.query.filter_by(id=system_obj.hypervisor_id).one()

        # build expected results
        exp_exclusive = [obj.name for obj in exclusive_objs] + ['kvm054']
        exp_shared = [hyp_obj.name, system_obj.name]

        # call the parser
        response = machine.PowerManagerMachine.parse(request)

        # validate results
        self.assertEqual(exp_exclusive.sort(),
                         response['resources']['exclusive'].sort())
        self.assertEqual(exp_shared.sort(),
                         response['resources']['shared'].sort())

    # test_parse_resources()

    def test_poweroff(self):
        """
        Exercise a system poweroff
        """
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()

        # remember last modified time before system power changes
        system_last_modified = system_obj.modified

        request = str({
            'systems': [
                {
                    'action': 'poweroff',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        hyp_prof = self._get_profile('cpc3lp52')
        self._assert_poweroff_action('kvm', hyp_prof, system_obj, 0, 0)

        # Validate that system modified time is updated
        updated_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(updated_system_obj.modified, system_last_modified,
                           'System modified time is updated')
    # test_poweroff()

    def test_poweroff_zvm(self):
        """
        Exercise a poweroff of a zvm guest
        """
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        # remember last modified time before system power changes
        system_last_modified = system_obj.modified

        guest_prof = self._get_profile(test_system)
        request = str({
            'systems': [
                {
                    'action': 'poweroff',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        hyp_prof = self._get_profile('cpc3lp55')
        self._assert_poweroff_action(
            'zvm', hyp_prof, system_obj, 0, 0, guest_prof)

        # Validate that system modified time is updated
        updated_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(updated_system_obj.modified, system_last_modified,
                           'System modified time is updated')
    # test_poweroff_zvm()

    def test_poweron_timeout(self):
        """
        Simulate a condition where the system is powered on but the machine
        times out trying to connect to it to verify its state.
        """
        # prepare mock, simulate system to be always unreachable
        self._mock_guest_obj.login.side_effect = ConnectionError('offline')
        # fake call to time so that we don't have to actually wait for the
        # timeout to occur
        def time_generator():
            """Simulate time.time()"""
            start = 1.0
            yield start
            while True:
                # step is half of timeout time to cause two calls to
                # _is_system_up
                start += machine.LOAD_TIMEOUT/2
                yield start
        patcher = patch.object(machine.time, 'time', autospec=True)
        mock_time = patcher.start()
        self.addCleanup(patcher.stop)
        get_time = time_generator()
        mock_time.side_effect = lambda: next(get_time)

        # collect necessary db objects
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name, 'dasd1')

        # run machine
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': test_system,
                    'profile': 'dasd1'
                },
            ]
        })

        timeout_error = 'Could not establish a connection to system {}'.format(
            test_system)
        machine_obj = machine.PowerManagerMachine(request)
        with self.assertRaisesRegex(TimeoutError, timeout_error):
            machine_obj.start()

        # validate call to verify if system is up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)
        self._assert_poweron_action('hmc', hyp_prof, prof_obj, 0)

        # validate stage verify - two calls should have been made
        for i in range(1, 3):
            self._assert_system_up_action(prof_obj, i)
        # timeout occurred so postinstall was not called
        self._mock_post_cls.assert_not_called()

    # test_poweron_timeout()

    def test_profile_override(self):
        """
        Try a poweron while specifying custom profile parameters. This test
        also covers the usage of the default profile when none was specified.
        """
        # collect necessary db objects
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)

        # store original values for later verification
        orig_cpu = prof_obj.cpu
        orig_mem = prof_obj.memory
        # set overrides
        override_cpu = prof_obj.cpu + 2
        override_memory = prof_obj.memory + 1500
        # have the mock validate if the overrides are in the profile object
        def mock_validate(check_prof_obj, *_args, **_kwargs):
            """validator for override values"""
            self.assertEqual(check_prof_obj.cpu, override_cpu)
            self.assertEqual(check_prof_obj.memory, override_memory)
            return self._mock_post_obj
        # mock_validate()
        self._mock_post_cls.side_effect = mock_validate

        # create request and execute machine
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                    'profile_override': {
                        'cpu': override_cpu,
                        'memory': override_memory,
                    }
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        self._mock_post_cls.side_effect = mock_validate
        machine_obj.start()

        # validate call to check if system is up
        self._assert_system_up_action(prof_obj, 0)

        # system was up and a poweroff is needed because of override
        # parameters, validate that this occurred
        hyp_prof = self._get_profile('cpc3')
        self._assert_poweroff_action('hmc', hyp_prof, system_obj, 0, 0)

        # validate call to poweron with override parameters
        self._assert_poweron_action('hmc', hyp_prof, prof_obj, 1,
                                    override_cpu, override_memory)

        # validate verify stage
        self._assert_system_up_action(prof_obj, 1)
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())

        # make sure overrides values were discarded
        self.assertEqual(prof_obj.cpu, orig_cpu)
        self.assertEqual(prof_obj.memory, orig_mem)

    # test_profile_override()

    def test_poweroff_already_down(self):
        """
        Validate that the operation is skipped when a system is already down
        """
        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()

        request = str({
            'systems': [
                {
                    'action': 'poweroff',
                    'name': system_obj.name,
                },
                {
                    'action': 'poweroff',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate that stop was called only once
        self._mock_hyp_obj.stop.assert_called_once_with(system_obj.name, {})
    # test_poweroff_already_down()

    def test_poweron_force(self):
        """
        Try a forced poweron operation, which occurs when the system is up
        and profile matches but a poweron is performed regardless. By using a
        kvm guest we also exercise the hypervisor chain verification.
        """
        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        # remember last modified time before forced power action
        pre_system_obj = System.query.filter_by(name=test_system).one()
        system_last_modified = pre_system_obj.modified

        prof_obj = self._get_profile(system_obj.name)
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                    'force': True
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof, 0)
        # validate call to verify if hypervisor matches profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(hyp_prof, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 1)

        # system was up and a poweroff is needed because of force flag,
        # validate that this occurred
        self._assert_poweroff_action('kvm', hyp_prof, system_obj, 0, 0)

        # validate call to poweron
        self._assert_poweron_action('kvm', hyp_prof, prof_obj, 1)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 2)
        self.assertEqual(
            self._mock_post_cls.call_args_list[1],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[1], call())

        # validate that system modified time is updated
        updated_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(updated_system_obj.modified, system_last_modified,
                           'System modified time is updated')
    # test_poweron_force()

    def test_poweron_already_up(self):
        """
        Validate that the operation is skipped when a system is already powered
        on and with correct profile
        """
        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)
        hyp_prof_obj = self._get_profile(system_obj.hypervisor_rel.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # remember last modified time before system power changes
        system_last_modified = system_obj.modified

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof_obj, 0)
        # validate call to verify if system was up
        self._assert_system_up_action(prof_obj, 1)
        # no call to power on system
        self._mock_hyp_cls.assert_not_called()

        # validate that system modified time is not updated
        updated_system_obj = System.query.filter_by(name=test_system).one()
        self.assertEqual(updated_system_obj.modified, system_last_modified,
                         'System modified time is not updated')
    # test_poweron_already_up()

    def test_poweron_already_up_profile_no_match(self):
        """
        Exercise the case where the system is already up but profile does not
        match.
        """
        # collect necessary db objects
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        # make post install verification fail on first try only
        self._mock_post_obj.verify.side_effect = [
            Exception('Memory mismatch'),
            None
        ]

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 0)
        # validate call to verify if guest state matched profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())

        # system was up and a poweroff is needed because of state mismatch,
        # validate that this occurred
        self._assert_poweroff_action('hmc', hyp_prof, system_obj, 0, 0)

        # validate call to poweron
        self._assert_poweron_action('hmc', hyp_prof, prof_obj, 1)

        # validate call to verify if guest state matched profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[1],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[1], call())

    # test_poweron_already_up_profile_no_match()

    def test_poweron_hypervisor_not_up(self):
        """
        Exercise the scenario where a poweron is requested but the system's
        hypervisor is down.
        """
        # prepare mocks, simulate hypervisor to be down
        self._mock_guest_obj.login.side_effect = ConnectionError('offline')

        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        hyp_obj = System.query.filter_by(id=system_obj.hypervisor_id).one()
        hyp_prof_obj = self._get_profile(hyp_obj.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        error_msg = (
            'Cannot poweron system {}, hypervisor {} is not up'.format(
                system_obj.name, hyp_obj.name))
        machine_obj = machine.PowerManagerMachine(request)
        with self.assertRaisesRegex(RuntimeError, error_msg):
            machine_obj.start()

        # validate that last call was to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof_obj, -1)
        # no call to power on system
        self._mock_hyp_cls.assert_not_called()
    # test_poweron_hypervisor_not_up(self):

    def test_poweron_hypervisor_no_profile(self):
        """
        Test the case where the system's profile has no hypervisor profile
        defined and the hypervisor tiself has no default profile.
        """
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        hyp_obj = System.query.filter_by(id=system_obj.hypervisor_id).one()
        hyp_prof = self._get_profile(hyp_obj.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })

        error_msg = (
            'Hypervisor {} of system {} has no default profile defined'
            .format(hyp_obj.name, system_obj.name))
        # an error should occur as it's not possible to proceed without
        # identifying the hypervisor's profile
        with self._mock_db_obj(hyp_prof, 'default', False):
            with self.assertRaisesRegex(ValueError, error_msg):
                machine.PowerManagerMachine(request)
    # test_poweron_hypervisor_no_profile()

    def test_poweron_hypervisor_up_profile_no_match(self):
        """
        Test the scenario where the hypervisor is up but the profile
        verification fails.
        """
        # make post install verification fail
        self._mock_post_obj.verify.side_effect = Exception('Failed')

        # collect necessary db objects
        test_system = 'kvm054'
        system_obj = System.query.filter_by(name=test_system).one()
        hyp_obj = System.query.filter_by(id=system_obj.hypervisor_id).one()
        hyp_prof = self._get_profile(hyp_obj.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        error_msg = (
            'Cannot poweron system {} because hypervisor {} does '
            'not match expected profile {}'.format(
                system_obj.name, hyp_obj.name, hyp_prof.name))
        machine_obj = machine.PowerManagerMachine(request)
        with self.assertRaisesRegex(RuntimeError, error_msg):
            machine_obj.start()

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof, 0)

        # validate call to verify hypervisor profile
        self._mock_post_cls.assert_called_with(hyp_prof, permissive=True)
        self._mock_post_obj.verify.assert_called_with()

        # no call to power on system
        self._mock_hyp_cls.assert_not_called()
    # test_poweron_hypervisor_profile_no_match

    def test_poweron_verify_fails(self):
        """
        Poweron is successfully executed but profile verification in
        stage_verify fails
        """
        # make post install verification fail
        self._mock_post_obj.verify.side_effect = Exception('Memory mismatch')

        # collect necessary db objects
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ],
            'verify': True,
        })
        error_msg = (
            'Failed to poweron system {} with expected configuration'.format(
                system_obj.name))
        machine_obj = machine.PowerManagerMachine(request)
        with self.assertRaisesRegex(RuntimeError, error_msg):
            machine_obj.start()

        # validate call to verify if system is up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('hmc', hyp_prof, prof_obj, 0)

        # validate stage verify
        self._mock_post_cls.assert_called_with(prof_obj, permissive=True)
        self._mock_post_obj.verify.assert_called_with()
    # test_poweron_verify_fails()

    def test_poweron_zvm_dasd(self):
        """
        Try a poweron operation of a zvm guest with dasd disk.
        """
        # collect necessary db objects
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name, 'dasd1')
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        # prepare mock, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # system is down
            ConnectionError('offline'),
            # system is up after poweron
            None
        ]

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                    'profile': 'dasd1'
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof, 0, prof_obj)

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('zvm', hyp_prof, prof_obj, 0)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 1)
        # validate that post install was called to verify profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())
    # test_poweron_zvm_dasd()

    def test_poweron_zvm_fcp_byuser(self):
        """
        Try a poweron operation of a zvm guest with fcp disk and byuser
        specified.
        """
        # collect necessary db objects
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        # prepare mock, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # system is down
            ConnectionError('offline'),
            # system is up after poweron
            None
        ]

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof, 0, prof_obj)

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('zvm', hyp_prof, prof_obj, 0)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 1)
        # validate that post install was called to verify profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())
    # test_poweron_zvm()

    def test_poweron_zvm_missing_cred(self):
        """
        Try a poweron operation of a zvm guest which has zvm credentials
        missing.
        """
        # collect necessary db objects
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        prof_obj = self._get_profile(system_obj.name)

        # prepare mock, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # system is down
            ConnectionError('offline'),
            # system is up after poweron
            None
        ]

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        with self._mock_db_obj(prof_obj, 'credentials', {}):
            msg = 'z/VM guest {} has no z/VM credentials defined'.format(
                system_obj.name)
            with self.assertRaisesRegex(ValueError, msg):
                machine_obj = machine.PowerManagerMachine(request)
                machine_obj.start()

    # test_poweron_zvm_missing_cred()

    def test_verify_on(self):
        """
        Try a poweron with verify flag off. This test also covers the usage
        of the default profile when none was specified.
        """
        # collect necessary db objects
        test_system = 'cpc3lp52'
        system_obj = System.query.filter_by(name=test_system).one()
        # remember last modified time before system power changes
        system_last_modified = system_obj.modified

        prof_obj = self._get_profile(system_obj.name)
        hyp_prof_obj = self._get_profile(system_obj.hypervisor_rel.name)

        # prepare mock, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # system is down
            ConnectionError('offline'),
            # system is up after poweron
            None
        ]

        # run machine
        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ],
            'verify': True
        })

        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('hmc', hyp_prof_obj, prof_obj, 0)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 1)

        # post checker should be called in permissive mode
        self._mock_post_cls.assert_called_with(prof_obj, permissive=True)
        self._mock_post_obj.verify.assert_called_with()

        # validate that system modified time is updated
        updated_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(updated_system_obj.modified, system_last_modified,
                           'System modified time is updated')
    # test_verify_off()

    def test_poweron_zvm_modified_date(self):
        """
        Try a poweron operation of a zvm guest and validate that
        'modified' attribute is updated.
        """
        # collect necessary db objects
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        # remember last modified time before the system is brought up
        system_last_modified = system_obj.modified

        prof_obj = self._get_profile(system_obj.name)
        hyp_prof = self._get_profile(system_obj.hypervisor_rel.name)

        # prepare mock, simulate system to be down
        self._mock_guest_obj.login.side_effect = [
            # system is down
            ConnectionError('offline'),
            # system is up after poweron
            None
        ]

        request = str({
            'systems': [
                {
                    'action': 'poweron',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        # validate call to verify if hypervisor was up
        self._assert_system_up_action(hyp_prof, 0, prof_obj)

        # validate call to verify if guest was up
        self._assert_system_up_action(prof_obj, 0)

        # validate call to poweron
        self._assert_poweron_action('zvm', hyp_prof, prof_obj, 0)

        # validate stage verify
        self._assert_system_up_action(prof_obj, 1)

        # validate that system modified time is updated
        up_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(up_system_obj.modified, system_last_modified,
                           'System modified time is updated')

        # validate that post install was called to verify profile
        self.assertEqual(
            self._mock_post_cls.call_args_list[0],
            call(prof_obj, permissive=True))
        self.assertEqual(
            self._mock_post_obj.verify.call_args_list[0], call())
    # test_poweron_zvm_modified_date()

    def test_poweroff_zvm_modified_date(self):
        """
        Exercise a poweroff of a zvm guest and verify that 'modified'
        attribute is updated
        """
        test_system = 'zvm033'
        system_obj = System.query.filter_by(name=test_system).one()
        # remember last modified time before the system is brought up
        system_last_modified = system_obj.modified

        guest_prof = self._get_profile(test_system)

        request = str({
            'systems': [
                {
                    'action': 'poweroff',
                    'name': system_obj.name,
                },
            ]
        })
        machine_obj = machine.PowerManagerMachine(request)
        machine_obj.start()

        hyp_prof = self._get_profile('cpc3lp55')
        self._assert_poweroff_action(
            'zvm', hyp_prof, system_obj, 0, 0, guest_prof)

        # validate that system modified time is updated
        down_system_obj = System.query.filter_by(name=test_system).one()
        self.assertGreater(down_system_obj.modified, system_last_modified,
                           'System modified time is updated')
    # test_poweroff_zvm_modified_date()

# TestPowerManagerMachine
