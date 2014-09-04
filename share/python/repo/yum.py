"""
Package to manage the Globus Toolkit Yum repositories
"""

import xml.etree.ElementTree as ET
import fnmatch
import gzip
import os
import os.path
import shutil
import repo
import repo.package

"""
Current set of yum repositories as of 2014-08-27
"""
default_yum_repos = {
            "el/5": ["i386", "SRPMS", "x86_64"],
            "el/6": ["i386", "SRPMS", "x86_64"],
            "el/7": ["SRPMS", "x86_64"],
            "fedora/19":  ["i386", "SRPMS", "x86_64"],
            "fedora/20":  ["i386", "SRPMS", "x86_64"]
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
    def __get_primary_path(repodir):
        repomd_path = os.path.join(repodir, "repodata", "repomd.xml")
        f = file(repomd_path, "r")
        tree = ET.fromstring(f.read())
        f.close()
        for data in tree:
            if data.tag == Repository.datatag:
                if data.attrib['type'] == 'primary':
                    location = data.find(Repository.repolocationtag)
                    return os.path.join(repodir, location.attrib['href'])


    @staticmethod
    def __parse_primary_xml(xmlpath):
        f = gzip.open(xmlpath,'rb')
        tree = ET.fromstring(f.read())
        f.close()

        return tree

    def __init__(self, repo_top, osname, arch):
        super(Repository, self).__init__()
        self.repo_path = os.path.join(repo_top, osname, arch)
        self.dirty = False
        self.os = osname

        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path, 0775)

        try:
            primary_path = Repository.__get_primary_path(self.repo_path)
        except:
            self.__createrepo()
            primary_path = Repository.__get_primary_path(self.repo_path)

        xml = Repository.__parse_primary_xml(primary_path)

        for package in xml:
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
            if not packagename in self.packages:
                self.packages[packagename] = []
            versionkey = (packagever, packagerel)
            self.packages[packagename].append(repo.package.Metadata(
                packagename,
                packagever,
                packagerel,
                packagepath,
                packagearch,
                pkgsource,
                self.os))
        for package in self.packages:
            self.packages[package].sort()

    def add_package(self, package, update_metadata=False):
        dest_rpm_path = os.path.join(self.repo_path,
            os.path.basename(package.path))
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
            self.__createrepo()
        else:
            self.dirty = True
        return new_package
        
    def update_metadata(self, force=False):
        if force or self.dirty:
            self.__createrepo()
            self.dirty = False

    def __createrepo(self):
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
        if package.arch in [ 'noarch', 'i686', 'i386' ]:
            return [self.repositories[package.os][arch]
                    for arch in self.get_architectures(package.os) 
                    if arch != 'src']
        else:
            return [self.repositories[package.os][package.arch]]

class Cache(repo.Cache):
    """
    Cache
    =====
    The repo.yum.Cache object manages a mirror of the builds.globus.org
    "rpm" subdirectory (except for sles). This mirror contains a
    repo.yum.Release object that contains info about all of the operating
    system versions and their architectures in the cache. 
    """
    def __init__(self, cache):
        """
        Constructor
        -----------
        Creates a new repo.yum.Cache object, syncing from the builds.globus.org
        repository directory and creating metadata based on the packages
        available.

        Parameters
        ----------
        *self*:
            New cache object.
        *cache*:
            Path of the cache root.
        """
        super(Cache, self).__init__(cache, "rpm", ["sles"])
        self.sync()

        cached_rpm_root = os.path.join(cache, 'rpm')
        cached_repos = {}
        # Create a cached_repos dict that is similar in form to
        # default_yum_repos, but contains the repos present in the cache
        for osname in os.listdir(cached_rpm_root):
            if osname == "sles":
                continue
            osdir = os.path.join(cached_rpm_root, osname)
            for osver in os.listdir(osdir):
                this_repo_topdir = os.path.join(osdir, osver)
                this_repo_subdirs = []
                this_repo_name = os.path.join(osname, osver)
                for repodir in os.listdir(this_repo_topdir):
                    if os.path.isdir(os.path.join(this_repo_topdir, repodir)):
                        this_repo_subdirs.append(repodir)
                cached_repos[this_repo_name] = this_repo_subdirs

        # Create a Release from the cached repos
        self.release = Release("cache", cached_rpm_root, cached_repos)

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.yum.Manager object manages the packages in a cache and release
    tree. New packages from the cache (including new repositories) can be
    promoted to any of the released package trees via methods in this class
    """
    def __init__(self, cache_root=repo.default_cache, root=repo.default_root,
            releases=repo.default_releases, use_cache=True):
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
        """
        cache = Cache(cache_root) if use_cache else None
        yum_releases = {}
        for release in releases:
            print "Initializing", release
            yum_releases[release] = Release(
                    release,
                    os.path.join(root, release, 'rpm'),
                    { osname: cache.get_architectures(osname)
                            for osname in cache.get_operating_systems()})
        super(Manager, self).__init__(cache, yum_releases)

