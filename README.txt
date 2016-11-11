Globus Release Tools
====================

Overview
--------
The tools in this package are used to manage software releases for the
Globus Toolkit project, so that packages, installers, and repositories
can be transferred from our build system to the Globus web server.

Repository Management Tools
---------------------------
The tools in this release are *repo-sync-unstable*, *repo-s3-sync*,
*repo-promote-package*, *repo-list-packages*, and *repo-link-duplicates*.

The *repo-sync-unstable* tool caches packages from the +builds.globus.org+
repository and publishes them as part of the 'unstable' release of the Globus
Toolkit.

The *repo-s3-sync* tool takes cached package data, which may already be
published at another location, and uploads it to
+s3://downloads.globus.org/data/toolkit/+.

The *repo-promote-package* tool copies a package and its metadata between
selected releases, from one of 'unstable' -> 'testing' -> 'stable'.

The *repo-list-packages* program will list the contents of a release,
optionally filtering by a base package name.

The *repo-link-duplicates* tool replaces identical binary package files
with hard links.

The *repo-sync-unstable*, *repo-s3-sync*, and *repo-promote-package* tools have
a '-dryrun' option that will not copy packages, though directory trees and
metadata might be updated depending on the state of the release directories.

The tools use a set of python packages in +share/python/repo+ to manage
the different directory layouts and repository metadata management commands
for the debian, yum, zypper, source tarball, and installer repository
types.

NOTE: these package tools can run for multiple minutes depending on the size of
the package repository metadata, as they potentially run *reprepro* and/or
*createrepo* multiple times and parse the (sometimes compressed) repository
metadata.

NOTE: You'll need access to the repository private key in order to publish
debian or zypper packages as those repositories are signed.

Examples
--------
To update the 'unstable' repository with all new packages:

    % globus-sync-unstable

To promote the 'globus-xio' package from *unstable* to *testing*:

    % globus-promote-package -f unstable -t testing -p globus-xio

To publish a new set of installers:

    % globus-sync-unstable -i

To publish the cached `foo/` directory to S3:

    % repo-s3-sync --subdir foo/

Links
-----
For further information about the tools, see the
link:share/doc/repo-promote-package.html[repo-promote-package],
link:share/doc/repo-sync-unstable.html[repo-sync-unstable],
link:share/doc/repo-s3-sync.html[repo-s3-sync],
link:share/doc/repo-list-packages.html[repo-list-packages],
and
link:share/doc/repo-link-duplicates.html[repo-link-duplicates],
documentation.
