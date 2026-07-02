#!/bin/bash

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Build a source RPM (.src.rpm) for the OpenTelemetry auto-instrumentation suite.
#
# Usage: packaging/rpm/make-srpm.sh <outdir>
#
# The resulting .src.rpm is placed in <outdir> (default: current directory).
# This is the entrypoint used by COPR's "make srpm" SCM build method via
# .copr/Makefile. The actual package build (agent downloads, %install) happens
# later on the COPR builders from this SRPM -- NOT here.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"
SPEC="$SCRIPT_DIR/opentelemetry.spec"

OUTDIR="${1:-$PWD}"
mkdir -p "$OUTDIR"

# Reuse the canonical version derivation.
# shellcheck disable=SC1091
. "$SCRIPT_DIR/common.sh"
VERSION="$(normalize_rpm_version "$(get_version)")"
echo "Building SRPM for opentelemetry ${VERSION}"

TOPDIR="$(mktemp -d)"
trap 'rm -rf "$TOPDIR"' EXIT
mkdir -p "$TOPDIR/SOURCES" "$TOPDIR/SPECS" "$TOPDIR/SRPMS"

TARBALL="$TOPDIR/SOURCES/opentelemetry-${VERSION}.tar.gz"
if git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$REPO_DIR" archive --format=tar.gz \
        --prefix="opentelemetry-${VERSION}/" -o "$TARBALL" HEAD
else
    # Fallback for non-git checkouts (e.g. exported tree).
    tar czf "$TARBALL" \
        --transform "s,^\.,opentelemetry-${VERSION}," \
        --exclude=.git --exclude=build -C "$REPO_DIR" .
fi

rpmbuild -bs "$SPEC" \
    --define "_topdir $TOPDIR" \
    --define "otel_version $VERSION"

cp -v "$TOPDIR"/SRPMS/*.src.rpm "$OUTDIR/"
