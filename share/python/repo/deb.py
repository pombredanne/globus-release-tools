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
Package to manage the Globus Toolkit Debian repositories
"""

import gzip
import os
import os.path
import re
import repo
import repo.package

default_codenames = ['squeeze', 'wheezy', 'lucid', 'precise', 'trusty']
default_arches = ['i386', 'amd64', 'source']
codename_re = re.compile(r"Codename:\s*(\S+)")
distro_re = re.compile(r"Distribution:\s*(\S+)")


class Repository(repo.Repository):
    """
    repo.deb.Repository
    ===================
    This class contains the debian package repository metadata. It extends the
    repo.Repository class with support code to parse debian package metadata
    from the release's Sources.gz file
    """

    def __init__(self, repo_path, codename, arch):
        super(Repository, self).__init__()
        self.repo_path = repo_path
        self.codename = codename
        self.dirty = False

        pooldir = os.path.join(repo_path, "pool", "contrib")
        distdir = os.path.join(repo_path, "dists", codename)

        if not os.path.exists(distdir):
            self.update_metadata(True)

        packages_file = os.path.join(
            distdir, "contrib", "binary-%s" % (arch), "Packages.gz")

        if arch == 'source' or arch == 'all':
            packages_file = os.path.join(
                distdir, "contrib", arch, "Sources.gz")

        pf = gzip.open(packages_file)

        name = None
        source = None
        version = None
        release = None
        filename = None
        pkgarch = None

        for line in pf:
            line = line.rstrip()

            if line.startswith("Package: "):
                name = line.split(": ", 1)[1]
            elif line.startswith("Source: "):
                source = line.split(": ", 1)[1]
            elif line.startswith("Version: "):
                version, release = line.strip().split(": ")[1].split("-", 1)
            elif line.startswith("Filename: "):
                filename = line.split(": ", 1)[1]
            elif line.startswith("Architecture: "):
                pkgarch = line.split(": ", 1)[1]
            elif line == "":
                if name not in self.packages:
                    self.packages[name] = []

                if arch == 'source':
                    src = name + "_" + version
                    suffix = "source"
                    filename = "%s-%s_%s.changes" % (src, release, suffix)
                    poolsubdir = filename[0:1]
                    if filename.startswith("lib"):
                        poolsubdir = filename[0:4]

                    filepath = os.path.join(
                            pooldir,
                            poolsubdir,
                            filename.split("_", 1)[0],
                            filename)
                    self.packages[name].append(
                            repo.package.Metadata(
                                name,
                                version,
                                release,
                                filepath,
                                'src',
                                src,
                                self.codename))
                    if pkgarch == 'all':
                        suffix = "all"
                        filename = "%s-%s_%s.changes" % (src, release, suffix)
                        poolsubdir = filename[0:1]
                        if filename.startswith("lib"):
                            poolsubdir = filename[0:4]
                        filepath = os.path.join(
                                pooldir,
                                poolsubdir,
                                filename.split("_", 1)[0],
                                filename)
                        self.packages[name].append(
                                repo.package.Metadata(
                                    name,
                                    version,
                                    release,
                                    filepath,
                                    pkgarch,
                                    src,
                                    self.codename))
                else:
                    if source is None:
                        source = name
                    src = source + "_" + version

                    archcands = [
                        pkgarch, "all+"+pkgarch,
                        "source+" + pkgarch, "source+all+" + pkgarch]
                    filepath = ""
                    for archcand in archcands:
                        changesfile = "%s-%s_%s.changes" % (
                            src, release, archcand)
                        poolsubdir = changesfile[0:1]
                        if changesfile.startswith("lib"):
                            poolsubdir = changesfile[0:4]
                        testfile = os.path.join(
                                pooldir,
                                poolsubdir,
                                changesfile.split("_", 1)[0],
                                changesfile)
                        if os.path.exists(testfile):
                            filepath = testfile
                            break
                    if filepath != "":
                        self.packages[name].append(
                                repo.package.Metadata(
                                    name,
                                    version,
                                    release,
                                    filepath,
                                    arch,
                                    src,
                                    self.codename))

                name = None
                source = None
                version = None
                release = None
                filename = None
                pkgarch = None

        for n in self.packages:
            self.packages[n].sort()

    def add_package(self, package, update_metadata=False):
        """
        Add *package* to this repository, optionally regenerating the
        metadata. If update_metadata is equal to False (the default), then
        the repository will be marked as dirty, but the update will not be
        done.

        Parameters
        ----------
        *package*::
            The package to add to this repository
        *update_metadata*::
            Flag indicating whether to update the repository metadata
            immediately or not.
        """
        pkg_basename = os.path.basename(package.path)
        pkg_dest_dir = os.path.join(
            self.repo_path, "pool", "contrib",
            pkg_basename[0],
            package.source_name[:package.source_name.find("_")])
        dest_path = os.path.join(pkg_dest_dir, pkg_basename)
        if not os.path.exists(pkg_dest_dir):
            os.makedirs(pkg_dest_dir)
            if repo.gid is not None:
                dirname = pkg_dest_dir
                while dirname != self.repo_path:
                    os.chown(dirname, repo.uid, repo.gid)
                    os.chmod(dirname, 0o2775)
                    dirname = os.path.dirname(dirname)
        if not os.path.exists(dest_path):
            oscmd = 'reprepro --silent -b %(repodir)s --export=never include %(codename)s %(pkgpath)s' % {
                        'repodir': self.repo_path,
                        'codename': self.codename,
                        'pkgpath': package.path
                    }
            os.system(oscmd)
            if update_metadata:
                self.update_metadata()
            else:
                self.dirty = True

        # Create a new repo.package.Metadata with the new path
        new_package = repo.package.Metadata(
                package.name,
                package.version.strversion, package.version.release,
                dest_path,
                package.arch,
                package.source_name,
                self.codename)

        if package.name not in self.packages:
            self.packages[package.name] = []
        self.packages[package.name].append(new_package)
        self.packages[package.name].sort()
        if update_metadata:
            self.update_metadata()
        else:
            self.dirty = True
        return new_package

    def update_metadata(self, force):
        """
        Update the package metadata from the changes files in a repository
        """
        if self.dirty or force:
            confdir = os.path.join(self.repo_path, "conf")
            distributions_file = os.path.join(confdir, "distributions")

            if not os.path.exists(confdir):
                os.makedirs(confdir, 0o755)

            Repository._update_deb_distributions_conf(
                distributions_file, self.codename)
            oscmd = 'reprepro --silent -b "%s" export' % (self.repo_path)
            os.system(oscmd)
            self.dirty = False

    @staticmethod
    def _update_deb_distributions_conf(conf_file_path, distro):
        """
        Update the +conf/distributions+ file at the specified path to contain
        information about the named distribution if it is not present yet.

        Parameters
        ----------
        *conf_file_path*::
            Path to the +conf/distributions+ to modify (str)
        *distro*::
            Distribution codename to add to 'conf_file_path' (str)
        """
        distribution_data = """
Label: Globus Toolkit
Codename: %s
Architectures: amd64 i386 source
Components: contrib
DebIndices: Packages Release . .gz .bz2
DscIndices: Sources Release .gz .bz2
Contents: . .gz .bz2
SignWith: yes
Tracking: keep includechanges
Description: Globus Toolkit Packages
""" % (distro)
        f = None
        if not os.path.exists(conf_file_path):
            f = file(conf_file_path, "w+")
        else:
            f = file(conf_file_path, "r+")

        for l in f:
            cnm = codename_re.match(l)
            if cnm is not None and cnm.group(1) == distro:
                f.close()
                return

        f.write(distribution_data)
        f.close()


class Release(repo.Release):
    def __init__(
            self, name, topdir, codenames=default_codenames,
            arches=default_arches):
        r = {}
        for codename in codenames:
            r[codename] = {}
            for arch in arches:
                if arch == 'source':
                    r[codename]['src'] = Repository(topdir, codename, arch)
                else:
                    r[codename][arch] = Repository(topdir, codename, arch)
        super(Release, self).__init__(name, r)

    def repositories_for_package(self, package):
        """
        Returns a list of repositories where the given package would belong.
        By default, its a list containing the repository that matches the
        package's os and arch, but subclasses can override this
        """
        repoarch = package.arch
        if package.arch == 'all':
            repoarch = 'src'
        if package.os in self.repositories:
            return [self.repositories[package.os][repoarch]]
        else:
            return []


class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.deb.Manager object manages the packages in a release
    tree. New packages from the repositories can be
    promoted to any of the released package trees via methods in this class
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
            (Optional) List of operating system codenames (e.g. wheezy) to
            manage. If None, then all debian-based OSes will be managed.
        *exclude_os_names*::
            (Optional) List of operating system codenames (e.g. wheezy) to
            skip. If None, then all debian-based OSes will be managed. This is
            evaluated after os_names
        """
        deb_releases = {}

        codenames = Manager.find_codenames(root, releases[0])

        if os_names is not None:
            codenames = [cn for cn in codenames if cn in os_names]
        if exclude_os_names is not None:
            codenames = [cn for cn in codenames if cn not in exclude_os_names]
        for release in releases:
            deb_releases[release] = Release(
                    release,
                    os.path.join(root, release, 'deb'),
                    codenames)
        super(Manager, self).__init__(deb_releases)

    @staticmethod
    def find_codenames(root, release):
        codenames = []
        release_dists_dir = os.path.join(root, release, "deb", "dists")

        if os.path.exists(release_dists_dir):
            for codename in os.listdir(release_dists_dir):
                if os.path.isdir(os.path.join(
                            release_dists_dir, codename)):
                    codenames.append(codename)
        return codenames

    def __str__(self):
        return " ".join(["Deb Manager [", ",".join(self.releases.keys()), "]"])

# vim: filetype=python:
