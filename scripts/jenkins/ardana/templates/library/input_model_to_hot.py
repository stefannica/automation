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
module: input_model_to_hot
short_description: Generate heat template structure from input model
description: |
  Take an input model as input and generate a data structure
  describing a heat orchestration template.
author: SUSE Linux GmbH
options:
  input_model: 
    description: Input model data structure 
'''

EXAMPLES = '''
- input_model_to_hot:
    input_model: '{{ input_model }}'
  register: _result
- debug: msg="{{ _result.heat_template }}"
'''

import os, yaml
from collections import OrderedDict


def enhance_input_model(input_model):
    """
    Enhance the input model structure:
      - use dictionaries instead of lists
      - use references instead of attributes
      - delete unused elements

    :param input_model: the input model loaded from disk
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


def main():

    argument_spec = dict(
        input_model=dict(type='dict', required=True)
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False)
    input_model = module.params['input_model']
    heat_template = OrderedDict()

    try:
        enhance_input_model(input_model)
    except Exception as e:
        module.fail_json(msg=e.message)
    module.exit_json(rc=0, changed=False, heat_template=heat_template)


from ansible.module_utils.basic import AnsibleModule
if __name__ == '__main__':
    main()
