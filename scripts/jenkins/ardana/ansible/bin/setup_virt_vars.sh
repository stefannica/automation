#!/usr/bin/env bash

# the name for the cloud defined in ~./config/openstack/clouds.yaml
CLOUD_CONFIG_NAME=engcloud-cloud-ci

set -ex

DEPLOYER_IP=$(openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name admin-floating-ip -c output_value -f value)

NETWORK_MGMT_ID=$(openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name mgmt-network-id -c output_value -f value)
cat << EOF > hosts
[hosts]
$DEPLOYER_IP ansible_user=root
EOF

cat hosts

cat << EOF > deployer_ip
$DEPLOYER_IP
EOF

cat << EOF > ardana_net_vars.yml
---
input_model_path: "$input_model_path"
deployer_mgmt_ip: $(openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name admin-mgmt-ip -c output_value -f value)
EOF

controller_mgmt_ips=$(openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name controller-mgmt-ips -c output_value -f value|grep -o '[0-9.]*')
if [ -n "$controller_mgmt_ips" ]; then
echo "controller_mgmt_ips:" >> ardana_net_vars.yml
for ip in $controller_mgmt_ips; do
    cat << EOF >> ardana_net_vars.yml
  - $ip
EOF
done
fi

compute_mgmt_ips=$(openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name compute-mgmt-ips -c output_value -f value|grep -o '[0-9.]*')
if [ -n "$compute_mgmt_ips" ]; then
echo "compute_mgmt_ips:" >> ardana_net_vars.yml
for ip in $compute_mgmt_ips; do
    cat << EOF >> ardana_net_vars.yml
  - $ip
EOF
done
fi

# Get the IP addresses of the dns servers from the mgmt network
echo "mgmt_dnsservers:" >> ardana_net_vars.yml
openstack --os-cloud $CLOUD_CONFIG_NAME port list --network $NETWORK_MGMT_ID \
        --device-owner network:dhcp -f value -c 'Fixed IP Addresses' | \
  sed -e "s/^ip_address='\(.*\)', .*$/\1/" | \
  while read line; do echo "  - $line" >> ardana_net_vars.yml; done;

cat ardana_net_vars.yml
