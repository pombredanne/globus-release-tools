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

import os
import re
import repo
import repo.artifacts
import repo.package

try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

class Manager(object):
    package_re = r"(?P<name>[a-z_]*)-(?P<version>([0-9.]|beta|rc)+)-doc.tar.bz2$"
    version_re = r"c-globus-(?P<major>[0-9]+)(\.(?P<minor>[0-9]+))?(\.(?P<release>[0-9]+))?$"
    def __init__(self, cache_root=repo.default_cache,
                       root=repo.default_api_root):
        self.cache_root = cache_root
        self.cache_dir = os.path.join(cache_root, "doxygen")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, 0o775)
        self.api_root = root
        self.packages = []

        artifacts = repo.artifacts.list_artifacts("GT6-INSTALLER", 
                ["packaging/artifacts/*-doc.tar.bz2"])
        for artifact in artifacts:
            filename = os.path.basename(artifact)
            m = re.match(self.package_re, filename)
            name = m.group('name')
            version = m.group('version')

            repo.artifacts.fetch_url(artifact, self.cache_dir)

            path = os.path.join(self.cache_dir, filename)
            metadata = repo.package.Metadata(name, version, None, path, None, None, "doxygen")
            self.packages.append(metadata)
            old_doc = os.path.join(self.api_root, "c")
            while os.path.islink(old_doc):
                old_doc = os.path.join(self.api_root, os.readlink(old_doc))
            self.old_doc_file = old_doc
        
    def promote_packages(self, dryrun=False):
        result_packages = []
        m = re.match(self.version_re, os.path.basename(self.old_doc_file))

        old_doc_major = m.group('major')
        old_doc_minor = m.group('minor')
        old_doc_release = m.group('release')

        for package in self.packages:
            package_dest = os.path.join(self.api_root, "c-globus-" + str(package.version))
            m = re.match(self.version_re, os.path.basename(package_dest))
            new_doc_major = m.group('major')
            new_doc_minor = m.group('minor')
            new_doc_release = m.group('release')

            if not os.path.exists(package_dest):
                result_packages.append(package)
                if not dryrun:
                    os.makedirs(package_dest, 0o775)
                    os.system("bzip2 -dc " + package.path + " | tar --strip 1 -x -f - -C " + package_dest)
                    new_major_minor = "c-globus-" + new_doc_major \
                                    + "." + new_doc_minor
                    new_major_minor_release = "c-globus-" + new_doc_major \
                                    + "." + new_doc_minor \
                                    + "." + new_doc_release
                    update_link = False
                    if (int(old_doc_major) < int(new_doc_major) or
                       (int(old_doc_major) == int(new_doc_major) and
                        int(old_doc_minor) < int(new_doc_minor))):
                        os.remove(os.path.join(self.api_root, "c"))
                        os.symlink(new_major_minor, "c")
                        update_link = True
                    elif (int(old_doc_major) == int(new_doc_major) and
                          int(old_doc_minor) == int(new_doc_minor) and
                          int(old_doc_release) < int(new_doc_release)):
                        update_link = True

                    if update_link:
                        os.remove(os.path.join(self.api_root, new_major_minor))
                        os.symlink(new_major_minor_release,
                                os.path.join(self.api_root, new_major_minor))
        return result_packages
