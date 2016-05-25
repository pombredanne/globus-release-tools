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


try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

import os
import os.path
import shutil

import repo
import repo.artifacts
import repo.package
import repo.packages

class InstallerInfo(object):
    def __init__(self, name, subdir, artifact_patterns,
            package_re, link=None):
        self.name = name
        self.subdir = subdir
        self.artifact_patterns = artifact_patterns
        self.package_re = package_re
        self.link = link

class Repository(repo.packages.Repository):
    def __init__(self, topdir, installer_info):
        self.installer_info = installer_info
        super(Repository, self).__init__(
                os.path.join(topdir, installer_info.subdir),
                installer_info.name, installer_info.package_re)

    def add_package(self, package, update_metadata=False):
        new_package = super(Repository, self).add_package(package,
                update_metadata=update_metadata)
        if self.installer_info.link is not None:
            linkfile = os.path.join(os.path.dirname(new_package.path),
                    self.installer_info.link)
            if os.path.exists(linkfile):
                os.remove(linkfile)
            os.link(new_package.path, linkfile)
            repo._digest_file(linkfile, force=True)

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

    def get_packages(self, name=None, os=None, version=None, arch=None,
            source=None, newest_only=False):
        return [p
                for repository in self.repositories_for_os_arch(os, arch)
                for p in repository.get_packages(
                    name=name, version=version, source=source, 
                    newest_only=newest_only) ]


class Cache(repo.Cache):
    JENKINS_BASE = "http://builds.globus.org/jenkins"
    JOB_PATTERN = JENKINS_BASE + "/job/%s/lastSuccessfulBuild/api/python"
    ARTIFACT_PATTERN = JENKINS_BASE + "/job/%s/lastSuccessfulBuild/artifact/%s"

    def __init__(self, cache):
        self.cache_dir = os.path.join(cache, 'installers')
        # The pkg_re values below are somewhat odd in that the name group
        # contains more than the package name. This keeps the similarly-named,
        # but differently versioned packages from interfering with each other
        self.installers = [
            InstallerInfo(
                "GT6-BINARIES-LINUX",
                "linux",
                ["artifacts/*.tar.gz"],
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)+)-(?P<arch>[a-z0-9_-]+))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "GT6-BINARIES-MAC",
                "mac",
                [
                    "artifacts/GlobusToolkit*.pkg",
                    "artifacts/Globus*.tar.gz"
                ],
                r"(?P<name>[a-zA-Z_]*-(?P<version>([0-9.]|beta|rc)+))(-build(?P<release>[0-9]+))?(\.pkg|\.tar\.gz)"),
            InstallerInfo(
                "GT6-REPO-RPM",
                'repo/rpm',
                [ "artifacts/*.noarch.rpm" ],
                r"(?P<name>[a-z-]*[a-z]-(?P<version>[0-9.]*[0-9]))-(?P<release>[0-9]+).*\.noarch\.rpm$",
                link="../globus-toolkit-repo-latest.noarch.rpm"),
            InstallerInfo(
                'GT6-REPO-DEB',
                "repo/deb",
                [ "artifacts/*_all.deb" ],
                r"(?P<name>[a-z-]*[a-z]_(?P<version>[0-9.]+))-(?P<release>[0-9]+)",
                link="../globus-toolkit-repo_latest_all.deb"),
            InstallerInfo(
                "GT6-INSTALLER",
                'src',
                ["packaging/artifacts/*.tar.gz"],
                r"(?P<name>[a-z_]*)-(?P<version>([0-9.]|beta|rc)*)\.tar\.gz"),
            InstallerInfo(
                "GT6-BINARIES-WIN32-CYGWIN",
                'windows',
                ["artifacts/*-i686-pc-cygwin-*.zip"],
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>i686-pc-cygwin))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "GT6-BINARIES-WIN64-CYGWIN",
                "windows",
                ["artifacts/*-x86_64-pc-cygwin-*.zip"],
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>x86_64-pc-cygwin))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "GT6-BINARIES-WIN32-MINGW",
                "windows",
                ["artifacts/*-i686-w64-mingw32-*.zip"],
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>i686-w64-mingw32))-Build-(?P<release>[0-9]+)"),
            InstallerInfo(
                "GT6-BINARIES-WIN64-MINGW",
                "windows",
                ["artifacts/*-x86_64-w64-mingw32-*.zip"],
                r"(?P<name>[a-z_]*-(?P<version>([0-9.]|beta|rc)*)-(?P<arch>x86_64-w64-mingw32))-Build-(?P<release>[0-9]+)")
        ]
        super(Cache, self).__init__(cache)
        self.sync()
        self.release = Release(self.cache_dir, 'installers', self.installers)

    def sync(self):
        for i in self.installers:
            i_cache_dir = os.path.join(self.cache_dir, i.subdir)
            if not os.path.exists(i_cache_dir):
                os.makedirs(i_cache_dir, 0o775)
                if repo.gid is not None:
                    dirname = i_cache_dir
                    while dirname != self.cache_dir:
                        os.chown(dirname, repo.uid, repo.gid)
                        os.chmod(dirname, 0o2775)
                        dirname = os.path.dirname(dirname)
            urls = repo.artifacts.list_artifacts(i.name, i.artifact_patterns)
            for u in urls:
                repo.artifacts.fetch_url(u, i_cache_dir)

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.installer.Manager object manages the packages in a cache and
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

        release = {"release": Release(
                    os.path.join(root, 'installers'),
                    "release",
                    cache.installers)}
        super(Manager, self).__init__(cache, release)

    def get_release(self, releasename):
        if releasename == 'cache':
            return self.cache.release
        else:
            return self.releases['release']

    def __str__(self):
        return " ".join(["Installers Manager [", ",".join(self.releases.keys()), "]"])

# vim: filetype=python:
