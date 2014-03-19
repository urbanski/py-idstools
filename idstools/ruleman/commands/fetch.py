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
import os.path
import tempfile
import shutil
import logging
import io

import idstools.net
import idstools.snort

from idstools.ruleman import util

from idstools.ruleman.commands.dumpdynamicrules import DumpDynamicRulesCommand

LOG = logging.getLogger()

class FetchCommand(object):

    def __init__(self, config, args):
        self.config = config
        self.args = args

        self.remotes = self.config.get_remotes()

    def run(self):

        fetched = []

        for remote in self.remotes.values():
            if self.args and remote["name"] not in self.args:
                continue
            if not remote["enabled"]:
                continue
            if self.check_checksum(remote):
                LOG.info("Remote checksum has not changed, not fetching")
            else:
                fileobj = self.fetch(remote)
                if fileobj:
                    fetched.append({"remote": remote, "fileobj": fileobj})

        print("Fetched:", [item["remote"]["name"] for item in fetched])

        for entry in fetched:
            remote = entry["remote"]
            print("Extracting %s." % remote["name"])
            dest = "remotes/%s" % remote["name"]
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            util.extract_archive(entry["fileobj"].name, dest)
            open("%s/checksum" % (dest), "w").write(
                util.md5_filename(entry["fileobj"].name))

            self.dump_dynamic_rules(remote["name"])

    def has_dynamic_rules(self, remote):
        if os.path.exists("remotes/%s/so_rules" % (remote)):
            return True
        else:
            return False

    def dump_dynamic_rules(self, remote):
        if not self.has_dynamic_rules(remote):
            LOG.debug("Remote %s does not appear to have dynamic rules",
                      remote)
            return

        if "snort" not in self.config:
            LOG.warn("Not generating dynamic rule stubs, snort not configured")
            return

        DumpDynamicRulesCommand(
            self.config, ["--remote", remote]).run()

    def check_checksum(self, remote):
        """ Check the current checksum against the remote checksum.

        Return True if they match, otherwise return False.
        """
        current_checksum = self.current_checksum(remote)
        if current_checksum:
            remote_checksum = self.fetch_checksum(remote)
            if remote_checksum and remote_checksum == current_checksum:
                return True
        return False

    def fetch(self, remote):

        print("Fetching %s : %s" % (
            remote["name"], util.get_filename_from_url(remote["url"])))
        fileobj = tempfile.NamedTemporaryFile(
            suffix=util.get_filename_from_url(remote["url"]), mode="wb")
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

    def current_checksum(self, remote):
        checksum_filename = "remotes/%s/checksum" % (remote["name"])
        if os.path.exists(checksum_filename):
            return open(checksum_filename, "rb").read()
        else:
            LOG.debug("No checksum file exists for ruleset %s", remote["name"])

    def fetch_checksum(self, remote):
        checksum_url = self.get_checksum_url(remote)
        buf = io.BytesIO()
        try:
            length, info = idstools.net.get(checksum_url, buf)
            return buf.getvalue().strip()
        except idstools.net.HTTPError as err:
            LOG.warn("Error fetching checksum url %s: %s %s" % (
                checksum_url, err.code, err.msg))
            return None

    def get_checksum_url(self, remote):
        filename = util.get_filename_from_url(remote["url"])
        checksum_filename = "%s.md5" % (filename)
        checksum_url = remote["url"].replace(filename, checksum_filename)
        return checksum_url

    def progress_hook(self, content_length, bytes_read):
        percent = int((bytes_read / float(content_length)) * 100)
        buf = " %3d%% - %-30s" % (
            percent, "%d/%d" % (bytes_read, content_length))
        sys.stdout.write(buf)
        sys.stdout.flush()
        sys.stdout.write("\b" * 38)
