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
Repository Management
"""

import atexit
import fnmatch
import hashlib
import os
import os.path
import re
import signal
from subprocess import Popen, PIPE

default_root = "/mcs/globus.org/ftppub/gt6"
default_api_root = "/mcs/globus.org/api"
default_releases = ["unstable", "testing", "stable"]
default_cache = os.path.join(os.getenv("HOME"), "repo-cache")

public_key = """-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.5 (GNU/Linux)

mQGiBE0PXQkRBAC12PfwFzMyTKAvCp3AEbzdwwDyEaBHYmd1+Dv+q5c48fEZQrzA
PuZ75BnG8BRIo3ZSYJll9Xf5v8A0M6F35msBBdjUpI+PHZvSQ+yru6U3w9XCsmO9
jSGWM1XAw/hcDWOsETOsjJ56AqIKndOXtG2jeOMFD0MwJus9paDcv5pPkwCgk3Fk
I+GdLaZf0O6vGUtq2Fo2EgkD/14AQ4SyUufwztQeLwlYXyihdUoIVBl4wm4fndJb
TuzTlp3V/oabM8t+V92ftbqlAesFb1FdFQ9NeUEY0VIODR2OTsmEfLUSMK/kRfXM
4FatObXpEp58EydZb3oz/vwASEk1Nno5OW2noGZL3sCk+3j65MstI2q4kMvNSvl+
JEjUBACgNv/mDrn0UjWBuzxOuZrh1r2rBdsjIHx31o/vBF5YLfQhErZQTm6cfpRK
W32Nm18btrqgxxHFAMb4wxnVxAxdM3zLSAaiqvi33z2wHReh5TfaVKpJBj7LpMSI
hwu50iovsBjE7HiusJQBWBtk8Bqp4g9ic2sPV0caEMCUXU5R9bQjR2xvYnVzIFRv
b2xraXQgPHN1cHBvcnRAZ2xvYnVzLm9yZz6IYAQTEQIAIAUCTQ9dCQIbAwYLCQgH
AwIEFQIIAwQWAgMBAh4BAheAAAoJEESufsL68kNlb6IAoIemS8dr65xCkA4GQzgJ
ngXwZgtvAKCOKs5Ork6HiNKIrWRGMLvA7iktBbkCDQRND10SEAgA37cRQGj/QNcc
OjyBrL6e2wPT7UtpXBEHzfjhtmT8+VC+PSbKRxVfawLBtrfzSAAwsmye3c+XK/VB
Pa06vSSmezeyNau+XtEVLwrwQwO/kM6wgNtb7zYyI67Y6XEPP+ZlqpZ0W14cTZBD
3SXWuu6zqjdtUnJCg/j/j0zH5TZa40aCfisERxNCQeoePk2gmMTJDJF0ASM3Nhys
QIP9qpCA+eOJnKmMeEgDCW9j2mYO4tp9lCSbi15HAb41HKN6xypNWk+EHKyu9n50
88UocRHXLZFujzNTGIokWAcoC0D3qpVQehtAVgt1VPrE6MxFPek8ZN4Ho++92KB7
F6E0OsfF6wADBggAnNPguzYAIztF/EzZANUU/7Eon9zJaD4Lf/mnhB3bMuGvenY0
7HSBAXbUxVXs7uX3S6u9PZ9dytl2Fqh8w47TNcC0ACKLRnhxTJ92LLakzAGVGtNz
2W9l+YJaZ6qIQR9FmYpCyIWp6Vm47yOARThrMtnwUhb53g5ZfxgzpHNUDN/7utTy
3sUaMRiijecmSVhDFbrz7ryY2Btlcr7ZrBo0ODHohDkZVn2UrzE6qg9g5np03zYe
5OUM5Lt5GYZJSKZO81aJ5+9DlkiAev3BFEeCsSOwjrqLZpsr0olbIfeHCi8pvjOJ
SCfx4Qs/hI34ykaUn3AgbgxqT0mSKfMasg2bIIhJBBgRAgAJBQJND10SAhsMAAoJ
EESufsL68kNlBuAAnRRI5jFAvyjtQaoQpVqSL4/O45D7AJ9WrW/vxTzN0OyZyUU6
8T0dJyXArA==
=r6rU
-----END PGP PUBLIC KEY BLOCK-----
"""

uid = os.getuid()
gid = None

def _digest_file(filename, force=False):
    """
    Compute the md5, sha1, sha512 hashes of a file and write them to disk.

    Parameters
    ----------
    *filename*::
        Name of the file to compute the hash of (str)
    *force*::
        Overwrite existing hash file (bool [False])
    """
    if fnmatch.fnmatch(filename, "*.md5") or \
            fnmatch.fnmatch(filename, "*.sha1") or \
            fnmatch.fnmatch(filename, "*.sha512"):
        return

    for h in ['md5', 'sha1', 'sha512']:
        hashname = filename + "." + h
        if force or not os.path.exists(hashname):
            digester = hashlib.new(h)
            f = file(filename, "r")
            digester.update(f.read())
            f.close()
            f = file(hashname, "w")
            f.write("%s  %s\n" %
                (digester.hexdigest(), filename.split(os.sep)[-1]))
            f.close()

class Repository(object):
    """
    Repository class
    ===================
    This class contains the generic package management features for the various
    metadata types associated with different repository systems. It contains
    algorithms for matching packages and selecting ones to copy into another
    repository based on version matches. This is subclassed to implement the
    actual metdata parsing for various metadata formats.
    """
    def __init__(self):
        self.packages = {}

    def get_packages(self, name=None, arch=None, version=None, source=None,
            newest_only=False):
        """
        Construct a list of packages that match the optional parameters. If
        source is an Metadata object, match packages that have that package
        as the source package. Otherwise, filter the package list based on
        the name if not None, further filtering on version and arch if they
        are not None. If newest_only is True, only return the highest versions
        of the packages which match
        """
        package_candidates = []
        if source is not None:
            source_name = source.source_name
            return [(package)
                for package_list in self.packages
                for package in self.packages[package_list]
                if package.source_name == source.source_name and \
                    package.version == source.version]
        elif name is not None:
            if name in self.packages:
                if version is not None:
                    package_candidates = [(pkg) for pkg in self.packages[name] 
                            if pkg.version == version]
                else:
                    package_candidates = self.packages[name]
            if arch is not None:
                package_candidates = [(p)
                        for p in package_candidates if p.arch==arch]
            if newest_only and len(package_candidates) > 0:
                newv = package_candidates[-1].version
                return [p for p in package_candidates if p.version == newv]
            elif newest_only:
                return []
            else:
                return package_candidates
        else:
            package_candidates = []
            for n in self.packages:
                package_candidates.extend(
                        self.get_packages(name=n, arch=arch,
                        newest_only=newest_only))
            return package_candidates

    def is_newer(self, pkg):
        """
        Check to see if *pkg* is newer than any versions of the same package
        name within this repository. Returns 'True' if it is, 'False'
        otherwise.

        Parameters
        ----------
        *self*:
            This Repository object
        *pkg*:
            Package metadata to compare against the versions in *self*.

        Returns
        -------
        Boolean
        """
        matches = self.get_packages(pkg.name, arch=pkg.arch, newest_only=True)

        return matches == [] or pkg > matches[-1]

    def __contains__(self, pkg):
        """
        Check to see if pkg is included in this Repository
        """
        return len(self.get_packages(name=pkg.name, arch=pkg.arch,
            version=pkg.version, newest_only=True)) > 0

    def __iter__(self):
        """
        Iterate through the packages in this repository
        """
        return self.packages.keys()

class Release(object):
    """
    A Release is a top-level collection of +repo.Repository+ objects for
    particular package stability ('unstable', 'testing', 'stable') or
    cache for each operating system.
    """
    def __init__(self, name, repositories):
        self.name = name
        self.repositories = repositories

    def get_packages(self, name=None, os=None, version=None, arch=None,
            source=None, newest_only=False):
        return [p
                for repository in self.repositories_for_os_arch(os, arch)
                for p in repository.get_packages(
                    name=name, arch=arch, version=version, source=source, 
                    newest_only=newest_only) ]

    def is_newer(self, package):
        for repository in self.repositories_for_package(package):
            if repository.is_newer(package):
                return True
        return False

    def add_package(self, package, update_metadata=False):
        return [
            repository.add_package(package, update_metadata)
            for repository in self.repositories_for_package(package)]

    def update_metadata(self, osname=None, arch=None, force=False):
        for repository in self.repositories_for_os_arch(osname, arch):
            repository.update_metadata(force)

    def repositories_for_os_arch(self, osname, arch):
        if osname is not None:
            if arch is not None:
                return [self.repositories[osname][arch]]
            else:
                return [self.repositories[osname][arch]
                    for arch in self.repositories[osname]]
        else:
            return [self.repositories[osname][arch]
                for osname in self.repositories
                for arch in self.repositories[osname]]
        
    def repositories_for_package(self, package):
        """
        Returns a list of repositories where the given package would belong.
        By default, its a list containing the repository that matches the
        package's os and arch, but subclasses can override this
        """
        if package.os in self.repositories:
            return [self.repositories[package.os][package.arch]]
        else:
            return []

    def get_operating_systems(self):
        return self.repositories.keys()

    def get_architectures(self, osname):
        return self.repositories[osname].keys()

    def __contains__(self, pkg):
        return len(self.get_packages(name=package.name, os=package.os,
                version=package.version, arch=package.arch)) > 0

class Cache(object):
    def __init__(self, cache_dir=default_cache, cache_subdir=None, excludes=[]):
        self._cache_dir = cache_dir
        self._cache_subdir = cache_subdir
        self._release = None
        self._excludes = excludes

    @property
    def release(self):
        return self._release

    @release.setter
    def release(self, value):
        if self._release is not None:
            raise ValueError("Cannot change release value")
        self._release = value

    @property
    def cache(self):
        return os.path.join(self._cache_dir, self._cache_subdir)

    def sync(self):
        source = "builds.globus.org:/var/www/html/repo6/"
        if os.uname()[1] == "builds.globus.org":
            if self._cache_dir == "/var/www/html/repo6":
                return
            else:
                source = "/var/www/html/repo6/"
        dest = self._cache_dir
        if self._cache_subdir is not None:
            source += self._cache_subdir + "/"
            dest += "/" + self._cache_subdir
        if not os.path.exists(dest):
            os.makedirs(dest)
            dirname = dest
            if gid is not None:
                while dirname != self._cache_dir:
                    os.chown(dirname, uid, gid)
                    os.chmod(dirname, 0o2775)
                    dirname = os.path.dirname(dirname)
        excludes = " ".join([("--exclude=" + ex) for ex in self._excludes])

        if not ":" in source:
            os.system('rsync -a --no-p --no-g --chmod=Du=rwx,Dg=rwxs,Do=rx --chmod=Fu=rw,Fg=rw,Fo=r %s "%s" "%s"' % (excludes, source, dest))
        else:
            os.system('rsync -a --no-p --no-g --chmod=Du=rwx,Dg=rwxs,Do=rx --chmod=Fu=rw,Fg=rw,Fo=r %s -e ssh "%s" "%s"' % (excludes, source, dest))

    def get_operating_systems(self):
        return self._release.get_operating_systems()

    def get_architectures(self, osname):
        return self._release.get_architectures(osname)

class Manager(object):
    def __init__(self, cache, releases):
        self.cache = cache
        self.releases = releases

    def get_release(self, releasename):
        if releasename == 'cache':
            return self.cache.release
        else:
            return self.releases[releasename]

    def package_name(self, name):
        return name.replace("_", "-") if name is not None else None

    def promote_packages(self, from_release=None, 
            to_release="unstable", os=None, name=None, version=None,
            dryrun=False, exclude_package_names=None):
        """
        Find new packages in the *from_release* (or from the Manager's *cache* 
        if from_release is None), that are not in *to_release* and
        copy them there and update the distro metadata. The packages to promote
        can be limited by specifying the package *name*, *version*, and
        particular *os* to update.

        Parameters
        ----------
        *from_release*::
            The name of a release in this Manager object to copy new packages
            from. If this is None, then the cache is used.
        *to_release*::
            The name of a release in this Manager object
            to copy new packages into.
        *os*::
            Optional operating system indicator (either version or codename)
            to restrict the package promotion to.
        *name*::
            Optional name of the packages to copy. If this is not present, all
            packages that have a newer source version in *from_release* than
            *to_release* are copied.
        *version*::
            Optional version of the packages to copy. This is only used if the
            *name* option is used to additionally limit the packages to copy.
        *dryrun*::
            (Optional) Boolean whether to prepare to promote the packages or
            just compute which packages are eligible for promotion.
        *exclude_package_names*::
            (Optional) List of regular expressions matching packages to 
            exclude from the promotion list.
        Returns
        -------
            This function returns a list of packages that were promoted 
            (or would have been if dryrun=False)
        """
        if from_release is None:
            from_release = self.cache.release
        else:
            from_release = self.get_release(from_release)

        # Find source packages in the from_release that are newer versions than
        # those in the to_release
        src_candidates = [src_info for src_info in from_release.get_packages(
                    name=self.package_name(name), os=os, version=version,
                    newest_only=True)]

        result = []
        seen = {}
        to_release_object = self.get_release(to_release)
        # For each package found above, find source and binaries in
        # from_release and copy them over if they are not in to_release
        for src in src_candidates:
            if src.name not in seen:
                seen[src.name] = True
                for package in from_release.get_packages(source=src):
                    skip = False
                    if exclude_package_names is not None:
                        for exclude in exclude_package_names:
                            if re.match(exclude, package.name) is not None:
                                skip = True
                                break
                    if (not skip) and to_release_object.is_newer(package):
                        if not dryrun:
                            to_release_object.add_package(package,
                                    update_metadata=False)
                        result.append(package)

        if not dryrun:
            to_release_object.update_metadata()
        return result

def setup_gpg_agent():
    if os.getenv("GPG_AGENT_INFO") is None:
        proc = Popen(["/usr/bin/gpg-agent", "--daemon", "--default-cache-ttl", "14400", "--max-cache-ttl", "14400"], stdout=PIPE)
        (procout, procerr) = proc.communicate()
        var, val = procout.split(";")[0].split("=")
        os.putenv(var, val)
        procpid = int(val.split(":")[1])
        atexit.register(lambda x: os.kill(x, signal.SIGTERM), procpid)

# vim: filetype=python:
