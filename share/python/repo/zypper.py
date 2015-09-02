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
Package to manage Globus Toolkit Zypper repositories
"""

from __future__ import print_function

import datetime
import fnmatch
import hashlib
import os
import os.path
import re
import repo
import repo.package
import shutil

"""
List of supported Zypper-based Linux distributions
"""
default_zypper_distros = ["sles/11"]

class Repository(repo.Repository):
    """
    Repository class
    ================
    This class contains the zypper package repository metadata for a particular
    operating system version. 
    """
    grp_restring = r"=Grp:[\t ]*(?P<group>.*)\n"
    lic_restring = r"=Lic:[\t ]*(?P<license>.*)\n"
    loc_restring = r"=Loc:[\t ]*(\d+)[\t ]+(?P<location>[^ \t\n]*).*\n"
    pkg_restring = r"=Pkg:[\t ]*(?P<pkgname>[^ \t]*)[\t ]+(?P<pkgversion>[^ \t]*)[ \t]+(?P<pkgrelease>[^ \t]*)[ \t]+(?P<arch>.+)\n"
    shr_restring = r"=Shr:[\t ].*\n"
    siz_restring = r"=Siz:[\t ]*(?P<size>\d+).*\n"
    src_restring = r"=Src:[\t ]*(?P<srcname>\S+)[\t ]+(?P<srcver>\S+)[\t ]+(?P<srcrel>\S+)[\t ]+(?P<srcarch>.+)\n"
    tim_restring = r"=Tim:[\t ]*(?P<time>\d+)\n"
    ver_restring = r"=Ver:[\t ]*(?P<repover>[0-9.]+)\n"
    con_restring = r"\+Con:[\t ]*(?P<conflicts>(\n(?!-Con:).*)*)\n-Con:\n"
    obs_restring = r"\+Obs:[\t ]*(?P<obsoletes>(\n(?!-Obs:).*)*)\n-Obs:\n"
    prq_restring = r"\+Prq:[\t ]*(?P<prq>(\n(?!-Prq:).*)*)\n-Prq:\n"
    prv_restring = r"\+Prv:[\t ]*(?P<prv>(\n(?!-Prv:).*)*)\n-Prv:\n"
    req_restring = r"\+Req:[\t ]*(?P<requires>(\n(?!-Req:).*)*)\n-Req:\n"
    dashd_restring = r"##[\t ]+-d.*\n"
    start_restring = r"##-+\n"

    parse_re = re.compile(ver_restring + "|" + start_restring + "(" + "|".join([grp_restring, lic_restring, loc_restring, pkg_restring, shr_restring, siz_restring, src_restring, tim_restring, con_restring, obs_restring, prq_restring, prv_restring, req_restring, dashd_restring]) + ")+", re.M)

    def __init__(self, repo_path, osname):
        super(Repository, self).__init__()
        self.repo_path = os.path.join(repo_path, osname)
        self.os = osname
        self.dirty = False
        self.packages_path = os.path.join(
                self.repo_path, "setup", "descr", "packages")

        if not os.path.exists(self.packages_path):
            self.update_metadata(force=True);

        f = file(self.packages_path, "r")
        metadata = f.read()

        datasize = len(metadata)
        offset = 0
        while offset < datasize:
            m = Repository.parse_re.match(metadata[offset:])
            if m is None:
                raise Exception("Parsing error", metadata[offset:offset+200])
            offset += len(m.group(0))
            if m is not None and m.group('pkgname') is not None:
                srcref = None
                if m.group('arch') == 'src':
                    srcref = "-".join([m.group('pkgname'),
                            m.group('pkgversion'),
                            m.group('pkgrelease')])
                else:
                    srcref = "-".join([
                                m.group('srcname'),
                                m.group('srcver'),
                                m.group('srcrel')])
                pkg = repo.package.Metadata(
                        m.group('pkgname'),
                        m.group('pkgversion'),
                        m.group('pkgrelease'),
                        os.path.join(self.repo_path, "RPMS", m.group('arch'),
                                m.group('location')),
                        m.group('arch'),
                        srcref,
                        self.os)
                if pkg.name not in self.packages:
                    self.packages[pkg.name] = []
                self.packages[pkg.name].append(pkg)
        for p in self.packages:
            self.packages[p].sort()

    def add_package(self, package, update_metadata=False):
        dest_rpm_path = os.path.join(self.repo_path,
            'RPMS', package.arch, os.path.basename(package.path))
        if not os.path.exists(dest_rpm_path):
            shutil.copy(package.path, dest_rpm_path)
        if not package.name in self.packages:
            self.packages[package.name] = []

        # Create a new repo.package.Metadata with the new path
        new_package = repo.package.Metadata(
                package.name,
                package.version.strversion, package.version.release,
                dest_rpm_path,
                package.arch,
                package.source_name,
                self.os)

        self.packages[package.name].append(new_package)
        self.packages[package.name].sort()
        if update_metadata:
            self.update_metadata()
        else:
            self.dirty = True
        return new_package
        
    def update_metadata(self, force=False):
        """
        Update the zypper repository metadata for the packages in the specified
        repository.
        """
        if not(force or self.dirty):
            return

        self.dirty = False
        distro_repodir = self.repo_path

        print("Updating metadata in ", distro_repodir)
        dirs = ["media.1", "RPMS/noarch", "RPMS/src", "RPMS/x86_64" ]
        for dirname in [(os.path.join(distro_repodir, x)) for x in dirs]:
            if not os.path.exists(dirname):
                os.makedirs(dirname, 0o775)
                if repo.gid is not None:
                    chgrp_dirname = dirname
                    while chgrp_dirname != distro_repodir:
                        os.chown(chgrp_dirname, repo.uid, repo.gid)
                        os.chmod(chgrp_dirname, 0o2775)
                        chgrp_dirname = os.path.dirname(chgrp_dirname)
        media_path = os.path.join(distro_repodir, "media.1", "media")

        if not os.path.exists(media_path):
            media_file = file(media_path, "w")
            media_file.write("Globus Support\n%s\n1\n" %
                    (datetime.datetime.now().strftime("%Y%m%d%H%M%S")))
            media_file.close()
        content_key_path = os.path.join(distro_repodir, "content.key")
        if not os.path.exists(content_key_path):
            content_key_file = file(content_key_path, "w")
            content_key_file.write(repo.public_key)
            content_key_file.close()

        content_path = os.path.join(distro_repodir, "content")
        content_file = file(content_path, "w")
        content_file.write("""PRODUCT Globus Toolkit
VERSION 6
LABEL Globus Toolkit (SUSE LINUX)
VENDOR Globus Support
ARCH.x86_64 x86_64 noarch
DEFAULTBASE x86_64
DESCRDIR setup/descr
DATADIR RPMS
""")
        directory_yast_path = os.path.join(distro_repodir, "directory.yast")
        directory_yast_file = file(directory_yast_path, "w")
        for entry in os.listdir(distro_repodir):
            directory_yast_file.write(entry + "\n")
        directory_yast_file.close()

        rpms_path = os.path.join(distro_repodir, "RPMS")
        os.system('cd "%s"; create_package_descr -d "RPMS"' % (distro_repodir))

        descr_dir = os.path.join(distro_repodir, "setup", "descr")

        for entry in os.listdir(descr_dir):
            entry_file = file(os.path.join(descr_dir, entry), "r")
            entry_sha1 = hashlib.sha1()
            entry_sha1.update(entry_file.read())
            content_file.write("META SHA1 %s  %s\n" % (
                entry_sha1.hexdigest(), entry))

        key_sha1 = hashlib.sha1()
        key_sha1.update(repo.public_key)
        content_file.write("KEY SHA1 %s  %s\n" % (
                key_sha1.hexdigest(), "content.key"))
        content_file.close()

        content_asc = os.path.join(distro_repodir, "content.asc")
        if os.path.exists(content_asc):
            os.remove(content_asc)
        if os.getenv("GPG_AGENT_INFO") is not None:
            os.system("cd \"%s\"; gpg --batch --use-agent -ab content" %
                (distro_repodir))
        else:
            os.system("cd \"%s\"; gpg -ab content" % (distro_repodir))


class Release(repo.Release):
    """
    Release
    =======
    Each Release contains a collection of repositories for different
    architectures for a particular operating system release.
    """
    def __init__(self, name, topdir, repos):
        r = {}
        for osname in repos:
            r[osname] = Repository(topdir, osname)
        super(Release, self).__init__(name, r)

    def repositories_for_os_arch(self, osname, arch):
        if osname is not None:
            return [self.repositories[osname]]
        else:
            return [self.repositories[repo] for repo in self.repositories]

    def repositories_for_package(self, package):
        return [self.repositories[package.os]]

class Cache(repo.Cache):
    """
    Cache
    =====
    The repo.zypper.Cache object manages a mirror of the builds.globus.org
    "rpm/sles" subdirectory. This mirror contains a repo.zypper.Distro() for
    each operating system/version in the cache. These Distro objects can be used
    to promote packages to the various trees in a DistroPoint
    """
    def __init__(self, cache):
        self.cache_dir = cache
        super(Cache, self).__init__(cache, "rpm", ['el', 'fedora'])
        self.sync()

        osname = 'sles'
        osdir = os.path.join(cache, 'rpm', osname)
        cached_repos = []

        for osver in os.listdir(osdir):
            this_repo_topdir = os.path.join(osdir, osver)
            if os.path.isdir(this_repo_topdir) and not \
                    os.path.islink(this_repo_topdir):
                this_repo_name = os.path.join(osname, osver)
                cached_repos.append(this_repo_name)
        self.release = Release("cache", os.path.join(cache, "rpm"),
                cached_repos)

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.zypper.Manager object manages the packages in a cache and release
    tree. New packages from the cache (including new repositories) can be
    promoted to any of the released package trees via methods in this class
    """
    def __init__(self, cache_root=repo.default_cache, root=repo.default_root,
            releases=repo.default_releases, use_cache=True, os_names=None,
            exclude_os_names=None):
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
        *releases*::
            Names of the releases within the release trees
        *use_cache*::
            (Optional) Parse packages in the cache
        *os_names*::
            (Optional) List of operating system name/version (e.g. sles/11) to
            manage. If None, then all zypper-based OSes will be managed.
        *exclude_os_names*::
            (Optional) List of operating system name/version (e.g. sles/11) to
            skip. If None, then all zypper-based OSes will be managed. This is
            evaluated after os_names
        """
        if use_cache:
            cache = Cache(cache_root) if use_cache else None
            oses = [osname for osname in cache.get_operating_systems()]
        else:
            cache = None
            oses = Manager.find_operating_systems(root, releases[0])

        if os_names is not None:
            oses = [osname for osname in oses if osname in os_names]
        if exclude_os_names is not None:
            oses = [osname for osname in oses if osname not in exclude_os_names]
        zypper_releases = {}
        for release in releases:
            zypper_releases[release] = Release(
                    release,
                    os.path.join(root, release, 'rpm'),
                    oses)
        super(Manager, self).__init__(cache, zypper_releases)

    @staticmethod
    def find_operating_systems(root, release):
        oses = []

        sles_top_dir = os.path.join(root, release, "rpm", "sles")

        for osver in os.listdir(sles_top_dir):
            osnameverdir = os.path.join(sles_top_dir, osver)
            if os.path.isdir(osnameverdir) and not os.path.islink(osnameverdir):
                osnamever = os.path.join("sles", osver)
                oses.append(osnamever)
    
        return oses

    def __str__(self):
        return " ".join(["Zypper Manager [", ",".join(self.releases.keys()), "]"])
# vim: filetype=python:
