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

import os
import os.path
import re
import shutil

import repo
import repo.package
import repo.packages


class InstallerInfo(object):
    def __init__(self, name, subdir, package_re, formatter):
        self.name = name
        self.subdir = subdir
        self.package_re = package_re
        self.formatter = formatter


class Repository(repo.packages.Repository):
    def __init__(self, topdir, installer_info):
        self.installer_info = installer_info
        super(Repository, self).__init__(
                os.path.join(topdir, installer_info.subdir),
                installer_info.name, installer_info.package_re)

    def add_package(self, package, update_metadata=False):
        if package.version.strversion != 'latest':
            new_package = super(Repository, self).add_package(
                package, update_metadata=update_metadata)
            groups = re.match(
                self.installer_info.package_re,
                os.path.basename(new_package.path)).groupdict()
            groups['version'] = 'latest'
            groups['release'] = ""
            groups['buildno'] = ""

            newname = self.installer_info.formatter(**groups)

            new_package_path = os.path.join(
                os.path.dirname(new_package.path),
                newname)
            latest_candidates = [
                (pkg)
                for pkg in self.packages[new_package.name]
                if pkg.name == new_package.name
                    and pkg.version.strversion != "latest"
                    and pkg.version > new_package.version
            ]
            if len(latest_candidates) == 0:
                shutil.copy(new_package.path, new_package_path)
                if update_metadata:
                    self.update_metadata(True)





class Release(repo.Release):
    """
    Release
    =======
    Each Release contains a collection of repositories for different
    architectures for a particular operating system release.
    """
    def __init__(self, topdir, name, installer_infos):
        repositories = {}
        for i in installer_infos:
            repositories[i.name] = Repository(topdir, i)
        super(Release, self).__init__(name, repositories)

    def repositories_for_os_arch(self, osname, arch):
        if osname:
            return [self.repositories[osname]]
        else:
            return [self.repositories[r] for r in self.repositories]

    def repositories_for_package(self, package):
        return [self.repositories[package.os]]

    def get_packages(
            self, name=None, os=None, version=None, arch=None,
            source=None, newest_only=False):
        res = [p
                for repository in self.repositories_for_os_arch(os, arch)
                for p in repository.get_packages(
                    name=name, version=version, source=source,
                    newest_only=newest_only)]
        return res

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.installer.Manager object manages the packages in a
    release tree. New packages from the repositories can be
    promoted to the release tree.
    """
    def __init__(self, root=repo.default_root, releases=repo.default_releases):
        """
        Constructor
        -----------
        Create a new Manager object.

        Parameters
        ----------
        *root*::
            Root of the release trees
        """
        self.installers = [
            InstallerInfo(
                "Linux Binary Installer",
                "linux",
                r"(?P<name>(?P<basename>[a-z_]*)-(?P<version>([0-9.]|beta|rc)+)-(?P<arch>[a-z0-9_-]+))(?P<buildno>-Build-(?P<release>[0-9]+)).tar.gz$",
                "{basename}-{version}-{arch}{buildno}.tar.gz".format),
            InstallerInfo(
                "macos Binary Installer",
                "mac",
                r"(?P<name>(?P<basename>[a-zA-Z_]*)-(?P<version>([0-9.]|beta|rc)+))(?P<buildno>-build(?P<release>[0-9]+))?(?P<extension>\.pkg|\.tar\.gz)$",
                "{basename}-{version}{buildno}{extension}".format),
            InstallerInfo(
                "RPM Installer",
                'repo/rpm',
                r"(?P<name>(?P<basename>[a-z-]*[a-z])-(?P<version>[0-9.]*[0-9]))(?P<buildno>-(?P<release>[0-9]+))(?P<extension>.*\.noarch\.rpm)$",
                "{basename}-{version}{buildno}{extension}".format),
            InstallerInfo(
                'Debian Installer',
                "repo/deb",
                r"(?P<name>(?P<basename>[a-z-]*[a-z])_(?P<version>[0-9.]+))(?P<buildno>-(?P<release>[0-9]+))?_all.deb$",
                "{basename}_{version}{buildno}_all.deb".format),
            InstallerInfo(
                "Source Installer",
                'src',
                r"(?P<name>[a-z_]*)-(?P<version>([0-9.]|beta|rc)*)\.tar\.gz$",
                "{name}-{version}.tar.gz".format),
            InstallerInfo(
                "Cygwin Installer",
                'windows',
                r"(?P<name>(?P<basename>[a-z_]*)-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>[a-z0-9]*-pc-cygwin))(?P<buildno>-Build-(?P<release>[0-9]+)).zip$",
                "{basename}-{version}-{arch}{buildno}.zip".format),
            InstallerInfo(
                "Mingw32 Installer",
                "windows",
                r"(?P<name>(?P<basename>[a-z_]*)-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>[a-z0-9]*-w64-mingw32))(?P<buildno>-Build-(?P<release>[0-9]+)).zip$",
                "{basename}-{version}-{arch}{buildno}.zip".format),
        ]

        release = {}
        for r in releases:
            release[r] = Release(
                os.path.join(root, r, 'installers'),
                r,
                self.installers)
        super(Manager, self).__init__(release)

    def get_release(self, releasename):
        return self.releases[releasename]

    def __str__(self):
        return " ".join(
            ["Installers Manager [", ",".join(self.releases.keys()), "]"])

# vim: filetype=python:
