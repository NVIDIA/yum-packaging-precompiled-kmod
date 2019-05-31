#!/bin/env python

from __future__ import print_function
from os import listdir
from os.path import isfile, join
import datetime
import os.path
import sys
import glob
import subprocess

# https://github.com/fedora-modularity/libmodulemd/blob/master/spec.v2.yaml

# We need a module.yaml file that we pass to modifyrepo so dnf knows
# how the stream are made up.
#
# Here we generate the module.yaml file.
KMOD_PKG_PREFIX = 'kmod-nvidia'

DESCRIPTION = [
  'This package provides the most recent NVIDIA display driver which allows for',
  'hardware accelerated rendering with recent NVIDIA chipsets.',
  '',
  'For the full product support list, please consult the release notes for',
  'driver version {version}.',
]

# Unrelated to the version a branch is at, we always
# use the latest version of these rpms in every branch
LATEST_PKGS = [
  'dnf-plugin-nvidia',
]

# Main package must be first!
BRANCH_PKGS = [
  'nvidia-driver',
  'nvidia-driver-libs',
  'nvidia-driver-devel',
  'nvidia-driver-NVML',
  'nvidia-driver-NvFBCOpenGL',
  'nvidia-driver-cuda',
  'nvidia-driver-cuda-libs',

  'nvidia-persistenced',
  'nvidia-modprobe',
  'nvidia-settings',
  'nvidia-xconfig',

  'cuda-drivers-redhat',
]

class Writer:
    output = ''

    def line(self, str):
        self.output += str + '\n'

    def write(self, target):
        if len(target) == 0:
            print(self.output)
        else:
            with open(target, 'w') as text_file:
                print(self.output, file=text_file)

    def tab(self):
        self.output += '    '
        return self

    def next(self):
        self.output += '...\n---\n'



class Branch:
    def __init__(self, name, major, minor):
        self.name = name
        self.major = major
        self.minor = minor

    def __repr__(self):
        return 'Branch ' + self.name + '(' + self.major + '.' + self.minor + ')'

    def __lt__(self, other):
        if self.major != other.major:
            return other.major < self.major;

        return other.minor < self.minor;

    def version(self):
        return str(self.major) + '.' + str(self.minor)

    def is_dkms(self):
        return 'dkms' in self.name

def kmod_belongs_to(kmod_filename, branch):
    return branch.version() in kmod_filename

def get_rpm_epoch(rpmfile, repodir):
    cmd = ['rpm', '-q', '--qf', '%{epochnum}', repodir + rpmfile]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout = process.communicate()[0]

    return stdout

def rpm_is_pkgname(rpm, pkgname, pkgversion = ''):
    """
    checks whether the given rpm filename fits the given package name
    """
    rpm_stops = len(rpm.split('-'))
    pkg_stops = len(pkgname.split('-'))

    if pkgversion == '':
        return rpm.startswith(pkgname) and rpm_stops == pkg_stops + 2
    else:
        return rpm.startswith(pkgname) and pkgversion in rpm and rpm_stops == pkg_stops + 2

def rpm_from_pkgname(rpms, pkgname, pkgversion = ''):
    relevant_rpms = filter(lambda f: rpm_is_pkgname(f, pkgname, pkgversion), rpms)

    if len(relevant_rpms) == 0:
        return None

    # If no pkgversion is given, we prefer the one with the highest version number,
    # just like package managers do.
    if pkgversion == '':
        relevant_rpms.sort(reverse = True) # Simply sort by name
    else:
        if len(relevant_rpms) > 1:
            print('Expected exactly one rpm for branch package "' + pkgname + '" in version ' \
                    + pkgversion + ' but I have ' + str(relevant_rpms))

    return relevant_rpms[0]

def filename_to_nevra(filename, repodir):
    epoch = get_rpm_epoch(filename, repodir)
    # Remove file extension
    filename = filename[:filename.rfind('.')]
    # Remove arch
    arch = filename[filename.rfind('.') + 1:]
    filename = filename[:filename.rfind('.')]
    # Remove dist
    dist = filename[filename.rfind('.') + 1:]
    filename = filename[:filename.rfind('.')]
    hyphen_parts = filename.split('-')
    nevra = ''
    for i in range(0, len(hyphen_parts) - 2):
        nevra += hyphen_parts[i]
        nevra += '-'

    nevra += str(epoch)+ ':'
    nevra += hyphen_parts[len(hyphen_parts) - 2]
    nevra += '-' + hyphen_parts[len(hyphen_parts) - 1]
    nevra += '.' + dist
    nevra += '.' + arch

    return nevra

if __name__ == '__main__':
    repodir = './rpms/'
    outfile = ''

    if len(sys.argv) > 1:
        repodir = sys.argv[1]
    else:
        print('Usage: ' + sys.argv[0] + ' [INDIR] [OUTFILE]')
        sys.exit()

    if len(sys.argv) > 2:
        outfile = sys.argv[2]

    out = Writer()
    now = datetime.datetime.now()

    repodir_contents = listdir(repodir)
    rpm_files = filter(lambda f: isfile(join(repodir, f)), repodir_contents)
    driver_rpms = filter(lambda n: n.startswith(BRANCH_PKGS[0]), rpm_files)
    kmod_rpms = filter(lambda n: n.startswith(KMOD_PKG_PREFIX), rpm_files)

    branches = []
    # Figure out the branches
    driver_rpms.sort(reverse = True)
    for pkg in driver_rpms:
        stops = len(BRANCH_PKGS[0].split('-'))
        pkg_stops = len(pkg.split('-'))
        if (pkg_stops != stops + 2):
            continue

        n = pkg[len(BRANCH_PKGS[0]) + 1:]
        version = n[0:n.index('-')]
        version_parts = version.split('.')
        major = version_parts[0]
        minor = version_parts[1]

        if len(branches) == 0:
            branches.append(Branch(major, major, minor))
        elif len(branches) > 0 and branches[len(branches) - 1].major != major:
            branches.append(Branch(major, major, minor))

    branches.sort()

    # Add 'latest' branch with the same version as the highest-versioned other branch
    latest = branches[0]
    latest_branch = Branch('latest', latest.major, latest.minor)
    branches.insert(0, latest_branch)
    print('Latest Branch: ' + latest_branch.version())

    for index, branch in enumerate(branches):
        if 'dkms' in branch.name:
            continue;

        dkms_branch = Branch(branch.name + '-dkms', branch.major, branch.minor)
        branches.insert(index + 1, dkms_branch)

    for branch in branches:
        print('Branch: ' + branch.name + '(Version: ' + branch.version()  + ')')
        out.line('document: modulemd')
        out.line('version: 2')
        out.line('data:')
        out.tab().line('name: nvidia-driver')
        out.tab().line('stream: ' + branch.name)
        out.tab().line('version: ' + now.strftime('%Y%m%d%H%M%S'))
        out.tab().line('arch: x86_64')
        out.tab().line('summary: Nvidia driver for ' + branch.name + ' branch')
        out.tab().line('description: >-')
        for line in DESCRIPTION:
            out.tab().tab().line(line.replace('{version}', branch.version()))
        out.tab().line('license:')
        out.tab().tab().line('module:')
        out.tab().tab().tab().line('- MIT')

        out.tab().line('profiles:')
        out.tab().tab().line('default:')
        out.tab().tab().tab().line('description: Default installation')
        out.tab().tab().tab().line('rpms:')
        out.tab().tab().tab().tab().line('- ' + BRANCH_PKGS[0])
        if branch.is_dkms():
            out.tab().tab().tab().tab().line('- dkms-nvidia')


        out.tab().line('artifacts:')
        out.tab().tab().line('rpms:')
        for pkg in BRANCH_PKGS:
            branch_pkg = rpm_from_pkgname(rpm_files, pkg, branch.version())
            if branch_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(branch_pkg, repodir))
            else:
                print('WARNING: Branch ' + branch.name + ' does not have a ' + pkg + ' package')

        for pkg in LATEST_PKGS:
            latest_pkg = rpm_from_pkgname(rpm_files, pkg)
            out.tab().tab().tab().line('- ' + filename_to_nevra(latest_pkg, repodir))

        # All the kmod rpms which belong to this branch
        for rpm in filter(lambda r: kmod_belongs_to(r, branch), kmod_rpms):
            out.tab().tab().tab().line('- ' + filename_to_nevra(rpm, repodir))

        if branch.is_dkms():
            dkms_pkg = rpm_from_pkgname(rpm_files, 'dkms-nvidia', branch.version())
            if dkms_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(dkms_pkg, repodir))
            else:
                print('WARNING: Branch ' + branch.name + ' does not have a dkms-nvidia package')

        out.next()

    out.line('document: modulemd-defaults')
    out.line('version: 1')
    out.line('data:')
    out.tab().line('module: nvidia-driver')
    out.tab().line('stream: latest')
    out.tab().line('profiles:')
    for branch in branches:
        out.tab().tab().line(branch.name + ': [default]')

    out.write(outfile)

    # Run modulemd-validator on the output, to catch
    # bugs early. Since modifyrepo doesn't do it...
    if len(outfile) > 0 and os.path.isfile('/usr/bin/modulemd-validator'):
        process = subprocess.Popen(['/usr/bin/modulemd-validator', outfile], \
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout = process.communicate()[0]

        if process.returncode != 0:
            print(stdout)
