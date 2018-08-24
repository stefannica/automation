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
    stage('setup build environment') {
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
    stage('parallel one') {
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

    stage('setup deployer media') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          script {
            sh './bin/bootstrap_clm.sh'
          }
        }
      }
    }

    stage('initialize deployer') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          script {
            sh '''
              source /opt/ansible/bin/activate
              ansible-playbook -v -e "build_url=$BUILD_URL" \
                                  -e cloudsource="${cloudsource}" \
                                  init.yml
            '''
          }
        }
      }
    }

    stage('deploy cloud') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          script {
            sh './bin/deploy_ardana.sh'
          }
        }
      }
    }

    stage('parallel two') {
      // run all stages to the end, even if one of them fails
      failFast false
      parallel {

        stage ('tempest') {
          when {
            expression { tempest_run_filter != '' }
          }
          steps {
            dir('automation-git/scripts/jenkins/ardana/ansible') {
              script {
                sh './bin/run_tempest.sh'
              }
            }
          }
        }

        stage ('post deploy checks') {
          steps {
            dir('automation-git/scripts/jenkins/ardana/ansible') {
              sh '''
                source /opt/ansible/bin/activate
                # Run post-deploy checks
                ansible-playbook -v post-deploy-checks.yml
              '''
            }
          }
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