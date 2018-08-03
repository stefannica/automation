/**
 * The openstack-ardana Jenkins Pipeline
 */

pipeline {
  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
    // lock(label: 'ECP-SLOT', quantity: 1)
  }

  agent {
    node {
      label 'cloud-ardana-ci'
      customWorkspace label ? "${JOB_NAME}-${label}" : "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('setup environment') {
      steps {
        script {
          if ("${label}" != '') {
            currentBuild.displayName = "#${BUILD_NUMBER} ${label}"
            //currentBuild.description = ""
          }
          else {
            currentBuild.displayName = "${JOB_NAME}-${BUILD_NUMBER}"
            //currentBuild.description = ""
          }
          env.cloud_release = "cloud"+cloudsource[-1]
          if ( "${want_caasp}" == '1' ) {
            // Use the CaaSP flavors instead of the default ones, when CaaSP is deployed
            env.virt_config="caasp.yml"
          }
        }
      }
    }

    stage('clone automation repo') {
      steps {
        dir('automation-git') {
          checkout scm
        }
      }
    }

    // TODO: more stages here (linter, etc)
    stage('parallel stage') {
      // abort all stages if one of them fails
      failFast true
      parallel {

        // TODO: more stages here (linter, etc)

        stage('build test packages') {
          when {
            expression { gerrit_change_ids != '' }
          }
          steps {
            build job: 'cloud-ardana-testbuild-gerrit', parameters: [
              string(name: 'gerrit_change_ids', value: "$gerrit_change_ids"),
              string(name: 'develproject', value: "$develproject"),
              string(name: 'homeproject', value: "$homeproject"),
              string(name: 'repository', value: "$repository"),
              string(name: 'git_automation_repo', value: "$git_automation_repo"),
              string(name: 'git_automation_branch', value: "$git_automation_branch")
            ], propagate: true, wait: true
          }
        }

        stage('prepare virtual environment') {
          steps {
            build job: 'openstack-ardana-vcloud', parameters: [
              string(name: 'label', value: "${label}"),
              string(name: 'cloud_release', value: "${cloud_release}"),
              string(name: 'git_automation_repo', value: "${git_automation_repo}"),
              string(name: 'git_automation_branch', value: "${git_automation_branch}"),
              string(name: 'git_input_model_repo', value: "${git_input_model_repo}"),
              string(name: 'git_input_model_branch', value: "${git_input_model_branch}"),
              string(name: 'git_input_model_path', value: "${git_input_model_path}"),
              string(name: 'model', value: "${model}"),
              string(name: 'scenario', value: "${scenario}"),
              string(name: 'os_cloud', value: "${os_cloud}"),
              string(name: 'reuse_node', value: "${NODE_NAME}"),
              string(name: 'reuse_workspace', value: "${WORKSPACE}")
            ], propagate: true, wait: true

            // Load the environment variables set by the downstream job
            load "openstack-ardana-vcloud.output.groovy"
          }
        } // stage('prepare virtual environment')
      } // parallel
    } // stage('parallel stage')

    stage('bootstrap CLM') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh './bin/bootstrap_clm.sh'
          script {
            env.verification_temp_dir = sh (returnStdout: true, script: 'cat verification_temp_dir')
          }
        }
      }
    }

    stage('deploy Ardana') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            # Run site.yml outside ansible for output streaming
            ssh $sshargs ardana@${CLM_IP} "cd ~/scratch/ansible/next/ardana/ansible ; \
                 ansible-playbook -v -i hosts/verb_hosts site.yml"
          '''
        }
      }
    }

    stage ('run Tempest') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            image_mirror_url=http://provo-clouddata.cloud.suse.de/images/openstack/x86_64
            source /opt/ansible/bin/activate
            # Run post-deploy checks
            ansible-playbook -v \
                -e "image_mirror_url=${image_mirror_url}" \
                -e "tempest_run_filter=${tempest_run_filter}" \
                -e "verification_temp_dir=$verification_temp_dir" \
                post-deploy-checks.yml
          '''
        }
      }
    }

    stage ('deploy CaaSP') {
      when {
        expression { want_caasp == '1' }
      }
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
            source /opt/ansible/bin/activate
            ansible-playbook -v \
                deploy-caasp.yml
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts '*'
      lock(resource: 'ECP-API') {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
             if [ "$cleanup" == "always" ] && [ -n "${heat_stack_name}" ]; then
               ./bin/heat_stack.sh delete "${heat_stack_name}"
             fi
          '''
        }
      }
    }
    success {
      lock(resource: 'ECP-API') {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
             if [ "$cleanup" == "on success" ] && [ -n "${heat_stack_name}" ]; then
               ./bin/heat_stack.sh delete "${heat_stack_name}"
             fi
          '''
        }
      }
    }
    failure {
      lock(resource: 'ECP-API') {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh '''
             if [ "$cleanup" == "on failure" ] && [ -n "${heat_stack_name}" ]; then
               ./bin/heat_stack.sh delete "${heat_stack_name}"
             fi
          '''
        }
      }
    }
  }

}