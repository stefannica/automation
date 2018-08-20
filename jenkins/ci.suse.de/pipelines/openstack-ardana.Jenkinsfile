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
      customWorkspace "openstack-ardana-pipeline-${BUILD_ID}"
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
            script {
              // TODO: every ECP slot must be uniquely associated with a heat stack
              env.heat_stack_name = "${JOB_NAME}-${BUILD_NUMBER}"
            }
            build job: 'openstack-ardana-venv', parameters: [
              string(name: 'git_automation_repo', value: "${git_automation_repo}"),
              string(name: 'git_automation_branch', value: "${git_automation_branch}"),
              string(name: 'build_pool_name', value: "${build_pool_name}"),
              string(name: 'git_input_model_repo', value: "${git_input_model_repo}"),
              string(name: 'git_input_model_branch', value: "${git_input_model_branch}"),
              string(name: 'git_input_model_path', value: "${git_input_model_path}"),
              string(name: 'model', value: "${model}"),
              string(name: 'scenario', value: "${scenario}"),
              string(name: 'heat_stack_name', value: "${heat_stack_name}"),
              string(name: 'build_pool_name', value: "${build_pool_name}"),
              string(name: 'build_pool_size', value: "${build_pool_size}"),
              string(name: 'reuse_node', value: "${NODE_NAME}"),
              string(name: 'reuse_workspace', value: "${WORKSPACE}"),
              string(name: 'job_desc', value: "${job_desc} (env: ${heat_stack_name})")
            ], propagate: true, wait: true

            // Load the environment variables set by the downstream job
            load "openstack-ardana-venv.output.groovy"
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
            ansible-playbook -v -i hosts \
                -e "image_mirror_url=${image_mirror_url}" \
                -e "tempest_run_filter=${tempest_run_filter}" \
                -e "verification_temp_dir=$verification_temp_dir" \
                post-deploy-checks.yml
          '''
        }
      }
    }
  }

  post {
    always {
        build job: 'openstack-ardana-heat', parameters: [
          string(name: 'action', value: "cleanup"),
          string(name: 'build_pool_name', value: "$build_pool_name"),
          string(name: 'build_pool_size', value: "$build_pool_size"),
          string(name: 'heat_stack_name', value: "$heat_stack_name"),
          string(name: 'heat_template_file', value: "$heat_template_file")
        ], propagate: false, wait: false
        build job: 'openstack-ardana-heat', parameters: [
          string(name: 'action', value: "cleanup"),
          string(name: 'build_pool_name', value: "$build_pool_name"),
          string(name: 'build_pool_size', value: "$build_pool_size")
        ], propagate: false, wait: false
    }
  }

}