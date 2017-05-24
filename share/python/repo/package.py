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

import repo
import repo.versioncompare


class Version(object):
    """
    Version class to allow comparison of package versions, including
    release versions and wildcards for releases
    """
    def __init__(self, version, release=None):
        """
        Initialize with a version string and a release string. If the release
        string is None, acts as a wildcard that matches all releases of that
        version
        """
        self.strversion = version
        self.version = repo.versioncompare.version2float(version)
        self.release = release
        if self.release is None:
            self.release = "*"

    def __lt__(self, other):
        return (
            (self.version < other.version)
            or (
                (self.version == other.version)
                and repo.versioncompare.ReleaseGreater(
                    other.release, self.release)))

    def __le__(self, other):
        return (self < other) or (self == other)

    def __eq__(self, other):
        return (
            (self.version == other.version)
            and ((self.release == other.release)
                 or (self.release == '*') or (other.release == '*')))

    def __ne__(self, other):
        return self.version != other.version or self.release != other.release

    def __gt__(self, other):
        return (
            (self.version > other.version)
            or ((self.version == other.version)
                and repo.versioncompare.ReleaseGreater(
                    self.release, other.release)))

    def __ge__(self, other):
        return (self > other) or (self == other)

    def __str__(self):
        if self.release == "*":
            return "%s" % self.strversion
        else:
            return "%s-%s" % (self.strversion, self.release)


class Metadata(object):
    def __init__(self, name, version, release, path, arch, source, os):
        self.name = name
        self.version = Version(version, release)
        self.path = path
        self.arch = arch
        self.source_name = source
        self.os = os

    def __cmp__(self, other):
        c = cmp(self.name, other.name)
        if c == 0:
            return cmp(self.version, other.version)
        else:
            return c

    def __str__(self):
        return "Name: %s\nVersion: %s\nRelease: %s\n" \
            + "Path: %s\nArch: %s\nSource: %s\nOS: %s\n" % (
                self.name,
                self.version.strversion,
                self.version.release,
                self.path,
                self.arch,
                self.source_name,
                self.os)

# vim: filetype=python:
