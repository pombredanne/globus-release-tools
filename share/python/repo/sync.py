#! /usr/bin/python

import fnmatch
import os
import os.path
import re
from repo.tree import default_root
import repo.tree.deb
import repo.tree.yum
import repo.tree.zypper

default_cache = os.path.join(os.getenv("HOME"), 'repo-sync')

distro_re = re.compile(r"Distribution:\s*(\S*)")
codenames_re = re.compile(r"^Codename:\s*(\S*)")

def update_deb_dest(root=default_root, cache=default_cache):
    builds_distros = os.path.join(cache, "deb", "conf", "distributions")
    builds_distro_file = file(builds_distros, "r")
    dest_debdir = os.path.join(root, "unstable", "deb")
    codenames = []

    # Make sure that all distros in the cache are in the dest repository
    for line in builds_distro_file:
        matches = codenames_re.match(line)
        if matches is not None:
            codenames.append(matches.group(1))
    repo.tree.deb.repo_tree_create_deb(root, distros=" ".join(codenames))

    # Make sure every changes file in the source is in the dest repository
    for dirpath, _, filenames in \
            os.walk(os.path.join(cache, "deb", "pool")):
        for fn in filenames:
            if fnmatch.fnmatch(fn, "*.changes"):
                print fn
                abspath = os.path.join(dirpath, fn)
                relpath = abspath[len(cache)+1:]
                destpath = os.path.join(root, "unstable", relpath)
                if not os.path.exists(destpath):
                    changes_file = file(abspath, "r")
                    for line in changes_file:
                        cnm = distro_re.match(line)
                        if cnm is not None:
                            cn = cnm.group(1)
                            rc = os.system(
                                'reprepro -b "%s" --export=never %s %s' %
                                (dest_debdir, cn, abspath))
                            if rc == 0:
                                any_changed = True
                            break
    if any_changed:
        os.system('reprepro -b "%s" export' % (dest_debdir))

def update_yum_dest(root=default_root, cache=default_cache):
    yum_repos = {}
    # Determine which architecture subdirectories are present for each
    # OSNAME/VERSION
    for osname in os.listdir(os.path.join(cache, "rpm")):
        if osname == 'sles':
            # Skip SuSE zypper repository
            continue
        for osver in os.listdir(os.path.join(cache, 'rpm', osname)):
            osnamever = os.path.join(osname, osver)
            yum_repos[osnamever] = []

            for archdir in os.listdir(os.path.join(cache, 'rpm', osnamever)):
                yum_repos[osnamever].append(archdir)

    print yum_repos
    repo.tree.yum.repo_tree_create_yum(root, yum_repos=yum_repos)
    # Copy the packages from the repos here to the destination
    for repo in yum_repos.keys():
        for archrepo in yum_repos[repo]:
            src_repodir = os.path.join(cache, "rpm", archrepo)
            dest_repodir = os.path.join(root, "unstable", "rpm", archrepo)
            changes = False
            print "Searching " + src_repodir
            for cached_rpm in os.listdir(src_repodir):
                if fnmatch.fnmatch(cached_rpm, "*.rpm"):
                    cached_rpm_path = os.path.join(src_repodir, cached_rpm)
                    new_rpm_path = os.path.join(dest_repodir, cached_rpm)
                    if not os.path.exists(new_rpm_path):
                        try:
                            os.link(cached_rpm, new_rpm_path)
                        except:
                            shutil.copy(cached_rpm, new_rpm_path)
                        changes = True
            if changes:
                os.system('createrepo -d "%s"' % (dest_repodir))


def sync_tree(root=default_root, cache=default_cache):
    os.system('rsync -a --ignore-errors -e ssh builds.globus.org:/var/www/html/repo6/ "%s"' % (cache))
    for dirpath, _, filenames in os.walk(os.path.join(cache, "packages")):
        for fn in filenames:
            if fnmatch.fnmatch(fn, "*.changes") or fnmatch.fnmatch(fn, "*.rpm"):
                destfn = os.path.join(root, "packages", fn)
                if not os.path.exists(destfn):
                    srcfn = os.path.join(cache, "packages", fn)
                    shutil.copy(srcfn, destfn)
                if not(fnmatch.fnmatch(fn, "*.md5") or
                       fnmatch.fnmatch(fn, "*.sha1") or
                       fnmatch.fnmatch(fn, "*.sha512")):
                    for ext in ['.md5', '.sha1', '.sha512']:
                        srchash = srcfn + ext
                        if os.path.exists(srcfn + ext):
                            desthash = destfn + ext
                            shutil.copy(srchash, desthash)
