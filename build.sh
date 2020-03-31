#!/usr/bin/env bash
err() { echo; echo "ERROR: $*"; exit 1; }
kmd() { echo; echo ">>> $*" | fold -s; eval "$*" || err "at line \`$*\`"; }
get_gpgkey() { gpgKey=$(gpg --list-secret-keys --with-colons | grep "^sec" | sort -t: -k 5 -r | grep -o -E "[A-Z0-9]{8,}" | grep "[0-9]" | grep "[A-Z]" | grep -oE "[0-9A-Z]{8}$"); }

# Inputs
runfile=$(readlink -e "$1")

# X.509 defaults
userName=$USER
userEmail=$(git config --get user.email)
configFile="x509-configuration.ini"
privateKey="private_key.priv"
publicKey="public_key.der"

# GPG defaults
gpgBin=$(type -p gpg)
gpgConfig="gpg.cfg"
gpgKey=""
[[ $gpgKey ]] || get_gpgkey
gpgArgs="$gpgBin --force-v3-sigs --digest-algo=sha512  --no-verbose --no-armor --no-secmem-warning"

# Build defaults
epoch=3
stream="latest"
topdir="$HOME/precompiled"
arch="x86_64"

# Driver defaults
version=$(basename "$runfile" | sed -e "s|NVIDIA\-Linux\-${arch}\-||" -e 's|\.run$||')
tarball=nvidia-kmod-${version}-${arch}
unpackDir="unpack"

# Kernel defaults
kernel=$(uname -r | awk -F '-' '{print $1}')
release=$(uname -r | awk -F '-' '{print $2}' | sed -r 's|\.[a-z]{2}[0-9]+| |' | awk '{print $1}')
dist=$(uname -r | awk -F '-' '{print $2}' | sed -r -e 's|\.[a-z]{2}[0-9]+| &|' -e "s|\.${arch}||" | awk '{print $2}')

# CUDA defaults
baseURL="http://developer.download.nvidia.com/compute/cuda/repos"
distro="rhel8"
downloads=$topdir/repo

# Repo defaults
myRepo="my-precompiled"
repoFile="${myRepo}.repo"


#
# Functions
#

clean_up() {
    rm -rf "$unpackDir"
    rm -rf nvidia-kmod-*-${arch}
    rm -vf nvidia-kmod-*-${arch}.tar.xz
    rm -vf primary.xml
    rm -vf modules.yaml
    rm -vf $configFile
    rm -vf $gpgConfig
    rm -vf $repoFile
    exit 1
}

git_ignore() {
    cat >.gitignore <<-EOF
	gpg.cfg
	modules.yaml
	my-precompiled.repo
	nvidia-kmod*.tar.xz
	primary.xml
	private_key.priv
	public_key.der
	x509-configuration.ini
EOF
}

generate_tarballs()
{
    mkdir "${tarball}"
    sh "${runfile}" --extract-only --target ${unpackDir}
    mv "${unpackDir}/kernel" "${tarball}/"
    rm -rf ${unpackDir}
    tar --remove-files -cJf "${tarball}.tar.xz" "${tarball}"
}

new_cert_config()
{
    [[ $userName ]] || err "Missing \$userName"
    [[ $userEmail ]] || err "Missing \$userEmail"
    echo ":: userName: $userName"
    echo ":: userEmail: $userEmail"

    # Configuration for X.509 certificate
    cat > $configFile <<-EOF
	[ req ]
	default_bits = 4096
	distinguished_name = req_distinguished_name
	prompt = no
	string_mask = utf8only
	x509_extensions = myexts

	[ req_distinguished_name ]
	O = $userName
	CN = $userName
	emailAddress = $userEmail

	[ myexts ]
	basicConstraints=critical,CA:FALSE
	keyUsage=digitalSignature
	subjectKeyIdentifier=hash
	authorityKeyIdentifier=keyid
EOF
}

new_certificate()
{
    if [[ -f "$configFile" ]]; then
        echo ":: using $configFile"
    else
        echo "  -> new_cert_config()"
        new_cert_config
    fi

    # Generate X.509 certificate
    kmd openssl req -x509 -new -nodes -utf8 -sha256 -days 36500 -batch -config $configFile \
      -outform DER -out $publicKey -keyout $privateKey
}

new_gpgkey()
{
    cat >$gpgConfig <<-EOF
	Key-Type: RSA
	Key-Length: 4096
	Name-Real: $userName
	Name-Email: $userEmail
	Expire-Date: 0
EOF

    kmd gpg --batch --generate-key $gpgConfig
    get_gpgkey
}

kmod_rpm()
{
    mkdir -p "$topdir"
    (cd "$topdir" && mkdir BUILD BUILDROOT RPMS SRPMS SOURCES SPECS)

    cp -v -- *key* "$topdir/SOURCES/"
    cp -v -- *tar* "$topdir/SOURCES/"
    cp -v -- *.spec "$topdir/SPECS/"
    cd "$topdir" || err "Unable to cd into $topdir"

    kmd rpmbuild \
        --define "'%_topdir $(pwd)'" \
        --define "'debug_package %{nil}'" \
        --define "'kernel $kernel'" \
        --define "'kernel_release $release'" \
        --define "'kernel_dist $dist'" \
        --define "'driver $version'" \
        --define "'epoch $epoch'" \
        --define "'driver_branch $stream'" \
        -v -bb SPECS/kmod-nvidia.spec

    cd - || err "Unable to cd into $OLDPWD"
}

sign_rpm()
{
    signature=$(rpm -qip "$1" | grep ^Signature)
    [[ $signature =~ "none" ]] || return

    kmd rpm \
        --define "'%_signature gpg'" \
        --define "'%_gpg_name $gpgKey'" \
        --define "'%__gpg $gpgBin'" \
        --define "'%_gpg_digest_algo sha512'" \
        --define "'%_binary_filedigest_algorithm 10'" \
        --define "'%__gpg_sign_cmd %{__gpg} $gpgArgs -u %{_gpg_name} -sbo %{__signature_filename} %{__plaintext_filename}'" \
        --addsign "$1"
}

copy_rpms()
{
    repoMD=$(curl -sL ${baseURL}/${distro}/${arch}/repodata/repomd.xml)
    gzipPath=$(echo "$repoMD" | grep primary\.xml | awk -F '"' '{print $2}')
    echo ":: $gzipPath"

    rm -f primary.xml
    curl -sL "${baseURL}/${distro}/${arch}/${gzipPath}" --output primary.xml.gz
    gunzip primary.xml.gz

    plugin=$(grep -E "plugin-nvidia" primary.xml | grep "<location" | awk -F '"' '{print $2}' | sort -rV | awk NR==1)
    driverFiles=$(grep -E "${version}-" primary.xml | grep "<location" | awk -F '"' '{print $2}')

    if [[ $distro == "rhel7" ]]; then
        plugin=$(grep -E "plugin-nvidia" primary.xml | grep "<location" | awk -F '"' '{print $2}' | sort -rV | awk NR==1)
        glvndFiles=$(grep -E "libglvnd" primary.xml | grep "<location" | awk -F '"' '{print $2}' | sort -rV | awk NR==1)
        if [[ $stream == "latest" ]]; then
            driverFiles=$(grep -E "${version}-" primary.xml | grep "<location" | awk -F '"' '{print $2}' | grep -E -v -e "latest-dkms" -e "branch")
        elif [[ $stream =~ "branch" ]]; then
            driverFiles=$(grep -E "${version}-" primary.xml | grep "<location" | awk -F '"' '{print $2}' | grep -E -v "latest")
        fi
    fi

    mkdir -p "$downloads"

    # Rest of driver packages
    for rpm in $plugin $glvndFiles $driverFiles; do
        echo "  -> $rpm"
        if [[ ! -f ${downloads}/${rpm} ]]; then
            curl -sL "${baseURL}/${distro}/${arch}/${rpm}" --output "${downloads}/${rpm}"
        fi
    done
}

make_repo()
{
    # genmodules.py
    if [[ ! -f genmodules.py ]]; then
        err "Unable to locate genmodules.py"
    fi

    # kmod packages
    for rpm in "$topdir/RPMS/${arch}"/*.rpm; do
        cp -v "$rpm" "$downloads/"
    done

    #cd $downloads

    if [[ $distro == "rhel7" ]]; then
        createrepo -v --database "$downloads" || err "createrepo"
    else
        createrepo_c -v --database "$downloads" || err "createrepo_c"
        python3 ./genmodules.py "$downloads" modules.yaml || err "genmodules.py"
        modifyrepo_c modules.yaml "$downloads/repodata" || err "modifyrepo_c"
    fi
}

repo_file()
{
    cat >$repoFile <<-EOF
	[$myRepo]
	name=$myRepo
	baseurl=file://${topdir}/repo
	enabled=1
	gpgcheck=0
EOF

    echo "  -> $repoFile"
}


#
# Stages
#

[[ $1 == "clean" ]] && clean_up

# Sanity check
if [[ -f $runfile ]] && [[ $version ]]; then
    echo ":: Building kmod package for $version @ $kernel-${release}${dist}"
else
    err "Missing runfile"
fi

# Create tarball from runfile contents
if [[ -f ${tarball}.tar.xz ]]; then
    echo "[SKIP] generate_tarballs()"
else
    echo "==> generate_tarballs()"
    generate_tarballs
fi

# Create X.509 certificate
if [[ -f $publicKey ]] && [[ -f $privateKey ]]; then
    echo "[SKIP] new_certificate()"
else
    echo "==> new_certificate()"
    new_certificate
fi

# Create GPG key
if [[ $gpgKey ]]; then
    echo "[SKIP] new_gpgkey()"
else
    echo "==> new_gpgkey()"
    new_gpgkey
fi

# Build RPMs
empty=$(find "$topdir/RPMS" -maxdepth 0 -type d -empty 2>/dev/null)
found=$(find "$topdir/RPMS" -mindepth 2 -maxdepth 2 -type f -name "*${version}*" 2>/dev/null)
if [[ ! -d "$topdir/RPMS" ]] || [[ $empty ]] || [[ ! $found ]]; then
    echo "==> kmod_rpm(${version})"
    kmod_rpm
else
    echo "[SKIP] kmod_rpm(${version})"
fi

# Sanity check
empty=$(find "$topdir/RPMS" -maxdepth 0 -type d -empty 2>/dev/null)
found=$(find "$topdir/RPMS" -mindepth 2 -maxdepth 2 -type f -name "*${version}*" 2>/dev/null)
if [[ $empty ]] || [[ ! $found ]]; then
    err "Missing kmod RPM package(s)"
elif [[ -z $gpgKey ]]; then
    err "Missing GPG key"
fi

# Sign RPMs
echo "==> sign_rpm($gpgKey)"
for pkg in "$topdir/RPMS/${arch}"/*; do
    sign_rpm "$pkg"
done
echo

# Copy RPMs from CUDA repository
echo "==> copy_rpms($baseURL/$distro/$arch)"
copy_rpms
echo

# Generate repodata
echo "==> make_repo()"
make_repo
echo

# .repo file
echo "==> repo_file()"
repo_file
echo

echo ":: Output repository to $topdir/repo"
git_ignore

