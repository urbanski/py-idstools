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

from common import BaseCommand
from common import CommandLineError

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
