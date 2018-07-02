#!/usr/bin/python
#
# (c) Copyright 2018 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

DOCUMENTATION = '''
---
module: load_input_model
short_description: Load an Ardana input model
description: |
  Load an Ardana input model from a directory structure
author: SUSE Linux GmbH
options:
  path:
    description: Root path where the input model is located 
'''

EXAMPLES = '''
- load_input_model:
    path: path/to/input/model
  register: input_model
- debug: msg="{{ input_model.input_model }}"
'''

import os, yaml
from collections import OrderedDict


def enhance_input_model(input_model, keep_refs=False):
    """
    Enhance the input model structure:
      - use dictionaries instead of lists
      - use references instead of attributes
      - delete unused elements

    :param input_model: the input model loaded from disk
    :param keep_refs: set to True to keep circular references in
    the input model (which is fatal if the input model is returned to ansible).
    """

    def convert_list_attr_to_map(element, attr_name, key='name'):
        if attr_name in element:
            element[attr_name] = {item[key]: item for item in element[attr_name]}
        else:
            element[attr_name] = {}

    def link_attr_to_element(element, attr_name, target_map, ref_list='refs'):
        key = element.setdefault(attr_name)
        if key and not isinstance(key, dict) and key in target_map:
            element[attr_name] = target_map[key]
            target_map[key].setdefault(ref_list, []).append(element)

    def link_attr_list_to_element(element, attr_name, target_map, ref_list='refs'):
        key_list = element.setdefault(attr_name, [])
        for key in key_list:
            if key and isinstance(key, dict) and key in target_map:
                element[attr_name] = target_map[key]
                target_map[key].setdefault(ref_list, []).append(element)

    def prune_unused_items(element_map):
        for name, element in element_map.items():
            if not element.get('refs'):
                del element_map[name]
            elif not keep_refs:
                # Delete gathered references to avoid circular references
                del element['refs']

    for top_level_list in ['control-planes',
                           'configuration-data',
                           'server-roles',
                           'disk-models',
                           'interface-models',
                           'networks',
                           'network-groups',
                           'nic-mappings',
                           'servers',
                           'server-groups',
                           'firewall-rules']:
        convert_list_attr_to_map(input_model, top_level_list,
                                 'id' if top_level_list == 'servers' else 'name')

    load_balancers = {}
    for cp in input_model['control-planes'].itervalues():
        convert_list_attr_to_map(cp, 'load-balancers')
        convert_list_attr_to_map(cp, 'clusters')
        convert_list_attr_to_map(cp, 'resources')
        link_attr_list_to_element(cp, 'configuration-data', input_model['configuration-data'])
        load_balancers.update(cp['load-balancers'])
        for cluster in cp['clusters'].itervalues():
            link_attr_to_element(cluster, 'server-role', input_model['server-roles'])
            link_attr_list_to_element(cluster, 'configuration-data', input_model['configuration-data'])
        for resource in cp['resources'].itervalues():
            link_attr_to_element(resource, 'server-role', input_model['server-roles'])
            link_attr_list_to_element(cluster, 'configuration-data', input_model['configuration-data'])

    prune_unused_items(input_model['configuration-data'])
    prune_unused_items(input_model['server-roles'])

    for server_role in input_model['server-roles'].itervalues():
        link_attr_to_element(server_role, 'interface-model', input_model['interface-models'])
        link_attr_to_element(server_role, 'disk-model', input_model['disk-models'])

    prune_unused_items(input_model['interface-models'])
    prune_unused_items(input_model['disk-models'])

    for server_id, server in input_model['servers'].items():
        link_attr_to_element(server, 'role', input_model['server-roles'])
        if not server['role']:
            # Keep only those servers that are actually required
            del input_model['servers'][server_id]
            continue
        link_attr_to_element(server, 'nic-mapping', input_model['nic-mappings'])

    prune_unused_items(input_model['nic-mappings'])

    for interface_model in input_model['interface-models'].itervalues():
        convert_list_attr_to_map(interface_model, 'network-interfaces')
        for interface in interface_model['network-interfaces'].itervalues():
            link_attr_list_to_element(interface, 'network-groups', input_model['network-groups'])
            link_attr_list_to_element(interface, 'forced-network-groups', input_model['network-groups'])

    prune_unused_items(input_model['network-groups'])

    for firewall_rule_id, firewall_rule in input_model['firewall-rules'].items():
        link_attr_list_to_element(firewall_rule, 'network-groups', input_model['network-groups'])
        if None in firewall_rule['network-groups']:
            # Keep only those firewall rules that are actually in use
            del input_model['firewall-rules'][firewall_rule_id]
            continue

    for network_group in input_model['network-groups'].itervalues():
        link_attr_list_to_element(network_group, 'load-balancers', load_balancers)

    # remove remaining circular references
    prune_unused_items(load_balancers)
    for top_level_list in ['network-groups',
                           'server-roles']:
        prune_unused_items(input_model[top_level_list])


def merge_input_model(data, input_model):
    for key, value in data.iteritems():
        if key in input_model and isinstance(input_model[key], list):
            input_model[key] += value
        else:
            input_model[key] = value


def load_input_model_file(file_name, input_model):
    if file_name.endswith('.yml') or file_name.endswith('.yaml'):
        with open(file_name, 'r') as data_file:
            data = yaml.load(data_file.read())
            merge_input_model(
                data,
                input_model)
    return input_model


def main():

    argument_spec = dict(
        path=dict(type='str', required=True)
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False)
    input_model_path = module.params['path']

    try:
        input_model = OrderedDict()

        if os.path.exists(input_model_path):
            if os.path.isdir(input_model_path):
                for root, dirs, files in os.walk(input_model_path):
                    for f in files:
                        file_name = os.path.join(root, f)
                        input_model = load_input_model_file(file_name, input_model)
            else:
                input_model = load_input_model_file(input_model_path, input_model)
            enhance_input_model(input_model)
    except Exception as e:
        module.fail_json(msg=e.message)
    module.exit_json(rc=0, changed=False, input_model=input_model)


from ansible.module_utils.basic import AnsibleModule
if __name__ == '__main__':
    main()
