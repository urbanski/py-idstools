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
import time

import idstools.net
from idstools.ruleman import util

class RemoteCommand(object):

    usage = """
usage: %(progname)s remote [-h]
   or: %(progname)s remote add <name> <url>
   or: %(progname)s remote remove <name>
""" % {"progname": sys.argv[0]}

    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.remotes = config["remotes"]

        self.subcommands = {
            "add": self.add,
            "remove": self.remove,

            # Aliases.
            "rm": self.remove,
        }

    def run(self):
        try:
            self.opts, self.args = getopt.getopt(self.args, "h")
        except getopt.GetoptError as err:
            print("error: %s" % (err), file=sys.stderr)
            print(self.usage, file=sys.stderr)
            return 1
        for o, a in self.opts:
            if o == "-h":
                print(self.usage)
                return 0

        if not self.args:
            return self.list()

        command = self.args.pop(0)

        if command in self.subcommands:
            try:
                return self.subcommands[command]()
            except Exception as err:
                print("error: %s" % (err), file=sys.stderr)
                print(self.subcommands[command].usage, file=sys.stderr)
        else:
            print("error: unknown subcommand: %s" % (command), file=sys.stderr)

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

class FetchCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

        self.remotes = self.config["remotes"]

    def run(self):

        fetched = []

        for name in self.remotes:
            if self.args and name not in self.args:
                continue
            remote = self.remotes[name]
            fileobj = self.fetch(self.remotes[name])
            if fileobj:
                fetched.append({"remote": remote, "fileobj": fileobj})

        print("Fetched:", [item["remote"]["name"] for item in fetched])

        for entry in fetched:
            print("Extracting %s." % entry["remote"]["name"])
            util.extract_archive(entry["fileobj"].name, ".")

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

commands = {
    "fetch": FetchCommand,
    "remote": RemoteCommand,
}
