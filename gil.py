#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gil (git links) tool allows to describe and manage complex git repositories
dependency with cycles and cross references
"""

import os
import re
import subprocess
import sys

__author__ = 'Ivan Shynkarenka'
__license__ = 'MIT License'
__url__ = 'https://github.com/chronoxor/gil'
__version__ = '1.0.0.0'


class GilRecord(object):
    def __init__(self, name, path, repo, branch):
        self.name = name
        self.path = path
        self.repo = repo
        self.branch = branch

    def __eq__(self, other):
        if not isinstance(self, other.__class__):
            return NotImplemented
        if not self.name == other.name:
            return False
        if not self.repo == other.repo:
            return False
        if not self.branch == other.branch:
            return False
        return True

    def __lt__(self, other):
        if not isinstance(self, other.__class__):
            return NotImplemented
        if not self.name < other.name:
            return True
        return False

    @property
    def __key__(self):
        return self.name, self.repo, self.branch

    def __hash__(self):
        return hash(self.__key__)

    def __str__(self):
        return "%s %s %s %s" % (self.name, self.path, self.repo, self.branch)


class GilContext(object):
    def __init__(self, path):
        self.records = {}
        self.path = os.path.abspath(path)
        print("Working path: %s" % self.path)

    def show(self):
        print("Gil context:")
        for value in self.records.values():
            print(value)

    def discover(self, path):
        current = os.path.abspath(path)

        # Recursive discover the parent path
        parent = os.path.abspath(os.path.join(current, os.pardir))
        if parent != current:
            self.discover(parent)

        # Discover the current directory
        records = self.discover_dir(current)

        # Insert discovered record into the records dictionary
        for record in records:
            self.records[record] = record

    def discover_dir(self, path):
        # Try to find .gitlinks file
        filename = os.path.join(path, ".gitlinks")
        if not os.path.exists(filename):
            return []

        print("Discover git links: %s" % filename)

        # Process .gitlinks file
        return self.process_links(path, filename)

    def process_links(self, path, filename):
        result = []
        with open(filename, 'r') as file:
            index = 0
            for line in file:
                # Skip empty lines and comments
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                # Split line into tokens
                tokens = self.split(line)
                if len(tokens) != 4:
                    raise Exception("%s:%d: Invalid git link format! Must be in the form of 'name path repo branch'" % (filename, index))
                # Create a new git link record
                gil_name = tokens[0]
                gil_path = os.path.abspath(os.path.join(path, tokens[1]))
                gil_repo = tokens[2]
                gil_branch = tokens[3]
                record = GilRecord(gil_name, gil_path, gil_repo, gil_branch)
                # Try to find git link record in the records dictionary
                if record not in self.records:
                    result.append(record)
                index += 1
        return result

    def clone(self, args=None):
        args = [] if args is None else args
        stack = list(self.records.values())
        stack.sort()
        while len(stack) > 0:
            value = stack.pop()
            path = value.path
            if not os.path.exists(path) or not os.listdir(path):
                # Perform git clone operation
                self.git_clone(value.path, value.repo, value.branch, args)
                # Discover new repository and append new records to the stack
                if os.path.exists(path) and os.listdir(path):
                    stack.extend(self.discover_dir(path))
                    stack.sort()

    def link(self, path=None):
        current = os.path.abspath(self.path if path is None else path)

        # Recursive discover the parent path
        parent = os.path.abspath(os.path.join(current, os.pardir))
        if parent != current:
            self.link(parent)

        # Link the current directory
        dirs = self.link_dir(current)

        # Link all child dirs
        for d in dirs:
            self.link_dir(d)

    def link_dir(self, path):
        # Try to find .gitlinks file
        filename = os.path.join(path, ".gitlinks")
        if not os.path.exists(filename):
            return []

        print("Updating git links: %s" % filename)

        # Process .gitlinks file
        return self.update_links(path, filename)

    def update_links(self, path, filename):
        result = []
        with open(filename, 'r') as file:
            index = 0
            for line in file:
                # Skip empty lines and comments
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                # Split line into tokens
                tokens = self.split(line)
                if len(tokens) != 4:
                    raise Exception("%s:%d: Invalid git link format! Must be in the form of 'name path repo branch'" % (filename, index))
                # Create a new git link record
                gil_name = tokens[0]
                gil_path = os.path.abspath(os.path.join(path, tokens[1]))
                gil_repo = tokens[2]
                gil_branch = tokens[3]
                record = GilRecord(gil_name, gil_path, gil_repo, gil_branch)
                # Try to find git link record in the records dictionary
                found = os.path.exists(gil_path) and os.listdir(gil_path)
                if record in self.records:
                    found = True
                    record = self.records[record]
                    # Try to check or create link to the existing git link record
                    src_path = record.path
                    dst_path = gil_path
                    # Add destination path to the result list
                    result.append(dst_path)
                    if src_path == dst_path:
                        # Do nothing here...
                        pass
                    elif os.path.exists(dst_path) and os.listdir(dst_path):
                        # Check the link
                        if os.path.islink(dst_path):
                            real_path = os.readlink(dst_path)
                            if real_path != src_path:
                                # Re-create the link
                                self.create_link(src_path, dst_path)
                    else:
                        self.create_link(src_path, dst_path)
                # Validate git link path
                if not found or not os.path.exists(gil_path) or not os.listdir(gil_path):
                    raise Exception("%s:%d: Invalid git link path! Please check %s git repository in %s" % (filename, index, gil_name, gil_path))
                index += 1
        return result

    def command(self, name, args=None):
        def git_callback(path):
            self.git_command(path, name, args)
        args = [] if args is None else args
        self.command_internal(git_callback)

    def command_internal(self, callback, path=None):
        current = os.path.abspath(self.path if path is None else path)

        # Call the command for the current directory
        self.command_dir(callback, current)

    def command_dir(self, callback, path):
        # Call the command callback
        callback(path)

        # Try to find .gitlinks file
        filename = os.path.join(path, ".gitlinks")
        if not os.path.exists(filename):
            return []

        print("Processing git links: %s" % filename)

        # Process .gitlinks file
        return self.command_links(callback, path, filename)

    def command_links(self, callback, path, filename):
        result = []
        with open(filename, 'r') as file:
            index = 0
            for line in file:
                # Skip empty lines and comments
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                # Split line into tokens
                tokens = self.split(line)
                if len(tokens) != 4:
                    raise Exception("%s:%d: Invalid git link format! Must be in the form of 'name path repo branch'" % (filename, index))
                # Create a new git link record
                gil_name = tokens[0]
                gil_path = os.path.abspath(os.path.join(path, tokens[1]))
                gil_repo = tokens[2]
                gil_branch = tokens[3]
                record = GilRecord(gil_name, gil_path, gil_repo, gil_branch)
                # Validate git link path
                if not os.path.exists(gil_path) or not os.listdir(gil_path):
                    raise Exception("%s:%d: Invalid git link path! Please check %s git repository in %s" % (filename, index, gil_name, gil_path))
                # Checkout to the required branch
                self.git_checkout(gil_path, gil_branch)
                # Call the command callback
                callback(record.path)
                index += 1
        return result

    # Filesystem methods

    @staticmethod
    def create_link(src_path, dst_path):
        # Create all directories at link path
        parent = os.path.abspath(os.path.join(dst_path, os.pardir))
        os.makedirs(parent, exist_ok=True)
        # Remove existing file, link or folder
        if os.path.exists(dst_path):
            if os.path.isdir(dst_path):
                os.rmdir(dst_path)
            else:
                os.remove(dst_path)
        # Create the link
        os.symlink(src_path, dst_path, target_is_directory=True)
        print("Update git link: %s -> %s" % (src_path, dst_path))

    # Git methods

    @staticmethod
    def git_clone(path, repo, branch, args):
        # Call git clone command
        print("Running git clone %s branch \"%s\" into %s" % (repo, branch, path))
        params = ["git", "clone", *args, "-b", branch, repo, path]
        process = subprocess.run(params)
        if process.returncode != 0:
            raise Exception("Failed to run git clone %s branch \"%s\" into %s" % (repo, branch, path))

    @staticmethod
    def git_checkout(path, branch):
        # Save the current working directory
        working = os.getcwd()
        # Change working directory into the current git repository
        os.chdir(path)
        # Call git checkout command
        print("Running: git checkout branch \"%s\" in %s" % (branch, path))
        params = ["git", "checkout", branch]
        process = subprocess.run(params)
        if process.returncode != 0:
            raise Exception("Failed to run git checkout branch \"%s\" in %s" % (branch, path))
        # Restore the current working directory
        os.chdir(working)

    @staticmethod
    def git_command(path, command, args):
        # Save the current working directory
        working = os.getcwd()
        # Change working directory into the current git repository
        os.chdir(path)
        # Call git command
        print("Running: git %s in %s" % (command, path))
        params = ["git", command, *args]
        process = subprocess.run(params)
        if process.returncode is None:
            raise Exception("Failed to run git %s in %s" % (command, path))
        # Restore the current working directory
        os.chdir(working)

    # Utility methods

    # Split a string by spaces preserving quoted substrings
    # Author: Ton van den Heuvel
    # https://stackoverflow.com/a/51560564
    @staticmethod
    def split(line):
        def strip_quotes(s):
            if s and (s[0] == '"' or s[0] == "'") and s[0] == s[-1]:
                return s[1:-1]
            return s
        return [strip_quotes(p).replace('\\"', '"').replace("\\'", "'") for p in re.findall(r'"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\'|[^\s]+', line)]


def show_help():
    print("usage: gil command arguments")
    print("Supported commands:")
    print("\thelp - show this help")
    print("\tversion - show version")
    print("\tcontext - show git links context")
    print("\tclone [args] - clone git repositories")
    print("\tlink - link git repositories")
    print("\tupdate - update git repositories (clone & link)")
    print("\tpull [args] - pull git repositories")
    print("\tpush [args] - push git repositories")
    print("\tcommit [args] - commit git repositories")
    sys.exit(1)


def show_version():
    print(__version__)
    sys.exit(1)


def main():
    # Show help message
    if len(sys.argv) <= 1:
        show_help()

    if sys.argv[1] == "help":
        show_help()
    elif sys.argv[1] == "version":
        show_version()

    # Get the current working directory
    path = os.getcwd()

    # Create git links context
    context = GilContext(path)

    # Discover working path
    context.discover(path)

    if sys.argv[1] == "context":
        context.show()
    elif sys.argv[1] == "clone":
        context.clone(sys.argv[2:])
    elif sys.argv[1] == "link":
        context.link()
    elif sys.argv[1] == "update":
        context.clone()
        context.link()
    elif (sys.argv[1] == "pull") or (sys.argv[1] == "push") or (sys.argv[1] == "commit"):
        context.command(sys.argv[1], sys.argv[2:])
    else:
        print("Unknown command: %s" % sys.argv[1])
        return -1
    return 0


if __name__ == "__main__":
    sys.exit(main())
