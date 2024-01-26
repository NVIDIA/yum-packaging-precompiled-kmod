# yum packaging precompiled kmod

## UEFI Secure Boot

For general information: https://www.redhat.com/en/blog/uefi-secure-boot

## Demo
[![asciinema](https://img.shields.io/badge/Play%20Video-asciinema-red)](https://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/uefi-mok-ascii/)

## Verify that Secure Boot is enabled
* The installation media (ISO-9660 image on CD/USB) for RHEL is bootable with UEFI Secure Boot enabled.
  * NOTE: make sure to select the EFI boot option to install an appropriate boot loader

```shell
$ sudo mokutil --sb-state
SecureBoot enabled
```

![UEFI boot](https://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/efi-stub-secureboot-enabled.png)

> _note:_ may see above message from EFI stub at boot up


### Precompiled driver
Instructions provided are for the precompiled streams only. Use of DKMS streams is not supported with this technique.

```shell
$ sudo dnf module install nvidia-driver:latest
```
_or_

```shell
$ sudo dnf module install nvidia-driver:XXX
```

### Runlevel 3
A clean install of RHEL (without the NVIDIA driver) is bootable with UEFI Secure Boot enabled. Once the NVIDIA driver is installed, the nouveau driver will be disabled.
Without the key enrolled in the MOK, the nvidia kernel modules will be unable to load. Therefore the system will either fallback to the VESA driver (if supported) or runlevel 3 (virtual terminal).

```shell
$ lsmod | grep -e nouveau -e nvidia
```
> _note:_ in this scenario, the output will be empty

To avoid this scenario, import the public key into the MOK database prior to reboot. See steps below.


## Enroll key in MOK

### Download the X.509 certificate public key
_note:_ skip this step if using your own certificate

* [NVIDIA 2019 for RHEL8](https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/NVIDIA2019-public_key.der): `NVIDIA2019-public_key.der`
  - [See table](https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/precompiled/) for supported kmod packages
  - Key is subject to change in a future release

* [NVIDIA 2019 for RHEL9](https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/NVIDIA2019-public_key.der): `NVIDIA2019-public_key.der`
  - [See table](https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/precompiled/) for supported kmod packages
  - Key is subject to change in a future release

### mokutil
```shell
$ sudo mokutil --import *public_key.der
```
> _note:_ you will be asked to create a new password (between 1-256 characters)

```shell
$ sudo mokutil --list-new | grep Issuer
```
> _note:_ the key to be enrolled should be listed


### UEFI environment

On the next reboot, the MOK management interface will load.

![UEFI enroll in MOK](https://developer.download.nvidia.com/compute/github-demos/yum-packaging-precompiled-kmod/enroll-uefi-mok.gif)

1. Press a key to continue.
2. Select enroll MOK
3. Select view key
4. Confirm the key is correct
5. Select yes to enroll the key into db
6. Input the password created from the `mokutil` step
7. Select reboot
8. The NVIDIA kernel modules will load
