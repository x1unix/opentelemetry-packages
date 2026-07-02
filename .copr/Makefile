# COPR SCM build entrypoint.
#
# COPR's "Make srpm" / SCM build method invokes:
#   make -f .copr/Makefile srpm outdir="/path"
# and expects exactly one .src.rpm in $(outdir). See:
#   https://docs.pagure.org/copr.copr/user_documentation.html#scm

outdir ?= $(CURDIR)

.PHONY: srpm
srpm:
	dnf -y install rpm-build git tar gzip curl coreutils >/dev/null
	./packaging/rpm/make-srpm.sh "$(outdir)"
