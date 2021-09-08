#!/bin/env python3

from __future__ import print_function
from os import listdir
from os.path import isfile, join
import datetime
import os.path
import sys
import glob
import subprocess
import hashlib

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
  'nvidia-libXNVCtrl',
  'nvidia-libXNVCtrl-devel',
  'nvidia-xconfig',
  'nvidia-kmod-common',

  'cuda-drivers',
]

# Add-ons
OPTIONAL_PKGS = [
  'nvidia-fabric-manager',
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
    def __init__(self, name, major, minor, micro = None, arch = "noarch"):
        self.name = name
        self.major = major
        self.minor = minor
        self.micro = micro
        self.arch = arch

    def __repr__(self):
        return 'Branch ({})'.format(self.version())

    def __lt__(self, other):
        if (self.major != other.major):
            return other.major < self.major

        if (self.minor != other.minor):
            return other.minor < self.minor

        if self.micro:
            return other.micro < self.micro

        return 0

    def version(self):
        return '{}.{}{}'.format(self.major, self.minor, '.' + str(self.micro) if self.micro else '')

    def is_dkms(self):
        return 'dkms' in self.name

def get_stream_hash(name, stream, version, distro):
    uniq_str = name + stream + version + distro
    hash_str = hashlib.md5(uniq_str.encode('utf-8')).hexdigest()[:10]
    print('context: ' + hash_str + ' = ', name, stream, version, distro)

    return hash_str

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
    micro = version_parts[2] if len(version_parts) == 3 else None

    return (version_parts[0], version_parts[1],  micro, release)

def arch_from_rpm_filename(filename):
    # name - version - release.dist.arch.rpm

    # remove extension
    arch = filename[:filename.rfind('.')]
    arch = arch[arch.rfind('.') + 1:]

    return arch

def distro_from_rpm_filename(filename):
    # name - version - release.dist.arch.rpm
    distro = filename.split('.')[-3]

    return distro

def verkey_rpms(rpm):
    version = version_from_rpm_filename(rpm)
    major = version[0].rjust(4, '0')
    minor = version[1].rjust(4, '0')
    micro = version[2].rjust(4, '0') if version[2] else '0000'
    rel   = version[3].rjust(4, '0')
    key = '{}{}{}{}'.format(major, minor, micro, rel)
    return int(key)

def sort_rpms(rpms):
    return sorted(rpms, reverse = True, key = verkey_rpms)

def rpm_is_kmod(filename):
    return filename.startswith(KMOD_PKG_PREFIX) and not 'dkms' in filename

def kmod_belongs_to(kmod_filename, branch):
    return branch.version() in kmod_filename

def get_rpm_epoch(rpmfile, repodir):
    cmd = ['rpm', '-qp', '--nosignature', '--qf', '%{epochnum}', repodir + rpmfile]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    # Print warnings but try to ignore the one about the key
    if stderr and not stderr.endswith('NOKEY\n'):
        print(stderr)

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

def all_rpms_from_pkgname(rpms, pkgname, majorversion):
    candidates = [f for f in rpms if rpm_is_pkgname(f, pkgname, majorversion)]

    return sort_rpms(candidates) # Sort them anyway, just because

def latest_rpm_from_pkgname(rpms, pkgname, pkgversion = ''):
    candidates = [f for f in rpms if rpm_is_pkgname(f, pkgname, pkgversion)]

    if len(candidates) == 0: return None

    # If a pkgversion is given, we should generally have only one rpm per
    # stream. However, if there are mulitple rpm files in the given version
    # but with different release numbers, we need to use the latest one, so
    # just sort the rpms

    candidates = sort_rpms(candidates)

    return candidates[0]

def filename_to_nevra(filename, repodir):
    epoch = get_rpm_epoch(filename, repodir)
    hyphen_parts = filename.split('-')

    assert len(hyphen_parts) > 2, "filename not well-formed: %r" % filename

    nevra = ''
    # Add all parts until the version
    for i in range(0, len(hyphen_parts) - 2):
        nevra += hyphen_parts[i] + '-'

    nevra += epoch
    nevra += ':'
    nevra += hyphen_parts[len(hyphen_parts) - 2]

    last = hyphen_parts[len(hyphen_parts) - 1] # Remove file extension
    last = last[:last.rfind('.')]
    nevra += '-'
    nevra += last

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

        version = version_from_rpm_filename(pkg)
        major = version[0]
        minor = version[1]
        micro = version[2]

        n_branches = len(branches)
        if n_branches == 0 or (n_branches > 0 and branches[n_branches - 1].major != major):
            arch = arch_from_rpm_filename(pkg)
            distro = distro_from_rpm_filename(pkg)
            branches.append(Branch(major, major, minor, micro, arch))
            branches.append(Branch(major + "-dkms", major, minor, micro, arch))

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
    latest_branch = Branch('latest', latest.major, latest.minor, latest.micro, latest.arch)
    branches.insert(0, latest_branch)
    print('Latest Branch: ' + latest_branch.version())
    latest_dkms_branch = Branch('latest-dkms', latest.major, latest.minor, latest.micro, latest.arch)
    branches.insert(1, latest_dkms_branch)

    for branch in branches:
        print('Branch: ' + branch.name + '(Version: ' + branch.version()  + ')')
        time_stamp = now.strftime('%Y%m%d%H%M%S')
        out.line('document: modulemd')
        out.line('version: 2')
        out.line('data:')
        out.tab().line('name: nvidia-driver')
        out.tab().line('stream: ' + branch.name)
        out.tab().line('version: ' + time_stamp)
        out.tab().line('context: ' + get_stream_hash('nvidia-driver', branch.name, time_stamp, distro))
        out.tab().line('arch: ' + branch.arch)
        out.tab().line('summary: Nvidia driver for ' + branch.name + ' branch')
        out.tab().line('description: >-')
        for line in DESCRIPTION:
            out.tab().tab().line(line.replace('{version}', branch.version()))
        out.tab().line('license:')
        out.tab().tab().line('module:')
        out.tab().tab().tab().line('- MIT')

        out.tab().line('artifacts:')
        out.tab().tab().line('rpms:')
        existing_branch_pkgs = set()
        optional_branch_pkgs = set()

        for pkg in BRANCH_PKGS:
            latest_pkg = latest_rpm_from_pkgname(rpm_files, pkg, branch.version())

            if not latest_pkg:
                print('WARNING: No package named ' + pkg + ' in version "' + \
                      branch.version() + '" found in rpmdir')

            for p in all_rpms_from_pkgname(rpm_files, pkg, branch.major):
                out.tab().tab().tab().line('- ' + filename_to_nevra(p, repodir))
                existing_branch_pkgs.add(pkg)

        for opt in OPTIONAL_PKGS:
            for o in all_rpms_from_pkgname(rpm_files, opt, branch.major):
                out.tab().tab().tab().line('- ' + filename_to_nevra(o, repodir))
                optional_branch_pkgs.add(opt)

        for pkg in LATEST_PKGS:
            latest_pkg = latest_rpm_from_pkgname(rpm_files, pkg)
            if latest_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(latest_pkg, repodir))
            else:
                print('WARNING: No package ' + str(pkg) + ' for branch ' + branch.name + ' found')

        if branch.is_dkms():
            dkms_pkg = latest_rpm_from_pkgname(rpm_files, 'kmod-nvidia-latest-dkms', branch.version())
            if dkms_pkg:
                out.tab().tab().tab().line('- ' + filename_to_nevra(dkms_pkg, repodir))
            else:
                print('WARNING: RPM kmod-nvidia-latest-dkms in version ' + branch.version() + ' not found')
        else:
            # All the kmod rpms which belong to this branch
            branch_kmod_rpms = list(filter(lambda r: kmod_belongs_to(r, branch), kmod_rpms))
            if not branch_kmod_rpms:
                print('WARNING: Branch %s in version %s is not a DKMS branch, but no precompiled kmod packages can be found' % (branch.name, branch.version()))
            else:
                for rpm in branch_kmod_rpms:
                    out.tab().tab().tab().line('- ' + filename_to_nevra(rpm, repodir))

        out.tab().line('profiles:')
        out.tab().tab().line('default:')
        out.tab().tab().tab().line('description: Default installation')
        out.tab().tab().tab().line('rpms:')
        for pkg in sorted(existing_branch_pkgs):
            out.tab().tab().tab().tab().line('- ' + pkg)

        if branch.is_dkms():
            out.tab().tab().tab().tab().line('- kmod-nvidia-latest-dkms')
        else:
            out.tab().tab().line('src:')
            out.tab().tab().tab().line('description: Source headers for compilation')
            out.tab().tab().tab().line('rpms:')
            out.tab().tab().tab().tab().line('- nvidia-kmod-headers')

        if branch.arch == "x86_64":
            out.tab().tab().line('fm:')
            out.tab().tab().tab().line('description: FabricManager installation')
            out.tab().tab().tab().line('rpms:')
            for pkg in sorted(existing_branch_pkgs):
                out.tab().tab().tab().tab().line('- ' + pkg)
            if branch.is_dkms():
                out.tab().tab().tab().tab().line('- kmod-nvidia-latest-dkms')
            if "latest" in branch.name:
                out.tab().tab().tab().tab().line('- ' + 'nvidia-fabric-manager')
                out.tab().tab().tab().tab().line('- ' + 'libnvidia-nscq-' + latest.major)
            elif int(branch.major) < 460:
                out.tab().tab().tab().tab().line('- ' + 'nvidia-fabricmanager-' + branch.major)
                out.tab().tab().tab().tab().line('- ' + 'libnvidia-nscq-' + branch.major)
            else:
                out.tab().tab().tab().tab().line('- ' + 'nvidia-fabric-manager')
                out.tab().tab().tab().tab().line('- ' + 'libnvidia-nscq-' + branch.major)

        if branch.arch == "aarch64" and int(branch.major) > 470:
            out.tab().tab().line('fm:')
            out.tab().tab().tab().line('description: FabricManager installation')
            out.tab().tab().tab().line('rpms:')
            for pkg in sorted(existing_branch_pkgs):
                out.tab().tab().tab().tab().line('- ' + pkg)
            if branch.is_dkms():
                out.tab().tab().tab().tab().line('- kmod-nvidia-latest-dkms')
            out.tab().tab().tab().tab().line('- ' + 'nvidia-fabric-manager')

        out.tab().tab().line('ks:')
        out.tab().tab().tab().line('description: Installation via kickstart')
        out.tab().tab().tab().line('rpms:')
        for pkg in sorted(existing_branch_pkgs):
            if "cuda-drivers" not in pkg:
                out.tab().tab().tab().tab().line('- ' + pkg)

        if branch.is_dkms():
            out.tab().tab().tab().tab().line('- kmod-nvidia-latest-dkms')

        out.next()

    out.line('document: modulemd-defaults')
    out.line('version: 1')
    out.line('data:')
    out.tab().line('module: nvidia-driver')
    out.tab().line('stream: latest-dkms')
    out.tab().line('profiles:')
    for branch in branches:
        out.tab().tab().line(branch.name + ': [default]')

    out.write(outfile)

    # Run modulemd-validator on the output, to catch
    # bugs early. Since modifyrepo doesn't do it...
    if len(outfile) > 0 and os.path.isfile('/usr/bin/modulemd-validator'):
        print('Running modulemd-validator...', end='')
        process = subprocess.Popen(['/usr/bin/modulemd-validator', outfile], \
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout = process.communicate()[0]

        if process.returncode != 0:
            print('')
            print(stdout)
        else:
            print(' OK')
