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
Package to manage the Globus Toolkit Yum repositories
"""

import xml.etree.ElementTree as ET
import gzip
import os
import os.path
import re
import shutil
import sqlite3
from subprocess import Popen, PIPE

import repo
import repo.package

"""
Current set of yum repositories as of 2014-08-27
"""
default_yum_repos = {
            "el/5": ["i386", "SRPMS", "x86_64"],
            "el/6": ["i386", "SRPMS", "x86_64"],
            "el/7": ["SRPMS", "x86_64"],
            "fedora/24":  ["i386", "SRPMS", "x86_64"],
            "fedora/25":  ["i386", "SRPMS", "x86_64"]
}


class Repository(repo.Repository):
    """
    Repository class
    ===================
    This class contains the metadata for all of the packages in a yum
    repository directory, as well as some methods to select packages
    matching names and versions, add them to the repository, and regenerate
    the repository metadata.
    """
    pkgtag = '{http://linux.duke.edu/metadata/common}package'
    nametag = '{http://linux.duke.edu/metadata/common}name'
    versiontag = '{http://linux.duke.edu/metadata/common}version'
    locationtag = '{http://linux.duke.edu/metadata/common}location'
    archtag = '{http://linux.duke.edu/metadata/common}arch'
    sourcerpmtag = "{http://linux.duke.edu/metadata/rpm}sourcerpm"
    formattag = "{http://linux.duke.edu/metadata/common}format"
    repolocationtag = '{http://linux.duke.edu/metadata/repo}location'
    datatag = "{http://linux.duke.edu/metadata/repo}data"

    @staticmethod
    def __get_primary_path(repodir, xml):
        repomd_path = os.path.join(repodir, "repodata", "repomd.xml")
        f = file(repomd_path, "r")
        tree = ET.fromstring(f.read())
        f.close()
        for data in tree:
            if data.tag == Repository.datatag:
                if xml is True and data.attrib['type'] == 'primary':
                    location = data.find(Repository.repolocationtag)
                    return os.path.join(repodir, location.attrib['href'])
                elif xml is False and data.attrib['type'] == 'primary_db':
                    location = data.find(Repository.repolocationtag)
                    return os.path.join(repodir, location.attrib['href'])

    def __parse_primary_xml(self, xmlpath):
        f = gzip.open(xmlpath, 'rb')
        tree = ET.fromstring(f.read())
        f.close()
        packages = dict()

        for package in tree:
            packagename = package.find(Repository.nametag).text
            v = package.find(Repository.versiontag)
            packagever = v.attrib['ver']
            packagerel = v.attrib['rel']
            packagehref = package.find(Repository.locationtag).attrib['href']
            packagepath = os.path.join(self.repo_path, packagehref)
            packagearch = package.find(Repository.archtag).text
            formatel = package.find(Repository.formattag)
            pkgsourceel = formatel.find(Repository.sourcerpmtag)
            pkgsource = None
            if pkgsourceel is not None:
                pkgsource = pkgsourceel.text
            if pkgsource is None or pkgsource == '':
                pkgsource = "-".join([packagename, packagever, packagerel]) \
                        + ".src.rpm"
            if packagename not in packages:
                packages[packagename] = []
            packages[packagename].append(repo.package.Metadata(
                packagename,
                packagever,
                packagerel,
                packagepath,
                packagearch,
                pkgsource,
                self.os))

        return packages

    def __parse_primary_db(self, dbpath):
        packages = dict()
        dbpath_uncompressed = dbpath.replace(".bz2", "")
        if (not os.path.exists(dbpath_uncompressed)) or \
                os.path.getmtime(dbpath_uncompressed) <= \
                os.path.getmtime(dbpath):
            os.system(
                'bzip2 -dc < "%s" > "%s"' % (dbpath, dbpath_uncompressed))
        conn = sqlite3.connect(dbpath_uncompressed)
        cur = conn.cursor()
        c = cur.execute("""
            select name, version, release, location_href, arch,
                   rpm_sourcerpm from packages""")
        for name, ver, rel, href, arch, source in c:
            packagename = str(name)
            packagever = ver
            packagerel = rel
            packagehref = href
            packagepath = os.path.join(self.repo_path, packagehref)
            packagearch = arch
            pkgsource = None
            if source is not None:
                pkgsource = source
            if source is None or source == '':
                pkgsource = "-".join([packagename, packagever, packagerel]) \
                        + ".src.rpm"
            if packagename not in packages:
                packages[packagename] = []
            packages[packagename].append(repo.package.Metadata(
                packagename,
                packagever,
                packagerel,
                packagepath,
                packagearch,
                pkgsource,
                self.os))
        conn.close()

        return packages

    def __init__(self, repo_top, osname, arch, xml=False):
        super(Repository, self).__init__()
        self.repo_path = os.path.join(repo_top, osname, arch)
        self.dirty = False
        self.os = osname

        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path, 0o775)
            if repo.gid is not None:
                dirname = self.repo_path
                while dirname != repo_top:
                    os.chown(dirname, repo.uid, repo.gid)
                    os.chmod(dirname, 0o2775)
                    dirname = os.path.dirname(dirname)

        out, err = Popen(
            ['createrepo', '--version'],
            stdout=PIPE).communicate()
        matches = re.search(r"(\d+).(\d+).(\d+)", out)
        if int(matches.group(1)) >= 1 or int(matches.group(2)) >= 9:
            self.use_sha_arg = True
        else:
            self.use_sha_arg = False

        try:
            primary_path = Repository.__get_primary_path(self.repo_path, xml)
        except:
            self.__createrepo()
            primary_path = Repository.__get_primary_path(self.repo_path, xml)

        if xml:
            self.packages = self.__parse_primary_xml(primary_path)
        else:
            self.packages = self.__parse_primary_db(primary_path)
        for package in self.packages:
            self.packages[package].sort()

    def add_package(self, package, update_metadata=False):
        dest_rpm_path = os.path.join(
            self.repo_path, os.path.basename(package.path))
        if not os.path.exists(dest_rpm_path):
            shutil.copy(package.path, dest_rpm_path)
        if package.name not in self.packages:
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
            self.__createrepo()
        else:
            self.dirty = True
        return new_package

    def update_metadata(self, force=False):
        if force or self.dirty:
            self.__createrepo()
            self.dirty = False

    def __createrepo(self):
        if '/el/5' in self.repo_path and self.use_sha_arg:
            os.system('createrepo -d "%s" -s sha' % (self.repo_path))
        else:
            os.system('createrepo -d "%s"' % (self.repo_path))


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
            r[osname] = {}
            for arch in repos[osname]:
                if arch == 'SRPMS' or arch == 'src':
                    r[osname]['src'] = Repository(topdir, osname, 'SRPMS')
                else:
                    r[osname][arch] = Repository(topdir, osname, arch)
        super(Release, self).__init__(name, r)

    def repositories_for_package(self, package):
        if package.arch in ['noarch', 'i686', 'i386']:
            if package.os in self.repositories:
                return [self.repositories[package.os][arch]
                        for arch in self.get_architectures(package.os)
                        if arch != 'src']
        else:
            if package.os in self.repositories:
                return [self.repositories[package.os][package.arch]]
        return []


class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.yum.Manager object manages the packages in a release
    tree. New packages can be promoted to any of the released package trees via
    methods in this class
    """
    def __init__(
            self, root=repo.default_root,
            releases=repo.default_releases, os_names=None,
            exclude_os_names=None):
        """
        Constructor
        -----------
        Create a new Manager object.

        Parameters
        ----------
        *root*::
            Root of the release trees
        *releases*::
            Names of the releases within the release trees
        *os_names*::
            (Optional) List of operating system name/version (e.g. el/7) to
            manage. If None, then all yum-based OSes will be managed.
        *exclude_os_names*::
            (Optional) List of operating system name/version (e.g. el/7) to
            skip. If None, then all yum-based OSes will be managed. This is
            evaluated after os_names
        """
        oses = dict()
        oses = Manager.find_operating_systems(root, releases[0])
        if os_names is not None:
            new_oses = dict()
            for osname in oses:
                if osname in os_names:
                    new_oses[osname] = oses[osname]
            oses = new_oses
        if exclude_os_names is not None:
            new_oses = dict()
            for osname in oses:
                if osname not in exclude_os_names:
                    new_oses[osname] = oses[osname]
            oses = new_oses
        yum_releases = {}
        for release in releases:
            yum_releases[release] = Release(
                    release,
                    os.path.join(root, release, 'rpm'),
                    oses)
        super(Manager, self).__init__(yum_releases)

    @staticmethod
    def find_operating_systems(root, release):
        oses = {}
        release_os_dir = os.path.join(root, release, "rpm")

        if os.path.exists(release_os_dir):
            for osname in os.listdir(release_os_dir):
                if osname == 'sles':
                    continue
                osnamedir = os.path.join(release_os_dir, osname)
                for osver in os.listdir(osnamedir):
                    osnamever = os.path.join(osname, osver)
                    osnameverdir = os.path.join(release_os_dir, osnamever)
                    if os.path.isdir(osnameverdir):
                        oses[osnamever] = []
                        for arch in os.listdir(osnameverdir):
                            oses[osnamever].append(arch)
        return oses

    def __str__(self):
        return " ".join(["Yum Manager [", ",".join(self.releases.keys()), "]"])

# vim: filetype=python:
