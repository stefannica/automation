#!/usr/bin/env bash
set -ex

sshargs="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
# FIXME: Use cloud-init in the used image
sshpass -p linux ssh-copy-id -o ConnectionAttempts=120 $sshargs root@${CLM_IP}

source /opt/ansible/bin/activate

ansible-playbook -v -i hosts ssh-keys.yml
if [ -n "$gerrit_change_ids" ] ; then
  test_repository=http://download.suse.de/ibs/${homeproject//:/:\/}:/ardana-ci-${gerrit_change_ids//,/-}/standard
fi

ansible-playbook -v -i hosts -e "build_url=$BUILD_URL" \
                           -e "cloudsource=${cloudsource}" \
                           -e "repositories='${repositories}'" \
                           -e "test_repository_url='${test_repository}'" \
                           repositories.yml

verification_temp_dir=$(ssh $sshargs root@$CLM_IP \
                        "mktemp -d /tmp/ardana-job-rpm-verification.XXXXXXXX")

cat << EOF > verification_temp_dir
$verification_temp_dir
EOF

ansible-playbook -v -i hosts -e "deployer_floating_ip=$CLM_IP" \
                           -e "verification_temp_dir=$verification_temp_dir" \
                           -e cloudsource="${cloudsource}" \
                           init.yml
