"""
Package to manage the Globus Toolkit Debian repositories
"""

import fnmatch
import os
import os.path
import re
import repo
import repo.package

default_codenames = [ 'squeeze', 'wheezy', 'lucid', 'precise', 'trusty' ]
default_arches = ['i386', 'amd64', 'source']
codename_re = re.compile(r"Codename:\s*(\S+)")
distro_re = re.compile(r"Distribution:\s*(\S+)")

class Repository(repo.Repository):
    """
    repo.deb.Repository 
    ===================
    This class contains the debian package repository metadata. It extends the
    repo.Repository class with support code to parse debian package metadata
    from changes files
    """

    changes_fields = ["Format", "Date", "Source", "Binary", "Architecture", "Version", "Distribution", "Urgency", "Maintainer", "Changed-By", "Description", "Changes", "Checksums-Sha1", "Checksums-Sha256", "Files"]

    changes_re = re.compile(r"-----BEGIN PGP SIGNED MESSAGE-----\nHash: .*\n\n(" + "|".join([ r"%s: (?P<%s>.*\n(( .+\n)*\n)?)" % ( field, field.replace("-", "") )  for field in changes_fields])+")*")

    def __init__(self, repo_path, codename, arch):
        super(Repository, self).__init__()
        self.repo_path = repo_path
        self.codename = codename
        self.dirty = False

        distdir = os.path.join(repo_path, "dists", codename)

        if not os.path.exists(distdir):
            self.update_metadata(True);

        matchstring = "*.%s_*.changes" % (codename)
        for dirpath, dirnames, filenames in os.walk(
                    os.path.join(self.repo_path, "pool")):
            for filename in filenames:
                if fnmatch.fnmatch(filename, matchstring):
                    pkgfile = os.path.join(dirpath, filename)
                    f = file(pkgfile, "r")
                    changes = Repository.changes_re.match(f.read())
                    if changes is not None:
                        pkg = None
                        version, release = changes.group('Version').strip().\
                                split("-", 1)
                        path = pkgfile
                        src = changes.group('Source').strip() + "_" + \
                                changes.group("Version")

                        if arch in changes.group('Architecture').strip().split(" "):
                            if arch == 'source':
                                name = changes.group('Source').strip()
                                pkg = repo.package.Metadata(
                                        name,
                                        version,
                                        release,
                                        pkgfile,
                                        'src',
                                        src,
                                        self.codename)
                            else:
                                name = changes.group('Binary').strip()
                                pkg = repo.package.Metadata(
                                        name,
                                        version,
                                        release,
                                        pkgfile,
                                        arch,
                                        src,
                                        self.codename)
                            if pkg.name not in self.packages:
                                self.packages[pkg.name] = []
                            self.packages[pkg.name].append(pkg)
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
        pkg_dest_dir = os.path.join(self.repo_path, "pool", "contrib",
                pkg_basename[0], package.source_name[:package.source_name.find("_")])
        dest_path = os.path.join(pkg_dest_dir, pkg_basename)
        if not os.path.exists(pkg_dest_dir):
            os.makedirs(pkg_dest_dir, 0775)
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
                os.makedirs(confdir, 0755)

            Repository._update_deb_distributions_conf(distributions_file, self.codename)
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
        distribution_data="""
Label: Globus Toolkit
Codename: %s
Architectures: amd64 i386 source
Components: contrib
DebIndices: Packages Release . .gz .bz2
DscIndices: Sources Release .gz .bz2
Contents: . .gz .bz2
SignWith: yes
Tracking: minimal includechanges
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
    def __init__(self, name, topdir, codenames=default_codenames, arches=default_arches):
        r = {}
        for codename in codenames:
            r[codename] = {}
            for arch in arches:
                if arch == 'source':
                    r[codename]['src'] = Repository(topdir, codename, arch)
                else:
                    r[codename][arch] = Repository(topdir, codename, arch)
        super(Release, self).__init__(name, r)

class Cache(repo.Cache):
    """
    Cache
    =====
    The repo.deb.Cache object manages a mirror of the builds.globus.org
    "deb" subdirectory. This mirror contains a repo.deb.Release object that
    contains info about all of the operating system versions and their
    architectures in the cache. 
    """
    def __init__(self, cache):
        """
        Constructor
        -----------
        Creates a new repo.deb.Cache object, syncing from the builds.globus.org
        repository directory and creating metadata based on the packages
        available.

        Parameters
        ----------
        *self*:
            New cache object.
        *cache*:
            Path of the cache root.
        """
        super(Cache, self).__init__(cache, "deb")
        self.sync()

        cached_deb_conf = os.path.join(self.cache, "conf/distributions")

        codenames = []
        if os.path.exists(cached_deb_conf):
            f = file(cached_deb_conf, "r")
            for l in f:
                m = codename_re.match(l)
                if m is not None:
                    codename = m.group(1)
                    codenames.append(codename)
        self.release = Release("cache", self.cache, codenames)

class Manager(repo.Manager):
    """
    Package Manager
    ===============
    The repo.deb.Manager object manages the packages in a cache and release
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
        deb_releases = {}
        for release in releases:
            print "Initializing", release
            deb_releases[release] = Release(
                    release,
                    os.path.join(root, release, 'deb'),
                    cache.get_operating_systems())
        super(Manager, self).__init__(cache, deb_releases)
