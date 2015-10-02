# Copyright 2014-2015 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Package to manage the installers repository
"""

import ast
import fnmatch
import os


try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

JENKINS_BASE = "http://builds.globus.org/jenkins"
JOB_PATTERN = JENKINS_BASE + "/job/%s/lastSuccessfulBuild/api/python"
ARTIFACT_PATTERN = JENKINS_BASE + "/job/%s/lastSuccessfulBuild/artifact/%s"

def list_artifacts(job, patterns):
    """
    Creates a list of URL strings matching the artifacts for this
    job which match a shell-style glob pattern
    """
    result_artifacts = []

    jenkins_job_url = JOB_PATTERN % (job)
    resp = urlopen(jenkins_job_url)
    code = resp.code if 'code' in resp.__dict__ else None

    if code == 200:
        artifacts = ast.literal_eval(resp.read()).get('artifacts')
        for artifact in artifacts:
            path = artifact['relativePath']
            for pattern in patterns:
                if fnmatch.fnmatch(path, pattern):
                    result_artifacts.append(ARTIFACT_PATTERN %
                        (job, artifact['relativePath']))
                    break
    resp.close()
    return result_artifacts

def fetch_url(url, dest_dir, force=False):
    local_name = os.path.join(dest_dir, os.path.basename(url))
    if force or not os.path.exists(local_name):
        resp = urlopen(url)
        code = resp.code if 'code' in resp.__dict__ else None
        if code == 200:
            f = file(local_name, "w")
            f.write(resp.read())
            f.close()
# vim: filetype=python:
