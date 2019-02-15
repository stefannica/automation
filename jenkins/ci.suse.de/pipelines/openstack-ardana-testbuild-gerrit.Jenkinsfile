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
      label "openstack-trackupstream"
    }
  }

  stages {
    stage('Setup workspace') {
      steps {
        cleanWs()
        script {
          // Set this variable to be used by upstream builds
          env.blue_ocean_buildurl = env.RUN_DISPLAY_URL
          if (gerrit_change_ids == '') {
            error("Empty 'gerrit_change_ids' parameter value.")
          }
          currentBuild.displayName = "#${BUILD_NUMBER}: ${gerrit_change_ids}"
          env.test_repository_url = sh (
            returnStdout: true,
            script: '''
              echo http://download.suse.de/ibs/${homeproject//:/:\\/}:/ardana-ci-${BUILD_NUMBER}/standard/${homeproject}:ardana-ci-${BUILD_NUMBER}.repo
            '''
          ).trim()
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
        sh '''
          cd automation-git/scripts/jenkins/ardana/gerrit
          set -eux
          python -u build_test_package.py --homeproject ${homeproject} --buildnumber ${BUILD_NUMBER} -c ${gerrit_change_ids//,/ -c }
          echo "zypper repository for test packages: $test_repository_url"
        '''
      }
    }
  }
}
