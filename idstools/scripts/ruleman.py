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
import os
import tarfile
import re
import getopt
import json

import yaml

if sys.argv[0] == __file__:
    sys.path.insert(
        0, os.path.abspath(os.path.join(__file__, "..", "..", "..")))

import idstools.rule
import idstools.ruleman.commands as commands

config_template = {
    "remotes": {},
}

class ReRuleMatcher(object):

    def __init__(self, pattern):
        self.pattern = pattern

    @classmethod
    def parse(cls, buf):
        if buf.startswith("re:"):
            try:
                pattern = re.compile(buf.split(":", 1)[1], re.I)
                return cls(pattern)
            except:
                pass
        return None

    def match(self, rule):
        if self.pattern.search(rule.raw):
            return True
        else:
            return False

    def __repr__(self):
        return "re:%s" % (self.pattern.pattern)

class SidRuleMatcher(object):

    def __init__(self, gid, sid):
        self.gid = gid
        self.sid = sid

    @classmethod
    def parse(cls, buf):
        try:
            parts = buf.split(":")
            if len(parts) == 1:
                return cls(1, int(parts[0]))
            elif len(parts) > 1:
                return cls(int(parts[0]), int(parts[1]))
        except:
            pass

    def __repr__(self):
        return "%d:%d" % (self.gid, self.sid)
        
def get_rule_matcher(arg):
    matcher = ReRuleMatcher.parse(arg)
    if matcher:
        return matcher
    matcher = SidRuleMatcher.parse(arg)
    if matcher:
        return matcher
    return None

def disable_rule(config, args):
    matcher = get_rule_matcher(args[0])
    if not matcher:
        return 1
    config["disabled-rules"].append(str(matcher))
    config["disabled-rules"] = list(set(config["disabled-rules"]))

class SearchCommand(object):

    def run(self, args):

        if not args:
            print("error: nothing to search for.")
            return 1

        matcher = ReRuleMatcher.parse("re:" + args[0])

        directories = ["rules", "so_rules", "preproc_rules"]

        for directory in directories:
            if os.path.exists(directory):
                for dirpath, dirnames, filenames in os.walk(directory):
                    for filename in filenames:
                        if filename.endswith(".rules"):
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

def load_config():
    config = dict(config_template)
    if os.path.exists("ruleman.yaml"):
        yaml_config = yaml.load(open("ruleman.yaml"))
        if yaml_config:
            config.update(yaml_config)
    return config

def main():

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", [])
    except getopt.GetoptError as err:
        print("error: %s" % (err), file=sys.stderr)
        return 1

    command = args.pop(0)
    config = load_config()

    if command == "disable":
        ret = disable_rule(config, args)
    elif command == "search":
        ret = SearchCommand().run(args)
    elif command in commands.commands:
        commands.commands[command](config, args).run()

    # Dump a YAML config as well.
    yaml.safe_dump(config, open(".ruleman.yaml", "w"), default_flow_style=False)
    os.rename(".ruleman.yaml", "ruleman.yaml")

if __name__ == "__main__":
    sys.exit(main())
