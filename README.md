# yum packaging precompiled kmod

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Contributing](https://img.shields.io/badge/Contributing-Developer%20Certificate%20of%20Origin-violet)](https://developercertificate.org)

## Overview

Packaging templates for `yum` and `dnf` based Linux distros to build NVIDIA driver precompiled kernel modules.

For official packages [see this table](https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/precompiled/) and developer [blog post](https://developer.nvidia.com/blog/streamlining-nvidia-driver-deployment-on-rhel-8-with-modularity-streams/).

The `main` branch contains this README and a sample build script. The `.spec` files can be found in the appropriate [rhel7](../../tree/rhel7), [rhel8](../../tree/rhel8), and [fedora](../../tree/fedora) branches.

## Table of Contents

- [Overview](#Overview)
- [Deliverables](#Deliverables)
- [Prerequisites](#Prerequisites)
  * [Clone this git repository](#Clone-this-git-repository)
  * [Download a NVIDIA driver runfile](#Download-a-NVIDIA-driver-runfile)
  * [Install build dependencies](#Install-build-dependencies)
- [Demo](#Demo)
- [Building with script](#Building-with-script)
  * [Fetch script from master branch](#Fetch-script-from-master-branch)
  * [Usage](#Usage)
- [Building Manually](#Building-Manually)
  * [Generate tarball from runfile](#Generate-tarball-from-runfile)
  * [X.509 Certificate](#X.509-Certificate)
  * [Compilation and Packaging](#Compilation-and-Packaging)
  * [Sign RPM packages with GPG signing key](#Sign-RPM-packages-with-GPG-signing-key)
- [RPM Repository](#RPM-Repository)
  * [Other NVIDIA driver packages](#Other-NVIDIA-driver-packages)
  * [Python script](#Python-script)
  * [Generate metadata](#Generate-metadata)
  * [Enable local repo](#Enable-local-repo)
- [Installing packages](#Installing-packages)
- [Modularity Profiles](#Modularity-Profiles)
- [Presentations](#Presentations)
  * [GPU Technology Conference](#GPU-Technology-Conference)
  * [Red Hat Summit](#Red-Hat-Summit)
- [Related](#Related)
  * [NVIDIA plugin](#NVIDIA-plugin)
  * [NVIDIA driver](#NVIDIA-driver)
- [Contributing](#Contributing)


## Deliverables

This repo contains the `.spec` file used to build the following **RPM** packages:

> *note:* `XXX` is the first `.` delimited field in the driver version, ex: `440` in `440.33.01`

* **RHEL8** or **Fedora** streams: `latest` and `XXX`
  ```shell
  kmod-nvidia-${driver}-${kernel}-${driver}-${rel}.${dist}.${arch}.rpm
  > ex: kmod-nvidia-440.33.01-4.18.0-147.5.1-440.33.01-2.el8_1.x86_64.rpm
  > ex: kmod-nvidia-450.51.06-5.6.11-300-450.51.06-4.fc32.x86_64.rpm
  ```
  *note:* requires [`genmodules.py`](https://github.com/NVIDIA/cuda-repo-management/blob/main/genmodules.py) to generate `modules.yaml` for [modularity streams](https://docs.pagure.org/modularity/).

* **RHEL7** flavor: `latest`
  ```shell
  kmod-nvidia-latest-${kernel}.r${driver}.${dist}.${arch}.rpm
  > ex: kmod-nvidia-latest-3.10.0-1062.18.1.r440.33.01.el7.x86_64.rpm
  ```

* **RHEL7** flavor: `branch-XXX`
  ```shell
  kmod-nvidia-branch-XXX-${kernel}.r${driver}.${dist}.${arch}.rpm
  > ex: kmod-nvidia-branch-440-3.10.0-1062.18.1.r440.33.01.el7.x86_64.rpm
  ```

These packages can be used in place of their equivalent [DKMS](https://en.wikipedia.org/wiki/Dynamic_Kernel_Module_Support) packages:

* **RHEL8** or **Fedora** streams: `latest-dkms` and `XXX-dkms`
  ```shell
  kmod-nvidia-latest-dkms-${driver}-${rel}.${dist}.${arch}.rpm
  > ex: kmod-nvidia-latest-dkms-440.33.01-1.el8.x86_64.rpm
  ```

* **RHEL7** flavor: `latest-dkms`
  ```shell
  kmod-nvidia-latest-dkms-${driver}-${rel}.${dist}.${arch}.rpm
  > ex: kmod-nvidia-latest-dkms-440.33.01-1.el7.x86_64.rpm
  ```

The `latest` and `latest-dkms` streams/flavors always update to the highest versioned driver, while the `XXX` and `XXX-dkms` streams/flavors lock driver updates to the specified driver branch.

> *note:* `XXX-dkms` is not available for RHEL7


## Prerequisites

### Clone this git repository:

Supported branches: `rhel7`, `rhel8` & `fedora`

```shell
git clone -b ${branch} https://github.com/NVIDIA/yum-packaging-precompiled-kmod
> ex: git clone -b rhel8 https://github.com/NVIDIA/yum-packaging-precompiled-kmod
```

### Download a NVIDIA driver runfile:

* **TRD** location: [http://us.download.nvidia.com/tesla/](http://us.download.nvidia.com/tesla/) (not browsable)

  *ex:* [http://us.download.nvidia.com/tesla/440.33.01/NVIDIA-Linux-x86_64-440.33.01.run](http://us.download.nvidia.com/tesla/440.33.01/NVIDIA-Linux-x86_64-440.33.01.run)

* **UDA** location: [http://download.nvidia.com/XFree86/Linux-x86_64/](http://download.nvidia.com/XFree86/Linux-x86_64/)

  *ex:* [http://download.nvidia.com/XFree86/Linux-x86_64/440.64/NVIDIA-Linux-x86_64-440.64.run](http://download.nvidia.com/XFree86/Linux-x86_64/440.64/NVIDIA-Linux-x86_64-440.64.run)

* **CUDA** runfiles: `cuda_${toolkit}_${driver}_linux.run` are not compatible.

  However a NVIDIA driver runfile can be extracted intact from a CUDA runfile:
  ```shell
  sh cuda_${toolkit}_${driver}_linux.run --tar mxvf
  > ex: sh cuda_11.1.0_455.23.05_linux.run --tar mxvf

  ls builds/NVIDIA-Linux-${arch}-${driver}.run
  > ex: ls builds/NVIDIA-Linux-x86_64-455.23.05.run
  ```

### Install build dependencies
> *note:* these are only needed for building not installation

```shell
# Compilation
yum install gcc

# Kernel headers and source code
yum install kernel-headers-$(uname -r) kernel-devel-$(uname -r)

# Packaging
yum install rpm-build

# Enable EPEL to install DKMS
yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-$(rpm -E %rhel).noarch.rpm
yum install dkms
```


## Demo

![Demo](https://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/demo.gif)

[![asciinema](https://img.shields.io/badge/Play%20Video-asciinema-red)](http://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/demo-ascii/)
[![webm](https://img.shields.io/badge/Play%20Video-webm-purple)](http://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/demo.webm)
[![svg](https://img.shields.io/badge/Play%20Video-svg-blue)](http://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/demo.svg)


## Building with script

### Fetch script from `main` branch

```shell
cd yum-packaging-precompiled-kmod
git checkout remotes/origin/main -- build.sh
```

### Usage
> *note*: distro: `fedora32`, `rhel7`, `rhel8`

```shell
./build.sh path/to/*.run ${distro}
> ex: time ./build.sh ~/Downloads/NVIDIA-Linux-x86_64-440.33.01.run rhel8
```


## Building Manually

### Generate tarball from runfile

```shell
mkdir nvidia-kmod-440.33.01-x86_64
sh NVIDIA-Linux-x86_64-440.33.01.run --extract-only --target .
mv kernel nvidia-kmod-440.33.01-x86_64/
tar -cJf nvidia-kmod-440.33.01-x86_64.tar.xz nvidia-kmod-440.33.01-x86_64
```

### X.509 Certificate

[Generate X.509](http://www.pellegrino.link/2015/11/29/signing-nvidia-proprietary-driver-on-fedora.html) `public_key.der` and `private_key.priv` files.

Example [x509-configuration.ini](https://gist.githubusercontent.com/kmittman/6941ff07f75a1dea9c1fb6b31623d085/raw/498bb259b3e6f796819bc204c8437c8efeea9e6d/x509-configuration.ini
). Replace `$USER` and `$EMAIL` values.
```
openssl req -x509 -new -nodes -utf8 -sha256 -days 36500 -batch \
  -config x509-configuration.ini \
  -outform DER -out public_key.der \
  -keyout private_key.priv
```

### Compilation and Packaging

> note: Fedora users may need to `export IGNORE_CC_MISMATCH=1`

```shell
mkdir BUILD BUILDROOT RPMS SRPMS SOURCES SPECS
cp public_key.der SOURCES/
cp private_key.priv SOURCES/
cp nvidia-kmod-440.33.01-x86-64.tar.xz SOURCES/
cp kmod-nvidia.spec SPECS/

rpmbuild \
    --define "%_topdir $(pwd)" \
    --define "debug_package %{nil}" \
    --define "kernel $kernel" \
    --define "kernel_release $release" \
    --define "kernel_dist $dist" \
    --define "driver $version" \
    --define "epoch 3" \
    --define "driver_branch $stream" \
    -v -bb SPECS/kmod-nvidia.spec

# Kernel: 4.18.0-147.5.1
# Driver: 440.33.01
# Stream: latest
> ex: rpmbuild \
    --define "%_topdir $(pwd)" \
    --define "debug_package %{nil}" \
    --define "kernel 4.18.0" \
    --define "kernel_release 147.5.1" \
    --define "kernel_dist .el8_1" \
    --define "driver 440.33.01" \
    --define "epoch 3" \
    --define "driver_branch latest" \
    -v -bb SPECS/kmod-nvidia.spec
```

### Sign RPM package(s) with GPG signing key

If one does not already exist, [generate a GPG key pair](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/packaging_and_distributing_software/advanced-topics)

```shell
gpg --generate-key
```

Set `$gpgKey` to secret key ID.

```shell
gpgArgs="/usr/bin/gpg --force-v3-sigs --digest-algo=sha512 --no-verbose --no-armor --no-secmem-warning"
for package in RPMS/*/kmod-nvidia*.rpm; do
  rpm \
    --define "%_signature gpg" \
    --define "%_gpg_name $gpgKey" \
    --define "%__gpg /usr/bin/gpg" \
    --define "%_gpg_digest_algo sha512" \
    --define "%_binary_filedigest_algorithm 10" \
    --define "%__gpg_sign_cmd %{__gpg} $gpgArgs -u %{_gpg_name} \
      -sbo %{__signature_filename} %{__plaintext_filename}" \
    --addsign "$package";
done
```

## RPM Repository

### Other NVIDIA driver packages

**RHEL8** or **Fedora**

Copy relevant packages from the [CUDA repository](http://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/)
```shell
* dnf-plugin-nvidia*.rpm
* cuda-drivers-${version}*.rpm
* nvidia-driver-${version}*.rpm
* nvidia-driver-cuda-${version}*.rpm
* nvidia-driver-cuda-libs-${version}*.rpm
* nvidia-driver-devel-${version}*.rpm
* nvidia-driver-libs-${version}*.rpm
* nvidia-driver-NvFBCOpenGL-${version}*.rpm
* nvidia-driver-NVML-${version}*.rpm
* nvidia-kmod-common-${version}*.rpm
* nvidia-libXNVCtrl-${version}*.rpm
* nvidia-libXNVCtrl-devel-${version}*.rpm
* nvidia-modprobe-${version}*.rpm
* nvidia-persistenced-${version}*.rpm
* nvidia-settings-${version}*.rpm
* nvidia-xconfig-${version}*.rpm
```
**RHEL7**

Copy relevant packages from the [CUDA repository](http://developer.download.nvidia.com/compute/cuda/repos/rhel7/x86_64/)
```shell
* yum-plugin-nvidia*.rpm
* cuda-drivers-${version}*.rpm
* nvidia-driver-${flavor}-${version}*.rpm
* nvidia-driver-${flavor}-NVML-${version}*.rpm
* nvidia-driver-${flavor}-NvFBCOpenGL-${version}*.rpm
* nvidia-driver-${flavor}-cuda-${version}*.rpm
* nvidia-driver-${flavor}-cuda-libs-${version}*.rpm
* nvidia-driver-${flavor}-devel-${version}*.rpm
* nvidia-driver-${flavor}-libs-${version}*.rpm
* nvidia-libXNVCtrl-${version}*.rpm
* nvidia-libXNVCtrl-devel-${version}*.rpm
* nvidia-modprobe-${flavor}-${version}*.rpm
* nvidia-persistenced-${flavor}-${version}*.rpm
* nvidia-settings-${version}*.rpm
* nvidia-xconfig-${flavor}-${version}*.rpm
```

### Python script

```shell
wget https://raw.githubusercontent.com/NVIDIA/cuda-repo-management/main/genmodules.py
```

### Generate metadata

```shell
mkdir my-first-repo
# Precompiled kmod package(s)
cp RPMS/*/kmod-nvidia*.rpm my-first-repo/
# Other NVIDIA driver packages
cp ~/Downloads/*.rpm my-first-repo/
```

**RHEL8** or **Fedora**
```shell
createrepo_c -v --database my-first-repo/
python3 ./genmodules.py my-first-repo/ modules.yaml
modifyrepo_c modules.yaml my-first-repo/repodata
```

**RHEL7**
```shell
createrepo -v --database my-first-repo
```

### Enable local repo

**Create `custom.repo` file**
```shell
[custom]
name=custom
baseurl=file:///path/to/my-first-repo
enabled=1
gpgcheck=0
```

**Copy to system path for `yum`/`dnf` package manager**
```shell
sudo cp custom.repo /etc/yum.repos.d/
```

**Clean `yum`/`dnf` cache**
```shell
yum clean all
```


## Installing packages

> *note:* `XXX` is the first `.` delimited field in the driver version, ex: `440` in `440.33.01`

* **RHEL8** or **Fedora** streams: `latest`, `XXX`, `latest-dkms`, `XXX-dkms`
  ```shell
  dnf module install nvidia-driver:${stream}
  > ex: dnf module install nvidia-driver:latest
  ```
  To [switch streams](https://docs.fedoraproject.org/en-US/modularity/using-modules-switching-streams/), first uninstall and clear the current stream
  ```shell
  dnf remove nvidia-driver
  dnf module reset nvidia-driver

* **RHEL7** flavors: `latest`, `branch-XXX`, `latest-dkms`
  ```shell
  yum install nvidia-driver-${flavor}
  > ex: yum install nvidia-driver-latest
  ```
  Then to install `nvidia-settings`
  ```shell
  yum install cuda-drivers
  ```


## Modularity Profiles


* **RHEL8** or **Fedora** profiles: `default`, `ks`, `fm`, `src`
  ```shell
  dnf module install nvidia-driver:${stream}/${profile}
  > ex: dnf module install nvidia-driver:450/fm
  ```

  The default profile (`default`) installs all of the driver packages for specified stream using [transitive closure](https://en.wikipedia.org/wiki/Transitive_closure)
  ```shell
  dnf module install nvidia-driver:${stream}/default
  ```
  > *note*: do not need to specify `default` profile

  The [kickstart](https://en.wikipedia.org/wiki/Kickstart_(Linux)) profile (`ks`) is used for unattended [Anaconda](https://fedoraproject.org/wiki/Anaconda) installs of `CentOS`, `Fedora`, & `RHEL` Linux OSes via a configuration file. This profile does not install the _cuda-drivers_ metapackage, which otherwise would attempt to uninstall any existing NVIDIA driver runfiles via a `%pretrans` hook
  ```shell
  %packages
  @^Minimal Install
  @nvidia-driver:${stream}/ks
  %end
  ```
  > *note*: any package warning is fatal to a kickstart installation

  The NvSwitch profile (`fm`) installs all of the driver packages, as well as Fabric Manager and NCSQ
  ```shell
  dnf module install nvidia-driver:${stream}/fm
  ```
  > *note*: this is intended for hardware containing NvSwitch such as DGX systems

  The Source profile (`src`) installs only the contents of `/usr/src/nvidia-${version}` which provides `nv-p2p.h` and other header files used for compiling NVIDIA kernel modules such as [GDRCopy](https://github.com/NVIDIA/gdrcopy) and [nvidia-fs](https://github.com/NVIDIA/gds-nvidia-fs)
  > *note*: this profile is only compatible with precompiled streams (`latest`, `XXX`); DKMS streams use `kmod-nvidia-latest-dkms`

  ```shell
  dnf module install nvidia-driver:${stream}/src
  ```
  > *note*: this profile should be combined with another profile, i.e `default`, `ks`, or `fm`

  ```shell
  dnf module install nvidia-driver:${stream}/{default,src}
  ```


## Presentations

### GPU Technology Conference

- [Precompiled Kernel Modules: Packaging & Deployment on RHEL8 with Modularity Streams](https://www.nvidia.com/en-us/gtc/session-catalog/?search=A21604&tab.catalogtabfields=1600209910618002Tlxt)
  - Fall 2020
  - [video](https://developer.download.nvidia.com/presentations/2020/gtc-fall/Precompiled_Kernel_Modules_Packaging_and_Deployment_on_RHEL8_with_Modularity_Streams.mp4) (MP4)
  - [slides](https://developer.download.nvidia.com/presentations/2020/gtc-fall/Precompiled_Kernel_Modules_Packaging_and_Deployment_on_RHEL8_with_Modularity_Streams.pdf) (PDF)

### Red Hat Summit

- [Simplifying NVIDIA GPU Driver Deployment on Red Hat Enterprise Linux](https://summit.redhat.com/conference/sessions/details/5530dede-518d-46e3-8038-ca62c242ea67)
  - Spring → Summer 2020
  - [video](https://developer.download.nvidia.com/presentations/2020/rhsummit/Simplifying_NVIDIA_GPU_Driver_Deployment_on_RHEL.mp4) (MP4)
  - [slides](https://developer.download.nvidia.com/presentations/2020/rhsummit/Simplifying_NVIDIA_GPU_Driver_Deployment_on_RHEL.pdf) (PDF)

## Related

### [UEFI](UEFI.md) Secure Boot guide

### [OCI](OCI.md) containerization guide

### NVIDIA plugin

- _dnf-plugin-nvidia_ & _yum-plugin-nvidia_
  * [https://github.com/NVIDIA/yum-packaging-nvidia-plugin](https://github.com/NVIDIA/yum-packaging-nvidia-plugin)

- nvidia-driver ([and 6 more](https://github.com/topics/yum-packaging?user=NVIDIA))
    * [https://github.com/NVIDIA/yum-packaging-nvidia-driver](https://github.com/NVIDIA/yum-packaging-nvidia-driver)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
