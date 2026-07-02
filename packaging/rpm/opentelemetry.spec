# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
#
# One SRPM -> five binary (sub)packages, mirroring the FPM-built layout:
#   opentelemetry                              (meta, requires all below)
#   opentelemetry-injector                     (LD_PRELOAD injector + libotelinject.so)
#   opentelemetry-java-autoinstrumentation     (noarch, javaagent.jar)
#   opentelemetry-nodejs-autoinstrumentation   (noarch, npm package)
#   opentelemetry-dotnet-autoinstrumentation   (x86_64 only, native agent)
#
# The language agents and the injector binary are DOWNLOADED at build time
# (COPR "Enable internet access during builds" must be on). This is fine for a
# COPR PoC but violates Fedora's hermetic-build guideline -- see .plans/concerns.md.

# Prebuilt binaries are shipped as-is: no stripping, no debuginfo, no build-id.
%global debug_package %{nil}
%global __strip /bin/true
%global _build_id_links none
# %install sources a bash library (common.sh) -- needs bash, not /bin/sh.
%global _buildshell /bin/bash

# Version is injected by .copr/Makefile / make-srpm.sh via --define "otel_version X".
%{!?otel_version: %global otel_version 0.0.0}

Name:           opentelemetry
Version:        %{otel_version}
Release:        1%{?dist}
Summary:        OpenTelemetry Auto-Instrumentation Suite (metapackage)
License:        Apache-2.0
URL:            https://github.com/mmanciop/opentelemetry-packages
Source0:        opentelemetry-%{version}.tar.gz

# Build-time tooling for downloading/assembling the agents.
BuildRequires:  bash
BuildRequires:  coreutils
BuildRequires:  findutils
BuildRequires:  sed
BuildRequires:  grep
BuildRequires:  gzip
BuildRequires:  tar
BuildRequires:  curl
BuildRequires:  unzip
BuildRequires:  npm

# The meta package pulls in every component. dotnet only exists on x86_64.
Requires:       opentelemetry-injector = %{version}-%{release}
Requires:       opentelemetry-java-autoinstrumentation = %{version}-%{release}
Requires:       opentelemetry-nodejs-autoinstrumentation = %{version}-%{release}
%ifarch x86_64
Requires:       opentelemetry-dotnet-autoinstrumentation = %{version}-%{release}
%endif

%description
Metapackage that installs the OpenTelemetry LD_PRELOAD injector together with
the Java, Node.js and .NET auto-instrumentation agents.

#---------------------------------------------------------------------
# opentelemetry-injector
#---------------------------------------------------------------------
%package -n opentelemetry-injector
Summary:        OpenTelemetry LD_PRELOAD-based automatic instrumentation injector
Requires:       sed
Requires:       grep

%description -n opentelemetry-injector
LD_PRELOAD-based injector (libotelinject.so) that transparently enables
OpenTelemetry auto-instrumentation for processes on the host. Registers itself
in /etc/ld.so.preload on install.

#---------------------------------------------------------------------
# opentelemetry-java-autoinstrumentation
#---------------------------------------------------------------------
%package -n opentelemetry-java-autoinstrumentation
Summary:        OpenTelemetry Java Auto-Instrumentation Agent
BuildArch:      noarch
Requires:       opentelemetry-injector >= %{version}

%description -n opentelemetry-java-autoinstrumentation
OpenTelemetry Java auto-instrumentation agent (javaagent.jar) and the injector
drop-in configuration that enables it.

#---------------------------------------------------------------------
# opentelemetry-nodejs-autoinstrumentation
#---------------------------------------------------------------------
%package -n opentelemetry-nodejs-autoinstrumentation
Summary:        OpenTelemetry Node.js Auto-Instrumentation
BuildArch:      noarch
Requires:       opentelemetry-injector >= %{version}

%description -n opentelemetry-nodejs-autoinstrumentation
OpenTelemetry Node.js auto-instrumentation (@opentelemetry/auto-instrumentations-node)
and the injector drop-in configuration that enables it.

#---------------------------------------------------------------------
# opentelemetry-dotnet-autoinstrumentation (x86_64 only)
#---------------------------------------------------------------------
%ifarch x86_64
%package -n opentelemetry-dotnet-autoinstrumentation
Summary:        OpenTelemetry .NET Auto-Instrumentation
Requires:       opentelemetry-injector >= %{version}

%description -n opentelemetry-dotnet-autoinstrumentation
OpenTelemetry .NET auto-instrumentation agent (glibc and musl flavors) and the
injector drop-in configuration that enables it.
%endif

#=====================================================================
%prep
%autosetup -n opentelemetry-%{version}

%build
# Nothing to compile: all artifacts are prebuilt and fetched in %%install.

%install
set -euo pipefail

# Reuse the canonical paths + download helpers. common.sh defines INSTALL_DIR,
# CONFIG_DIR, MAN_DIR, DOC_DIR, LICENSE_DIR, COMMON_DIR and the download_*/
# generate_man_page functions. We deliberately do NOT call setup_*_buildroot:
# those chown root:root, which fails for the unprivileged rpmbuild user.
source packaging/rpm/common.sh

# Map RPM arch -> the amd64/arm64 naming used by the release assets / scripts.
case "%{_arch}" in
    x86_64)  otel_arch=amd64 ;;
    aarch64) otel_arch=arm64 ;;
    *) echo "unsupported arch %{_arch}" >&2; exit 1 ;;
esac
export ARCH="$otel_arch"

br="%{buildroot}"

# ---- injector ------------------------------------------------------
inj_tag="$(tail -n 1 packaging/injector-release.txt)"
install -d -m 0755 "${br}${INJECTOR_INSTALL_DIR}"
curl -sfL \
    "https://github.com/open-telemetry/opentelemetry-injector/releases/download/${inj_tag}/libotelinject_${otel_arch}.so" \
    -o "${br}${LIBOTELINJECT_INSTALL_PATH}"
chmod 0755 "${br}${LIBOTELINJECT_INSTALL_PATH}"

install -d -m 0755 "${br}${INJECTOR_CONFIG_DIR}"
install -d -m 0755 "${br}${INJECTOR_CONFIG_DIR}/conf.d"
install -m 0644 "$COMMON_DIR/injector/otelinject.conf"  "${br}${INJECTOR_CONFIG_DIR}/"
install -m 0644 "$COMMON_DIR/injector/default_env.conf" "${br}${INJECTOR_CONFIG_DIR}/"

install -d -m 0755 "${br}${MAN_DIR}/man8"
generate_man_page "$COMMON_DIR/injector/opentelemetry-injector.8.tmpl" \
    "${br}${MAN_DIR}/man8/opentelemetry-injector.8.gz" "%{version}"

install -d -m 0755 "${br}${DOC_DIR}/opentelemetry-injector"
install -m 0644 "$COMMON_DIR/injector/README.md" "${br}${DOC_DIR}/opentelemetry-injector/"
install -d -m 0755 "${br}${LICENSE_DIR}/opentelemetry-injector"
install -m 0644 LICENSE "${br}${LICENSE_DIR}/opentelemetry-injector/"

# ---- java ----------------------------------------------------------
java_tag="$(tail -n 1 "$JAVA_AGENT_RELEASE_PATH")"
install -d -m 0755 "${br}${JAVA_INSTALL_DIR}"
download_java_agent "$java_tag" "${br}${JAVA_AGENT_INSTALL_PATH}"
chmod 0644 "${br}${JAVA_AGENT_INSTALL_PATH}"
install -d -m 0755 "${br}${JAVA_CONFIG_DIR}"
install -m 0644 "$COMMON_DIR/java/otel-config.yaml" "${br}${JAVA_CONFIG_DIR}/"
install -m 0644 "$COMMON_DIR/java/injector.conf" "${br}${INJECTOR_CONFIG_DIR}/conf.d/java.conf"
install -d -m 0755 "${br}${MAN_DIR}/man1"
generate_man_page "$COMMON_DIR/java/opentelemetry-java.1.tmpl" \
    "${br}${MAN_DIR}/man1/opentelemetry-java.1.gz" "%{version}"
install -d -m 0755 "${br}${DOC_DIR}/opentelemetry-java-autoinstrumentation"
install -m 0644 "$COMMON_DIR/java/README.md" "${br}${DOC_DIR}/opentelemetry-java-autoinstrumentation/"
install -d -m 0755 "${br}${LICENSE_DIR}/opentelemetry-java-autoinstrumentation"
install -m 0644 LICENSE "${br}${LICENSE_DIR}/opentelemetry-java-autoinstrumentation/"

# ---- nodejs --------------------------------------------------------
nodejs_tag="$(tail -n 1 "$NODEJS_AGENT_RELEASE_PATH")"
install -d -m 0755 "${br}${INSTALL_DIR}"
download_nodejs_agent "$nodejs_tag" "${br}${INSTALL_DIR}"
chmod -R u+rwX,go+rX "${br}${NODEJS_INSTALL_DIR}"
install -d -m 0755 "${br}${NODEJS_CONFIG_DIR}"
install -m 0644 "$COMMON_DIR/nodejs/otel-config.yaml" "${br}${NODEJS_CONFIG_DIR}/"
install -m 0644 "$COMMON_DIR/nodejs/injector.conf" "${br}${INJECTOR_CONFIG_DIR}/conf.d/nodejs.conf"
generate_man_page "$COMMON_DIR/nodejs/opentelemetry-nodejs.1.tmpl" \
    "${br}${MAN_DIR}/man1/opentelemetry-nodejs.1.gz" "%{version}"
install -d -m 0755 "${br}${DOC_DIR}/opentelemetry-nodejs-autoinstrumentation"
install -m 0644 "$COMMON_DIR/nodejs/README.md" "${br}${DOC_DIR}/opentelemetry-nodejs-autoinstrumentation/"
install -d -m 0755 "${br}${LICENSE_DIR}/opentelemetry-nodejs-autoinstrumentation"
install -m 0644 LICENSE "${br}${LICENSE_DIR}/opentelemetry-nodejs-autoinstrumentation/"

# ---- dotnet (x86_64 only) ------------------------------------------
if [[ "%{_arch}" == "x86_64" ]]; then
    dotnet_tag="$(tail -n 1 "$DOTNET_AGENT_RELEASE_PATH")"
    install -d -m 0755 "${br}${DOTNET_INSTALL_DIR}"
    download_dotnet_agent "$dotnet_tag" "${br}${DOTNET_INSTALL_DIR}"
    chmod -R u+rwX,go+rX "${br}${DOTNET_INSTALL_DIR}"
    install -d -m 0755 "${br}${DOTNET_CONFIG_DIR}"
    install -m 0644 "$COMMON_DIR/dotnet/otel-config.yaml" "${br}${DOTNET_CONFIG_DIR}/"
    install -m 0644 "$COMMON_DIR/dotnet/injector.conf" "${br}${INJECTOR_CONFIG_DIR}/conf.d/dotnet.conf"
    generate_man_page "$COMMON_DIR/dotnet/opentelemetry-dotnet.1.tmpl" \
        "${br}${MAN_DIR}/man1/opentelemetry-dotnet.1.gz" "%{version}"
    install -d -m 0755 "${br}${DOC_DIR}/opentelemetry-dotnet-autoinstrumentation"
    install -m 0644 "$COMMON_DIR/dotnet/README.md" "${br}${DOC_DIR}/opentelemetry-dotnet-autoinstrumentation/"
    install -d -m 0755 "${br}${LICENSE_DIR}/opentelemetry-dotnet-autoinstrumentation"
    install -m 0644 LICENSE "${br}${LICENSE_DIR}/opentelemetry-dotnet-autoinstrumentation/"
fi

# ---- meta ----------------------------------------------------------
install -d -m 0755 "${br}${DOC_DIR}/opentelemetry"
echo "OpenTelemetry Auto-Instrumentation Suite" > "${br}${DOC_DIR}/opentelemetry/README"

#=====================================================================
# Injector scriptlets: register/unregister libotelinject.so in ld.so.preload.
# (Ported from packaging/common/scripts/{postinstall,preuninstall}-injector.sh.)
%post -n opentelemetry-injector
PRELOAD_PATH="/etc/ld.so.preload"
LIBOTELINJECT_PATH="/usr/lib/opentelemetry/injector/libotelinject.so"
if [ -f "$PRELOAD_PATH" ] && grep -q "$LIBOTELINJECT_PATH" "$PRELOAD_PATH"; then
    exit 0
fi
echo "$LIBOTELINJECT_PATH" >> "$PRELOAD_PATH"

%preun -n opentelemetry-injector
# $1 == 0 -> final removal (not an upgrade)
if [ "$1" = "0" ]; then
    PRELOAD_PATH="/etc/ld.so.preload"
    LIBOTELINJECT_PATH="/usr/lib/opentelemetry/injector/libotelinject.so"
    if [ -f "$PRELOAD_PATH" ] && grep -q "$LIBOTELINJECT_PATH" "$PRELOAD_PATH"; then
        sed -i -e "s|$LIBOTELINJECT_PATH||" "$PRELOAD_PATH"
        if [ ! -s "$PRELOAD_PATH" ] || ! grep -q '[^[:space:]]' "$PRELOAD_PATH"; then
            rm -f "$PRELOAD_PATH"
        fi
    fi
fi

#=====================================================================
%files
%doc /usr/share/doc/opentelemetry/README

%files -n opentelemetry-injector
%license /usr/share/licenses/opentelemetry-injector/LICENSE
%doc /usr/share/doc/opentelemetry-injector/README.md
%dir /usr/lib/opentelemetry
%dir /usr/lib/opentelemetry/injector
/usr/lib/opentelemetry/injector/libotelinject.so
%dir /etc/opentelemetry
%dir /etc/opentelemetry/injector
%dir /etc/opentelemetry/injector/conf.d
%config(noreplace) /etc/opentelemetry/injector/otelinject.conf
%config(noreplace) /etc/opentelemetry/injector/default_env.conf
%{_mandir}/man8/opentelemetry-injector.8.gz

%files -n opentelemetry-java-autoinstrumentation
%license /usr/share/licenses/opentelemetry-java-autoinstrumentation/LICENSE
%doc /usr/share/doc/opentelemetry-java-autoinstrumentation/README.md
%dir /usr/lib/opentelemetry/java
/usr/lib/opentelemetry/java/opentelemetry-javaagent.jar
%dir /etc/opentelemetry/java
%config(noreplace) /etc/opentelemetry/java/otel-config.yaml
%config(noreplace) /etc/opentelemetry/injector/conf.d/java.conf
%{_mandir}/man1/opentelemetry-java.1.gz

%files -n opentelemetry-nodejs-autoinstrumentation
%license /usr/share/licenses/opentelemetry-nodejs-autoinstrumentation/LICENSE
%doc /usr/share/doc/opentelemetry-nodejs-autoinstrumentation/README.md
/usr/lib/opentelemetry/nodejs
%dir /etc/opentelemetry/nodejs
%config(noreplace) /etc/opentelemetry/nodejs/otel-config.yaml
%config(noreplace) /etc/opentelemetry/injector/conf.d/nodejs.conf
%{_mandir}/man1/opentelemetry-nodejs.1.gz

%ifarch x86_64
%files -n opentelemetry-dotnet-autoinstrumentation
%license /usr/share/licenses/opentelemetry-dotnet-autoinstrumentation/LICENSE
%doc /usr/share/doc/opentelemetry-dotnet-autoinstrumentation/README.md
/usr/lib/opentelemetry/dotnet
%dir /etc/opentelemetry/dotnet
%config(noreplace) /etc/opentelemetry/dotnet/otel-config.yaml
%config(noreplace) /etc/opentelemetry/injector/conf.d/dotnet.conf
%{_mandir}/man1/opentelemetry-dotnet.1.gz
%endif

%changelog
* Thu Jul 02 2026 OpenTelemetry <opentelemetry> - %{version}-%{release}
- COPR PoC: initial spec producing injector + java/nodejs/dotnet + meta packages.
