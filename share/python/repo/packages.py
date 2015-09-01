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
Package to manage the Globus Toolkit source tarball repository
"""

import fnmatch
import hashlib
import os
import os.path
import re
import repo
import repo.package
import shutil

class Repository(repo.Repository):
    """
    Repository class
    ================
    This class contains the source package repository metadata.
    """
    def __init__(self, repo_path, name, pkg_re):
        super(Repository, self).__init__()
        self.repo_path = repo_path
        self.name = name
        self.pkg_re = re.compile(pkg_re)
        self.dirty = False

        if not os.path.exists(self.repo_path):
            self.update_metadata(True)

        for tarball in os.listdir(self.repo_path):
            m = self.pkg_re.match(tarball)
            if m is not None:
                d = m.groupdict()
                pkg = repo.package.Metadata(
                        d.get('name'),
                        d.get('version'),
                        d.get('release', '0'),
                        os.path.join(repo_path, tarball),
                        d.get('arch', 'src'),
                        os.path.join(repo_path, tarball),
                        name)
                if pkg.name not in self.packages:
                    self.packages[pkg.name] = []
                self.packages[pkg.name].append(pkg)
        for p in self.packages:
            self.packages[p].sort()

    def add_package(self, package, update_metadata=False):
        dest_path = os.path.join(self.repo_path,
            os.path.basename(package.path))
        if not os.path.exists(dest_path):
            shutil.copy(package.path, dest_path)
        if not package.name in self.packages:
            self.packages[package.name] = []

        # Create a new repo.package.Metadata with the new path
        new_package = repo.package.Metadata(
                package.name,
                package.version.strversion, package.version.release,
                dest_path,
                package.arch,
                package.source_name,
                'src')

        self.packages[package.name].append(new_package)
        self.packages[package.name].sort()
        if update_metadata:
            self.update_metadata()
        else:
            self.dirty = True
        return new_package
        

    def update_metadata(self, force=False):
        """
        Update the checksums for the packages in this repository
        """
        if self.dirty or force:
            distro_repodir = self.repo_path

            if not os.path.exists(distro_repodir):
                os.makedirs(distro_repodir, 0o755)
                if repo.gid is not None:
                    os.chown(distro_repodir, repo.uid, repo.gid)
                    os.chmod(distro_repodir, 0o2775)

            for pkg in os.listdir(distro_repodir):
                pkg_filename = os.path.join(distro_repodir, pkg)
                if os.path.isfile(pkg_filename):
                    repo._digest_file(pkg_filename)
            gcs = self.packages.get('globus_connect_server',[])
            max_gcs_version = package.Version("0")
            for gcs_pkg in gcs:
                if gcs_pkg.version > max_gcs_version:
                    max_gcs_version = gcs_pkg.version
            latest_file = file(
                    os.path.join(
                            distro_repodir, "GLOBUS_CONNECT_SERVER_LATEST"),
                            "w")
            latest_file.write(max_gcs_version.strversion + "\n")
            latest_file.close()

class Release(repo.Release):
    """
    Release
    =======
    Each Release contains a collection of repositories for different
    architectures for a particular operating system release.
    """
    pkg_re = re.compile(r"(?P<name>(?!globusonline-)[^-]*|globusonline-[a-z-]*[a-z]*)-(?P<version>.*?)(-src|-gt5.2)?.tar.gz$")
    def __init__(self, name, topdir):
        r = Repository(topdir, "packages", Release.pkg_re)
        super(Release, self).__init__(name, r)

    def repositories_for_os_arch(self, osname, arch):
        return [self.repositories]

    def repositories_for_package(self, package):
        return [self.repositories]

class Cache(repo.Cache):
    """
    Cache
    =====
    The repo.packages.Cache object manages a mirror of the builds.globus.org
    "packages" subdirectory. This mirror contains a repo.packages.Distro() for
    the source packages in the cache. This Distro object can be used
    to promote packages from the cache
    """
    def __init__(self, cache):
        self.cache_dir = cache
        super(Cache, self).__init__(cache, "packages")
        self.sync()

        cache_root = os.path.join(cache, 'packages')
        self.release = Release("cache", cache_root)

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.packages.Manager object manages the packages in a cache and
    release tree. New packages from the cache can be
    promoted to the release tree.
    """
    def __init__(self, cache_root=repo.default_cache, root=repo.default_root,
            use_cache=True):
        """
        Constructor
        -----------
        Create a new Manager object.

        Parameters
        ----------
        *cache_root*::
            Root of the cache to manage
        *root*::
            Root of the release trees
        *use_cache*::
            (Optional) Parse packages in the cache
        """
        cache = Cache(cache_root) if use_cache else None

        release = {"release": Release("release",
                    os.path.join(root, 'packages'))}
        super(Manager, self).__init__(cache, release)

    def get_release(self, releasename):
        if releasename == 'cache':
            return self.cache.release
        else:
            return self.releases['release']

    def package_name(self, name):
        return name.replace("-", "_") if name is not None else None

    def __str__(self):
        return " ".join(["Packages Manager [", ",".join(self.releases.keys()), "]"])
