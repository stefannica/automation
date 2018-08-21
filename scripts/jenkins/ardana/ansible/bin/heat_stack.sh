#!/usr/bin/env bash

delete_heat_stack() {
    stack_name=$1
    delete_rc=0

    # Resume stack before deletion, otherwise deleting it results in failure
    openstack --os-cloud ${cloud_config} stack delete --wait $stack_name && rc=$? || rc=$?
    if [[ $rc != 0 ]]; then
        # Attempt a brute force type of cleanup (delete servers and volumes)
        openstack --os-cloud ${cloud_config} stack resource list --filter type=OS::Nova::Server \
          -f value -c physical_resource_id $stack_name |
          awk '{print "openstack --os-cloud '${cloud_config}' server delete --wait "$1 }' | sh -x || :
        openstack --os-cloud ${cloud_config} stack resource list --filter type=OS::Cinder::Volume \
          -f value -c physical_resource_id $stack_name |
          awk '{print "openstack --os-cloud '${cloud_config}' volume delete "$1 }' | sh -x || :
        openstack --os-cloud ${cloud_config} stack delete --wait $stack_name && rc=$? || rc=$?
        if [[ $rc != 0 ]]; then
            # Usually, retrying after a short break works
            sleep 20
            openstack --os-cloud ${cloud_config} stack delete --wait $stack_name && rc=$? || rc=$?
            delete_rc=$rc
        fi
    fi

    return $delete_rc
}

get_heat_stack() {
    stack_name=$1
    openstack --os-cloud ${cloud_config} stack list \
              -f value -c 'Stack Name' \
              grep "^$stack_name$" || :
}

action=$1
heat_stack_name=$2
heat_template_file=$3

if [[ $action == "create" ]]; then
    heat_stack=$(get_heat_stack $heat_stack_name)
    if [[ -n $heat_stack ]]; then
        delete_heat_stack $heat_stack_name
    fi
    exit_rc=0
    openstack --os-cloud ${cloud_config} stack create --timeout 10 --wait \
        -t "$heat_template_file"  \
        $heat_stack_name && rc=$? || rc=$?
    if [[ $rc != 0 ]]; then
        exit_rc=$rc
        delete_heat_stack $heat_stack_name || :
        exit $exit_rc
    fi
elif [[ $action == "update" ]]; then
    openstack --os-cloud ${cloud_config} stack update --timeout 10 --wait \
        -t "$heat_template_file"  \
        $heat_stack_name
elif [[ $action == "delete" ]]; then
    heat_stack=$(get_heat_stack $heat_stack_name)
    if [[ -n $heat_stack ]]; then
        delete_heat_stack $heat_stack_name
    fi
fi
