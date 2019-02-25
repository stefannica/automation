/**
 * The openstack-ardana-testbuild-gerrit Jenkins Pipeline
 *
 * This job creates test IBS packages corresponding to supplied Gerrit patches.
 */

def ardana_lib = null

pipeline {

  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
    timestamps()
  }

  agent {
    node {
      label "cloud-ardana-ci"
      customWorkspace "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('Setup workspace') {
      steps {
        script {
          // Set this variable to be used by upstream builds
          env.blue_ocean_buildurl = env.RUN_DISPLAY_URL
          if (gerrit_changes == '') {
            error("Empty 'gerrit_changes' parameter value.")
          }
          currentBuild.displayName = "#${BUILD_NUMBER}: ${gerrit_changes}"
          sh('''
            git clone $git_automation_repo --branch $git_automation_branch automation-git
          ''')
          ardana_lib = load "automation-git/jenkins/ci.suse.de/pipelines/openstack-ardana.groovy"
          ardana_lib.load_extra_params_as_vars(extra_params)
        }
      }
    }

    stage('build test packages') {
      steps {
        sh('echo "IBS project for test packages: https://build.suse.de/project/show/${homeproject}:ardana-ci-${BUILD_NUMBER}"')
        sh('echo "zypper repository for test packages: http://download.suse.de/ibs/${homeproject//:/:\\/}:/ardana-ci-${BUILD_NUMBER}/standard/${homeproject}:ardana-ci-${BUILD_NUMBER}.repo"')
        timeout(time: 30, unit: 'MINUTES', activity: true) {
          sh('''
            cd automation-git/scripts/jenkins/ardana/gerrit
            set -eux
            python -u build_test_package.py --homeproject ${homeproject} --buildnumber ${BUILD_NUMBER} -c ${gerrit_changes//,/ -c }
          ''')
        }
      }
    }
  }
  post {
    cleanup {
      cleanWs()
    }
  }
}
