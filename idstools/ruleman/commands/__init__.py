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

from idstools.ruleman.commands.common import BaseCommand
from idstools.ruleman.commands.common import CommandLineError
from idstools.ruleman.commands.remote import RemoteCommand
from idstools.ruleman.commands.fetch import FetchCommand
from idstools.ruleman.commands.dumpdynamicrules import DumpDynamicRulesCommand

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
                fileobj.write((str(rule) + "\n").encode())

commands = {
    "fetch": FetchCommand,
    "remote": RemoteCommand,
    "disable": DisableRuleCommand,
    "search": SearchCommand,
    "apply": ApplyCommand,
    "dump-dynamic-rules": DumpDynamicRulesCommand,
}
