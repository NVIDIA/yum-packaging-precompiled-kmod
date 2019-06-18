#!/bin/env python3

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
  'nvidia-kmod-common',

  'cuda-drivers',
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

def version_from_rpm_filename(filename):
    # name - version - release.dist.arch.rpm
    hyphen_parts = filename.split('-')

    assert(len(hyphen_parts) >= 3)

    dotpart = hyphen_parts[len(hyphen_parts) - 1]
    ndots = len(dotpart.split('.'))
    dotpart = dotpart[:dotpart.rfind('.')] # Remove the file extension
    dotpart = dotpart[:dotpart.rfind('.')] # Remove the arch
    if ndots >= 4:
        dotpart = dotpart[:dotpart.rfind('.')] # Remove the dist

    # The remainder should just be the release.
    release = dotpart

    # Get the version
    version = hyphen_parts[len(hyphen_parts) - 2]
    version_parts = version.split('.')

    return (int(version_parts[0]), int(version_parts[1]), int(release))

def verkey_rpms(rpm_a):
    version_a = version_from_rpm_filename(rpm_a)
    return (version_a[0] * 1000 * 1000) + (version_a[1] * 1000) + (version_a[2])

def sort_rpms(rpms):
    return sorted(rpms, reverse = True, key = verkey_rpms)

def rpm_is_kmod(filename):
    return filename.startswith(KMOD_PKG_PREFIX) and not 'dkms' in filename

def kmod_belongs_to(kmod_filename, branch):
    return branch.version() in kmod_filename

def get_rpm_epoch(rpmfile, repodir):
    cmd = ['rpm', '-q', '--qf', '%{epochnum}', repodir + rpmfile]
    null = open(os.devnull, 'w')
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=null)
    stdout = process.communicate()[0]

    return stdout.decode('utf-8')

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
    candidates = [f for f in rpms if rpm_is_pkgname(f, pkgname, pkgversion)]

    if len(candidates) == 0:
        print('ERROR: No package named ' + pkgname + ' in version "' + \
                pkgversion + '" found in rpmdir')
        return None

    # If a pkgversion is given, we should generally have only one rpm per
    # stream. However, if there are mulitple rpm files in the given version
    # but with different release numbers, we need to use the latest one, so
    # just sort the rpms

    candidates = sort_rpms(candidates)

    return candidates[0]

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
        repodir = sys.argv[1] + '/'
    else:
        print('Usage: ' + sys.argv[0] + ' [INDIR] [OUTFILE]')
        sys.exit()

    if len(sys.argv) > 2:
        outfile = sys.argv[2]

    out = Writer()
    now = datetime.datetime.now()

    repodir_contents = listdir(repodir)
    rpm_files = [f for f in repodir_contents if isfile(join(repodir, f))]
    driver_rpms = [n for n in rpm_files if n.startswith(BRANCH_PKGS[0])]
    kmod_rpms = [n for n in rpm_files if rpm_is_kmod(n)]

    if len(driver_rpms) == 0:
        print('Error: No driver rpms (starting with ' + BRANCH_PKGS[0] + ') found.')
        sys.exit()

    branches = []
    # Figure out the branches
    driver_rpms = sort_rpms(driver_rpms)

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

    branches = sorted(branches)

    if len(branches) == 0:
        print('Error: Could not determine branches from the given rpm files in ' + repodir)
        print('RPM files found:')
        for p in repodir_contents:
            print(' - ' + str(p))
        print('Driver rpms:')
        for p in driver_rpms:
            print(' - ' + str(p))

        sys.exit()

    # Add 'latest' branch with the same version as the highest-versioned other branch
    latest = branches[0]
    latest_branch = Branch('latest', latest.major, latest.minor)
    branches.insert(0, latest_branch)
    print('Latest Branch: ' + latest_branch.version())
    latest_dkms_branch = Branch('latest-dkms', latest.major, latest.minor)
    branches.insert(1, latest_dkms_branch)

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

        out.tab().line('artifacts:')
        out.tab().tab().line('rpms:')
        existing_branch_pkgs = []
        for pkg in BRANCH_PKGS:
            branch_pkg = rpm_from_pkgname(rpm_files, pkg, branch.version())
            if branch_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(branch_pkg, repodir))
                existing_branch_pkgs.append(pkg)
        for pkg in LATEST_PKGS:
            latest_pkg = rpm_from_pkgname(rpm_files, pkg)
            out.tab().tab().tab().line('- ' + filename_to_nevra(latest_pkg, repodir))
        if branch.is_dkms():
            dkms_pkg = rpm_from_pkgname(rpm_files, 'kmod-nvidia-latest-dkms', branch.version())
            if dkms_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(dkms_pkg, repodir))
        else:
            # All the kmod rpms which belong to this branch
            for rpm in filter(lambda r: kmod_belongs_to(r, branch), kmod_rpms):
                out.tab().tab().tab().line('- ' + filename_to_nevra(rpm, repodir))

        out.tab().line('profiles:')
        out.tab().tab().line('default:')
        out.tab().tab().tab().line('description: Default installation')
        out.tab().tab().tab().line('rpms:')
        for pkg in existing_branch_pkgs:
            out.tab().tab().tab().tab().line('- ' + pkg)
        if branch.is_dkms():
            out.tab().tab().tab().tab().line('- kmod-nvidia-latest-dkms')

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
