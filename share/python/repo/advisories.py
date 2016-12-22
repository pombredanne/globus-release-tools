#! /usr/bin/python

import json

class Advisories(object):
    def __init__(self, initial_advisories_path=None, format="txt"):
        self.advisories = []
        self.added_packages = {}

        if initial_advisories_path is not None:
            f = open(initial_advisories_path, "r")
            if format == 'json':
                self.advisories = json.load(f)
            else:
                for line in f:
                    self.parse_line(line)
            f.close()


    def parse_line(self, line):
        line = line.strip()
        if line.startswith("#") or line == "":
            return
        d, p, v, f, desc = line.split(";", 4)
        pkgs = p.split(",")
        flags = f.split(" ")
        desc = desc.replace("\"", "\\\"")
        obj = {
            "date": d,
            "packages": pkgs,
            "toolkit_version": v,
            "flags": flags,
            "description": desc,
        }
        self.advisories.append(obj)

    def add_advisories(self, packages):
        for p in packages:
            if p.arch == 'src' and p.name not in self.added_packages and \
                    ".src.rpm" in p.path:
                pfd = os.popen('rpm -q -p "%s" --changelog' % p.path)
                dateline = pfd.readline()
                changelog = ""
                for l in pfd:
                    if l.startswith("*"):
                        break
                    else:
                        if l.startswith("- "):
                            l = l.replace("- ", "", 1)
                        changelog += l
                pfd.close()
                changelog = changelog.strip().replace("\n","<br />")
                pfd = os.popen('rpm -q -p "%s" -l' % p.path)
                files = []
                for l in pfd:
                    if ".tar.gz" in l:
                        l = l.replace(".tar.gz", "").strip()
                        matches = re.match(l, r"([a-z-]+)(-[0-9.]+)")
                        if matches is not None:
                            l = matches.group(1).replace("-", "_") + \
                                matches.group(2)
                        files.append(l.replace(".tar.gz", "").strip())
                pfd.close()
                if len(files) > 0:
                    obj = {
                        "date": today,
                        "packages": ",".join(files),
                        "toolkit_version": "6.0",
                        "flags": "bug",
                        "description": changelog
                    }
                    self.advisories.append(obj)
                    self.added_packages[p.name] = obj

    def to_json(self):
        return "advisories = " + json.dumps(self.advisories) + ";\n"

    def new_to_text(self):
        s = ""
        for k in self.added_packages:
            a = self.added_packages[k]
            date = a['date'];
            pkgs = " ".join(a['packages'])
            toolkit_version = a['toolkit_version']
            flags = " ".join(a['flags'])
            desc = a['description'].replace("\\\"", "\"")
            s += "%s;%s;%s;%s;%s\n" % \
                (date, pkgs, toolkit_version, flags, desc)
        return s

    def to_text(self):
        s = "";
        for a in self.advisories:
            date = a['date'];
            pkgs = " ".join(a['packages'])
            toolkit_version = a['toolkit_version']
            flags = " ".join(a['flags'])
            desc = a['description'].replace("\\\"", "\"")
            s += "%s;%s;%s;%s;%s\n" % \
                (date, pkgs, toolkit_version, flags, desc)
        return s
