#! /usr/bin/env python
#
# Copyright (c) 2011 Jason Ish
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

import sys
import getopt
import tempfile
import subprocess
import os.path
import shutil

import idstools.net
import idstools.rule

from idstools.ruleman import util
from idstools.ruleman import matchers
from idstools.ruleman import core

class BaseCommand(object):
    pass

class CommandLineError(Exception):
    pass

class RemoteSubCommandIgnoreFile(BaseCommand):

    usage = """
usage: ignore-file <remote-name> <filename>
   or: ignore-file --remove <remote-name> <filename>
"""

    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.remotes = config.get_remotes()

        self.opt_remove = False

    def run(self):
        opts, self.args = getopt.getopt(self.args, "", ["remove"])
        for o, a in opts:
            if o in ["--remove"]:
                self.opt_remove = True

        try:
            name = self.args.pop(0)
            filename = self.args.pop(0)
        except:
            raise CommandLineError("not enough arguments")

        if name not in self.remotes:
            print("error: remote %s does not exist" % (name), file=sys.stderr)
            return 1
        remote = self.remotes[name]
        if "ignore-files" not in remote:
            remote["ignore-files"] = []
        if self.opt_remove:
            if filename in remote["ignore-files"]:
                remote["ignore-files"].remove(filename)
        else:
            remote["ignore-files"].append(filename)
            remote["ignore-files"] = list(set(remote["ignore-files"]))

class RemoteCommand(object):

    usage = """
usage: %(progname)s remote [-h]
   or: %(progname)s remote add <name> <url>
   or: %(progname)s remote remove <name>
   or: %(progname)s remote disable <name>
   or: %(progname)s remote enable <name>
   or: %(progname)s remote set <name> <parameter> <value>
   or: %(progname)s remote ignore-file <remote-name> <filename>
   or: %(progname)s remote ignore-file --remove <remote-name> <filename>
""" % {"progname": sys.argv[0]}

    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.remotes = config.get_remotes()

        self.opt_remove = False

        self.subcommands = {
            "add": self.add,
            "remove": self.remove,
            "enable": self.enable,
            "disable": self.disable,
            "set": self.set_parameter,

            "ignore-file": RemoteSubCommandIgnoreFile,

            # Aliases.
            "rm": self.remove,
        }

    def run(self):
        try:
            self.opts, self.args = getopt.getopt(self.args, "h", ["remove"])
        except getopt.GetoptError as err:
            print("error: %s" % (err), file=sys.stderr)
            print(self.usage, file=sys.stderr)
            return 1
        for o, a in self.opts:
            if o == "-h":
                print(self.usage)
                return 0
            elif o in ["--remove"]:
                self.opt_remove = True

        if not self.args:
            return self.list()

        command = self.args.pop(0)

        if command in self.subcommands:
            try:
                if issubclass(self.subcommands[command], BaseCommand):
                    return self.subcommands[command](
                        self.config, self.args).run()
                else:
                    return self.subcommands[command]()
            except (getopt.GetoptError, CommandLineError) as err:
                print("error: %s" % (err), file=sys.stderr)
                print(self.subcommands[command].usage, file=sys.stderr)
        else:
            print("error: unknown subcommand: %s" % (command), file=sys.stderr)

    def set_parameter(self):
        name = self.args.pop(0)
        key = self.args.pop(0)
        val = self.args.pop(0)

        if name not in self.remotes:
            print("error: remote %s does not exist." % (name), file=sys.stderr)

        self.remotes[name][key] = val

    def list(self):
        for remote in self.remotes:
            print("%s: %s" % (remote, self.remotes[remote]))

    def add(self):
        name = self.args.pop(0)
        url = self.args.pop(0)

        if name in self.remotes:
            print("error: remote %s already exists" % (name), file=sys.stderr)
            return 1

        self.remotes[name] = {
            "name": name,
            "url": url,
        }

    add.usage = "usage: add <name> <url>"

    def remove(self):
        name = self.args.pop(0)
        if name not in self.remotes:
            print("error: remote %s does not exist" % (name), file=sys.stderr)
            return 1
        del(self.remotes[name])
    
    remove.usage = "usage: remove <name>"

    def enable(self):
        name = self.args.pop(0)
        if name not in self.remotes:
            print("error: remote %s does not exist" % (name), file=sys.stderr)
        self.remotes[name]["enabled"] = True

    enable.usage = "usage: enable <name>"

    def disable(self):
        name = self.args.pop(0)
        if name == "*":
            for remote in self.remotes.values():
                remote["enabled"] = False
        else:
            if name not in self.remotes:
                print("error: remote %s does not exist" % (name),
                      file=sys.stderr)
                self.remotes[name]["enabled"] = False

    disable.usage = "usage: disable <name>"

class FetchCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

        self.remotes = self.config.get_remotes()

    def run(self):

        fetched = []

        for remote in self.remotes.values():
            if self.args and name not in self.args:
                continue
            if not remote["enabled"]:
                continue
            fileobj = self.fetch(remote)
            if fileobj:
                fetched.append({"remote": remote, "fileobj": fileobj})

        print("Fetched:", [item["remote"]["name"] for item in fetched])

        for entry in fetched:
            print("Extracting %s." % entry["remote"]["name"])
            dest = "remotes/%s" % entry["remote"]["name"]
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            util.extract_archive(entry["fileobj"].name, dest)
            open("%s/checksum" % (dest), "w").write(
                util.md5_filename(entry["fileobj"].name))

        # for fileobj in fetched:
        #     util.extract_archive(fileobj.name, ".")

    def fetch(self, remote):
        print("Fetching %s : %s" % (
            remote["name"], util.get_filename_from_url(remote["url"])))
        fileobj = tempfile.NamedTemporaryFile(
            suffix=util.get_filename_from_url(remote["url"]))
        try:
            length, info = idstools.net.get(
                remote["url"], fileobj, self.progress_hook)
            # A print to print a new line.
            print("")
            return fileobj
        except idstools.net.HTTPError as err:
            # HTTP errors.
            print(" error: %s %s" % (err.code, err.msg))
            body = err.read().strip()
            for line in body.split("\n"):
                print("  | %s" % (line))
        except Exception as err:
            print(" error: %s" % (err))

    def progress_hook(self, content_length, bytes_read):
        percent = int((bytes_read / float(content_length)) * 100)
        buf = " %3d%% - %-30s" % (
            percent, "%d/%d" % (bytes_read, content_length))
        sys.stdout.write(buf)
        sys.stdout.flush()
        sys.stdout.write("\b" * 38)

    def extract(self, filename):
        util.extract_archive(filename, ".")

class SyncCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

    def run(self):
        git = subprocess.Popen("git diff", shell=True, stdout=subprocess.PIPE)
        diff = git.communicate()[0]
        for line in diff.split("\n"):
            if line.startswith(" "):
                continue
            elif line.startswith("---") or line.startswith("+++"):
                continue
            elif line.startswith("+"):
                print(line)
            elif line.startswith("-"):
                print(line)

class DisableRuleCommand(object):

    usage = """
usage: %(progname)s disable [-h]
   or: %(progname)s disable [-r] <gid:sid>
   or: %(progname)s disable [-r] re:<regex>

    -r,--remove      Removes the rule matcher from the disabled list.
""" % {"progname": sys.argv[0]}

    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.opt_remove = False

    def run(self):
        try:
            opts, self.args = getopt.getopt(
                self.args, 
                "hr",
                ["help", "remove"])
        except getopt.GetoptError as err:
            print("error: %s" % (err), file=sys.stderr)
            print(usage)
            return 1
        for o, a in opts:
            if o == "-h":
                print(self.usage)
                return 0
            elif o in ["-r", "--remove"]:
                self.opt_remove = True

        if not self.args:
            return self.list()
        elif self.opt_remove:
            return self.remove()

        descriptor = self.args[0]
        message = " ".join(self.args[1:])

        matcher = matchers.parse(self.args[0])
        if not matcher:
            print("error: invalid rule matcher: %s" % (descriptor))
            return 1

        disabled_rules = self.config["disabled-rules"]

        exists = filter(lambda m: m["matcher"] == str(matcher), disabled_rules)
        if exists:
            print("error: rules matching %s are already disabled." % (
                str(matcher)))
            print(" - comment: %s" % (exists[0]["comment"]))
            return 1

        disabled_rules.append({
            "matcher": str(matcher),
            "comment": message,
        })

    def remove(self):
        """Remove the matcher for the disabled list."""
        self.config["disabled-rules"] = filter(
            lambda m: m["matcher"] != self.args[0],
            self.config["disabled-rules"])

    def list(self):
        for disabled in self.config["disabled-rules"]:
            print("%s: %s" % (disabled["matcher"], disabled["comment"]))

class SearchCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

    def run(self):
        if not self.args:
            print("error: nothing to search for.")
            return 1

        matcher = matchers.ReRuleMatcher.parse("re:" + self.args[0])

        directories = ["rules", "so_rules", "preproc_rules"]

        for directory in [d for d in directories if os.path.exists(d)]:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in \
                    [fn for fn in filenames if fn.endswith(".rules")]:
                    path = os.path.join(dirpath, filename)
                    rules = idstools.rule.parse_fileobj(open(path))
                    for rule in rules:
                        if matcher.match(rule):
                            print("%s %s" % (
                                path, self.render_brief(rule)))

    def render_brief(self, rule):
        return "%s[%d:%d:%d] %s" % (
            "" if rule.enabled else "# ",
            rule.gid, rule.sid, rule.rev,
            rule.msg)

class ApplyCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

    def run(self):

        rulesets = []

        remotes = self.config.get_remotes()
        for remote in remotes.values():
            if remote["enabled"]:
                print("Loading rules from %s" % (remote["name"]))
                ruleset = core.Ruleset(remote)
                ruleset.load_rules()
                print("- Loaded %d rules." % (len(ruleset.rules)))
                rulesets.append(ruleset)

        rules = {}

        for ruleset in rulesets:
            for rule_id, rule in ruleset.rules.items():
                if rule.id in rules:
                    print("Duplicate rule found:", rule.id)
                else:
                    rules[rule.id] = rule

        with open("snort.rules", "wb") as fileobj:
            for rule in rules.values():
                fileobj.write(str(rule) + "\n")

commands = {
    "fetch": FetchCommand,
    "remote": RemoteCommand,
    "disable": DisableRuleCommand,
    "search": SearchCommand,

    "sync": SyncCommand,
    "apply": ApplyCommand,
}
