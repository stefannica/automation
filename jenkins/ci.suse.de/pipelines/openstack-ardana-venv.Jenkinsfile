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
      customWorkspace reuse_workspace ? reuse_workspace : "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('setup environment') {
      steps {

        // Replace the created workspace with a symlink to the reused one
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
          if ("${job_desc}" != '') {
            currentBuild.displayName = "#${BUILD_NUMBER} ${job_desc}"
            //currentBuild.description = ""
          }
          else {
            currentBuild.displayName = "${JOB_NAME}-${BUILD_NUMBER}"
            //currentBuild.description = ""
          }
          env.input_model_path = "${WORKSPACE}/input-model"
          env.heat_template_file = "${WORKSPACE}/heat-ardana-${model}.yaml"
          if ("${heat_stack_name}" == '') {
            env.heat_stack_name = "${JOB_NAME}-${BUILD_NUMBER}"
          }
          env.CLOUD_CONFIG_NAME = "engcloud-cloud-ci"
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
          sh 'ln -s ./input-model-git/${git_input_model_path}/${model} $input_model_path'
        }
      }
    }

    stage('generate input model') {
      when {
          expression { scenario != '' }
      }
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            source /opt/ansible/bin/activate
            ansible-playbook -v \
                             -e scenario_name=${scenario} \
                             -e input_model_dir=${input_model_path} \
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
                             -e input_model_path=${input_model_path} \
                             -e heat_template_file=${heat_template_file} \
                             generate-heat.yml
            '''
        }
      }
    }

    stage('create virtual env') {
      //options {
      //  lock(resource: 'ECP-API')
      //}
      steps {
        build job: 'openstack-ardana-heat', parameters: [
          string(name: 'action', value: "create"),
          string(name: 'build_pool_name', value: "${build_pool_name}"),
          string(name: 'build_pool_size', value: "${build_pool_size}"),
          string(name: 'heat_stack_name', value: "${heat_stack_name}"),
          string(name: 'heat_template_file', value: "${heat_template_file}")
        ], propagate: true, wait: true
      }
    }

    stage('get CLM IP') {
      steps {
        script {
          env.CLM_IP = sh (
            script: 'openstack --os-cloud $CLOUD_CONFIG_NAME stack output show $heat_stack_name admin-floating-ip -c output_value -f value',
            returnStdout: true
          ).trim()
          echo "CLM is reachable at root@${CLM_IP}"
        }
      }
    }

    stage('setup ansible vars') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh './bin/setup_virt_vars.sh'
        }
      }
    }

    stage('setup output variables') {
      steps {
        sh '''
          cat << EOF > ${JOB_NAME}.output.groovy
env.CLM_IP="${CLM_IP}"
env.heat_stack_name="${heat_stack_name}"
env.heat_template_file="${heat_template_file}"
env.input_model_path="${input_model_path}"
EOF
        '''
      }
    }
  }
  post {
    failure {
        build job: 'openstack-ardana-heat', parameters: [
          string(name: 'action', value: "cleanup"),
          string(name: 'build_pool_name', value: "${build_pool_name}"),
          string(name: 'build_pool_size', value: "${build_pool_size}"),
          string(name: 'heat_stack_name', value: "${heat_stack_name}"),
          string(name: 'heat_template_file', value: "${heat_template_file}")
        ], propagate: false, wait: false
    }
    always {
        build job: 'openstack-ardana-heat', parameters: [
          string(name: 'action', value: "cleanup"),
          string(name: 'build_pool_name', value: "${build_pool_name}"),
          string(name: 'build_pool_size', value: "${build_pool_size}")
        ], propagate: false, wait: false
    }
  }
}