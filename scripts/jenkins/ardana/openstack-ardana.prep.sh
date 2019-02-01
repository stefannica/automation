#!/bin/bash -xu
shopt -s extglob

mkdir -p "$SHARED_WORKSPACE"

# emptying the workspace
cd $SHARED_WORKSPACE
rm -rf ./* ./.[a-zA-Z]*

# have to account for the fact that sometimes SHARED_WORKSPACE and
# WORKSPACE are not the same. archiveArtifacts and junit don't support
# absolute paths, so we have to to this instead
if [[ $SHARED_WORKSPACE != $WORKSPACE ]]; then
    ln -s ${SHARED_WORKSPACE}/.artifacts ${WORKSPACE}
fi

export automationrepo=~/github.com/${git_automation_fork}/automation
export AUTOMATION_REPO=github.com/${git_automation_fork}/automation#${git_automation_branch}

# automation bootstrapping
if ! [ -e ${automationrepo}/scripts/jenkins/update_automation ] ; then
  rm -rf ${automationrepo}
  curl https://raw.githubusercontent.com/${git_automation_fork}/automation/${git_automation_branch}/scripts/jenkins/update_automation | bash
fi

# fetch the latest automation updates
${automationrepo}/scripts/jenkins/update_automation

automationrepo_orig=$automationrepo
automationrepo=${SHARED_WORKSPACE}/automation-git

mkdir -p $automationrepo
rsync -a ${automationrepo_orig%/}/ $automationrepo/
pushd $automationrepo
ghremote=origin

# Support for automation self-gating
if [ -n "$github_pr_id" ]; then
    git config --get-all remote.${ghremote}.fetch | grep -q pull || \
        git config --add remote.${ghremote}.fetch "+refs/pull/*/head:refs/remotes/${ghremote}/pr/*"
    git fetch $ghremote 2>&1 | grep -v '\[new ref\]' || :
    git checkout -t $ghremote/pr/$github_pr_id
    git config user.email cloud-devel+jenkins@suse.de
    git config user.name "Jenkins User"
    echo "we merge to always test what will end up in master"
    git merge master -m temp-merge-commit
fi
# Show latest commit in log to see what's really tested.
# Include a unique indent so that the log parser plugin
# can ignore the output and avoid false positives.
git --no-pager show | sed 's/^/|@| /'
popd
