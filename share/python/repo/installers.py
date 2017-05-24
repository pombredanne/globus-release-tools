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

import repo
import repo.package
import repo.packages


class InstallerInfo(object):
    def __init__(self, name, subdir, package_re):
        self.name = name
        self.subdir = subdir
        self.package_re = package_re


class Repository(repo.packages.Repository):
    def __init__(self, topdir, installer_info):
        self.installer_info = installer_info
        super(Repository, self).__init__(
                os.path.join(topdir, installer_info.subdir),
                installer_info.name, installer_info.package_re)

    def add_package(self, package, update_metadata=False):
        return super(Repository, self).add_package(
                package, update_metadata=update_metadata)


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
        return [p
                for repository in self.repositories_for_os_arch(os, arch)
                for p in repository.get_packages(
                    name=name, version=version, source=source,
                    newest_only=newest_only)]

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
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)+)-(?P<arch>[a-z0-9_-]+))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "macos Binary Installer",
                "mac",
                r"(?P<name>[a-zA-Z_]*-(?P<version>([0-9.]|beta|rc)+))(-build(?P<release>[0-9]+))?(\.pkg|\.tar\.gz)"),
            InstallerInfo(
                "RPM Installer",
                'repo/rpm',
                r"(?P<name>[a-z-]*[a-z]-(?P<version>[0-9.]*[0-9]))-(?P<release>[0-9]+).*\.noarch\.rpm$"),
            InstallerInfo(
                'Debian Installer',
                "repo/deb",
                r"(?P<name>[a-z-]*[a-z]_(?P<version>[0-9.]+))(-(?P<release>[0-9]+))?.deb"),
            InstallerInfo(
                "Source Installer",
                'src',
                r"(?P<name>[a-z_]*)-(?P<version>([0-9.]|beta|rc)*)\.tar\.gz"),
            InstallerInfo(
                "Cygwin Installer",
                'windows',
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>[a-z0-9]*-pc-cygwin))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "Mingw32 Installer",
                "windows",
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>[a-z0-9]*-w64-mingw32))-Build-(?P<release>[0-9]+)"),
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
