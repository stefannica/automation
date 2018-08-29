/**
 * The openstack-ardana-virtual Jenkins Pipeline
 *
 * This jobs creates an ECP virtual environment that can be used to deploy
 * an Ardana input model which is either predefined or generated based on
 * the input parameters.
 */
pipeline {

  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
  }

  agent {
    node {
      label reuse_node ? reuse_node : "cloud-ardana-ci"
      customWorkspace clm_env ? "${JOB_NAME}-${clm_env}" : "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('setup workspace and environment') {
      steps {
        cleanWs()

        // If the job is set up to reuse an existing workspace, replace the
        // current workspace with a symlink to the reused one.
        // NOTE: even if we specify the reused workspace as the
        // customWorkspace variable value, Jenkins will refuse to reuse a
        // workspace that's already in use by one of the currently running
        // jobs and will just create a new one.
        sh '''
          if [ -n "${reuse_workspace}" ]; then
            rmdir "${WORKSPACE}"
            ln -s "${reuse_workspace}" "${WORKSPACE}"
          fi
        '''

        script {
          if ( clm_env == '') {
            error("Empty 'clm_env' parameter value.")
          }
          currentBuild.displayName = "#${BUILD_NUMBER} ${clm_env}"
          env.heat_stack_name="$JOB_NAME-$clm_env"
          env.input_model_path = "${WORKSPACE}/input-model"
          env.heat_template_file = "${WORKSPACE}/heat-ardana-${model}.yaml"
        }
      }
    }

    stage('clone automation repo') {
      when {
        expression { reuse_workspace == '' }
      }
      steps {
        dir("automation-git") {
          checkout scm
        }
      }
    }

    stage('clone input model repo') {
      when {
        expression { git_input_model_repo != '' && scenario == '' }
      }
      steps {
        dir('input-model-git') {
          git(
             url: "${git_input_model_repo}",
             branch: "${git_input_model_branch}"
          )
        }
        script {
          env.input_model_path = "${WORKSPACE}/input-model-git/${git_input_model_path}/${model}"
        }
      }
    }

    stage('generate input model') {
      when {
          expression { scenario != '' }
      }
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          script {
            env.virt_config = "${WORKSPACE}/${scenario}-virt-config.yml"
          }
          sh '''
            source /opt/ansible/bin/activate
            ansible-playbook -v \
                             -e cloud_release="${cloud_release}" \
                             -e scenario_name="${scenario}" \
                             -e input_model_dir="${input_model_path}" \
                             -e virt_config_file="${virt_config}" \
                             -e clm_model=$clm_model \
                             -e controllers=$controllers \
                             -e sles_computes=$sles_computes \
                             -e rhel_computes=$rhel_computes \
                             -e rc_notify=$rc_notify \
                             generate-input-model.yml
          '''
        }
      }
    }

    stage('generate heat') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            source /opt/ansible/bin/activate
            ansible-playbook -v \
                             -e cloud_release="${cloud_release}" \
                             -e input_model_path="${input_model_path}" \
                             -e heat_template_file="${heat_template_file}" \
                             -e virt_config_file="${virt_config}" \
                             generate-heat.yml
          '''
        }
      }
    }

    stage('create virtual env') {
      steps {
        lock(resource: 'ECP-API') {
          dir('automation-git/scripts/jenkins/ardana/ansible') {
            sh './bin/heat_stack.sh create "${heat_stack_name}" "${heat_template_file}"'
          }
        }
      }
    }

    stage('setup ansible vars') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh './bin/setup_virt_vars.sh'
          script {
            env.DEPLOYER_IP = sh (
              script: '''
                source /opt/ansible/bin/activate
                ansible -o localhost -a "echo {{ hostvars['ardana-$clm_env'].ansible_host }}" | cut -d' ' -f 8
              ''',
              returnStdout: true
            ).trim()
          }
        }
      }
    }

    stage('setup SSH access') {
      steps {
        sh '''
          sshargs="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
          # FIXME: Use cloud-init in the used image
          sshpass -p linux ssh-copy-id -o ConnectionAttempts=120 $sshargs root@${DEPLOYER_IP}
        '''
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            source /opt/ansible/bin/activate
            ansible-playbook -v -e clm_env=$clm_env \
                                ssh-keys.yml
          '''
        }
      }
    }
  }

  post {
    success{
      echo """
*****************************************************************
** The virtual environment is reachable at
**
**        ssh root@${DEPLOYER_IP}
**
** Please delete the $heat_stack_name stack manually when you're done.
*****************************************************************
      """
    }
    failure {
      lock(resource: 'ECP-API') {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            if [ -n "${heat_stack_name}" ]; then
              ./bin/heat_stack.sh delete "${heat_stack_name}"
            fi
          '''
        }
      }
    }
  }
}