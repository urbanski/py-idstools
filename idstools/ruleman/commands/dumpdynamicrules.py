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
import os.path
import getopt

import idstools.snort

from idstools.ruleman.commands.common import BaseCommand

class DumpDynamicRulesCommand(BaseCommand):

    usage = """
usage: %(progname)s dump-dynamic-rules --remote <remote>
""" % {"progname": sys.argv[0]}

    def __init__(self, config, args):
        self.config = config
        self.args = args

        self.opt_remote = None

    def run(self):

        try:
            opts, self.args = getopt.getopt(self.args, "", ["remote="])
        except getopt.GetoptError as err:
            print("error: %s" % (err), file=sys.stderr)
            print(self.usage, file=sys.stderr)
            return 1
        for o, a in opts:
            if o in ["--remote"]:
                self.opt_remote = a

        if self.opt_remote:
            return self.dump_remote()

    def dump_remote(self):

        remote_path = os.path.join("remotes", self.opt_remote)
        if not os.path.exists(remote_path):
            print("error: remote %s does not exist" % (self.opt_remote),
                  file=sys.stderr)
            return 1

        if not os.path.exists(os.path.join(remote_path, "so_rules")):
            print("error: remote %s does not appear to have dynamic rules" % (
                self.opt_remote), file=sys.stderr)
            return 1

        if not "snort" in self.config:
            print("error: snort configuration section does not exist",
                  file=sys.stderr)
            return 1

        snortapp = idstools.snort.SnortApp(self.config.get("snort"))
        files = snortapp.dump_dynamic_rules(
            snortapp.find_dynamic_detection_lib_dir(
                "remotes/%s" % (self.opt_remote)))
        if files:
            destination_dir = os.path.join(
                "remotes", self.opt_remote, "so_rules")  
            for filename in files:
                if os.path.exists(os.path.join(destination_dir, filename)):
                    print("Overwriting %s." % os.path.join(
                        destination_dir, filename))
            for filename in os.listdir(destination_dir):
                if filename.endswith(".rules") and filename not in files:
                    path = os.path.join(destination_dir, filename)
                    print("Removing %s as it was not regenerated." % (filename))
                    os.unlink(path)

