/**
 * The openstack-ardana-testbuild-gerrit Jenkins Pipeline
 *
 * This job creates test IBS packages corresponding to supplied Gerrit patches.
 */
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
            # temporary, until git_automation_repo is re-purposed to hold only
            # the fork name and renamed to git_automation_fork
            IFS='/' read -r -a repo_arr <<< "$git_automation_repo"
            git_automation_fork="${repo_arr[3]}
            export github_pr_id=$github_pr

            export automationrepo=~/github.com/${git_automation_fork}/automation
            export AUTOMATION_REPO=github.com/${git_automation_fork}/automation#${git_automation_branch}
            export SHARED_WORKSPACE=$WORKSPACE

            # automation bootstrapping
            if ! [ -e ${automationrepo}/scripts/jenkins/update_automation ] ; then
              rm -rf ${automationrepo}
              curl https://raw.githubusercontent.com/${git_automation_fork}/automation/${git_automation_branch}/scripts/jenkins/update_automation | bash
            fi

            # fetch the latest automation updates
            ${automationrepo}/scripts/jenkins/update_automation

            # prepare the shared workspace
            ${automationrepo}/scripts/jenkins/ardana/openstack-ardana.prep.sh
          ''')
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
